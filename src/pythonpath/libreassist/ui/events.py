# -*- coding: utf-8 -*-
# libreassist/ui/events.py - Event handlers

import importlib
import uno
import unohelper
from com.sun.star.awt import XActionListener, XItemListener, XTextListener, XCallback
from com.sun.star.document import XDocumentEventListener
from libreassist.i18n import t
from libreassist import core, settings as lib_settings, document as lib_document


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def showMessageBox(title, message, messageType="infobox", buttons=1):
    """
    Show a modal message box.

    Args:
        title:       Dialog title
        message:     Dialog message
        messageType: 'infobox', 'warningbox', 'querybox'
        buttons:     1=OK, 4=Yes+No

    Returns:
        Button pressed (2=Yes/OK, 3=No, 0=cancelled)
    """
    from com.sun.star.awt.MessageBoxButtons import BUTTONS_OK, BUTTONS_YES_NO
    from com.sun.star.awt.MessageBoxType import INFOBOX, WARNINGBOX, QUERYBOX

    typeMap = {
        "infobox":   INFOBOX,
        "warningbox": WARNINGBOX,
        "querybox":  QUERYBOX,
    }
    buttonsMap = {
        1: BUTTONS_OK,
        4: BUTTONS_YES_NO,
    }

    ctx     = uno.getComponentContext()
    smgr    = ctx.ServiceManager
    desktop = smgr.createInstance("com.sun.star.frame.Desktop")
    frame   = desktop.getCurrentFrame()
    if not frame:
        return 0
    window  = frame.getContainerWindow()
    toolkit = window.getToolkit()

    msgBox = toolkit.createMessageBox(
        window,
        typeMap.get(messageType, INFOBOX),
        buttonsMap.get(buttons, BUTTONS_OK),
        title,
        message
    )
    return msgBox.execute()


def _scrollToEnd(historyControl, text):
    """Scroll the chat history control to the end."""
    model = historyControl.getModel()
    wasReadOnly = model.ReadOnly
    model.ReadOnly = False
    historyControl.setSelection(
        uno.createUnoStruct("com.sun.star.awt.Selection", len(text), len(text)))
    model.ReadOnly = wasReadOnly


# ---------------------------------------------------------------------------
# Async completion callback
# ---------------------------------------------------------------------------

