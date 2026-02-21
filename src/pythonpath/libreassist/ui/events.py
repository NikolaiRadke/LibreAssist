# -*- coding: utf-8 -*-
# libreassist/ui/events.py - Event handlers

import uno
import unohelper
from com.sun.star.awt import XActionListener, XItemListener, XTextListener
from com.sun.star.document import XDocumentEventListener
from libreassist.i18n import t
from libreassist import core, settings as lib_settings


def showMessageBox(title, message, messageType="infobox", buttons=1):
    """
    Show a message box dialog.
    
    Args:
        title: Dialog title
        message: Dialog message
        messageType: 'infobox', 'warningbox', 'errorbox', 'querybox', 'messbox'
        buttons: 1=OK, 2=OK+Cancel, 3=Yes+No+Cancel, 4=Yes+No
        
    Returns:
        Button pressed (1=OK/Yes, 2=Cancel/No, 0=Cancel)
    """
    ctx = uno.getComponentContext()
    smgr = ctx.ServiceManager
    desktop = smgr.createInstance("com.sun.star.frame.Desktop")
    frame = desktop.getCurrentFrame()
    window = frame.getContainerWindow()
    
    toolkit = window.getToolkit()
    
    from com.sun.star.awt.MessageBoxButtons import BUTTONS_OK, BUTTONS_YES_NO
    from com.sun.star.awt.MessageBoxType import INFOBOX, WARNINGBOX, QUERYBOX
    
    # Map string to constants
    typeMap = {
        "infobox": INFOBOX,
        "warningbox": WARNINGBOX,
        "querybox": QUERYBOX
    }
    
    buttonsMap = {
        1: BUTTONS_OK,
        4: BUTTONS_YES_NO
    }
    
    msgBox = toolkit.createMessageBox(
        window,
        typeMap.get(messageType, INFOBOX),
        buttonsMap.get(buttons, BUTTONS_OK),
        title,
        message
    )
    
    return msgBox.execute()


class ActionEventHandler(unohelper.Base, XActionListener):
    """
    Handles all button click events.
    """
    
    def __init__(self, factory):
        self.factory = factory
    
    def actionPerformed(self, event):
        """Main event router for all button actions."""
        
        # ---- Send ----
        if event.ActionCommand == "Send_OnClick":
            try:
                inputControl = self.factory.panelWin.getControl("InputField")
                historyControl = self.factory.panelWin.getControl("ChatHistory")

                userText = inputControl.getText()
                if userText.strip():
                    currentHistory = historyControl.getText()
                    newHistory = currentHistory + "User:\n" + userText + "\n\n"
                    historyControl.setText(newHistory)

                    model = historyControl.getModel()
                    wasReadOnly = model.ReadOnly
                    model.ReadOnly = False
                    textLength = len(newHistory)
                    historyControl.setSelection(uno.createUnoStruct(
                        "com.sun.star.awt.Selection", textLength, textLength))
                    model.ReadOnly = wasReadOnly

                    inputControl.setText("")

                    responseText = core.handleUserInput(userText, newHistory)

                    if responseText:
                        currentHistory = historyControl.getText()
                        newHistory = currentHistory + responseText + "\n\n"
                        historyControl.setText(newHistory)

                        model = historyControl.getModel()
                        wasReadOnly = model.ReadOnly
                        model.ReadOnly = False
                        textLength = len(newHistory)
                        historyControl.setSelection(uno.createUnoStruct(
                            "com.sun.star.awt.Selection", textLength, textLength))
                        model.ReadOnly = wasReadOnly

                        # Save history to disk
                        lib_settings.saveHistory(newHistory)

            except Exception as e:
                print("Error in Send_OnClick:", e)
                import traceback
                traceback.print_exc()

        # ---- Undo ----
        elif event.ActionCommand == "Undo_OnClick":
            try:
                core.handleUserInput("__undo__")
            except Exception as e:
                print("Error in Undo:", e)
                import traceback
                traceback.print_exc()

        # ---- Redo ----
        elif event.ActionCommand == "Redo_OnClick":
            try:
                core.handleUserInput("__redo__")
            except Exception as e:
                print("Error in Redo:", e)
                import traceback
                traceback.print_exc()

        # ---- Settings toggle ----
        elif event.ActionCommand == "Settings_OnClick":
            if self.factory.currentView == "settings":
                self.factory.showView("chat")
            else:
                self.factory.showView("settings")

        # ---- About toggle ----
        elif event.ActionCommand == "About_OnClick":
            if self.factory.currentView == "about":
                self.factory.showView("chat")
            else:
                self.factory.showView("about")

        # ---- Back button ----
        elif event.ActionCommand == "Back_OnClick":
            self.factory.showView("chat")

        # ---- Reset Session ----
        elif event.ActionCommand == "ResetSession_OnClick":
            try:
                # Sicherheitsabfrage
                result = showMessageBox(
                    t("reset_session_title"),
                    t("reset_session_confirm"),
                    messageType="querybox",
                    buttons=4
                )
                
                if result == 2:  # Yes clicked
                    lib_settings.resetSession()
                    
                    showMessageBox(
                        t("reset_session_success_title"),
                        t("reset_session_success"),
                        messageType="infobox",
                        buttons=1
                    )
            except Exception as e:
                print("Error in ResetSession:", e)
                showMessageBox(
                    t("error_title"),
                    t("reset_session_error", "Failed to reset session: {error}").format(error=str(e)),
                    messageType="errorbox",
                    buttons=1
                )

        # ---- Clear History ----
        elif event.ActionCommand == "ClearHistory_OnClick":
            try:
                # Sicherheitsabfrage
                result = showMessageBox(
                    t("clear_history_title"),
                    t("clear_history_confirm"),
                    messageType="querybox",
                    buttons=4
                )
                
                if result == 2:  # Yes clicked
                    lib_settings.clearHistory()

                    historyControl = self.factory.panelWin.getControl("ChatHistory")
                    historyControl.setText("Chat History\n")
                    
                    showMessageBox(
                        t("clear_history_success_title"),
                        t("clear_history_success"),
                        messageType="infobox",
                        buttons=1
                    )
            except Exception as e:
                print("Error in ClearHistory:", e)
                showMessageBox(
                    t("error_title"),
                    t("clear_history_error", "Failed to clear history: {error}").format(error=str(e)),
                    messageType="errorbox",
                    buttons=1
                )


