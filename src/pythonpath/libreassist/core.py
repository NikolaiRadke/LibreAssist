# -*- coding: utf-8 -*-
# libreassist/core.py - Core logic and provider routing

import os
import threading
import importlib
import uno

from .i18n import t
from .document import getCurrentDocument
from . import discovery, provider_base, settings, backup, sandbox


# ---------------------------------------------------------------------------
# Provider registry  (built dynamically from provider config)
# ---------------------------------------------------------------------------

DEFAULT_PROVIDER = "claude_code"

# Extensions treated as ODF documents when detecting newly created files
_ODF_EXTS = (".odt", ".ods", ".odp", ".odg")


def _buildProviderRegistry():
    """Build provider dicts from user provider config."""
    from libreassist.settings import loadProviderConfig
    config = loadProviderConfig()

    providers    = {}
    displayNames = {}

    for name, entry in config.items():
        providers[name]    = f"libreassist.providers.{name}"
        displayNames[name] = entry.get("display_name", name.title())

    return providers, displayNames


def getProviders():
    """Return {name: module_path} dict for all configured providers."""
    providers, _ = _buildProviderRegistry()
    return providers


def getDisplayNames():
    """Return {name: display_name} dict for all configured providers."""
    _, displayNames = _buildProviderRegistry()
    return displayNames


