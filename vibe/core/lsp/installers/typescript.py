from __future__ import annotations

import asyncio
import subprocess
from logging import getLogger
from pathlib import Path

from vibe.core.lsp.installer import LSPServerInstaller
from vibe.core.lsp.mason_paths import MasonPaths

logger = getLogger("vibe")


class TypeScriptLSPInstaller(LSPServerInstaller):

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

        logger.info(f"Installing typescript-language-server and typescript in {install_dir}...")
        proc = await asyncio.create_subprocess_exec(
            "npm",
            "install",
            "typescript-language-server",
            "typescript",
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

        logger.info("typescript-language-server and typescript installed successfully")
        return True

    def get_executable_path_from_mason(self) -> Path | None:
        # Look for typescript-language-server in Mason packages
        return MasonPaths.find_typescript_in_mason()

    def _get_default_executable_path(self) -> Path | None:
        # Check if installed via npm
        node_modules = self.install_dir / "node_modules"
        if node_modules.exists():
            # Check for the modern ESM version (cli.mjs)
            cli_mjs = node_modules / "typescript-language-server" / "lib" / "cli.mjs"
            if cli_mjs.exists():
                return cli_mjs

            # Check for the older CommonJS version
            tsserver_js = node_modules / "typescript-language-server" / "bin" / "typescript-language-server.js"
            if tsserver_js.exists():
                return tsserver_js

            # Also check for the alternative location
            main_js = node_modules / "typescript-language-server" / "out" / "node" / "server.js"
            if main_js.exists():
                return main_js

        return None

    def is_installed(self) -> bool:
        # Check if installed in ~/.vibe/lsp/typescript
        exec_path = self.get_executable_path()
        return exec_path is not None and exec_path.exists()
