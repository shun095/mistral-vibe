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

    # FIXME: should be able to handle multiple servers with same extention considering ruff + pyright.
    @classmethod
    def detect_server_for_file(cls, file_path: Path) -> str | None:
        """Detect the appropriate LSP server based on file extension."""
        extension = file_path.suffix.lower()

        # Mapping of file extensions to LSP servers
        extension_map = {
            ".py": "pyright",
            ".pyi": "pyright",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "typescript",
            ".jsx": "typescript",
        }

        return extension_map.get(extension)
