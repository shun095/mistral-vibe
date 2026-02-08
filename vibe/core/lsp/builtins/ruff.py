from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from vibe.core.lsp.installers.ruff import RuffLSPInstaller
from vibe.core.lsp.project_root import ProjectRootFinder
from vibe.core.lsp.server import LSPServer

logger = logging.getLogger(__name__)


class RuffLSP(LSPServer):
    name = "ruff"
    command = ["ruff", "server"]

    async def get_command(self) -> list[str]:
        # Get command for Ruff LSP server
        installer = RuffLSPInstaller()

        # Check if ruff is installed
        exec_path = installer.get_executable_path()
        if exec_path and exec_path.exists():
            # Use the found ruff executable
            return [str(exec_path), "server"]

        # Auto-install ruff if not found
        logger.info("Ruff not found. Attempting to install...")
        if await installer.install():
            exec_path = installer.get_executable_path()
            if exec_path and exec_path.exists():
                return [str(exec_path), "server"]

        # If we still can't find it, raise an error
        raise RuntimeError(
            "ruff server not found. "
            "Please ensure ruff is installed (pip install ruff)."
        )

    def _find_python_project_root(self) -> str:
        # Find Python project root by walking up from current directory
        # FIXME: root_mark should be configurable by config file.
        root_markers = [
            "pyproject.toml",
            "ruff.toml",
            "setup.py",
            "setup.cfg",
            "requirements.txt",
            "Pipfile",
            ".git",
        ]
        return ProjectRootFinder.find_project_root(root_markers)

    def get_initialization_params(self) -> dict[str, Any]:
        # Get initialization params for Ruff LSP server
        params: dict[str, Any] = {}

        # Find Python project root
        root_uri = self._find_python_project_root()
        params["rootUri"] = root_uri

        # Include workspaceFolders with the detected project root
        workspace_folder = {
            "uri": root_uri,
            "name": Path(root_uri[7:]).name  # Remove 'file://' prefix and get folder name
        }
        params["workspaceFolders"] = [workspace_folder]

        # Minimal settings for Ruff diagnostics and formatting
        # Ruff will automatically detect pyproject.toml or ruff.toml
        params["settings"] = {
            "ruff": {}
        }

        return params