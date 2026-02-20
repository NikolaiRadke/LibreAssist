# -*- coding: utf-8 -*-
# libreassist/provider_base.py - Generic subprocess handler for all CLI providers
# Equivalent to processProvider.js in AI.duino

import subprocess
import os


def _resolveExecutable(providerModule):
    """
    Resolve the full path to a provider's executable.
    Uses auto-discovery, falls back to module's EXECUTABLE.

    Args:
        providerModule: Imported provider module

    Returns:
        Executable path string
    """
    try:
        from libreassist import discovery
        path = discovery.discoverProvider(providerModule.NAME)
        if path:
            return path
    except Exception as e:
        print(f"Discovery failed for {providerModule.NAME}: {e}")

    # Fallback: use bare executable name (works if it's in PATH)
    return providerModule.EXECUTABLE


def executeProvider(providerModule, prompt, workingDir, sessionId=None, timeout=600):
    """
    Generic executor for any CLI provider.
    Uses buildArgs() and extractResponse() from the provider module.
    Auto-discovers the executable path.

    Args:
        providerModule: Imported provider module (e.g. claude_code)
        prompt:         User prompt string
        workingDir:     Working directory for the subprocess (document directory)
        sessionId:      Optional session ID for persistent providers
        timeout:        Timeout in seconds (default: 600)

    Returns:
        dict with 'response' (str) and 'sessionId' (str or None)
    """
    executablePath = _resolveExecutable(providerModule)
    
    if hasattr(providerModule, 'NEEDS_NODEJS') and providerModule.NEEDS_NODEJS:
        from libreassist import discovery
        nodePath = discovery.findNodeJS()
        
        if not nodePath:
            raise RuntimeError("Node.js v20+ not found. Codex CLI requires Node.js.")
        
        # Build args without executable, then prepend executable
        args = providerModule.buildArgs(prompt, sessionId, None)
        args = [executablePath] + args
        executable = nodePath

    else:
        args = providerModule.buildArgs(prompt, sessionId, executablePath)
        executable = executablePath

    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,  # Binary read for UTF-8 safety
        cwd=workingDir
    )
    
    # Wait with timeout and read completely
    try:
        stdout_bytes, stderr_bytes = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout_bytes, stderr_bytes = process.communicate()
        raise TimeoutError(f"Provider timed out after {timeout}s")
    
    returncode = process.returncode
    
    # Manually decode with error handling
    try:
        rawOutput = stdout_bytes.decode('utf-8')
    except UnicodeDecodeError:
        rawOutput = stdout_bytes.decode('utf-8', errors='replace')
    
    try:
        stderr = stderr_bytes.decode('utf-8')
    except UnicodeDecodeError:
        stderr = stderr_bytes.decode('utf-8', errors='replace')

    # If we got output, try to extract response even if returncode != 0
    if rawOutput.strip():
        return providerModule.extractResponse(rawOutput, stderr)

    # Only error if no output at all
    if returncode != 0:
        raise RuntimeError(stderr.strip() or f"Provider exited with code {returncode}")

    return providerModule.extractResponse(rawOutput, stderr)# -*- coding: utf-8 -*-
# libreassist/provider_base.py - Generic subprocess handler for all CLI providers
# Equivalent to processProvider.js in AI.duino

import subprocess
import os


def _resolveExecutable(providerModule):
    """
    Resolve the full path to a provider's executable.
    Uses auto-discovery, falls back to module's EXECUTABLE.

    Args:
        providerModule: Imported provider module

    Returns:
        Executable path string
    """
    try:
        from libreassist import discovery
        path = discovery.discoverProvider(providerModule.NAME)
        if path:
            return path
    except Exception as e:
        print(f"Discovery failed for {providerModule.NAME}: {e}")

    # Fallback: use bare executable name (works if it's in PATH)
    return providerModule.EXECUTABLE


def executeProvider(providerModule, prompt, workingDir, sessionId=None, timeout=600):
    """
    Generic executor for any CLI provider.
    Uses buildArgs() and extractResponse() from the provider module.
    Auto-discovers the executable path.

    Args:
        providerModule: Imported provider module (e.g. claude_code)
        prompt:         User prompt string
        workingDir:     Working directory for the subprocess (document directory)
        sessionId:      Optional session ID for persistent providers
        timeout:        Timeout in seconds (default: 600)

    Returns:
        dict with 'response' (str) and 'sessionId' (str or None)
    """
    executablePath = _resolveExecutable(providerModule)
    
    if hasattr(providerModule, 'NEEDS_NODEJS') and providerModule.NEEDS_NODEJS:
        from libreassist import discovery
        nodePath = discovery.findNodeJS()
        
        if not nodePath:
            raise RuntimeError("Node.js v20+ not found. Codex CLI requires Node.js.")
        
        # Build args without executable, then prepend executable
        args = providerModule.buildArgs(prompt, sessionId, None)
        args = [executablePath] + args
        executable = nodePath

    else:
        args = providerModule.buildArgs(prompt, sessionId, executablePath)
        executable = executablePath

    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,  # Binary read for UTF-8 safety
        cwd=workingDir
    )
    
    # Wait with timeout and read completely
    try:
        stdout_bytes, stderr_bytes = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout_bytes, stderr_bytes = process.communicate()
        raise TimeoutError(f"Provider timed out after {timeout}s")
    
    returncode = process.returncode
    
    # Manually decode with error handling
    try:
        rawOutput = stdout_bytes.decode('utf-8')
    except UnicodeDecodeError:
        rawOutput = stdout_bytes.decode('utf-8', errors='replace')
    
    try:
        stderr = stderr_bytes.decode('utf-8')
    except UnicodeDecodeError:
        stderr = stderr_bytes.decode('utf-8', errors='replace')

    # If we got output, try to extract response even if returncode != 0
    if rawOutput.strip():
        return providerModule.extractResponse(rawOutput, stderr)

    # Only error if no output at all
    if returncode != 0:
        raise RuntimeError(stderr.strip() or f"Provider exited with code {returncode}")

    return providerModule.extractResponse(rawOutput, stderr)
