from __future__ import annotations

from pathlib import Path
from typing import Any, Type

from vibe.core.lsp.types import LSPServerHandle

class LSPServer:
    name: str
    command: list[str]

    async def get_command(self) -> list[str]:
        return self.command

    def get_initialization_params(self) -> dict[str, Any]:
        return {}

class LSPServerRegistry:
    _servers: dict[str, Type[LSPServer]] = {}

    @classmethod
    def register(cls, server: Type[LSPServer]) -> None:
        cls._servers[server.name] = server

    @classmethod
    def get_server(cls, name: str) -> Type[LSPServer] | None:
        return cls._servers.get(name)

    @classmethod
    def detect_server_for_file(cls, file_path: Path) -> str | None:
        """Detect the appropriate LSP server based on file extension.
        
        For Python files (.py, .pyi), this returns 'pyright' by default for backward compatibility.
        Use get_servers_for_file() to get all available servers for a file extension.
        """
        extension = file_path.suffix.lower()

        # Mapping of file extensions to default LSP servers
        extension_map = {
            ".py": "pyright",
            ".pyi": "pyright",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "typescript",
            ".jsx": "typescript",
        }

        return extension_map.get(extension)

    @classmethod
    def get_servers_for_file(cls, file_path: Path) -> list[str]:
        """Get all available LSP servers that can handle the given file extension.
        
        This method returns all registered servers that support the file's extension,
        allowing for multiple servers (e.g., both pyright and ruff for Python files).
        
        Args:
            file_path: Path to the file to analyze
            
        Returns:
            List of server names that can handle the file, in order of preference
        """
        extension = file_path.suffix.lower()

        # Mapping of file extensions to all available LSP servers
        extension_servers = {
            ".py": ["pyright", "ruff"],
            ".pyi": ["pyright", "ruff"],
            ".ts": ["typescript"],
            ".tsx": ["typescript"],
            ".js": ["typescript"],
            ".jsx": ["typescript"],
        }

        return extension_servers.get(extension, [])
