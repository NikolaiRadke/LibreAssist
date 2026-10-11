# -*- coding: utf-8 -*-
# libreassist/sandbox.py - Run provider CLIs inside a bubblewrap jail
#
# The providers are started with their approval prompts disabled, so a
# prompt injection hidden in a document could otherwise run arbitrary
# commands as the user. Inside the jail the agent sees only:
#   - the system directories (/usr, /etc, ... read-only)
#   - its own installation directory (read-only)
#   - a private HOME (sandbox-home/, holds the agent's login and sessions)
#   - a private work directory containing a copy of the document
# The real home directory, /tmp, /dev/shm, /run/user and every other
# document are invisible. Network access stays on (the API needs it).
#
# Used on Linux when bubblewrap is installed and the "sandbox" setting is on;
# elsewhere the provider runs unconfined in the document directory as before.

import os
import sys
import shutil


# System paths bound read-only into the jail (skipped if missing)
_SYSTEM_RO_PATHS = ("/usr", "/etc", "/opt")

# Top-level paths that are usually symlinks into /usr on merged-usr systems
_SYSTEM_LINK_PATHS = ("/bin", "/sbin", "/lib", "/lib64", "/lib32")

# Files whose symlink targets must be reachable (DNS, TLS certificates)
_SYSTEM_LINKED_FILES = ("/etc/resolv.conf", "/etc/ssl/certs",
                        "/etc/ssl/ca-bundle.pem", "/etc/ssl/cert.pem",
                        "/etc/pki/tls/certs")

# Environment passed into the jail; everything else is dropped
_ENV_PASSTHROUGH = ("LANG", "LC_ALL", "LC_CTYPE", "TERM", "TZ",
                    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "MISTRAL_API_KEY",
                    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
                    "http_proxy", "https_proxy", "no_proxy")


class SandboxUnavailable(RuntimeError):
    """Raised when the agent cannot be isolated and therefore must not run."""


def isAvailable():
    """Return True if bubblewrap can be used on this system."""
    return sys.platform.startswith("linux") and shutil.which("bwrap") is not None


def _underHome(path):
    home = os.path.realpath(os.path.expanduser("~"))
    return path == home or path.startswith(home + os.sep)


def _installRoot(realExe):
    """
    Directory to expose for an executable that lives in the user's home.
    Uses the grandparent of the resolved file, which covers the common layouts:
      ~/.local/share/claude/versions/<ver>          -> ~/.local/share/claude
      <npm>/lib/node_modules/@openai/codex/bin/x.js -> .../@openai/codex
      ~/.local/share/uv/tools/mistral-vibe/bin/vibe -> .../tools/mistral-vibe
      ~/.nvm/versions/node/v22/bin/node             -> ~/.nvm/versions/node/v22
    """
    return os.path.dirname(os.path.dirname(realExe))


