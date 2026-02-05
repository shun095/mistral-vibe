from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from vibe.core.paths.global_paths import VIBE_HOME


class LSPServerInstaller(ABC):
    def __init__(self, server_name: str) -> None:
        self.server_name = server_name
        # FIXME: must be defined in global_paths.
        self.install_dir = VIBE_HOME.path / "lsp" / server_name

    @abstractmethod
    async def install(self) -> bool:
        pass

    @abstractmethod
    def is_installed(self) -> bool:
        pass

    @abstractmethod
    def get_executable_path(self) -> Path | None:
        pass