class LLMCompletionCallback(unohelper.Base, XCallback):
    """
    Invoked on the Main-UNO-Thread when the async LLM subprocess finishes.
    panelWin is captured at creation time so it always refers to the correct
    sidebar panel, regardless of which window the user may have switched to.
    """

    def __init__(self, factory, panelWin, historyBeforeResponse):
        self.factory              = factory
        self.panelWin             = panelWin             # Captured at Send click time
        self.historyBeforeResponse = historyBeforeResponse
        self.payload              = None  # Set by _run() before asyncCb.addCallback()
        self.process              = None  # Subprocess handle, set via onProcess callback

    def notify(self, data):
        """Runs on the Main-UNO-Thread – safe to call UNO APIs."""
        try:
            import time

            payload         = self.payload or {}
            responseText    = payload.get("response") or payload.get("error") or t('error_general', error="No response")
            fileWasModified = payload.get("fileWasModified", False)
            docDir          = payload.get("docDir")

            historyControl = self.panelWin.getControl("ChatHistory")

            # Restore Undo/Redo button states from the correct document's settings
            docSettings = lib_settings.loadSettingsForDir(docDir) if docDir else lib_settings.loadSettings()
            self.panelWin.getControl("UndoButton").getModel().Enabled = docSettings.get("undo_available", False)
            self.panelWin.getControl("RedoButton").getModel().Enabled = docSettings.get("redo_available", False)

            if fileWasModified:
                # Document was changed: close and reload in the correct frame.
                # The sidebar panel will be recreated with the updated history.
                url       = payload.get("url")
                frameName = payload.get("frameName", "_default")
                try:
                    ctx     = uno.getComponentContext()
                    desktop = ctx.ServiceManager.createInstance("com.sun.star.frame.Desktop")
                    docToClose = payload.get("doc")
                    if docToClose:
                        docToClose.close(False)
                    time.sleep(0.3)
                    desktop.loadComponentFromURL(url, frameName, 0, ())
                except Exception as e:
                    print(f"Error reloading document: {e}")
            else:
                # No file change: update chat history display manually.
                newHistory = self.historyBeforeResponse + responseText + "\n\n"
                historyControl.setText(newHistory)
                _scrollToEnd(historyControl, newHistory)
                # History was already saved in _run(); save again in case of race.
                if docDir:
                    lib_settings.saveHistoryForDir(docDir, newHistory)
                else:
                    lib_settings.saveHistory(newHistory)

        except Exception as e:
            print(f"Error in LLMCompletionCallback.notify: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Always re-enable the Send button
            try:
                sendButton = self.panelWin.getControl("SendButton")
                sendButton.getModel().Label = t("send_button")
                sendButton.setActionCommand("Send_OnClick")
                sendButton.getModel().Enabled = True
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Button event handler
# ---------------------------------------------------------------------------

class ActionEventHandler(unohelper.Base, XActionListener):
    """Handles all button click events."""

    def __init__(self, factory):
        self.factory = factory

    def actionPerformed(self, event):
        """Main event router for all button actions."""

        # ---- Send ----
        if event.ActionCommand == "Send_OnClick":
            try:
                # Derive the panel window from the button that was clicked.
                # This is always the correct panel, even if the user switches
                # windows during processing.
                panelWin      = event.Source.getContext()
                inputControl  = panelWin.getControl("InputField")
                historyControl = panelWin.getControl("ChatHistory")
                sendButton    = event.Source

                userText = inputControl.getText()
                if not userText.strip():
                    return

                # Append user message to chat
                currentHistory = historyControl.getText()
                newHistory     = currentHistory + "User:\n" + userText + "\n\n"
                historyControl.setText(newHistory)
                _scrollToEnd(historyControl, newHistory)
                inputControl.setText("")

                # Handle special commands synchronously
                if userText.strip().startswith("__"):
                    responseText = core.handleUserInput(userText, newHistory)
                    if responseText:
                        newHistory = newHistory + responseText + "\n\n"
                        historyControl.setText(newHistory)
                        _scrollToEnd(historyControl, newHistory)
                        lib_settings.saveHistory(newHistory)
                    return

                # Resolve provider module
                providerKey = None
                prompt      = userText
                for prefix in list(core.getProviders().keys()) + list(core.getAliases().keys()):
                    if userText.lower().startswith(prefix + " "):
                        providerKey = core.getAliases().get(prefix, prefix)
                        prompt      = userText[len(prefix) + 1:]
                        break

                if providerKey is None:
                    globalSettings = lib_settings.loadGlobalSettings()
                    providerKey    = globalSettings.get("default_provider", core.DEFAULT_PROVIDER)

                moduleName = core.getProviders().get(providerKey)
                if not moduleName:
                    return

                try:
                    providerModule = importlib.import_module(moduleName)
                except ImportError:
                    return

                # Show processing indicator
                workingHistory = newHistory + t('processing_info') + "\n\n"
                historyControl.setText(workingHistory)
                _scrollToEnd(historyControl, workingHistory)

                # Disable buttons during processing
                sendButton.getModel().Label = t("cancel_button")
                sendButton.setActionCommand("Cancel_OnClick")
                panelWin.getControl("UndoButton").getModel().Enabled = False
                panelWin.getControl("RedoButton").getModel().Enabled = False

                # Capture the document at click time (before possible window switch)
                doc = lib_document.getCurrentDocument()

                # Start async call
                callback = LLMCompletionCallback(self.factory, panelWin, newHistory)
                self.factory._activeCallback = callback
                core.callLLMAsync(providerModule, prompt, newHistory, callback, doc)

            except Exception as e:
                print("Error in Send_OnClick:", e)
                import traceback
                traceback.print_exc()
                try:
                    event.Source.getModel().Enabled = True
                except Exception:
                    pass

        # ---- Cancel ----
        elif event.ActionCommand == "Cancel_OnClick":
            try:
                callback = getattr(self.factory, '_activeCallback', None)
                if callback and callback.process:
                    callback.process.kill()
            except Exception as e:
                print(f"Error in Cancel: {e}")

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
                result = showMessageBox(
                    t("reset_session_title"),
                    t("reset_session_confirm"),
                    messageType="querybox",
                    buttons=4
                )
                if result == 2:  # Yes
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
                    t("reset_session_error", error=str(e)),
                    messageType="errorbox",
                    buttons=1
                )

        # ---- Clear History ----
        elif event.ActionCommand == "ClearHistory_OnClick":
            try:
                result = showMessageBox(
                    t("clear_history_title"),
                    t("clear_history_confirm"),
                    messageType="querybox",
                    buttons=4
                )
                if result == 2:  # Yes
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
                    t("clear_history_error", error=str(e)),
                    messageType="errorbox",
                    buttons=1
                )

        # ---- Delete All Data ----
        elif event.ActionCommand == "DeleteAllData_OnClick":
            try:
                result = showMessageBox(
                    t("delete_all_data_title"),
                    t("delete_all_data_confirm"),
                    messageType="querybox",
                    buttons=4
                )
                if result == 2:  # Yes
                    if lib_settings.deleteAllData():
                        historyControl = self.factory.panelWin.getControl("ChatHistory")
                        historyControl.setText("Chat History\n")
                        showMessageBox(
                            t("delete_all_data_success_title"),
                            t("delete_all_data_success"),
                            messageType="infobox",
                            buttons=1
                        )
                    else:
                        showMessageBox(
                            t("error_title"),
                            t("delete_all_data_error", error="Unknown error"),
                            messageType="errorbox",
                            buttons=1
                        )
            except Exception as e:
                print("Error in DeleteAllData:", e)

        # ---- Open Provider Config ----
        elif event.ActionCommand == "OpenProviderConfig_OnClick":
            try:
                import subprocess, sys
                configFile = lib_settings.getProviderConfigFile()
                if not configFile:
                    return
                # Ensure the file exists (copies default if needed)
                lib_settings.loadProviderConfig()
                if sys.platform == "win32":
                    subprocess.Popen(["notepad", configFile])
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", "-t", configFile])
                else:
                    # Try common Linux editors, fall back to xdg-open
                    for editor in ["xdg-open", "gedit", "kate", "mousepad"]:
                        import shutil
                        if shutil.which(editor):
                            subprocess.Popen([editor, configFile])
                            break
            except Exception as e:
                print(f"Error opening provider config: {e}")


