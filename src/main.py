# -*- coding: utf-8 -*-
# main.py - LibreAssist Extension Entry Point

import uno
import unohelper

from libreassist.ui import ElementFactory


# Register the extension with LibreOffice
g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    ElementFactory,
    "org.libreoffice.libreassist.LibreAssistFactory",
    ("com.sun.star.task.Job",),
)
