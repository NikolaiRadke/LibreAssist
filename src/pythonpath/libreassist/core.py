# -*- coding: utf-8 -*-
# libreassist/core.py - Core logic and provider routing

import os
import threading
import importlib
import uno

from .i18n import t
from .document import getCurrentDocument
from . import discovery, provider_base, settings, backup
from .providers import claude_code, codex_cli


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

# Registered CLI providers
PROVIDERS = {
    "claude_code": "libreassist.providers.claude_code",
    "codex_cli":   "libreassist.providers.codex_cli",
}

# Aliases for short prefix input
PROVIDER_ALIASES = {
    "claude": "claude_code",
    "codex":  "codex_cli",
}

# Reverse mapping for display names
DISPLAY_NAMES = {v: k.title() for k, v in PROVIDER_ALIASES.items()}

DEFAULT_PROVIDER = "claude_code"


# ---------------------------------------------------------------------------
# Simple command handler (Undo / Redo only)
# ---------------------------------------------------------------------------

def handleUserInput(userInput, currentHistory=""):
    """
    Handle special commands triggered from the chat input.
    Only __undo__ and __redo__ are processed here; all LLM requests
    go through callLLMAsync directly.

    Returns: Response string for display
    """
    if userInput == "__undo__":
        return backup.restoreBackup()
    if userInput == "__redo__":
        return backup.restoreChanged()
    return ""


# ---------------------------------------------------------------------------
# Async LLM execution
# ---------------------------------------------------------------------------

