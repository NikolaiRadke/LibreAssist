# -*- coding: utf-8 -*-
# libreassist/providers/claude_code.py - Claude Code CLI provider

NAME = "claude_code"
EXECUTABLE = "claude"  # Fallback if auto-discovery fails


def buildArgs(prompt, sessionId=None, executable=EXECUTABLE):
    args = [
        executable,
        "--verbose",
        "--dangerously-skip-permissions",
        "--output-format", "stream-json",
        "--include-partial-messages"
    ]
    
    if sessionId:
        args.extend(["--resume", sessionId])
    
    args.append(prompt)
    return args


def extractResponse(rawOutput, stderr=""):
    import json

    collectedText = ""
    newSessionId = None

    for line in rawOutput.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            jsonLine = json.loads(line)
            eventType = jsonLine.get("type")

            if eventType == "assistant":
                for block in jsonLine.get("message", {}).get("content", []):
                    if block.get("type") == "text":
                        collectedText += block.get("text", "")

            elif eventType == "result":
                newSessionId = jsonLine.get("session_id")

        except json.JSONDecodeError:
            pass

    return {
        "response": collectedText.strip(),
        "sessionId": newSessionId
    }
