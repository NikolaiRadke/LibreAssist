# -*- coding: utf-8 -*-
# libreassist/backup.py - Backup and restore functions

import os
import shutil
import time
import uno
from .document import getCurrentDocument, getDocumentPath
from .settings import getDocSettingsDir, loadSettings, saveSettings

_undo_state = "original"  # Track state: "original" or "changed"


def createBackup(fullPath, docDir):
    """
    Create a backup of the document before the provider modifies it.
    Safe to call from the Main-UNO-Thread – does not use getCurrentDocument().

    Args:
        fullPath: Absolute path to the document file
        docDir:   Settings directory for this document

    Returns: True if successful, False otherwise
    """
    try:
        if not fullPath or not docDir:
            return False
        filename = os.path.basename(fullPath)
        backupPath = os.path.join(docDir, "backup" + os.path.splitext(filename)[1])
        shutil.copy2(fullPath, backupPath)
        return True
    except Exception as e:
        print(f"Error creating backup: {e}")
        return False


def restoreBackup():
    """
    Restore document from backup (Undo).
    Called from the Undo button – getCurrentDocument() is correct here.
    Returns: Status message string
    """
    global _undo_state

    try:
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
        frameName = frame.getName()
        if not frameName:
            frameName = f"la_{id(frame)}"
            frame.setName(frameName)
        url = doc.getURL()

        data = loadSettings()
        data["undo_available"] = False
        data["redo_available"] = True
        saveSettings(data)

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
    Called from the Redo button – getCurrentDocument() is correct here.
    Returns: Status message string
    """
    global _undo_state

    try:
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
        frameName = frame.getName()
        if not frameName:
            frameName = f"la_{id(frame)}"
            frame.setName(frameName)
        url = doc.getURL()

        data = loadSettings()
        data["undo_available"] = True
        data["redo_available"] = False
        saveSettings(data)

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