def getAliases():
    """Return {alias: provider_name} for prefix matching in chat."""
    from libreassist.settings import loadProviderConfig
    config = loadProviderConfig()
    aliases = {}
    for name, entry in config.items():
        key = entry.get("alias") or entry.get("display_name", name).lower()
        aliases[key] = name
    return aliases


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

    fullPath = uno.fileUrlToSystemPath(url)
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

    globalSettings = settings.loadGlobalSettings()
    useSandbox     = globalSettings.get("sandbox", True) and sandbox.isAvailable()

    if useSandbox:
        # The agent never sees the document's directory: it works on a private
        # copy in docDir/work, inside a sandbox with its own HOME
        sandboxHome = settings.getSandboxHome()
        runDir      = os.path.join(docDir, "work")
        try:
            stagedPath   = sandbox.stageDocument(fullPath, runDir)
            stagedBefore = os.stat(stagedPath)
        except OSError as e:
            completionCallback.payload = {"error": t('error_general', error=str(e)), "fileWasModified": False}
            _fireCallback(completionCallback)
            return
    else:
        sandboxHome = None
        runDir      = directory
        # Snapshot the working directory to detect newly created documents
        dirBefore = set(os.listdir(directory))

    frame = doc.getCurrentController().getFrame()
    frameName = frame.getName()
    if not frameName:
        frameName = f"la_{id(frame)}"
        frame.setName(frameName)
    settingsData = settings.loadSettingsForDir(docDir, fullPath)
    sessionId = settingsData.get("session_ids", {}).get(providerModule.NAME)
    timeout   = settingsData.get("timeout", 600)

    customInstructions = globalSettings.get("custom_instructions", "").strip()

    basePrompt = (
        f"You have access to {filename} in the current directory. "
        f"This is a {os.path.splitext(filename)[1]} file. "
        f"User request: {userPrompt}. "
        "IMPORTANT: Write your response directly into the document by editing the file, "
        "UNLESS the user is asking a pure information question (like 'what day is it?' or 'what's in the document?'). "
        "For content creation, editing, or writing tasks, always modify the document directly. "
        "If the user explicitly asks for a separate or new document, create a new "
        "ODF file (e.g. .odt) in the current directory instead of editing this one. "
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

        responseText   = None
        newSessionId   = None
        fileWasModified = False
        newFiles       = []

        try:
            def _onProcess(proc):
                completionCallback.process = proc

            result = provider_base.executeProvider(
                providerModule,
                fullPrompt,
                runDir,
                sessionId=sessionId,
                timeout=timeout,
                onProcess=_onProcess,
                sandboxHome=sandboxHome
            )
            collectedText  = result.get("response", "")
            newSessionId   = result.get("sessionId")

            if useSandbox:
                # Copy the edited document and new ODF files back from the work dir
                newFiles = sandbox.collectResults(
                    fullPath, stagedPath, runDir, stagedBefore, _ODF_EXTS)
            else:
                dirAfter = set(os.listdir(directory))
                newFiles = [
                    os.path.join(directory, f)
                    for f in (dirAfter - dirBefore)
                    if os.path.splitext(f)[1].lower() in _ODF_EXTS
                ]

            modTimeAfter    = os.stat(fullPath).st_mtime
            fileWasModified = (modTimeAfter != modTimeBefore)

            if fileWasModified and hasattr(providerModule, 'postProcess'):
                providerModule.postProcess(fullPath)

            displayName  = getDisplayNames().get(providerModule.NAME, "Assistant")
            responseText = f"{displayName}:\n{collectedText.strip()}"
            if useSandbox and ("/login" in collectedText or "not logged in" in collectedText.lower()):
                responseText += "\n\n" + _sandboxLoginHint(providerModule, sandboxHome)

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
                    if useSandbox:
                        responseText += "\n\n" + _sandboxLoginHint(providerModule, sandboxHome)
                else:
                    lines    = stderr.split('\n')
                    filtered = '\n'.join(lines[:10] + ['... (truncated) ...'] + lines[-10:]) if len(lines) > 30 else stderr
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

        # Save changed-state / created-files and update undo/redo flags
        if newFiles and docDir:
            # A new document was created - store copies for redo, record paths
            for path in newFiles:
                copyPath = os.path.join(docDir, "created_" + os.path.basename(path))
                shutil.copy2(path, copyPath)
            settingsData3 = settings.loadSettingsForDir(docDir, fullPath)
            settingsData3["last_action"]    = "create"
            settingsData3["created_files"]  = newFiles
            settingsData3["undo_available"] = True
            settingsData3["redo_available"] = False
            settings.saveSettingsForDir(docDir, settingsData3, fullPath)
        elif fileWasModified and docDir:
            changedPath = os.path.join(docDir, "changed" + os.path.splitext(filename)[1])
            shutil.copy2(fullPath, changedPath)
            backup._undo_state = "changed"
            settingsData3 = settings.loadSettingsForDir(docDir, fullPath)
            settingsData3["last_action"]    = "edit"
            settingsData3["undo_available"] = True
            settingsData3["redo_available"] = False
            settings.saveSettingsForDir(docDir, settingsData3, fullPath)
        elif docDir:
            # Pure information response or error - no file change. The backup was
            # already overwritten with the current state at call time, so there is
            # nothing to undo; reset action state to neutral.
            settingsData3 = settings.loadSettingsForDir(docDir, fullPath)
            settingsData3["last_action"]    = "none"
            settingsData3["undo_available"] = False
            settingsData3["redo_available"] = False
            settings.saveSettingsForDir(docDir, settingsData3, fullPath)

        # Save history
        updatedHistory = currentHistory + responseText + "\n\n"
        settings.saveHistoryForDir(docDir, updatedHistory)

        completionCallback.payload = {
            "response":        responseText,
            "fileWasModified": fileWasModified,
            "newFiles":        newFiles,
            "url":             url,
            "frameName":       frameName,
            "doc":             doc,
            "docDir":          docDir,
        }
        asyncCb.addCallback(completionCallback, None)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


def _sandboxLoginHint(providerModule, sandboxHome):
    """Explain how to log the provider in inside the sandbox's private HOME."""
    exe = getattr(providerModule, "EXECUTABLE", "claude")
    loginCmd = {"claude": "claude /login", "codex": "codex login"}.get(exe, exe)
    return ("LibreAssist runs the agent in a sandbox with its own login, separate "
            "from your normal one. Log in once from a terminal:\n"
            f"HOME='{sandboxHome}' {loginCmd}\n"
            "(The sandbox can be switched off in Settings.)")


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
    from libreassist.settings import loadProviderConfig
    config      = loadProviderConfig()
    allProviders = list(config.keys())

    found = discovery.discoverAllProviders(allProviders)

    globalSettings = settings.loadGlobalSettings()
    globalSettings["discovered_providers"] = found
    settings.saveGlobalSettings(globalSettings)

    return found
