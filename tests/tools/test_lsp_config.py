"""Tests for LSP configuration functionality.

This module tests the LSPConfig model, LSPDiagnosticsState, and their
integration with VibeConfig and LSPClientManager.
"""

from __future__ import annotations

from pathlib import Path


class TestLSPConfig:
    """Tests for LSPConfig model."""

    def test_default_enable_diagnostics(self) -> None:
        """Test that enable_diagnostics defaults to True."""
        from vibe.core.lsp.config import LSPConfig

        config = LSPConfig()
        assert config.enable_diagnostics is True

    def test_enable_diagnostics_false(self) -> None:
        """Test setting enable_diagnostics to False."""
        from vibe.core.lsp.config import LSPConfig

        config = LSPConfig(enable_diagnostics=False)
        assert config.enable_diagnostics is False

    def test_enable_diagnostics_true(self) -> None:
        """Test setting enable_diagnostics to True."""
        from vibe.core.lsp.config import LSPConfig

        config = LSPConfig(enable_diagnostics=True)
        assert config.enable_diagnostics is True


class TestLSPDiagnosticsState:
    """Tests for LSPDiagnosticsState class."""

    def test_default_state(self) -> None:
        """Test that diagnostics are enabled by default."""
        from vibe.core.lsp.config import LSPDiagnosticsState

        state = LSPDiagnosticsState()
        assert state.is_enabled is True

    def test_config_enabled_false(self) -> None:
        """Test setting config enabled to False."""
        from vibe.core.lsp.config import LSPDiagnosticsState

        state = LSPDiagnosticsState()
        state.set_config_enabled(False)
        assert state.is_enabled is False

    def test_config_enabled_true(self) -> None:
        """Test setting config enabled to True."""
        from vibe.core.lsp.config import LSPDiagnosticsState

        state = LSPDiagnosticsState()
        state.set_config_enabled(True)
        assert state.is_enabled is True

    def test_runtime_disable_overrides_config(self) -> None:
        """Test that runtime disable overrides config setting."""
        from vibe.core.lsp.config import LSPDiagnosticsState

        state = LSPDiagnosticsState()
        state.set_config_enabled(True)
        assert state.is_enabled is True

        state.disable_runtime()
        assert state.is_enabled is False

    def test_runtime_enable_restores_config(self) -> None:
        """Test that runtime enable restores config-based behavior."""
        from vibe.core.lsp.config import LSPDiagnosticsState

        state = LSPDiagnosticsState()
        state.set_config_enabled(True)
        state.disable_runtime()
        assert state.is_enabled is False

        state.enable_runtime()
        assert state.is_enabled is True

    def test_runtime_enable_with_config_false(self) -> None:
        """Test runtime enable when config is False."""
        from vibe.core.lsp.config import LSPDiagnosticsState

        state = LSPDiagnosticsState()
        state.set_config_enabled(False)
        state.disable_runtime()
        assert state.is_enabled is False

        state.enable_runtime()
        assert state.is_enabled is False


