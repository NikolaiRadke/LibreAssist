# -*- coding: utf-8 -*-
# libreassist/settings.py - Settings and history management

import uno
from .document import getCurrentDocument, getDocumentPath


def getLibreAssistDir():
    """
    Get the base LibreAssist data directory in LibreOffice user profile.
    Creates directory if it doesn't exist.
    Returns: path string or None
    """
    try:
        import os

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
    Creates directory if it doesn't exist.
    Returns: path string or None
    """
    try:
        import os
        import hashlib

        directory, filename, fullPath = getDocumentPath()
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
        print(f"Error getting document settings directory: {e}")
        return None


def loadSettings():
    """
    Load settings for current document.
    Returns: settings dict with defaults
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
        import json
        import os

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
            # Merge with defaults so new keys are always present
            defaults.update(saved)
            return defaults

    except Exception as e:
        print(f"Error loading settings: {e}")
        return defaults


def saveSettings(settings):
    """
    Save settings for current document.
    """
    try:
        import json
        import os

        docDir = getDocSettingsDir()
        if not docDir:
            return False

        directory, filename, fullPath = getDocumentPath()
        settings["document_path"] = fullPath

        settingsFile = os.path.join(docDir, "settings.json")
        with open(settingsFile, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2)

        return True

    except Exception as e:
        print(f"Error saving settings: {e}")
        return False


def getGlobalSettingsFile():
    """
    Get path to global settings file (not document-specific).
    """
    try:
        import os
        baseDir = getLibreAssistDir()
        if not baseDir:
            return None
        return os.path.join(baseDir, "global_settings.json")
    except Exception as e:
        print(f"Error getting global settings file: {e}")
        return None


def loadGlobalSettings():
    """
    Load global settings (providers, default provider, etc.)
    """
    defaults = {
        "discovered_providers": {},
        "default_provider": "claude_code",
        "timeout": 600,
        "custom_instructions": ""
    }
    
    try:
        import json
        import os
        
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


def saveGlobalSettings(settings):
    """
    Save global settings.
    """
    try:
        import json
        
        settingsFile = getGlobalSettingsFile()
        if not settingsFile:
            return False
        
        with open(settingsFile, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving global settings: {e}")
        return False


def loadHistory():
    """
    Load chat history from document's settings directory.
    Returns: history text or default header
    """
    try:
        import os

        docDir = getDocSettingsDir()
        if not docDir:
            return "Chat History\n"

        historyFile = os.path.join(docDir, "history.txt")
        if os.path.exists(historyFile):
            with open(historyFile, 'r', encoding='utf-8') as f:
                return f.read()

        return "Chat History\n"

    except Exception as e:
        print(f"Error loading history: {e}")
        return "Chat History\n"


def saveHistory(historyText):
    """
    Save chat history to document's settings directory.
    """
    try:
        import os

        docDir = getDocSettingsDir()
        if not docDir:
            return False

        historyFile = os.path.join(docDir, "history.txt")
        with open(historyFile, 'w', encoding='utf-8') as f:
            f.write(historyText)

        return True

    except Exception as e:
        print(f"Error saving history: {e}")
        return False


def clearHistory():
    """Clear chat history for the current document."""
    saveHistory("Chat History\n")


def resetSession():
    """Reset the current session ID for all providers."""
    settings = loadSettings()
    settings["session_ids"] = {}
    saveSettings(settings)


def cleanupOrphanedDirs():
    """
    Remove settings directories where the original document no longer exists.
    Called on extension startup.
    """
    try:
        import json
        import os
        import shutil

        baseDir = getLibreAssistDir()
        if not baseDir:
            return

        for dirName in os.listdir(baseDir):
            dirPath = os.path.join(baseDir, dirName)
            if not os.path.isdir(dirPath):
                continue

            settingsFile = os.path.join(dirPath, "settings.json")
            if not os.path.exists(settingsFile):
                shutil.rmtree(dirPath)
                continue

            with open(settingsFile, 'r', encoding='utf-8') as f:
                settings = json.load(f)

            docPath = settings.get("document_path")
            if not docPath or not os.path.exists(docPath):
                shutil.rmtree(dirPath)

    except Exception as e:
        print(f"Error during cleanup: {e}")


def migrateSettingsIfNeeded(oldPath, newPath):
    """
    Migrate settings if document was saved under new path.
    Called by SaveAs event listener.
    
    Args:
        oldPath: Previous document path
        newPath: Current document path
    """
    if not oldPath or not newPath or oldPath == newPath:
        return
    
    try:
        import os
        import shutil
        import hashlib
        
        baseDir = getLibreAssistDir()
        if not baseDir:
            return
        
        oldHash = hashlib.md5(oldPath.encode()).hexdigest()[:12]
        newHash = hashlib.md5(newPath.encode()).hexdigest()[:12]
        
        oldDir = os.path.join(baseDir, oldHash)
        newDir = os.path.join(baseDir, newHash)
        
        # Migrate: delete existing newDir first, then copy from oldDir
        if os.path.exists(oldDir):
            if os.path.exists(newDir):
                shutil.rmtree(newDir)
            os.makedirs(newDir, exist_ok=True)
            
            # Copy all files
            for item in os.listdir(oldDir):
                src = os.path.join(oldDir, item)
                dst = os.path.join(newDir, item)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
            
            # Update document path in settings
            settingsFile = os.path.join(newDir, "settings.json")
            if os.path.exists(settingsFile):
                import json
                with open(settingsFile, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                settings["document_path"] = newPath
                with open(settingsFile, 'w', encoding='utf-8') as f:
                    json.dump(settings, f, indent=2)
            
            # Delete old directory
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
        import os
        baseDir = getLibreAssistDir()
        if baseDir and os.path.exists(baseDir):
            shutil.rmtree(baseDir)
            return True
        return False
    except Exception as e:
        print(f"Error deleting all data: {e}")
        return False
