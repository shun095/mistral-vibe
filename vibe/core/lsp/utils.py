from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path


def get_python_path() -> str | None:
    """Get the path to the Python executable.
    
    Checks virtual environments and system Python installations.
    Used primarily by Pyright LSP server.
    
    Returns:
        Path to Python executable as string, or None if not found.
    """
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
