from __future__ import annotations

from pathlib import Path

from vibe.core.config import LSPServerConfig
from vibe.core.lsp.server import LSPServerRegistry


class LSPServerDetector:
    """Detects the appropriate LSP server for a given file.
    
    This class handles the logic for matching files to LSP servers
    based on file extensions and configuration patterns.
    """
    
    def __init__(self, config: dict[str, LSPServerConfig] | None = None) -> None:
        """Initialize the detector with optional configuration.
        
        Args:
            config: Dictionary of server name to LSPServerConfig mapping
        """
        self.config = config or {}
    
    def detect_server_for_file(self, file_path: Path) -> str | None:
        """Detect the appropriate LSP server based on file extension.
        
        First checks configured servers with file patterns, then falls back
        to built-in servers via the registry.
        
        Args:
            file_path: Path to the file to analyze
            
        Returns:
            Server name if detected, None otherwise
        """
        # Try to match with configured servers first
        if not self.config:
            # Fallback to built-in servers via registry
            return LSPServerRegistry.detect_server_for_file(file_path)

        for server_name, server_config in self.config.items():
            if not server_config.file_patterns:
                # Server handles all files
                return server_name

            for pattern in server_config.file_patterns:
                if pattern.startswith("*") and pattern.endswith("*"):
                    # Handle patterns like *.py
                    if file_path.suffix.lower() == pattern[1:-1].lower():
                        return server_name
                elif pattern.startswith("*"):
                    # Handle patterns like *.py
                    if file_path.suffix.lower() == pattern[1:].lower():
                        return server_name

        # Fallback to built-in servers via registry
        return LSPServerRegistry.detect_server_for_file(file_path)
