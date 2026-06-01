from __future__ import annotations

import os
from pathlib import Path
import platform
import subprocess

from vibe.core.lsp import LSPClientManager, LSPDiagnosticFormatter


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
        result = subprocess.run(["which", "python"], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

        result = subprocess.run(["which", "python3"], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except FileNotFoundError:
        pass

    return None


async def get_lsp_diagnostics(file_path: str | Path) -> str | None:
    """Fetch and format LSP diagnostics for a file.

    Returns formatted diagnostics string if any diagnostics exist, else None.
    Silently catches all exceptions so LSP failures never break tool operations.
    """
    path = file_path if isinstance(file_path, Path) else Path(file_path)
    try:
        client_manager = LSPClientManager()
        diagnostics_list = await client_manager.get_diagnostics_from_all_servers(path)
        if diagnostics_list:
            return LSPDiagnosticFormatter.format_diagnostics_for_llm(
                diagnostics_list, path
            )
    except Exception:
        pass
    return None
