from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path

from vibe.core.lsp.installer import LSPServerInstaller
from vibe.core.paths.global_paths import VIBE_HOME

logger = logging.getLogger(__name__)


class PyrightInstaller(LSPServerInstaller):
    """Installer for Pyright LSP server."""

    def __init__(self) -> None:
        super().__init__("pyright")

    async def install(self) -> bool:
        install_dir = self.install_dir
        install_dir.mkdir(parents=True, exist_ok=True)

        # Check if npm is available
        result = subprocess.run(
            ["npm", "--version"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error("npm is not available. Please install Node.js and npm first.")
            return False

        logger.info(f"Installing pyright in {install_dir}...")
        proc = await asyncio.create_subprocess_exec(
            "npm",
            "install",
            "pyright",
            "--prefix",
            str(install_dir),
            cwd=install_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.error(f"Failed to install pyright: {stderr.decode()}")
            return False

        logger.info("pyright installed successfully")
        return True

    def is_installed(self) -> bool:
        # Check if installed in ~/.vibe/lsp/pyright
        exec_path = self.get_executable_path()
        return exec_path is not None and exec_path.exists()

    def get_executable_path(self) -> Path | None:
        # Check if installed via npm
        node_modules = self.install_dir / "node_modules"
        if node_modules.exists():
            pyright_js = node_modules / "pyright" / "dist" / "pyright-langserver.js"
            if pyright_js.exists():
                return pyright_js

        return None
