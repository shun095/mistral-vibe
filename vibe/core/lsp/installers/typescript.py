from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path

from vibe.core.lsp.installer import LSPServerInstaller

logger = logging.getLogger(__name__)


class TypeScriptLSPInstaller(LSPServerInstaller):
    """Installer for TypeScript Language Server."""

    def __init__(self) -> None:
        super().__init__("typescript")

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

        logger.info(f"Installing typescript-language-server in {install_dir}...")
        proc = await asyncio.create_subprocess_exec(
            "npm",
            "install",
            "typescript-language-server",
            "--prefix",
            str(install_dir),
            cwd=install_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.error(f"Failed to install typescript-language-server: {stderr.decode()}")
            return False

        logger.info("typescript-language-server installed successfully")
        return True

    def is_installed(self) -> bool:
        # Check if typescript-language-server is in PATH
        try:
            result = subprocess.run(
                ["which", "typescript-language-server"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return True
        except FileNotFoundError:
            pass

        # Check if installed via npm
        exec_path = self.get_executable_path()
        return exec_path is not None and exec_path.exists()

    def get_executable_path(self) -> Path | None:
        # Check if typescript-language-server is in PATH
        try:
            result = subprocess.run(
                ["which", "typescript-language-server"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return Path(result.stdout.strip())
        except FileNotFoundError:
            pass

        # Check if installed via npm
        node_modules = self.install_dir / "node_modules"
        if node_modules.exists():
            # Check for the main module
            tsserver_js = node_modules / "typescript-language-server" / "bin" / "typescript-language-server.js"
            if tsserver_js.exists():
                return tsserver_js

            # Also check for the alternative location
            main_js = node_modules / "typescript-language-server" / "out" / "node" / "server.js"
            if main_js.exists():
                return main_js

        return None
