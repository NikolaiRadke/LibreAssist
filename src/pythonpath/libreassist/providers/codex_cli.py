# -*- coding: utf-8 -*-
# libreassist/providers/codex_cli.py - Codex / ChatGPT CLI provider

NAME = "codex_cli"
EXECUTABLE = "codex"  # Fallback if auto-discovery fails
NEEDS_NODEJS = True


def buildArgs(prompt, sessionId=None, executable=EXECUTABLE):
    args = []
    # Don't add executable - handled by provider_base for Node.js providers
    args.extend(["exec", "--skip-git-repo-check", "--full-auto", "--json", prompt])
    return args


def extractResponse(rawOutput, stderr=""):
    import json

    collectedText = ""

    for line in rawOutput.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            if event.get("type") == "item.completed":
                item = event.get("item", {})
                if item.get("text"):
                    collectedText += item["text"]
        except json.JSONDecodeError:
            pass

    # Fallback to raw output if no structured events found
    if not collectedText and rawOutput.strip():
        collectedText = rawOutput.strip()

    return {
        "response": collectedText.strip(),
        "sessionId": None  # Codex CLI has no persistent sessions
    }