def buildCommand(args, workDir, homeDir, extraRoPaths=(), newSession=True):
    """
    Wrap a command line so it runs inside bubblewrap.

    Args:
        args:         Command line; leading absolute paths (executable, script)
                      are resolved and exposed read-only
        workDir:      Directory the agent may read and write; becomes the cwd
        homeDir:      Private HOME for the agent (persistent, writable)
        extraRoPaths: Additional paths to expose read-only (~ is expanded)
        newSession:   Detach from the controlling terminal (False for an
                      interactive login)

    Returns:
        (wrappedArgs, env) tuple for subprocess.Popen
    """
    if not isAvailable():
        raise SandboxUnavailable(
            "Sandbox unavailable: bubblewrap (bwrap) was not found.")

    workDir = os.path.realpath(workDir)
    homeDir = os.path.realpath(homeDir)
    os.makedirs(homeDir, exist_ok=True)

    bw = ["bwrap",
          "--unshare-all", "--share-net",
          "--die-with-parent",
          "--proc", "/proc",
          "--dev", "/dev",
          "--tmpfs", "/tmp",
          "--tmpfs", "/var/tmp"]
    if newSession:
        bw.append("--new-session")

    for path in _SYSTEM_RO_PATHS:
        bw += ["--ro-bind-try", path, path]
    for path in _SYSTEM_LINK_PATHS:
        if os.path.islink(path):
            bw += ["--symlink", os.readlink(path), path]
        elif os.path.isdir(path):
            bw += ["--ro-bind", path, path]
    for path in _SYSTEM_LINKED_FILES:
        real = os.path.realpath(path)
        if real != path and os.path.exists(real) and not real.startswith(("/usr/", "/etc/")):
            bw += ["--ro-bind", real, real]

    # Resolve leading absolute paths (executable, and script for node providers)
    resolved = list(args)
    roPaths  = []
    if resolved and not os.path.isabs(resolved[0]):
        found = shutil.which(resolved[0])
        if found:
            resolved[0] = found
    for i, arg in enumerate(resolved[:2]):
        if os.path.isabs(arg) and os.path.exists(arg):
            real = os.path.realpath(arg)
            resolved[i] = real
            if _underHome(real):
                roPaths.append(_installRoot(real))
    for path in extraRoPaths:
        path = os.path.realpath(os.path.expanduser(path))
        if os.path.exists(path):
            roPaths.append(path)

    bw += ["--bind", homeDir, homeDir]
    for path in roPaths:
        bw += ["--ro-bind", path, path]
    bw += ["--bind", workDir, workDir,
           "--chdir", workDir,
           "--"]

    env = {k: os.environ[k] for k in _ENV_PASSTHROUGH if k in os.environ}
    env.update({
        "HOME": homeDir,
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "TMPDIR": "/tmp",
        "DISABLE_AUTOUPDATER": "1",
    })
    if "LANG" not in env:
        env["LANG"] = "C.UTF-8"

    return bw + resolved, env


# ---------------------------------------------------------------------------
# Document staging
# ---------------------------------------------------------------------------

def stageDocument(fullPath, workDir):
    """
    Create a fresh work directory containing only a copy of the document.
    Returns: path of the copy inside workDir
    """
    if os.path.exists(workDir):
        shutil.rmtree(workDir)
    os.makedirs(workDir)
    stagedPath = os.path.join(workDir, os.path.basename(fullPath))
    shutil.copy2(fullPath, stagedPath)
    return stagedPath


def _freeName(directory, name):
    """Return a filename in directory that does not exist yet."""
    base, ext = os.path.splitext(name)
    candidate = name
    n = 1
    while os.path.exists(os.path.join(directory, candidate)):
        candidate = f"{base} ({n}){ext}"
        n += 1
    return candidate


def collectResults(fullPath, stagedPath, workDir, statBefore, newFileExts):
    """
    Copy the agent's results from the work directory back next to the document.
    Only the edited document itself and new top-level files with an extension
    in newFileExts are copied; nothing else leaves the work directory.
    Existing files are never overwritten except the document itself.

    Args:
        fullPath:    Original document path
        stagedPath:  Path of the staged copy
        workDir:     Work directory
        statBefore:  os.stat() of the staged copy before the agent ran
        newFileExts: Tuple of lowercase extensions accepted for new files

    Returns:
        List of newly created file paths next to the original document
    """
    if os.path.isfile(stagedPath) and not os.path.islink(stagedPath):
        st = os.stat(stagedPath)
        if (st.st_mtime_ns, st.st_size) != (statBefore.st_mtime_ns, statBefore.st_size):
            shutil.copyfile(stagedPath, fullPath)

    directory = os.path.dirname(fullPath)
    stagedName = os.path.basename(stagedPath)
    newFiles = []
    for name in sorted(os.listdir(workDir)):
        src = os.path.join(workDir, name)
        if name == stagedName or os.path.islink(src) or not os.path.isfile(src):
            continue
        if os.path.splitext(name)[1].lower() not in newFileExts:
            continue
        dst = os.path.join(directory, _freeName(directory, name))
        shutil.copyfile(src, dst)
        newFiles.append(dst)
    return newFiles