class ProviderChangeListener(unohelper.Base, XItemListener):
    """
    Handles provider dropdown changes.
    """
    
    def __init__(self, factory):
        self.factory = factory
        
    def itemStateChanged(self, event):
        try:
            globalSettings = lib_settings.loadGlobalSettings()
            providerList = self.factory.panelWin.getControl("ProviderList")
            selectedItems = providerList.getSelectedItemPos()
            
            if selectedItems >= 0:
                # Save selected provider
                globalSettings["default_provider"] = providerList.getItem(selectedItems)
                lib_settings.saveGlobalSettings(globalSettings)
        except Exception as e:
            print(f"Error saving provider: {e}")
            
    def disposing(self, event):
        pass


class TimeoutChangeListener(unohelper.Base, XTextListener):
    """
    Handles timeout field changes.
    """
    
    def __init__(self, factory):
        self.factory = factory
        
    def textChanged(self, event):
        try:
            globalSettings = lib_settings.loadGlobalSettings()
            timeoutField = self.factory.panelWin.getControl("TimeoutField")
            globalSettings["timeout"] = int(timeoutField.getValue())
            lib_settings.saveGlobalSettings(globalSettings)
        except Exception as e:
            print(f"Error saving timeout: {e}")
            
    def disposing(self, event):
        pass


class SaveAsListener(unohelper.Base, XDocumentEventListener):
    """
    Handles Save As events for settings migration.
    """
    
    def __init__(self):
        self.oldPath = None
    
    def documentEventOccured(self, event):
        if event.EventName == "OnSaveAsDone":
            try:
                doc = event.Source
                newPath = uno.fileUrlToSystemPath(doc.getURL())
                lib_settings.migrateSettingsIfNeeded(self.oldPath, newPath)
                self.oldPath = newPath
            except Exception as e:
                print(f"Error in SaveAs listener: {e}")
                import traceback
                traceback.print_exc()
    
    def disposing(self, event):
        pass

class InstructionsChangeListener(unohelper.Base, XTextListener):
    """
    Handles custom instructions field changes.
    """
    
    def __init__(self, factory):
        self.factory = factory
        
    def textChanged(self, event):
        try:
            globalSettings = lib_settings.loadGlobalSettings()
            instructionsField = self.factory.panelWin.getControl("InstructionsField")
            globalSettings["custom_instructions"] = instructionsField.getText()
            lib_settings.saveGlobalSettings(globalSettings)
        except Exception as e:
            print(f"Error saving instructions: {e}")
            
    def disposing(self, event):
        pass
