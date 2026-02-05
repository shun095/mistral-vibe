from __future__ import annotations

from logging import getLogger
from pathlib import Path
from typing import Any

from vibe.core.lsp.installers.typescript import TypeScriptLSPInstaller
from vibe.core.lsp.project_root import ProjectRootFinder
from vibe.core.lsp.server import LSPServer

logger = getLogger("vibe")


class TypeScriptLSP(LSPServer):
    name = "typescript"
    # Base command without options
    command = ["typescript-language-server"]
    # Additional options to append to the command
    command_options = ["--stdio", "--log-level", "4"]

    async def get_command(self) -> list[str]:
        # Get command for TypeScript Language Server
        installer = TypeScriptLSPInstaller()

        # Check if typescript-language-server is installed
        exec_path = installer.get_executable_path()
        if exec_path and exec_path.exists():
            if exec_path.suffix in [".js", ".mjs"]:
                # Use node to run the JS/MJS file
                return ["node", str(exec_path)] + self.command_options
            else:
                # Direct executable
                return [str(exec_path)] + self.command_options

        # Auto-install typescript-language-server if not found
        logger.info("TypeScript Language Server not found. Attempting to install...")
        if await installer.install():
            exec_path = installer.get_executable_path()
            if exec_path and exec_path.exists():
                if exec_path.suffix in [".js", ".mjs"]:
                    return ["node", str(exec_path)] + self.command_options
                else:
                    return [str(exec_path)] + self.command_options

        # If we still can't find it, raise an error
        raise RuntimeError(
            "typescript-language-server not found. "
            "Please ensure it's installed in ~/.vibe/lsp/typescript."
        )

    def _find_typescript_project_root(self) -> str:
        # Find TypeScript/JavaScript project root by walking up from current directory
        # FIXME: root_mark should be configurable by config file.
        root_markers = [
            "tsconfig.json",
            "jsconfig.json",
            "package.json",
            ".git",
            "node_modules",
        ]
        return ProjectRootFinder.find_project_root(root_markers)

    def get_initialization_params(self) -> dict[str, Any]:
        # Get minimal initialization params for TypeScript Language Server
        params: dict[str, Any] = {}

        # Find TypeScript/JavaScript project root
        root_uri = self._find_typescript_project_root()
        params["rootUri"] = root_uri
        
        # Include workspaceFolders with the detected project root
        workspace_folder = {
            "uri": root_uri,
            "name": Path(root_uri[7:]).name  # Remove 'file://' prefix and get folder name
        }
        params["workspaceFolders"] = [workspace_folder]
        
        # Minimal settings for TypeScript/JavaScript diagnostics
        params["settings"] = {
            "typescript": {},
            "javascript": {}
        }

        return params