def callLLMAsync(providerModule, userPrompt, currentHistory, completionCallback, doc=None):
    """
    Run the CLI provider in a background thread.
    The completionCallback (XCallback) is invoked on the Main-UNO-Thread
    when the subprocess finishes.

    All UNO API calls happen before the thread starts (Main-Thread only).
    Everything inside _run() is pure Python / file I/O.

    Args:
        providerModule:     Imported provider module
        userPrompt:         The user's instruction
        currentHistory:     Chat history up to and including the user message
        completionCallback: XCallback instance
        doc:                Document object captured at click time; if None,
                            falls back to getCurrentDocument()
    """
    if doc is None:
        doc = getCurrentDocument()
    if not doc:
        completionCallback.payload = {"error": "No document open", "fileWasModified": False}
        _fireCallback(completionCallback)
        return

    url = doc.getURL()
    if not url:
        completionCallback.payload = {"error": t('error_not_saved'), "fileWasModified": False}
        _fireCallback(completionCallback)
        return

    fullPath  = uno.fileUrlToSystemPath(url)
    directory = os.path.dirname(fullPath)
    filename  = os.path.basename(fullPath)

    # --- All UNO calls must happen here, before the thread starts ---

    doc.store()

    docDir = settings.getDocSettingsDirForPath(fullPath)

    if not backup.createBackup(fullPath, docDir):
        completionCallback.payload = {"error": "Could not create backup!", "fileWasModified": False}
        _fireCallback(completionCallback)
        return

    modTimeBefore = os.stat(fullPath).st_mtime

    frame     = doc.getCurrentController().getFrame()
    frameName = frame.getName()
    if not frameName:
        frameName = f"la_{id(frame)}"
        frame.setName(frameName)

    settingsData = settings.loadSettingsForDir(docDir, fullPath)
    sessionId    = settingsData.get("session_ids", {}).get(providerModule.NAME)
    timeout      = settingsData.get("timeout", 600)

    globalSettings     = settings.loadGlobalSettings()
    customInstructions = globalSettings.get("custom_instructions", "").strip()

    basePrompt = (
        f"You have access to {filename} in the current directory. "
        f"This is a {os.path.splitext(filename)[1]} file. "
        f"User request: {userPrompt}. "
        "IMPORTANT: Write your response directly into the document by editing the file, "
        "UNLESS the user is asking a pure information question (like 'what day is it?' or 'what's in the document?'). "
        "For content creation, editing, or writing tasks, always modify the document directly. "
        "Response format: Plain text only, no Markdown."
    )

    if customInstructions:
        fullPrompt = f"{basePrompt}\n\nMANDATORY: Apply these rules to your response:\n{customInstructions}"
    else:
        fullPrompt = basePrompt

    # AsyncCallback must be created on the Main-Thread
    ctx     = uno.getComponentContext()
    asyncCb = ctx.ServiceManager.createInstance("com.sun.star.awt.AsyncCallback")

    # --- Background thread ---

    def _run():
        import shutil

        responseText    = None
        newSessionId    = None
        fileWasModified = False
        displayName     = DISPLAY_NAMES.get(providerModule.NAME, "Assistant")

        try:
            def _onProcess(proc):
                completionCallback.process = proc

            _streamBuffer = []

            def _onChunk(delta):
                _streamBuffer.append(delta)
                cumulativeText = "".join(_streamBuffer)
                completionCallback.payload = {
                    "partial":   True,
                    "chunkText": f"{displayName}:\n{cumulativeText}",
                }
                asyncCb.addCallback(completionCallback, None)

            result = provider_base.executeProvider(
                providerModule,
                fullPrompt,
                directory,
                sessionId=sessionId,
                timeout=timeout,
                onProcess=_onProcess,
                onChunk=_onChunk,
            )
            collectedText  = result.get("response", "")
            newSessionId   = result.get("sessionId")

            modTimeAfter    = os.stat(fullPath).st_mtime
            fileWasModified = (modTimeAfter != modTimeBefore)

            responseText = f"{displayName}:\n{collectedText.strip()}"

        except TimeoutError:
            responseText = t('error_timeout')
        except FileNotFoundError:
            responseText = t('error_not_found')
        except RuntimeError as e:
            stderr      = str(e)
            if "code -9" in stderr:
                responseText = t('cancelled')
            else:
                stderrLower = stderr.lower()
                if "model not found" in stderrLower or "modelnotfounderror" in stderrLower:
                    responseText = t('error_model_not_found')
                elif "rate limit" in stderrLower or "429" in stderr:
                    responseText = t('error_rate_limit')
                elif "no capacity" in stderrLower or "capacity_exhausted" in stderrLower:
                    responseText = t('error_no_capacity')
                elif "authentication" in stderrLower or "unauthorized" in stderrLower:
                    responseText = t('error_authentication')
                else:
                    lines    = stderr.split('\n')
                    filtered = '\n'.join(lines[:10] + ['... (truncated) ...'] + lines[-10:]) if len(lines) > 30 else stderr
                    responseText = t('error_provider', error=filtered)
                responseText = t('error_provider', error=filtered)
        except Exception as e:
            import traceback
            traceback.print_exc()
            responseText = t('error_general', error=str(e))

        # Save session ID
        settingsData2 = settings.loadSettingsForDir(docDir, fullPath)
        session_ids   = settingsData2.get("session_ids", {})
        session_ids[providerModule.NAME] = newSessionId
        settingsData2["session_ids"]     = session_ids
        settings.saveSettingsForDir(docDir, settingsData2, fullPath)

        # Save changed-state file and update undo/redo flags
        if fileWasModified and docDir:
            changedPath = os.path.join(docDir, "changed" + os.path.splitext(filename)[1])
            shutil.copy2(fullPath, changedPath)
            backup._undo_state = "changed"
            settingsData3 = settings.loadSettingsForDir(docDir, fullPath)
            settingsData3["undo_available"] = True
            settingsData3["redo_available"] = False
            settings.saveSettingsForDir(docDir, settingsData3, fullPath)

        # Save history
        updatedHistory = currentHistory + responseText + "\n\n"
        settings.saveHistoryForDir(docDir, updatedHistory)

        completionCallback.payload = {
            "response":        responseText,
            "fileWasModified": fileWasModified,
            "url":             url,
            "frameName":       frameName,
            "doc":             doc,
            "docDir":          docDir,
        }
        asyncCb.addCallback(completionCallback, None)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


def _fireCallback(completionCallback):
    """Helper: fire callback immediately on Main-Thread (error path)."""
    ctx = uno.getComponentContext()
    ctx.ServiceManager.createInstance("com.sun.star.awt.AsyncCallback").addCallback(completionCallback, None)


# ---------------------------------------------------------------------------
# Provider discovery
# ---------------------------------------------------------------------------

def discoverProviders():
    """
    Discover all installed CLI providers and cache results in global settings.
    Called once on startup.
    """
    allProviders = [
        claude_code.NAME,
        codex_cli.NAME,
    ]

    found = discovery.discoverAllProviders(allProviders)

    globalSettings = settings.loadGlobalSettings()
    globalSettings["discovered_providers"] = found
    settings.saveGlobalSettings(globalSettings)

    return found
