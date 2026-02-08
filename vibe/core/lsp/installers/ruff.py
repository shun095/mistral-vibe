from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path

from vibe.core.lsp.installer import LSPServerInstaller
from vibe.core.paths.global_paths import VIBE_HOME

logger = logging.getLogger(__name__)


class RuffLSPInstaller(LSPServerInstaller):
    """Installer for Ruff LSP server."""

    def __init__(self) -> None:
        super().__init__("ruff")

    async def install(self) -> bool:
        install_dir = self.install_dir
        venv_dir = install_dir / ".venv"
        venv_dir.mkdir(parents=True, exist_ok=True)

        # Check if python is available
        result = subprocess.run(
            ["python3", "--version"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error("python3 is not available. Please install Python 3 first.")
            return False

        # Create virtual environment if it doesn't exist
        if not (venv_dir / "bin" / "python").exists() and not (venv_dir / "Scripts" / "python.exe").exists():
            logger.info(f"Creating virtual environment in {venv_dir}...")
            proc = await asyncio.create_subprocess_exec(
                "python3",
                "-m",
                "venv",
                str(venv_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.error(f"Failed to create virtual environment: {stderr.decode()}")
                return False

        # Determine the pip executable path
        pip_exe = venv_dir / "bin" / "pip"
        if not pip_exe.exists():
            pip_exe = venv_dir / "Scripts" / "pip.exe"
        
        if not pip_exe.exists():
            logger.error(f"pip not found in virtual environment: {pip_exe}")
            return False

        logger.info(f"Installing ruff in virtual environment {venv_dir}...")
        proc = await asyncio.create_subprocess_exec(
            str(pip_exe),
            "install",
            "ruff",
            cwd=venv_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.error(f"Failed to install ruff: {stderr.decode()}")
            return False

        logger.info("ruff installed successfully")
        return True

    def is_installed(self) -> bool:
        # Check if installed in ~/.vibe/lsp/ruff/.venv or in PATH
        exec_path = self.get_executable_path()
        return exec_path is not None and exec_path.exists()

    def get_executable_path(self) -> Path | None:
        # First check if ruff is available in PATH
        try:
            result = subprocess.run(
                ["which", "ruff"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                return Path(result.stdout.strip())
        except FileNotFoundError:
            pass

        # Check if installed in our virtual environment
        venv_dir = self.install_dir / ".venv"
        
        # Check for Linux/macOS
        ruff_exe = venv_dir / "bin" / "ruff"
        if ruff_exe.exists():
            return ruff_exe

        # Check for Windows
        ruff_exe_win = venv_dir / "Scripts" / "ruff.exe"
        if ruff_exe_win.exists():
            return ruff_exe_win

        return None