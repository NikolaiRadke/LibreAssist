# -*- coding: utf-8 -*-
# libreassist/backup.py - Backup and restore functions

import uno
from .document import getCurrentDocument, getDocumentPath
from .settings import getDocSettingsDir, loadSettings, saveSettings

_undo_state = "original"  # Track state: "original" or "changed"


def createBackup():
    """
    Create backup file before provider changes the document.
    Returns: True if successful, False otherwise
    """
    try:
        import shutil
        import os

        directory, filename, fullPath = getDocumentPath()
        if not fullPath:
            return False

        docDir = getDocSettingsDir()
        if not docDir:
            return False

        backupPath = os.path.join(docDir, "backup" + os.path.splitext(filename)[1])
        shutil.copy2(fullPath, backupPath)

        return True

    except Exception as e:
        print(f"Error creating backup: {e}")
        return False


def restoreBackup():
    """
    Restore document from backup and reload.
    Returns: Status message string
    """
    global _undo_state

    try:
        import shutil
        import time
        import os

        doc = getCurrentDocument()
        if not doc:
            return "No document open"

        directory, filename, fullPath = getDocumentPath()
        if not fullPath:
            return "Document not saved"

        docDir = getDocSettingsDir()
        backupPath = os.path.join(docDir, "backup" + os.path.splitext(filename)[1])

        if not os.path.exists(backupPath):
            return "No backup available"

        frame = doc.getCurrentController().getFrame()
        frameName = frame.getName() if frame.getName() else "_default"
        url = doc.getURL()

        settings = loadSettings()
        settings["undo_available"] = False
        settings["redo_available"] = True
        saveSettings(settings)

        doc.close(False)
        time.sleep(0.3)

        shutil.copy2(backupPath, fullPath)

        ctx = uno.getComponentContext()
        desktop = ctx.ServiceManager.createInstance("com.sun.star.frame.Desktop")
        desktop.loadComponentFromURL(url, frameName, 0, ())

        _undo_state = "original"
        return "Document restored from backup"

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Error restoring backup: {str(e)}"


def restoreChanged():
    """
    Restore document from changed state (Redo).
    Returns: Status message string
    """
    global _undo_state

    try:
        import shutil
        import time
        import os

        doc = getCurrentDocument()
        if not doc:
            return "No document open"

        directory, filename, fullPath = getDocumentPath()
        if not fullPath:
            return "Document not saved"

        docDir = getDocSettingsDir()
        changedPath = os.path.join(docDir, "changed" + os.path.splitext(filename)[1])

        if not os.path.exists(changedPath):
            return "No changed state available"

        frame = doc.getCurrentController().getFrame()
        frameName = frame.getName() if frame.getName() else "_default"
        url = doc.getURL()

        settings = loadSettings()
        settings["undo_available"] = True
        settings["redo_available"] = False
        saveSettings(settings)

        doc.close(False)
        time.sleep(0.3)

        shutil.copy2(changedPath, fullPath)

        ctx = uno.getComponentContext()
        desktop = ctx.ServiceManager.createInstance("com.sun.star.frame.Desktop")
        desktop.loadComponentFromURL(url, frameName, 0, ())

        _undo_state = "changed"
        return "Changes restored"

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Error restoring changes: {str(e)}"
