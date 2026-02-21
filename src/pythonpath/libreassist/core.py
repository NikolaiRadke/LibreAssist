# -*- coding: utf-8 -*-
# libreassist/core.py - Core logic and provider routing

import uno

# Import from libreassist modules
from .i18n import t, getVersion
from .document import getCurrentDocument, getDocumentPath
from . import discovery, provider_base, settings, backup
from .providers import claude_code, codex_cli


# Registered CLI providers
PROVIDERS = {
    "claude_code": "libreassist.providers.claude_code",
    "codex_cli":  "libreassist.providers.codex_cli",
}

# Aliases for short prefix input
PROVIDER_ALIASES = {
    "claude": "claude_code",
    "codex":  "codex_cli",
}

# Reverse mapping for display names
DISPLAY_NAMES = {v: k.title() for k, v in PROVIDER_ALIASES.items()}

DEFAULT_PROVIDER = "claude_code"


def handleUserInput(userInput, currentHistory=""):
    """
    Main entry point - routes all user commands.

    Args:
        userInput:      String from the input field or special commands
        currentHistory: Current chat history text (for saving)

    Returns:
        String to display in chat history
    """
    # Debug command
    if userInput == "debug":
        settingsData = settings.loadSettings()
        docDir = settings.getDocSettingsDir()
        return f"docDir: {docDir}\nsettings: {settingsData}"

    # Undo command (triggered by Undo button)
    if userInput == "__undo__":
        return backup.restoreBackup()

    # Redo command (triggered by Redo button)
    if userInput == "__redo__":
        return backup.restoreChanged()

    # Detect provider prefix (e.g. "claude ...", "codex ...")
    providerKey = None
    prompt = None

    for prefix in list(PROVIDERS.keys()) + list(PROVIDER_ALIASES.keys()):
        if userInput.lower().startswith(prefix + " "):
            providerKey = PROVIDER_ALIASES.get(prefix, prefix)
            prompt = userInput[len(prefix) + 1:]
            break

    if providerKey is not None:
        # Prefix-based provider selection
        moduleName = PROVIDERS[providerKey]
    else:
        # No prefix: use default provider from global settings
        globalSettings = settings.loadGlobalSettings()
        activeProvider = globalSettings.get("default_provider", DEFAULT_PROVIDER)
        if activeProvider in PROVIDERS:
            moduleName = PROVIDERS[activeProvider]
            prompt = userInput
        else:
            return f"Unknown provider '{activeProvider}'. Check settings."

    return _callProvider(moduleName, prompt, currentHistory)


def _callProvider(moduleName, userPrompt, currentHistory=""):
    """
    Load the provider module and call the LLM.

    Args:
        moduleName:     Python module name string (e.g. 'libreassist.providers.claude_code')
        userPrompt:     The user's instruction
        currentHistory: Current chat history including user input

    Returns:
        Response string for display
    """
    import importlib

    try:
        providerModule = importlib.import_module(moduleName)
    except ImportError as e:
        return f"Could not load provider module '{moduleName}': {e}"

    return callLLM(providerModule, userPrompt, currentHistory)


