from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from vibe.core.lsp.installer import LSPServerInstaller

logger = logging.getLogger(__name__)

# TODO: should be implemented properly.
class DenoLSPInstaller(LSPServerInstaller):
    """Installer for Deno LSP server."""

    def __init__(self) -> None:
        super().__init__("deno")

    async def install(self) -> bool:
        # Deno is typically installed globally, not via package manager
        logger.info("Deno LSP server requires Deno to be installed globally.")
        logger.info("Please install Deno from https://deno.land/")
        return False

    def is_installed(self) -> bool:
        try:
            result = subprocess.run(
                ["which", "deno"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def get_executable_path(self) -> Path | None:
        try:
            result = subprocess.run(
                ["which", "deno"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return Path(result.stdout.strip())
        except FileNotFoundError:
            pass
        return None
