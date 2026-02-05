from __future__ import annotations

import asyncio
import logging
import os
import platform
import subprocess
from pathlib import Path
from typing import Any

from vibe.core.lsp.installers.pyright import PyrightInstaller
from vibe.core.lsp.installer import get_python_path
from vibe.core.lsp.server import LSPServer

logger = logging.getLogger(__name__)


class PyrightLSP(LSPServer):
    name = "pyright"
    command = ["pyright-langserver", "--stdio"]

    async def get_command(self) -> list[str]:
        # Get command for Pyright LSP server
        installer = PyrightInstaller()

        # Check if pyright-langserver is available in PATH
        try:
            result = subprocess.run(
                ["which", "pyright-langserver"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return ["pyright-langserver", "--stdio"]
        except FileNotFoundError:
            pass

        # Check if pyright is installed
        exec_path = installer.get_executable_path()
        if exec_path and exec_path.exists():
            if exec_path.suffix == ".js":
                # Use node to run the JS file
                return ["node", str(exec_path), "--stdio"]
            else:
                # Direct executable
                return [str(exec_path), "--stdio"]

        # Auto-install pyright if not found
        logger.info("Pyright not found. Attempting to install...")
        if await installer.install():
            exec_path = installer.get_executable_path()
            if exec_path and exec_path.exists():
                if exec_path.suffix == ".js":
                    return ["node", str(exec_path), "--stdio"]
                else:
                    return [str(exec_path), "--stdio"]

        # If we still can't find it, raise an error
        raise RuntimeError(
            "pyright-langserver not found. "
            "Please install it with: npm install -g pyright "
            "or ensure it's in your PATH."
        )

    def _find_python_project_root(self) -> str:
        # Find Python project root by walking up from current directory
        current_dir = Path.cwd()
        # FIXME: root_mark should be configuarable by config file.
        root_markers = ['pyrightconfig.json', 'pyproject.toml', 'setup.py', 'setup.cfg', 'requirements.txt', 'Pipfile', '.git']

        # Walk up the directory tree looking for root markers
        check_dir = current_dir
        max_depth = 100
        depth = 0

        while depth <= max_depth:
            # Check if current directory contains any root marker
            for marker in root_markers:
                marker_path = check_dir / marker
                try:
                    if marker_path.exists():
                        # Found a project root, return its URI
                        return str(check_dir.resolve().as_uri())
                except (OSError, PermissionError):
                    continue

            # Move up to parent directory
            try:
                parent = check_dir.parent
                if str(parent) == str(check_dir):
                    # Reached root
                    break
                check_dir = parent
                depth += 1
            except (ValueError, RuntimeError):
                break

        # No project root found, use current directory
        return str(current_dir.resolve().as_uri())

    def get_initialization_params(self) -> dict[str, Any]:
        # Get initialization params for Pyright LSP server
        params: dict[str, Any] = {}

        # Find Python project root and use workspaceFolders (preferred over rootUri)
        root_uri = self._find_python_project_root()
        params["workspaceFolders"] = [
            {
                "uri": root_uri,
                "name": Path(root_uri).name
            }
        ]
        # Also include rootUri for backward compatibility
        params["rootUri"] = root_uri

        # Find Python path for pyright configuration
        python_path = get_python_path()
        if python_path:
            params["pythonPath"] = python_path

        # Set pyright-specific settings
        params["settings"] = {
            "python": {
                "analysis": {
                    "autoSearchPaths": True,
                    "diagnosticMode": "openFilesOnly",
                    "useLibraryCodeForTypes": True
                }
            }
        }

        return params