def callLLM(providerModule, userPrompt, currentHistory=""):
    """
    Execute the LLM call via the given provider module.
    Handles document backup, status indicator, file modification detection,
    history persistence, and document reload.

    Args:
        providerModule: Imported provider module with buildArgs() + extractResponse()
        userPrompt:     The user's instruction
        currentHistory: Current chat history including user input

    Returns:
        Response string for display
    """
    try:
        import time
        import shutil
        import os

        doc = getCurrentDocument()
        if not doc:
            return "No document open"

        url = doc.getURL()
        directory, filename, fullPath = getDocumentPath()

        if not fullPath:
            return t('error_not_saved')

        # Save document before provider works on it
        doc.store()

        if not backup.createBackup():
            return "Could not create backup!"

        modTimeBefore = os.stat(fullPath).st_mtime

        frame = doc.getCurrentController().getFrame()
        frameName = frame.getName() if frame.getName() else "_default"

        statusIndicator = frame.createStatusIndicator()
        statusIndicator.start(t('wait_title'), 0)

        # Load session ID from settings
        settingsData = settings.loadSettings()
        sessionId = settingsData.get("session_ids", {}).get(providerModule.NAME)

        # Load custom instructions
        globalSettings = settings.loadGlobalSettings()
        customInstructions = globalSettings.get("custom_instructions", "").strip()

        # Build full prompt with document context
        basePrompt = (
            f"You have access to {filename} in the current directory. "
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

        try:
            result = provider_base.executeProvider(
                providerModule,
                fullPrompt,
                directory,
                sessionId=sessionId,
                timeout=settingsData.get("timeout", 600)
            )
        except TimeoutError:
            statusIndicator.end()
            return t('error_timeout')
        except FileNotFoundError:
            statusIndicator.end()
            return t('error_not_found')
        except RuntimeError as e:
            statusIndicator.end()
            stderr = str(e)
            stderrLower = stderr.lower()
        
            # Parse common errors and return user-friendly messages
            if "model not found" in stderrLower or "modelnotfounderror" in stderrLower:
                return t('error_model_not_found')
            elif "rate limit" in stderrLower or "429" in stderr:
                return t('error_rate_limit')
            elif "no capacity" in stderrLower or "capacity_exhausted" in stderrLower:
                return t('error_no_capacity')
            elif "authentication" in stderrLower or "unauthorized" in stderrLower:
                return t('error_authentication')
            else:
                # Filter stderr - show first/last 10 lines
                lines = stderr.split('\n')
                if len(lines) > 30:
                    filtered = '\n'.join(lines[:10] + ['... (truncated) ...'] + lines[-10:])
                else:
                    filtered = stderr
                return t('error_provider', error=filtered)
        except Exception as e:
            statusIndicator.end()
            import traceback
            traceback.print_exc()
            return t('error_general', error=str(e))

        statusIndicator.end()

        # Save session ID (only providers that support sessions will return one)
        settingsData = settings.loadSettings()
        session_ids = settingsData.get("session_ids", {})
        session_ids[providerModule.NAME] = result.get("sessionId")
        settingsData["session_ids"] = session_ids
        settings.saveSettings(settingsData)

        collectedText = result.get("response", "")

        modTimeAfter = os.stat(fullPath).st_mtime
        fileWasModified = (modTimeAfter != modTimeBefore)

        # Save complete history before potential reload
        updatedHistory = currentHistory + "Assistant:\n" + collectedText.strip() + "\n\n"
        settings.saveHistory(updatedHistory)

        if fileWasModified:
            docDir = settings.getDocSettingsDir()
            changedPath = os.path.join(docDir, "changed" + os.path.splitext(filename)[1])
            shutil.copy2(fullPath, changedPath)

            backup._undo_state = "changed"

            settingsData = settings.loadSettings()
            settingsData["undo_available"] = True
            settingsData["redo_available"] = False
            settings.saveSettings(settingsData)

            doc.close(False)
            time.sleep(0.3)

            ctx = uno.getComponentContext()
            desktop = ctx.ServiceManager.createInstance("com.sun.star.frame.Desktop")
            desktop.loadComponentFromURL(url, frameName, 0, ())

        displayName = DISPLAY_NAMES.get(providerModule.NAME, "Assistant")
        return f"{displayName}:\n{collectedText.strip()}"

    except Exception as e:
        try:
            statusIndicator.end()
        except:
            pass
        try:
            ctx = uno.getComponentContext()
            desktop = ctx.ServiceManager.createInstance("com.sun.star.frame.Desktop")
            desktop.loadComponentFromURL(url, frameName, 0, ())
        except:
            pass
        import traceback
        traceback.print_exc()
        return t('error_general', error=str(e))


def discoverProviders():
    """
    Discover all installed CLI providers and cache results in GLOBAL settings.
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
