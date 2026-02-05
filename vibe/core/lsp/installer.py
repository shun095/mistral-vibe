from __future__ import annotations

import os
import platform
import subprocess
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





# Utility function to get Python path (used by Pyright)
def get_python_path() -> str | None:
    potential_venv_paths = [
        os.environ.get("VIRTUAL_ENV"),
        Path.cwd() / ".venv",
        Path.cwd() / "venv",
    ]

    for venv_path in potential_venv_paths:
        if venv_path and isinstance(venv_path, str):
            venv_path = Path(venv_path)
        if venv_path and venv_path.exists():
            if platform.system() == "Windows":
                python_path = venv_path / "Scripts" / "python.exe"
            else:
                python_path = venv_path / "bin" / "python"
            if python_path.exists():
                return str(python_path)

    try:
        result = subprocess.run(
            ["which", "python"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

        result = subprocess.run(
            ["which", "python3"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except FileNotFoundError:
        pass

    return None
