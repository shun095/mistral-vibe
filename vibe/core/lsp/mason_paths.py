from __future__ import annotations

from pathlib import Path
from typing import Optional


class MasonPaths:
    """Utility for locating Mason-installed LSP servers."""
    
    @staticmethod
    def get_mason_base_dir() -> Path:
        """Get the base Mason packages directory."""
        return Path("~/.local/share/nvim/mason/packages").expanduser()
    
    @staticmethod
    def get_mason_package_dirs() -> list[Path]:
        """Get all Mason package directories."""
        base_dir = MasonPaths.get_mason_base_dir()
        if not base_dir.exists():
            return []
        
        return list(base_dir.iterdir())
    
    @staticmethod
    def find_pyright_in_mason() -> Optional[Path]:
        """Find pyright-langserver.js in Mason packages."""
        for package_dir in MasonPaths.get_mason_package_dirs():
            if package_dir.name != "pyright":
                continue
            
            # Pyright structure: node_modules/pyright/dist/pyright-langserver.js
            pyright_js = package_dir / "node_modules" / "pyright" / "dist" / "pyright-langserver.js"
            if pyright_js.exists():
                return pyright_js
        
        return None
    
    @staticmethod
    def find_ruff_in_mason() -> Optional[Path]:
        """Find ruff executable in Mason packages."""
        for package_dir in MasonPaths.get_mason_package_dirs():
            if package_dir.name != "ruff":
                continue
            
            # Ruff structure: venv/bin/ruff (Linux/macOS) or venv/Scripts/ruff.exe (Windows)
            ruff_exe = package_dir / "venv" / "bin" / "ruff"
            if ruff_exe.exists():
                return ruff_exe
            
            ruff_exe_win = package_dir / "venv" / "Scripts" / "ruff.exe"
            if ruff_exe_win.exists():
                return ruff_exe_win
        
        return None
    
    @staticmethod
    def find_typescript_in_mason() -> Optional[Path]:
        """Find typescript-language-server in Mason packages."""
        for package_dir in MasonPaths.get_mason_package_dirs():
            if package_dir.name != "typescript-language-server":
                continue
            
            # TypeScript structure: node_modules/typescript-language-server/lib/cli.mjs
            cli_mjs = package_dir / "node_modules" / "typescript-language-server" / "lib" / "cli.mjs"
            if cli_mjs.exists():
                return cli_mjs
        
        return None