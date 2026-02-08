from __future__ import annotations

from vibe.core.lsp.installer import LSPServerInstaller
from vibe.core.lsp.installers.deno import DenoLSPInstaller
from vibe.core.lsp.installers.pyright import PyrightInstaller
from vibe.core.lsp.installers.ruff import RuffLSPInstaller
from vibe.core.lsp.installers.typescript import TypeScriptLSPInstaller


class LSPServerInstallerFactory:
    @staticmethod
    def create_installer(server_name: str) -> LSPServerInstaller | None:
        installers = {
            "pyright": PyrightInstaller,
            "typescript": TypeScriptLSPInstaller,
            "deno": DenoLSPInstaller,
            "ruff": RuffLSPInstaller,
        }
        installer_class = installers.get(server_name)
        if installer_class:
            return installer_class()
        return None
