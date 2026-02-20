# -*- coding: utf-8 -*-
# libreassist/ui/ui.py - UI components and helpers

import uno
import unohelper

from com.sun.star.lang import XComponent
from com.sun.star.ui import XUIElement, XToolPanel, XSidebarPanel, LayoutSize
from com.sun.star.ui.UIElementType import TOOLPANEL as UET_TOOLPANEL


def getLocalizedString(key, fallback=""):
    """
    Load a localized string from the extension's locale files.
    
    Args:
        key: Translation key
        fallback: Fallback string if key not found
        
    Returns:
        Translated string or fallback
    """
    try:
        import json
        import os

        ctx = uno.getComponentContext()

        configProvider = ctx.ServiceManager.createInstance(
            "com.sun.star.configuration.ConfigurationProvider")
        prop = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        prop.Name = "nodepath"
        prop.Value = "/org.openoffice.Setup/L10N"
        settings = configProvider.createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationAccess", (prop,))
        locale = settings.getByName("ooLocale")
        locale = locale[:2] if locale else 'en'

        pip = ctx.getValueByName(
            "/singletons/com.sun.star.deployment.PackageInformationProvider")
        extensionPath = pip.getPackageLocation("org.libreoffice.libreassist")

        if extensionPath.startswith("vnd.sun.star.expand:"):
            pathSubst = ctx.ServiceManager.createInstance(
                "com.sun.star.util.PathSubstitution")
            extensionPath = pathSubst.substituteVariables(extensionPath, True)

        if extensionPath.startswith("file://"):
            extensionPath = uno.fileUrlToSystemPath(extensionPath)

        localeFile = os.path.join(extensionPath, "locales", f"{locale}.json")
        if not os.path.exists(localeFile):
            localeFile = os.path.join(extensionPath, "locales", "en.json")

        with open(localeFile, 'r', encoding='utf-8') as f:
            translations = json.load(f)

        return translations.get(key, fallback)

    except Exception as e:
        print(f"Error loading localized string: {e}")
        return fallback


class LibreAssistPanel(unohelper.Base, XSidebarPanel, XUIElement, XToolPanel, XComponent):
    """
    Panel implementation for LibreOffice sidebar.
    """

    def __init__(self, ctx, frame, xParentWindow, url):
        self.ctx = ctx
        self.xParentWindow = xParentWindow
        self.window = None
        self.height = 100

    def getRealInterface(self):
        if not self.window:
            dialogUrl = "vnd.sun.star.extension://org.libreoffice.libreassist/empty_dialog.xdl"
            provider = self.ctx.ServiceManager.createInstanceWithContext(
                "com.sun.star.awt.ContainerWindowProvider", self.ctx)
            self.window = provider.createContainerWindow(
                dialogUrl, "", self.xParentWindow, None)
        return self

    @property
    def Frame(self):
        return None

    @property
    def ResourceURL(self):
        return ""

    @property
    def Type(self):
        return UET_TOOLPANEL

    def dispose(self):
        pass

    def addEventListener(self, ev):
        pass

    def removeEventListener(self, ev):
        pass

    def createAccessible(self, parent):
        return self

    @property
    def Window(self):
        return self.window

    def getHeightForWidth(self, width):
        return LayoutSize(self.height, self.height, self.height)

    def getMinimalWidth(self):
        return 300
