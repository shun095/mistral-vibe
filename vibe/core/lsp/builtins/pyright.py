from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from vibe.core.lsp.installers.pyright import PyrightInstaller
from vibe.core.lsp.project_root import ProjectRootFinder
from vibe.core.lsp.server import LSPServer
from vibe.core.lsp.utils import get_python_path

logger = logging.getLogger(__name__)


class PyrightLSP(LSPServer):
    name = "pyright"
    command = ["pyright-langserver", "--stdio"]

    async def get_command(self) -> list[str]:
        # Get command for Pyright LSP server
        installer = PyrightInstaller()

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
            "Please ensure it's installed in ~/.vibe/lsp/pyright."
        )

    def _find_python_project_root(self) -> str:
        # Find Python project root by walking up from current directory
        # FIXME: root_mark should be configuarable by config file.
        root_markers = ['pyrightconfig.json', 'pyproject.toml', 'setup.py', 'setup.cfg', 'requirements.txt', 'Pipfile', '.git']
        return ProjectRootFinder.find_project_root(root_markers)

    def get_initialization_params(self) -> dict[str, Any]:
        # Get minimal initialization params for Pyright LSP server
        params: dict[str, Any] = {}

        # Find Python project root
        root_uri = self._find_python_project_root()
        params["rootUri"] = root_uri

        return params


