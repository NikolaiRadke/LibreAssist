![LIbreAssist](https://www.nikolairadke.de/aiduino/libreassist_banner2.png) 
# LibreAssist

**AI-powered Agentic Writing Assistant for LibreOffice**

LibreAssist is a LibreOffice extension that brings AI-powered writing assistance directly into your documents. Unlike traditional copy-paste solutions, LibreAssist provides true **Agentic Writing** - AI tools that can directly manipulate your documents through command-line interfaces, even design.

**LibreOffice Extensions page**: https://extensions.libreoffice.org/en/extensions/show/99521

🆕 What's new?  
* **10.03.2026** **Release V1.0.3** with provider settings and support for Mistal Vibe.    
    -- More news? Check the [newsblog](https://github.com/NikolaiRadke/LibreAssist/blob/main/NEWS.md).

## Features

- 🤖 **Multi-Provider Support** - Works with Claude Code CLI and Codex CLI
- 💬 **Session-Based Conversations** - Maintains context across multiple interactions
- ✏️ **Direct Document Manipulation** - AI writes directly into your document, even design elements
- ↩️ **Undo/Redo System** - Full backup and restore capabilities for AI changes
- 💾 **Persistent Chat History** - Conversations are saved per document
- 🌍 **Multilingual** - en, de, fr, it and es localization included, more will follow
- 🔄 **Provider Switching** - Easy switching between different AI providers
- ⚙️ **Configurable Timeouts** - Adjust processing timeouts as needed

## Screenshot

![LibreAssist Screenshot](https://www.nikolairadke.de/aiduino/libreassist_screenshot.png)
![LibreAssist Screenshot](https://www.nikolairadke.de/aiduino/libreassist_screenshot2.png)

## Supported Providers

### ✅ Working Providers

- **Claude Code CLI** - Anthropic's Claude via command-line interface
  - Install: `npm install -g @anthropic-ai/claude-code`
  - Supports LibreOffice files natively

- **Codex CLI** - OpenAI's GPT models via command-line interface
  - Install: Follow instructions at [github.com/microsoft/codex-cli](https://github.com/microsoft/codex-cli)
  - Requires Node.js v20+
  - Supports LibreOffice files natively

- **Mistral Vibe CLI** - Mistral AI models via command-line interface
  - Install: `pip install mistral-vibe`
  - ⚠️ Experimental: Mistral Vibe does not natively support LibreOffice files.
    LibreAssist works around this via automatic ODT post-processing, which may not always produce correct results.
    
### ❌ Tested But Not Compatible

The following providers were tested but **cannot edit LibreOffice .odt files**:

- **Gemini CLI** - Google's Gemini models
- **Groq Code** - Groq's LPU-accelerated models  

These providers work for chat-only interactions but lack the ability to manipulate LibreOffice document formats. 
For use with API Providers, there are many ohter extensions, like [LibreThinker](https://github.com/mihailthebuilder/librethinker-extension).  

## Requirements

- **LibreOffice**
- **Python** 3.8+ (embedded in LibreOffice)
- **At least one supported CLI provider** (Claude Code or Codex CLI)
- **Node.js v20+** (required for Codex CLI only)

## Installation

1. **Download** the latest `LibreAssist.oxt` from the [Releases](https://github.com/NikolaiRadke/LibreAssist/releases) page

2. **Install a CLI Provider:**
   ```bash
   # For Claude Code:
   npm install -g @anthropic-ai/claude-code
   
   # For Codex CLI:
   # Follow instructions at https://github.com/microsoft/codex-cli

   # For Mistral Vibe (experimental):
   pip install mistral-vibe
   ```

3. **Install the Extension:**
   - Open LibreOffice
   - Go to `Tools` → `Extension Manager`
   - Click `Add`
   - Select the downloaded `LibreAssist.oxt` file
   - Click `Accept` to install
   - Restart LibreOffice

4. **Access LibreAssist:**
   - Open or create a Writer document
   - **Save the document first** (required for AI providers to access the file)
   - Open the sidebar: `View` → `Sidebar` (or press F5)
   - Click the `LibreAssist` panel

## Usage

### Basic Workflow

1. **Save your document** - AI providers need a saved file to work with
2. **Open the LibreAssist sidebar**
3. **Type your request** in the input field
4. **Click Send** or press Enter
5. **Wait for the AI** to process (may take 1-2 minutes)
6. **Review the changes** in your document

### Provider Prefixes

You can specify which provider to use by prefixing your prompt:

```
claude Write an executive summary
codex Fix all typos in this document
mistral Change background color to blue
```

Without a prefix, the default provider (set in Settings) will be used.

### Undo/Redo

- **Undo Button** (↶) - Restores the document to the state before the last AI change
- **Redo Button** (↷) - Re-applies the AI changes after an undo

The document will automatically reload after undo/redo operations.

### Settings

Click the **⚙ Settings** button to configure:

- **Provider** - Select your default AI provider
- **Timeout** - Maximum processing time (60-3600 seconds)
- **Reset Session** - Start a new conversation (with confirmation dialog)
- **Clear History** - Delete the chat history (with confirmation dialog)
- **Custom Instructions** - Instructions included in every request
- **Open Provider Config** - Edit `providers.json` to add or customize providers
- **Delete All Data** - Remove all chat history, backups and settings

## Configuration

### Provider Discovery

LibreAssist automatically discovers installed CLI providers by searching:

- System PATH
- npm global directories
- nvm Node.js installations
- Common installation locations

## Links

- **AI.duino**: [https://github.com/NikolaiRadke/AI.duino](https://github.com/NikolaiRadke/AI.duino)

## Contributing

This is a maker project, not a professional software product. Contributions, bug reports, and feature requests are welcome through GitHub issues and pull requests.

---

**Happy Writing with AI! 🚀**

