# -*- coding: utf-8 -*-
# libreassist/document.py - Document operations

import uno


def getCurrentDocument():
    """
    Get the current document (Writer, Calc, Impress, Draw, Math).
    Returns: document object or None
    """
    try:
        ctx = uno.getComponentContext()
        smgr = ctx.ServiceManager
        desktop = smgr.createInstance("com.sun.star.frame.Desktop")
        doc = desktop.getCurrentComponent()

        if doc and (
            doc.supportsService("com.sun.star.text.TextDocument") or
            doc.supportsService("com.sun.star.sheet.SpreadsheetDocument") or
            doc.supportsService("com.sun.star.presentation.PresentationDocument") or
            doc.supportsService("com.sun.star.drawing.DrawingDocument") or
            doc.supportsService("com.sun.star.formula.FormulaProperties")
        ):
            return doc
        else:
            return None
    except Exception as e:
        print("Error in getCurrentDocument:", e)
        return None


def getDocumentPath():
    """
    Get the file system path of the current document.
    Returns: (directory, filename, fullpath) tuple or (None, None, None) if not saved
    """
    try:
        doc = getCurrentDocument()
        if not doc:
            return (None, None, None)

        url = doc.getURL()
        if not url:
            return (None, None, None)

        fullPath = uno.fileUrlToSystemPath(url)

        import os
        directory = os.path.dirname(fullPath)
        filename = os.path.basename(fullPath)

        return (directory, filename, fullPath)

    except Exception as e:
        print("Error in getDocumentPath:", e)
        return (None, None, None)
