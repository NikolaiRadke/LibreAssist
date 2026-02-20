# -*- coding: utf-8 -*-
# libreassist/discovery.py - Automatic provider discovery
# Ported from providerDiscovery.js in AI.duino

import os
import sys
import shutil


def findExecutable(name):
    """
    Find an executable in system PATH or common installation locations.

    Args:
        name: Executable name (e.g. 'claude', 'codex', 'gemini')

    Returns:
        Full path string or None if not found
    """
    # 1. Try system PATH first (covers most standard installations)
    found = shutil.which(name)
    if found and os.path.exists(found):
        return found

    # 2. Check common installation locations
    for candidate in _getCommonInstallPaths(name):
        if os.path.exists(candidate):
            return candidate

    return None


def _getCommonInstallPaths(name):
    """
    Return list of common installation paths for a given executable name.
    Covers Linux, macOS and Windows.
    """
    homeDir = os.path.expanduser("~")
    isWindows = sys.platform == "win32"
    paths = []

    if isWindows:
        paths += [
            os.path.join(homeDir, "AppData", "Roaming", "npm", f"{name}.cmd"),
            os.path.join(homeDir, "AppData", "Local", "Programs", name, f"{name}.exe"),
            os.path.join(homeDir, ".local", "bin", f"{name}.exe"),
        ]
        if name == "vibe":
            paths += [
                os.path.join(homeDir, "AppData", "Roaming", "uv", "tools", "mistral-vibe", "Scripts", "vibe.exe"),
                os.path.join(homeDir, "AppData", "Local",   "uv", "tools", "mistral-vibe", "Scripts", "vibe.exe"),
            ]
    else:
        paths += [
            os.path.join(homeDir, ".local", "bin", name),
            os.path.join(homeDir, f".{name}", "bin", name),
            f"/usr/local/bin/{name}",
            f"/usr/bin/{name}",
        ]
        if name == "vibe":
            paths.append(os.path.join(homeDir, ".local", "share", "uv", "tools", "mistral-vibe", "bin", name))

    # npm global locations
    for npmDir in _getNpmGlobalPaths():
        exe = f"{name}.cmd" if isWindows else name
        paths.append(os.path.join(npmDir, exe))

    # nvm locations (newest Node version first)
    for nvmDir in _getNvmNodePaths():
        exe = f"{name}.cmd" if isWindows else name
        paths.append(os.path.join(nvmDir, "bin", exe))

    return paths


def _getNpmGlobalPaths():
    """
    Return npm global bin directories.
    """
    homeDir = os.path.expanduser("~")
    isWindows = sys.platform == "win32"

    try:
        import subprocess
        prefix = subprocess.check_output(
            ["npm", "config", "get", "prefix"],
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()
        return [prefix if isWindows else os.path.join(prefix, "bin")]
    except Exception:
        if isWindows:
            return [os.path.join(homeDir, "AppData", "Roaming", "npm")]
        else:
            return [
                "/usr/local/bin",
                os.path.join(homeDir, ".npm-global", "bin"),
            ]


def _getNvmNodePaths():
    """
    Return nvm Node.js installation directories, sorted newest first.
    """
    homeDir = os.path.expanduser("~")
    paths = []

    nvmRoots = [
        os.path.join(homeDir, ".nvm", "versions", "node"),          # Unix
        os.path.join(homeDir, "AppData", "Roaming", "nvm"),         # Windows nvm-windows
    ]

    for nvmRoot in nvmRoots:
        if not os.path.isdir(nvmRoot):
            continue
        try:
            versions = [
                v for v in os.listdir(nvmRoot)
                if v.startswith("v")
            ]
            # Sort newest first by major version number
            versions.sort(key=lambda v: int(v[1:].split(".")[0]), reverse=True)
            paths += [os.path.join(nvmRoot, v) for v in versions]
        except Exception:
            pass

    return paths


def discoverProvider(providerName):
    """
    Discover a single provider by its module NAME constant.

    Args:
        providerName: Value of provider module's NAME constant
                      (e.g. 'claude_code', 'codex_cli')

    Returns:
        Full path string or None if not found
    """
    # Map provider NAME → executable name
    executableNames = {
        "claude_code": "claude",
        "codex_cli":   "codex",
        # "gemini_cli":  "gemini",  # Cannot edit .odt files
        # "mistral_vibe": "vibe",  # Cannot edit .odt files
        # "opencode":    "opencode",  # Cannot edit .odt files
        # "groq_code":   "groq",  # Cannot edit .odt files
    }

    execName = executableNames.get(providerName)
    if not execName:
        return None

    return findExecutable(execName)


def discoverAllProviders(providerNames):
    """
    Discover all providers from a list of provider NAME constants.

    Args:
        providerNames: List of provider NAME strings

    Returns:
        dict mapping providerName → full executable path
    """
    discovered = {}
    for name in providerNames:
        path = discoverProvider(name)
        if path:
            discovered[name] = path
    return discovered

def findNodeJS():
    """
    Find Node.js v20+ installation, preferring newest nvm version.
    
    Returns:
        Full path to node executable or None if not found
    """
    import subprocess
    
    # 1. Check nvm installations (newest first)
    nvmPaths = _getNvmNodePaths()
    for nvmPath in nvmPaths:
        nodeBin = os.path.join(nvmPath, "bin", "node")
        if os.path.exists(nodeBin):
            # Check version
            try:
                version = subprocess.check_output(
                    [nodeBin, "--version"],
                    stderr=subprocess.DEVNULL,
                    text=True
                ).strip()
                # Extract major version: v22.2.0 -> 22
                major = int(version.lstrip('v').split('.')[0])
                if major >= 20:
                    return nodeBin
            except Exception:
                continue
    
    # 2. Check system node
    systemNode = shutil.which("node")
    if systemNode:
        try:
            version = subprocess.check_output(
                [systemNode, "--version"],
                stderr=subprocess.DEVNULL,
                text=True
            ).strip()
            major = int(version.lstrip('v').split('.')[0])
            if major >= 20:
                return systemNode
        except Exception:
            pass
    
    return None
