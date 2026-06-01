"""LSP server configuration.

This module contains configuration models for LSP (Language Server Protocol) servers.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LSPDiagnosticsState:
    """Centralized state management for LSP diagnostics.

    Provides a single source of truth for diagnostics enable/disable state,
    separating configuration from runtime overrides.
    """

    def __init__(self) -> None:
        self._config_enabled: bool = True
        self._runtime_disabled: bool = False

    @property
    def is_enabled(self) -> bool:
        """Check if diagnostics are currently enabled.

        Returns:
            True if diagnostics are enabled (config allows and not runtime-disabled)
        """
        return self._config_enabled and not self._runtime_disabled

    def set_config_enabled(self, enabled: bool) -> None:
        """Set diagnostics enabled state from config.

        Args:
            enabled: Whether diagnostics should be enabled per config
        """
        self._config_enabled = enabled

    def disable_runtime(self) -> None:
        """Disable diagnostics at runtime (overrides config)."""
        self._runtime_disabled = True

    def enable_runtime(self) -> None:
        """Clear runtime disable flag, restoring config-based behavior."""
        self._runtime_disabled = False


class LSPConfig(BaseModel):
    """Global LSP configuration.

    This model defines global settings for LSP diagnostics and behavior.
    """

    enable_diagnostics: bool = Field(
        default=True,
        description="Whether to automatically run LSP diagnostics on file operations",
    )


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
