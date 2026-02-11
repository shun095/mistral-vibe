from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from vibe.core.lsp.mason_paths import MasonPaths
from vibe.core.paths.global_paths import VIBE_HOME


class LSPServerInstaller(ABC):
    def __init__(self, server_name: str) -> None:
        self.server_name = server_name
        # FIXME: must be defined in global_paths.
        self.install_dir = VIBE_HOME.path / "lsp" / server_name

    def get_executable_path_from_mason(self) -> Path | None:
        """Check if the server is available in Mason packages."""
        # This will be overridden by specific installers
        return None

    def get_executable_path(self) -> Path | None:
        # First check Mason packages
        mason_path = self.get_executable_path_from_mason()
        if mason_path:
            return mason_path
        
        # Fallback to default installation
        return self._get_default_executable_path()

    @abstractmethod
    def _get_default_executable_path(self) -> Path | None:
        # Original implementation - to be overridden by specific installers
        pass

    @abstractmethod
    async def install(self) -> bool:
        pass

    @abstractmethod
    def is_installed(self) -> bool:
        pass