# ---------------------------------------------------------------------------
# Settings-view listeners
# ---------------------------------------------------------------------------

class ProviderChangeListener(unohelper.Base, XItemListener):
    """Handles provider dropdown changes."""

    def __init__(self, factory):
        self.factory = factory

    def itemStateChanged(self, event):
        try:
            globalSettings = lib_settings.loadGlobalSettings()
            providerList   = self.factory.panelWin.getControl("ProviderList")
            idx            = providerList.getSelectedItemPos()
            if idx >= 0:
                globalSettings["default_provider"] = providerList.getItem(idx)
                lib_settings.saveGlobalSettings(globalSettings)
        except Exception as e:
            print(f"Error saving provider: {e}")

    def disposing(self, event):
        pass


class TimeoutChangeListener(unohelper.Base, XTextListener):
    """Handles timeout field changes."""

    def __init__(self, factory):
        self.factory = factory

    def textChanged(self, event):
        try:
            globalSettings = lib_settings.loadGlobalSettings()
            timeoutField   = self.factory.panelWin.getControl("TimeoutField")
            globalSettings["timeout"] = int(timeoutField.getValue())
            lib_settings.saveGlobalSettings(globalSettings)
        except Exception as e:
            print(f"Error saving timeout: {e}")

    def disposing(self, event):
        pass


class InstructionsChangeListener(unohelper.Base, XTextListener):
    """Handles custom instructions field changes."""

    def __init__(self, factory):
        self.factory = factory

    def textChanged(self, event):
        try:
            globalSettings     = lib_settings.loadGlobalSettings()
            instructionsField  = self.factory.panelWin.getControl("InstructionsField")
            globalSettings["custom_instructions"] = instructionsField.getText()
            lib_settings.saveGlobalSettings(globalSettings)
        except Exception as e:
            print(f"Error saving instructions: {e}")

    def disposing(self, event):
        pass


# ---------------------------------------------------------------------------
# Document event listeners
# ---------------------------------------------------------------------------

class SaveAsListener(unohelper.Base, XDocumentEventListener):
    """Handles Save As events for settings migration."""

    def __init__(self):
        self.oldPath = None

    def documentEventOccured(self, event):
        if event.EventName == "OnSaveAsDone":
            try:
                doc     = event.Source
                newPath = uno.fileUrlToSystemPath(doc.getURL())
                lib_settings.migrateSettingsIfNeeded(self.oldPath, newPath)
                self.oldPath = newPath
            except Exception as e:
                print(f"Error in SaveAs listener: {e}")
                import traceback
                traceback.print_exc()

    def disposing(self, event):
        pass
