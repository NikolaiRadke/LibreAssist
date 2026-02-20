# -*- coding: utf-8 -*-
# libreassist/i18n.py - Internationalization

import uno

_translations = None
_current_locale = None


def getLocale():
    """
    Get current LibreOffice UI language.
    Returns: Language code (e.g. 'en', 'de')
    """
    try:
        ctx = uno.getComponentContext()
        configProvider = ctx.ServiceManager.createInstance(
            "com.sun.star.configuration.ConfigurationProvider")

        prop = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        prop.Name = "nodepath"
        prop.Value = "/org.openoffice.Setup/L10N"

        settings = configProvider.createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationAccess", (prop,))

        locale = settings.getByName("ooLocale")
        return locale[:2] if locale else 'en'
    except:
        return 'en'


def loadTranslations():
    """
    Load translation file for current locale from extension.
    """
    global _translations, _current_locale

    try:
        import json
        import os

        locale = getLocale()
        _current_locale = locale

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

        localeFile = os.path.join(extensionPath, "locales", f"{locale}.json")

        if not os.path.exists(localeFile):
            localeFile = os.path.join(extensionPath, "locales", "en.json")

        with open(localeFile, 'r', encoding='utf-8') as f:
            _translations = json.load(f)

        return True

    except Exception as e:
        print(f"Error loading translations: {e}")
        _translations = {
            "wait_title": "⏳ Working...",
            "error_not_saved": "ERROR: Please save the document first!",
            "error_timeout": "ERROR: Claude timed out (10 min)",
            "error_not_found": "ERROR: CLI tool not found",
            "error_general": "ERROR: {error}",
        }
        return False


def t(key, **kwargs):
    """
    Translate a key to current language.
    Supports placeholder substitution: t('error_general', error='File not found')
    """
    global _translations

    if _translations is None:
        loadTranslations()

    text = _translations.get(key, key)

    if kwargs:
        text = text.format(**kwargs)

    return text


def getVersion():
    """
    Read version from description.xml.
    """
    try:
        import xml.etree.ElementTree as ET
        import os

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

        descFile = os.path.join(extensionPath, "description.xml")
        tree = ET.parse(descFile)
        root = tree.getroot()

        ns = {"d": "http://openoffice.org/extensions/description/2006"}
        version = root.find("d:version", ns)

        return version.get("value") if version is not None else "unknown"

    except Exception as e:
        print(f"Error reading version: {e}")
        return "unknown"
