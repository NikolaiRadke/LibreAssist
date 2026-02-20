# -*- coding: utf-8 -*-
# libreassist/ui/factory.py - UI Factory for creating panels

import uno
import unohelper

from com.sun.star.ui import XUIElementFactory
from libreassist import core, settings as lib_settings, i18n, document
from .ui import LibreAssistPanel, getLocalizedString
from .events import ActionEventHandler, ProviderChangeListener, TimeoutChangeListener, SaveAsListener


class ElementFactory(unohelper.Base, XUIElementFactory):
    """
    Factory for creating LibreAssist UI elements.
    """

    # View control groups
    _CHAT_CONTROLS = ["ChatHistory", "InputField", "SendButton", "InfoLabel"]
    _SETTINGS_CONTROLS = ["ProviderLabel", "ProviderList", "TimeoutLabel", "TimeoutField",
                          "ResetSessionButton", "ClearHistoryButton"]
    _ABOUT_CONTROLS = ["AboutLogo", "AboutText"]

    def __init__(self, ctx):
        self.ctx = uno.getComponentContext()
        self.panelWin = None
        self.currentView = "chat"
        self.providerNames = []

    def createUIElement(self, url, args):
        """Create a UI element for the sidebar."""
        try:
            xParentWindow = None
            xFrame = None

            for arg in args:
                if arg.Name == "Frame":
                    xFrame = arg.Value
                elif arg.Name == "ParentWindow":
                    xParentWindow = arg.Value

            xUIElement = LibreAssistPanel(self.ctx, xFrame, xParentWindow, url)
            xUIElement.getRealInterface()
            panelWin = xUIElement.Window
            panelWin.Visible = True

            height = self.createPanelContent(panelWin, url)
            xUIElement.height = height

            return xUIElement

        except Exception as e:
            print("Error creating UI element:", e)
            import traceback
            traceback.print_exc()

    def createPanelContent(self, panelWin, url):
        """Create the complete panel UI."""
        if url == "private:resource/toolpanel/LibreAssistFactory/LibreAssistPanel":
            ctx = uno.getComponentContext()
            self.panelWin = panelWin

            dialogModel = ctx.ServiceManager.createInstance(
                "com.sun.star.awt.UnoControlDialogModel")
            panelWin.setModel(dialogModel)
            dialogModel.Width = 150
            dialogModel.Height = 690

            # Initialize
            lib_settings.cleanupOrphanedDirs()
            discovered = core.discoverProviders()
            print(f"DEBUG: discovered = {discovered}")
            
            globalSettings = lib_settings.loadGlobalSettings()
            docSettings = lib_settings.loadSettings()
            loadedHistory = lib_settings.loadHistory()

            # Create UI components
            self._createToolbar(dialogModel, docSettings)
            self._createChatView(dialogModel, loadedHistory)
            self._createSettingsView(dialogModel, globalSettings, discovered)
            self._createAboutView(dialogModel)
            
            # Attach event listeners
            self._attachEventListeners(panelWin)
            
            # Initialize view state
            self._initializeViewState(globalSettings, docSettings)
            
            # Register document listener
            self._registerDocumentListener()

            return 690

        return 100

    def _createToolbar(self, dialogModel, docSettings):
        """Create top toolbar with Undo/Redo/Settings/About buttons."""
        
        # Undo button
        undoButtonModel = dialogModel.createInstance("com.sun.star.awt.UnoControlButtonModel")
        undoButtonModel.Name = "UndoButton"
        undoButtonModel.TabIndex = 1
        undoButtonModel.PositionX = 36
        undoButtonModel.PositionY = 10
        undoButtonModel.Width = 23
        undoButtonModel.Height = 23
        undoButtonModel.Label = getLocalizedString("undo_button", "↶")
        undoButtonModel.HelpText = getLocalizedString("undo_tooltip", "Undo")
        undoButtonModel.Enabled = docSettings.get("undo_available", False)
        dialogModel.insertByName("UndoButton", undoButtonModel)

        # Redo button
        redoButtonModel = dialogModel.createInstance("com.sun.star.awt.UnoControlButtonModel")
        redoButtonModel.Name = "RedoButton"
        redoButtonModel.TabIndex = 2
        redoButtonModel.PositionX = 62
        redoButtonModel.PositionY = 10
        redoButtonModel.Width = 23
        redoButtonModel.Height = 23
        redoButtonModel.Label = getLocalizedString("redo_button", "↷")
        redoButtonModel.HelpText = getLocalizedString("redo_tooltip", "Redo")
        redoButtonModel.Enabled = docSettings.get("redo_available", False)
        dialogModel.insertByName("RedoButton", redoButtonModel)

        # Back button
        backButtonModel = dialogModel.createInstance("com.sun.star.awt.UnoControlButtonModel")
        backButtonModel.Name = "BackButton"
        backButtonModel.TabIndex = 3
        backButtonModel.PositionX = 10
        backButtonModel.PositionY = 10
        backButtonModel.Width = 23
        backButtonModel.Height = 23
        backButtonModel.Label = "←"
        backButtonModel.HelpText = getLocalizedString("back_button", "Back to Chat")
        dialogModel.insertByName("BackButton", backButtonModel)

        # Settings button
        settingsButtonModel = dialogModel.createInstance("com.sun.star.awt.UnoControlButtonModel")
        settingsButtonModel.Name = "SettingsButton"
        settingsButtonModel.TabIndex = 4
        settingsButtonModel.PositionX = 88
        settingsButtonModel.PositionY = 10
        settingsButtonModel.Width = 23
        settingsButtonModel.Height = 23
        settingsButtonModel.Label = "⚙"
        settingsButtonModel.HelpText = getLocalizedString("settings_button", "Settings")
        dialogModel.insertByName("SettingsButton", settingsButtonModel)

        # About button
        aboutButtonModel = dialogModel.createInstance("com.sun.star.awt.UnoControlButtonModel")
        aboutButtonModel.Name = "AboutButton"
        aboutButtonModel.TabIndex = 5
        aboutButtonModel.PositionX = 114
        aboutButtonModel.PositionY = 10
        aboutButtonModel.Width = 23
        aboutButtonModel.Height = 23
        aboutButtonModel.Label = "?"
        aboutButtonModel.HelpText = getLocalizedString("about_button", "About")
        dialogModel.insertByName("AboutButton", aboutButtonModel)

    def _createChatView(self, dialogModel, loadedHistory):
        """Create chat view components."""
        
        # Chat history display
        chatHistoryModel = dialogModel.createInstance("com.sun.star.awt.UnoControlEditModel")
        chatHistoryModel.Name = "ChatHistory"
        chatHistoryModel.PositionX = 10
        chatHistoryModel.PositionY = 40
        chatHistoryModel.Width = 130
        chatHistoryModel.Height = 200
        chatHistoryModel.MultiLine = True
        chatHistoryModel.ReadOnly = True
        chatHistoryModel.VerticalAlign = "TOP"
        chatHistoryModel.AutoVScroll = True
        chatHistoryModel.Text = loadedHistory
        dialogModel.insertByName("ChatHistory", chatHistoryModel)

        # Input field
        inputModel = dialogModel.createInstance("com.sun.star.awt.UnoControlEditModel")
        inputModel.Name = "InputField"
        inputModel.PositionX = 10
        inputModel.PositionY = 248
        inputModel.Width = 130
        inputModel.Height = 100
        inputModel.MultiLine = True
        inputModel.VerticalAlign = "TOP"
        inputModel.AutoVScroll = True
        dialogModel.insertByName("InputField", inputModel)

        # Send button
        sendButtonModel = dialogModel.createInstance("com.sun.star.awt.UnoControlButtonModel")
        sendButtonModel.Name = "SendButton"
        sendButtonModel.TabIndex = 5
        sendButtonModel.PositionX = 10
        sendButtonModel.PositionY = 355
        sendButtonModel.Width = 130
        sendButtonModel.Height = 23
        sendButtonModel.Label = "Send"
        dialogModel.insertByName("SendButton", sendButtonModel)

        # Info label
        infoLabelModel = dialogModel.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        infoLabelModel.Name = "InfoLabel"
        infoLabelModel.PositionX = 10
        infoLabelModel.PositionY = 385
        infoLabelModel.Width = 130
        infoLabelModel.Height = 30
        infoLabelModel.Label = getLocalizedString("processing_info", "Processing may take some minutes")
        infoLabelModel.Align = 0
        infoLabelModel.MultiLine = True
        dialogModel.insertByName("InfoLabel", infoLabelModel)

    def _createSettingsView(self, dialogModel, globalSettings, discovered):
        """Create settings view components."""
        
        # Provider label
        providerLabelModel = dialogModel.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        providerLabelModel.Name = "ProviderLabel"
        providerLabelModel.PositionX = 10
        providerLabelModel.PositionY = 40
        providerLabelModel.Width = 130
        providerLabelModel.Height = 15
        providerLabelModel.Label = getLocalizedString("settings_provider", "Provider")
        dialogModel.insertByName("ProviderLabel", providerLabelModel)

        # Provider dropdown
        providerListModel = dialogModel.createInstance("com.sun.star.awt.UnoControlListBoxModel")
        providerListModel.Name = "ProviderList"
        providerListModel.PositionX = 10
        providerListModel.PositionY = 57
        providerListModel.Width = 130
        providerListModel.Height = 25
        providerListModel.Dropdown = True
        providerNames = list(discovered.keys()) or ["claude_code"]
        providerListModel.StringItemList = tuple(providerNames)
        self.providerNames = providerNames
        dialogModel.insertByName("ProviderList", providerListModel)

        # Timeout label
        timeoutLabelModel = dialogModel.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        timeoutLabelModel.Name = "TimeoutLabel"
        timeoutLabelModel.PositionX = 10
        timeoutLabelModel.PositionY = 92
        timeoutLabelModel.Width = 130
        timeoutLabelModel.Height = 15
        timeoutLabelModel.Label = getLocalizedString("settings_timeout", "Timeout (seconds)")
        dialogModel.insertByName("TimeoutLabel", timeoutLabelModel)

        # Timeout field
        timeoutFieldModel = dialogModel.createInstance("com.sun.star.awt.UnoControlNumericFieldModel")
        timeoutFieldModel.Name = "TimeoutField"
        timeoutFieldModel.PositionX = 10
        timeoutFieldModel.PositionY = 109
        timeoutFieldModel.Width = 130
        timeoutFieldModel.Height = 20
        timeoutFieldModel.Value = globalSettings.get("timeout", 600)
        timeoutFieldModel.ValueMin = 60
        timeoutFieldModel.ValueMax = 3600
        timeoutFieldModel.DecimalAccuracy = 0
        dialogModel.insertByName("TimeoutField", timeoutFieldModel)

        # Reset session button
        resetSessionModel = dialogModel.createInstance("com.sun.star.awt.UnoControlButtonModel")
        resetSessionModel.Name = "ResetSessionButton"
        resetSessionModel.TabIndex = 6
        resetSessionModel.PositionX = 10
        resetSessionModel.PositionY = 140
        resetSessionModel.Width = 130
        resetSessionModel.Height = 23
        resetSessionModel.Label = getLocalizedString("settings_reset_session", "Reset Session")
        dialogModel.insertByName("ResetSessionButton", resetSessionModel)

        # Clear history button
        clearHistoryModel = dialogModel.createInstance("com.sun.star.awt.UnoControlButtonModel")
        clearHistoryModel.Name = "ClearHistoryButton"
        clearHistoryModel.TabIndex = 7
        clearHistoryModel.PositionX = 10
        clearHistoryModel.PositionY = 170
        clearHistoryModel.Width = 130
        clearHistoryModel.Height = 23
        clearHistoryModel.Label = getLocalizedString("settings_clear_history", "Clear History")
        dialogModel.insertByName("ClearHistoryButton", clearHistoryModel)

    def _createAboutView(self, dialogModel):
        """Create about view components."""
    
        # Logo image
        logoModel = dialogModel.createInstance("com.sun.star.awt.UnoControlImageControlModel")
        logoModel.Name = "AboutLogo"
        logoModel.PositionX = 51  # Centered (150 - 48) / 2
        logoModel.PositionY = 50
        logoModel.Width = 48
        logoModel.Height = 48
        logoModel.ScaleImage = True
        logoModel.ImageURL = "vnd.sun.star.extension://org.libreoffice.libreassist/icons/logo-48.png"
        dialogModel.insertByName("AboutLogo", logoModel)
    
        # About text (moved down to make room for logo)
        aboutTextModel = dialogModel.createInstance("com.sun.star.awt.UnoControlEditModel")
        aboutTextModel.Name = "AboutText"
        aboutTextModel.PositionX = 10
        aboutTextModel.PositionY = 110  # 50 + 48 + 12 spacing
        aboutTextModel.Width = 130
        aboutTextModel.Height = 240  # Reduced from 300
        aboutTextModel.MultiLine = True
        aboutTextModel.ReadOnly = True
        aboutTextModel.VerticalAlign = "TOP"
        aboutTextModel.Text = getLocalizedString("about_text", "LibreAssist").format(
            version=i18n.getVersion())
        dialogModel.insertByName("AboutText", aboutTextModel)

    def _attachEventListeners(self, panelWin):
        """Attach all event listeners to UI controls."""
        
        # Create event handler instance
        eventHandler = ActionEventHandler(self)
        
        # Button events
        for buttonName in ["SendButton", "UndoButton", "RedoButton", "SettingsButton", 
                          "AboutButton", "BackButton", "ResetSessionButton", "ClearHistoryButton"]:
            panelWin.getControl(buttonName).addActionListener(eventHandler)
            panelWin.getControl(buttonName).setActionCommand(f"{buttonName.replace('Button', '')}_OnClick")

        # Provider change listener
        panelWin.getControl("ProviderList").addItemListener(ProviderChangeListener(self))

        # Timeout change listener
        panelWin.getControl("TimeoutField").addTextListener(TimeoutChangeListener(self))

    def _initializeViewState(self, globalSettings, docSettings):
        """Initialize UI view state and control visibility."""
        
        # Hide settings and about controls initially
        for name in self._SETTINGS_CONTROLS + self._ABOUT_CONTROLS:
            self.panelWin.getControl(name).setVisible(False)

        # Set initial provider selection
        currentProvider = globalSettings.get("default_provider", "claude_code")
        if currentProvider in self.providerNames:
            providerList = self.panelWin.getControl("ProviderList")
            providerList.selectItemPos(self.providerNames.index(currentProvider), True)
        
        # Hide back button initially
        self.panelWin.getControl("BackButton").setVisible(False)

    def _registerDocumentListener(self):
        """Register listener for document Save As events."""
        
        doc = document.getCurrentDocument()
        if doc:
            listener = SaveAsListener()
            directory, filename, fullPath = document.getDocumentPath()
            listener.oldPath = fullPath
            doc.addDocumentEventListener(listener)

    def showView(self, view):
        """
        Switch between chat, settings, and about views.
        
        Args:
            view: View name ('chat', 'settings', or 'about')
        """
        for name in self._CHAT_CONTROLS:
            self.panelWin.getControl(name).setVisible(view == "chat")
        for name in self._SETTINGS_CONTROLS:
            self.panelWin.getControl(name).setVisible(view == "settings")
        for name in self._ABOUT_CONTROLS:
            self.panelWin.getControl(name).setVisible(view == "about")
        
        # Back button visible in Settings/About, hidden in Chat
        self.panelWin.getControl("BackButton").setVisible(view != "chat")
        
        self.currentView = view
