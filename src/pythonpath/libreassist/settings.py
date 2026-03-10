# -*- coding: utf-8 -*-
# libreassist/settings.py - Settings and history management

import os
import json
import hashlib
import uno
from .document import getCurrentDocument, getDocumentPath


# ---------------------------------------------------------------------------
# Base directory helpers
# ---------------------------------------------------------------------------

def getLibreAssistDir():
    """
    Get the base LibreAssist data directory in LibreOffice user profile.
    Creates directory if it doesn't exist.
    Returns: path string or None
    """
    try:
        ctx = uno.getComponentContext()
        pathSubst = ctx.ServiceManager.createInstance(
            "com.sun.star.util.PathSubstitution")
        userPath = pathSubst.getSubstituteVariableValue("user")

        if userPath.startswith("file://"):
            userPath = uno.fileUrlToSystemPath(userPath)

        baseDir = os.path.join(userPath, "libreassist")
        os.makedirs(baseDir, exist_ok=True)

        return baseDir

    except Exception as e:
        print(f"Error getting LibreAssist directory: {e}")
        return None


def getDocSettingsDir():
    """
    Get the settings directory for the current document (hash-based).
    Uses getCurrentDocument() – only call from the Main-UNO-Thread.
    Returns: path string or None
    """
    try:
        directory, filename, fullPath = getDocumentPath()
        if not fullPath:
            return None
        return getDocSettingsDirForPath(fullPath)

    except Exception as e:
        print(f"Error getting document settings directory: {e}")
        return None


def getDocSettingsDirForPath(fullPath):
    """
    Get the settings directory for a specific document path (hash-based).
    Safe to call from background threads – does not use getCurrentDocument().
    Returns: path string or None
    """
    try:
        if not fullPath:
            return None
        baseDir = getLibreAssistDir()
        if not baseDir:
            return None
        pathHash = hashlib.md5(fullPath.encode()).hexdigest()[:12]
        docDir = os.path.join(baseDir, pathHash)
        os.makedirs(docDir, exist_ok=True)
        return docDir

    except Exception as e:
        print(f"Error getting doc settings dir for path: {e}")
        return None


# ---------------------------------------------------------------------------
# Document-specific settings  (path-aware versions for async use)
# ---------------------------------------------------------------------------

def loadSettingsForDir(docDir, fullPath=None):
    """
    Load settings from a specific docDir.
    Safe to call from background threads.
    """
    defaults = {
        "document_path": fullPath,
        "provider": "claude_code",
        "session_ids": {},
        "timeout": 600,
        "undo_available": False,
        "redo_available": False
    }
    try:
        if not docDir:
            return defaults
        settingsFile = os.path.join(docDir, "settings.json")
        if not os.path.exists(settingsFile):
            return defaults
        with open(settingsFile, 'r', encoding='utf-8') as f:
            saved = json.load(f)
            defaults.update(saved)
            return defaults
    except Exception as e:
        print(f"Error loading settings for dir: {e}")
        return defaults


