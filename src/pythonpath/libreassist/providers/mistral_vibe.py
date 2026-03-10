# -*- coding: utf-8 -*-
# libreassist/providers/mistral_vibe.py - Mistral Vibe CLI provider

NAME = "mistral_vibe"
EXECUTABLE = "vibe"

_ODT_HINT = (
    "The file you are working with is an ODF document (e.g. .odt, .ods, .odp, .odg), "
    "which is a ZIP archive. "
    "To edit it, you must: (1) Extract ALL files from the ZIP archive, "
    "(2) modify only content.xml using proper ODF namespace elements "
    "(e.g. text:p, text:span, text:h) without breaking the structure, "
    "(3) repack ALL original files back into a valid ZIP archive, preserving "
    "the exact internal paths (files must be at the root, not in a subfolder). "
    "The mimetype file must be the first entry and stored uncompressed. "
    "Always overwrite the original file in place. Do not create a new or modified copy. "
    "IMPORTANT: Only edit the document for content creation or editing tasks. "
    "For pure information questions (e.g. 'what day is it?', 'are you Mistral?'), "
    "respond with plain text only and do NOT modify the file."
)


def buildArgs(prompt, sessionId=None, executable=EXECUTABLE):
    fullPrompt = f"{_ODT_HINT}\n\nUser request: {prompt}"
    args = [
        executable,
        "--auto-approve",
        "--output", "json",
    ]

    if sessionId:
        args.extend(["--resume", sessionId])

    args.extend(["-p", fullPrompt])
    return args


def extractResponse(rawOutput, stderr=""):
    import json

    try:
        jsonResponse = json.loads(rawOutput)

        # Vibe returns an array of messages
        if isinstance(jsonResponse, list):
            assistantMessages = [m for m in jsonResponse if m.get("role") == "assistant"]
            if assistantMessages:
                lastAssistant = assistantMessages[-1]
                return {
                    "response": lastAssistant.get("content", "").strip(),
                    "sessionId": None
                }

        # Fallback for other formats
        response = jsonResponse.get("result") or jsonResponse.get("content") or ""
        return {
            "response": response.strip(),
            "sessionId": jsonResponse.get("session_id")
        }

    except (json.JSONDecodeError, AttributeError):
        # Last resort: return raw output stripped of ANSI codes
        import re
        ansiEscape = re.compile(r'\x1b\[[0-9;]*m')
        return {
            "response": ansiEscape.sub('', rawOutput).strip(),
            "sessionId": None
        }

def postProcess(filePath):
    import zipfile, os, shutil

    tempPath = filePath + ".tmp"

    try:
        with zipfile.ZipFile(filePath, 'r') as zin:
            entries = zin.infolist()
            names = [e.filename for e in entries]

            # Detect prefix: entries that have a subdirectory AND a root-level duplicate
            prefix = ""
            for name in names:
                if '/' in name:
                    candidate = name.split('/')[0] + '/'
                    stripped = name[len(candidate):]
                    if stripped and stripped in names:
                        prefix = candidate
                        break

            # Build final file set: prefer prefixed versions if prefix found
            finalEntries = {}
            for entry in entries:
                if prefix and entry.filename.startswith(prefix):
                    # Use stripped name as key (overrides root-level version)
                    key = entry.filename[len(prefix):]
                    if key and not key.endswith('/'):
                        finalEntries[key] = entry
                elif not prefix:
                    name = entry.filename
                    if name and not name.endswith('/'):
                        finalEntries[name] = entry
                else:
                    # Root-level entry: only add if not already covered by prefix version
                    name = entry.filename
                    if name and not name.endswith('/') and name not in finalEntries:
                        finalEntries[name] = entry

            with zipfile.ZipFile(tempPath, 'w') as zout:
                # mimetype first, uncompressed
                if "mimetype" in finalEntries:
                    data = zin.read(finalEntries["mimetype"].filename)
                    zout.writestr(zipfile.ZipInfo("mimetype"), data,
                                  compress_type=zipfile.ZIP_STORED)

                for key, entry in finalEntries.items():
                    if key == "mimetype":
                        continue
                    data = zin.read(entry.filename)
                    zout.writestr(key, data, compress_type=zipfile.ZIP_DEFLATED)

        shutil.move(tempPath, filePath)

    except Exception as e:
        print(f"postProcess failed: {e}")
        if os.path.exists(tempPath):
            os.remove(tempPath)
