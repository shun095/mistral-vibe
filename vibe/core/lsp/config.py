"""LSP server configuration.

This module contains configuration models for LSP (Language Server Protocol) servers.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LSPServerConfig(BaseModel):
    """Configuration for an LSP (Language Server Protocol) server.

    This model defines the configuration options for an LSP server,
    including command, file patterns, and other settings.
    """

    name: str = Field(
        description="Name of the LSP server (e.g., 'pyright', 'tsserver')"
    )
    command: list[str] = Field(
        description="Command to start the LSP server (e.g., ['pyright-langserver', '--stdio'])"
    )
    enabled: bool = Field(
        default=True, description="Whether this LSP server is enabled"
    )
    file_patterns: list[str] = Field(
        default_factory=list,
        description=(
            "File patterns this server should handle (e.g., ['*.py', '*.pyi']). "
            "Empty list means handle all files."
        ),
    )
    timeout_seconds: float = Field(
        default=10.0, description="Timeout for server startup in seconds"
    )
    auto_start: bool = Field(
        default=True, description="Whether to automatically start this server"
    )
    env: dict[str, str] | None = Field(
        default=None,
        description="Environment variables to set for the LSP server process",
    )
    cwd: str | None = Field(
        default=None,
        description="Working directory for the LSP server (defaults to project root)",
    )