def saveSettingsForDir(docDir, settingsData, fullPath=None):
    """
    Save settings to a specific docDir.
    Safe to call from background threads.
    """
    try:
        if not docDir:
            return False
        if fullPath:
            settingsData["document_path"] = fullPath
        settingsFile = os.path.join(docDir, "settings.json")
        with open(settingsFile, 'w', encoding='utf-8') as f:
            json.dump(settingsData, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving settings for dir: {e}")
        return False


def loadHistoryForDir(docDir):
    """
    Load chat history from a specific docDir.
    Safe to call from background threads.
    """
    try:
        if not docDir:
            return "Chat History\n"
        historyFile = os.path.join(docDir, "history.txt")
        if os.path.exists(historyFile):
            with open(historyFile, 'r', encoding='utf-8') as f:
                return f.read()
        return "Chat History\n"
    except Exception as e:
        print(f"Error loading history for dir: {e}")
        return "Chat History\n"


def saveHistoryForDir(docDir, historyText):
    """
    Save chat history to a specific docDir.
    Safe to call from background threads.
    """
    try:
        if not docDir:
            return False
        historyFile = os.path.join(docDir, "history.txt")
        with open(historyFile, 'w', encoding='utf-8') as f:
            f.write(historyText)
        return True
    except Exception as e:
        print(f"Error saving history for dir: {e}")
        return False


# ---------------------------------------------------------------------------
# Document-specific settings  (current-document versions for UI use)
# ---------------------------------------------------------------------------

def loadSettings():
    """
    Load settings for the current document.
    Only call from the Main-UNO-Thread.
    """
    defaults = {
        "document_path": None,
        "provider": "claude_code",
        "session_ids": {},
        "timeout": 600,
        "undo_available": False,
        "redo_available": False
    }
    try:
        docDir = getDocSettingsDir()
        if not docDir:
            return defaults
        settingsFile = os.path.join(docDir, "settings.json")
        if not os.path.exists(settingsFile):
            directory, filename, fullPath = getDocumentPath()
            defaults["document_path"] = fullPath
            saveSettings(defaults)
            return defaults
        with open(settingsFile, 'r', encoding='utf-8') as f:
            saved = json.load(f)
            defaults.update(saved)
            return defaults
    except Exception as e:
        print(f"Error loading settings: {e}")
        return defaults


def saveSettings(settingsData):
    """
    Save settings for the current document.
    Only call from the Main-UNO-Thread.
    """
    try:
        docDir = getDocSettingsDir()
        if not docDir:
            return False
        directory, filename, fullPath = getDocumentPath()
        settingsData["document_path"] = fullPath
        settingsFile = os.path.join(docDir, "settings.json")
        with open(settingsFile, 'w', encoding='utf-8') as f:
            json.dump(settingsData, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False


def loadHistory():
    """
    Load chat history for the current document.
    Only call from the Main-UNO-Thread.
    """
    try:
        docDir = getDocSettingsDir()
        return loadHistoryForDir(docDir)
    except Exception as e:
        print(f"Error loading history: {e}")
        return "Chat History\n"


def saveHistory(historyText):
    """
    Save chat history for the current document.
    Only call from the Main-UNO-Thread.
    """
    try:
        docDir = getDocSettingsDir()
        return saveHistoryForDir(docDir, historyText)
    except Exception as e:
        print(f"Error saving history: {e}")
        return False


def clearHistory():
    """Clear chat history for the current document."""
    saveHistory("Chat History\n")


def resetSession():
    """Reset session IDs for all providers in the current document."""
    data = loadSettings()
    data["session_ids"] = {}
    saveSettings(data)


# ---------------------------------------------------------------------------
# Global settings
# ---------------------------------------------------------------------------

def getGlobalSettingsFile():
    """Get path to global settings file (not document-specific)."""
    try:
        baseDir = getLibreAssistDir()
        if not baseDir:
            return None
        return os.path.join(baseDir, "global_settings.json")
    except Exception as e:
        print(f"Error getting global settings file: {e}")
        return None


def loadGlobalSettings():
    """Load global settings (providers, default provider, etc.)"""
    defaults = {
        "discovered_providers": {},
        "default_provider": "claude_code",
        "timeout": 600,
        "custom_instructions": ""
    }
    try:
        settingsFile = getGlobalSettingsFile()
        if not settingsFile or not os.path.exists(settingsFile):
            return defaults
        with open(settingsFile, 'r', encoding='utf-8') as f:
            saved = json.load(f)
            defaults.update(saved)
            return defaults
    except Exception as e:
        print(f"Error loading global settings: {e}")
        return defaults


def saveGlobalSettings(settingsData):
    """Save global settings."""
    try:
        settingsFile = getGlobalSettingsFile()
        if not settingsFile:
            return False
        with open(settingsFile, 'w', encoding='utf-8') as f:
            json.dump(settingsData, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving global settings: {e}")
        return False


# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------

def cleanupOrphanedDirs():
    """
    Remove settings directories where the original document no longer exists.
    Called on extension startup.
    """
    try:
        baseDir = getLibreAssistDir()
        if not baseDir:
            return

        import shutil
        for dirName in os.listdir(baseDir):
            dirPath = os.path.join(baseDir, dirName)
            if not os.path.isdir(dirPath):
                continue
            settingsFile = os.path.join(dirPath, "settings.json")
            if not os.path.exists(settingsFile):
                shutil.rmtree(dirPath)
                continue
            with open(settingsFile, 'r', encoding='utf-8') as f:
                data = json.load(f)
            docPath = data.get("document_path")
            if not docPath or not os.path.exists(docPath):
                shutil.rmtree(dirPath)

    except Exception as e:
        print(f"Error during cleanup: {e}")


def migrateSettingsIfNeeded(oldPath, newPath):
    """
    Migrate settings if document was saved under a new path.
    Called by the SaveAs event listener.
    """
    if not oldPath or not newPath or oldPath == newPath:
        return
    try:
        import shutil

        baseDir = getLibreAssistDir()
        if not baseDir:
            return

        oldHash = hashlib.md5(oldPath.encode()).hexdigest()[:12]
        newHash = hashlib.md5(newPath.encode()).hexdigest()[:12]

        oldDir = os.path.join(baseDir, oldHash)
        newDir = os.path.join(baseDir, newHash)

        if os.path.exists(oldDir):
            if os.path.exists(newDir):
                shutil.rmtree(newDir)
            os.makedirs(newDir, exist_ok=True)

            for item in os.listdir(oldDir):
                src = os.path.join(oldDir, item)
                dst = os.path.join(newDir, item)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)

            # Update stored path in settings
            settingsFile = os.path.join(newDir, "settings.json")
            if os.path.exists(settingsFile):
                with open(settingsFile, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                data["document_path"] = newPath
                with open(settingsFile, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)

            shutil.rmtree(oldDir)
            print(f"Migrated settings from {oldPath} to {newPath}")

    except Exception as e:
        print(f"Error migrating settings: {e}")
        import traceback
        traceback.print_exc()


def deleteAllData():
    """Delete the complete libreassist data directory."""
    try:
        import shutil
        baseDir = getLibreAssistDir()
        if baseDir and os.path.exists(baseDir):
            shutil.rmtree(baseDir)
            return True
        return False
    except Exception as e:
        print(f"Error deleting all data: {e}")
        return False


# ---------------------------------------------------------------------------
# Provider configuration
# ---------------------------------------------------------------------------

def getProviderConfigFile():
    """Get path to the user-editable provider config file."""
    try:
        baseDir = getLibreAssistDir()
        if not baseDir:
            return None
        return os.path.join(baseDir, "providers.json")
    except Exception as e:
        print(f"Error getting provider config file: {e}")
        return None


def loadProviderConfig():
    """
    Load provider config from user data dir.
    If it doesn't exist yet, copy the default from the extension package.
    Returns: dict of provider entries, or empty dict on failure.
    """
    import json, shutil

    userFile = getProviderConfigFile()
    if not userFile:
        return {}

    if not os.path.exists(userFile):
        # Copy default from extension package
        try:
            ctx = uno.getComponentContext()
            pip = ctx.getValueByName(
                "/singletons/com.sun.star.deployment.PackageInformationProvider")
            extensionPath = pip.getPackageLocation("org.libreoffice.libreassist")
            if extensionPath.startswith("vnd.sun.star.expand:"):
                pathSubst = ctx.ServiceManager.createInstance(
                    "com.sun.star.util.PathSubstitution")
                extensionPath = pathSubst.substituteVariables(extensionPath, True)
            if extensionPath.startswith("file://"):
                extensionPath = uno.fileUrlToSystemPath(extensionPath)
            defaultFile = os.path.join(extensionPath, "providers.json")
            if os.path.exists(defaultFile):
                shutil.copy2(defaultFile, userFile)
        except Exception as e:
            print(f"Error copying default providers.json: {e}")
            return {}

    try:
        with open(userFile, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading provider config: {e}")
        return {}