class TestVibeConfigLSPIntegration:
    """Tests for LSP config integration with VibeConfig."""

    def test_vibe_config_has_lsp_field(self) -> None:
        """Test that VibeConfig has lsp field."""
        from vibe.core.config import VibeConfig
        from vibe.core.lsp.config import LSPConfig

        # Check that lsp field exists in model_fields
        assert "lsp" in VibeConfig.model_fields

        # Check that default value is LSPConfig instance
        config = VibeConfig.model_construct()
        assert isinstance(config.lsp, LSPConfig)
        assert config.lsp.enable_diagnostics is True

    def _reset_lsp_state(self) -> None:
        """Reset LSP diagnostics state to defaults."""
        from vibe.core.lsp import LSPClientManager

        LSPClientManager._diagnostics_state = (
            LSPClientManager._diagnostics_state.__class__()
        )

    def _load_config_with_lsp_setting(
        self, tmp_path: Path, enable_diagnostics: bool
    ) -> tuple[bool, bool]:
        """Helper to load config with specific lsp setting.

        Returns:
            Tuple of (config value, LSPClientManager value)
        """
        from vibe.core.config import VibeConfig
        from vibe.core.config.harness_files import (
            get_harness_files_manager,
            init_harness_files_manager,
            reset_harness_files_manager,
        )
        from vibe.core.lsp import LSPClientManager

        # Reset state
        reset_harness_files_manager()
        self._reset_lsp_state()

        # Create config file
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            f"""
[lsp]
enable_diagnostics = {str(enable_diagnostics).lower()}
"""
        )

        # Set environment to use temp dir
        import os

        os.environ["VIBE_HOME"] = str(tmp_path)

        # Initialize harness files manager
        init_harness_files_manager("user")

        # Verify config file is found
        mgr = get_harness_files_manager()
        assert mgr.config_file == config_file

        # Load config
        config = VibeConfig.load()

        # Verify lsp config is loaded correctly
        config_value = config.lsp.enable_diagnostics

        # Verify LSPClientManager respects the config
        LSPClientManager.set_diagnostics_enabled_from_config(config_value)
        manager_value = LSPClientManager.are_diagnostics_enabled()

        return config_value, manager_value

    def test_vibe_config_load_with_lsp_false(self, tmp_path: Path) -> None:
        """Test loading VibeConfig with lsp.enable_diagnostics = false."""
        config_value, manager_value = self._load_config_with_lsp_setting(
            tmp_path, False
        )

        assert config_value is False
        assert manager_value is False

    def test_vibe_config_load_with_lsp_true(self, tmp_path: Path) -> None:
        """Test loading VibeConfig with lsp.enable_diagnostics = true."""
        config_value, manager_value = self._load_config_with_lsp_setting(tmp_path, True)

        assert config_value is True
        assert manager_value is True

    def test_vibe_config_load_without_lsp_section(self, tmp_path: Path) -> None:
        """Test loading VibeConfig without lsp section (should default to True)."""
        from vibe.core.config import VibeConfig
        from vibe.core.config.harness_files import (
            get_harness_files_manager,
            init_harness_files_manager,
            reset_harness_files_manager,
        )
        from vibe.core.lsp import LSPClientManager

        # Reset state
        reset_harness_files_manager()
        self._reset_lsp_state()

        # Create config file without lsp section
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
# Empty config
"""
        )

        # Set environment to use temp dir
        import os

        os.environ["VIBE_HOME"] = str(tmp_path)

        # Initialize harness files manager
        init_harness_files_manager("user")

        # Verify config file is found
        mgr = get_harness_files_manager()
        assert mgr.config_file == config_file

        # Load config
        config = VibeConfig.load()

        # Verify lsp config defaults to enabled
        assert config.lsp.enable_diagnostics is True

        # Verify LSPClientManager automatically respects the config (applied in load())
        assert LSPClientManager.are_diagnostics_enabled() is True


class TestVibeConfigLoadAppliesLSPConfig:
    """Tests that VibeConfig.load() automatically applies LSP config."""

    def _reset_lsp_state(self) -> None:
        """Reset LSP diagnostics state to defaults."""
        from vibe.core.lsp import LSPClientManager

        LSPClientManager._diagnostics_state = (
            LSPClientManager._diagnostics_state.__class__()
        )

    def test_load_applies_lsp_diagnostics_false(self, tmp_path: Path) -> None:
        """Test that VibeConfig.load() applies lsp.enable_diagnostics=false."""
        from vibe.core.config import VibeConfig
        from vibe.core.config.harness_files import (
            get_harness_files_manager,
            init_harness_files_manager,
            reset_harness_files_manager,
        )
        from vibe.core.lsp import LSPClientManager

        # Reset state
        reset_harness_files_manager()
        self._reset_lsp_state()

        # Create config file with diagnostics disabled
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[lsp]
enable_diagnostics = false
"""
        )

        # Set environment to use temp dir
        import os

        os.environ["VIBE_HOME"] = str(tmp_path)

        # Initialize harness files manager
        init_harness_files_manager("user")

        # Verify config file is found
        mgr = get_harness_files_manager()
        assert mgr.config_file == config_file

        # Load config - this should automatically apply LSP settings
        config = VibeConfig.load()

        # Verify config value
        assert config.lsp.enable_diagnostics is False

        # Verify LSPClientManager automatically has diagnostics disabled
        # (no manual call to set_diagnostics_enabled_from_config)
        assert LSPClientManager.are_diagnostics_enabled() is False

    def test_load_applies_lsp_diagnostics_true(self, tmp_path: Path) -> None:
        """Test that VibeConfig.load() applies lsp.enable_diagnostics=true."""
        from vibe.core.config import VibeConfig
        from vibe.core.config.harness_files import (
            get_harness_files_manager,
            init_harness_files_manager,
            reset_harness_files_manager,
        )
        from vibe.core.lsp import LSPClientManager

        # Reset state
        reset_harness_files_manager()
        self._reset_lsp_state()

        # Create config file with diagnostics enabled
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[lsp]
enable_diagnostics = true
"""
        )

        # Set environment to use temp dir
        import os

        os.environ["VIBE_HOME"] = str(tmp_path)

        # Initialize harness files manager
        init_harness_files_manager("user")

        # Verify config file is found
        mgr = get_harness_files_manager()
        assert mgr.config_file == config_file

        # Load config - this should automatically apply LSP settings
        config = VibeConfig.load()

        # Verify config value
        assert config.lsp.enable_diagnostics is True

        # Verify LSPClientManager automatically has diagnostics enabled
        # (no manual call to set_diagnostics_enabled_from_config)
        assert LSPClientManager.are_diagnostics_enabled() is True


class TestLSPClientManagerConfig:
    """Tests for LSPClientManager config integration."""

    def test_are_diagnostics_enabled_default(self) -> None:
        """Test that are_diagnostics_enabled returns True by default."""
        from vibe.core.lsp import LSPClientManager

        # Reset state
        LSPClientManager._diagnostics_state = (
            LSPClientManager._diagnostics_state.__class__()
        )

        assert LSPClientManager.are_diagnostics_enabled() is True

    def test_are_diagnostics_enabled_with_config_true(self) -> None:
        """Test that are_diagnostics_enabled respects config True."""
        from vibe.core.lsp import LSPClientManager

        # Reset state
        LSPClientManager._diagnostics_state = (
            LSPClientManager._diagnostics_state.__class__()
        )

        # Set config
        LSPClientManager.set_diagnostics_enabled_from_config(True)

        assert LSPClientManager.are_diagnostics_enabled() is True

    def test_are_diagnostics_enabled_with_config_false(self) -> None:
        """Test that are_diagnostics_enabled respects config False."""
        from vibe.core.lsp import LSPClientManager

        # Reset state
        LSPClientManager._diagnostics_state = (
            LSPClientManager._diagnostics_state.__class__()
        )

        # Set config
        LSPClientManager.set_diagnostics_enabled_from_config(False)

        assert LSPClientManager.are_diagnostics_enabled() is False

    def test_are_diagnostics_enabled_disabled_overrides_config(self) -> None:
        """Test that disable_diagnostics overrides config."""
        from vibe.core.lsp import LSPClientManager

        # Reset state
        LSPClientManager._diagnostics_state = (
            LSPClientManager._diagnostics_state.__class__()
        )

        # Set config to True
        LSPClientManager.set_diagnostics_enabled_from_config(True)
        assert LSPClientManager.are_diagnostics_enabled() is True

        # Disable globally
        LSPClientManager.disable_diagnostics()
        assert LSPClientManager.are_diagnostics_enabled() is False

    def test_are_diagnostics_enabled_enable_clears_disabled(self) -> None:
        """Test that enable_diagnostics clears the disabled flag."""
        from vibe.core.lsp import LSPClientManager

        # Reset state
        LSPClientManager._diagnostics_state = (
            LSPClientManager._diagnostics_state.__class__()
        )

        # Disable globally
        LSPClientManager.disable_diagnostics()
        assert LSPClientManager.are_diagnostics_enabled() is False

        # Enable globally
        LSPClientManager.enable_diagnostics()
        assert LSPClientManager.are_diagnostics_enabled() is True
