"""Tests for terminal_setup module."""

from __future__ import annotations

import json
import os
import platform
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe.cli.terminal_setup import (
    Terminal,
    SetupResult,
    _get_cursor_keybindings_path,
    _get_vscode_keybindings_path,
    _has_shift_enter_binding,
    _is_cursor,
    _parse_keybindings,
    _read_existing_keybindings,
    _setup_ghostty,
    _setup_iterm2,
    _setup_vscode_like_terminal,
    _setup_wezterm,
    detect_terminal,
    setup_terminal,
)


class TestTerminalDetection:
    """Test terminal detection functions."""

    @patch.dict(os.environ, {"TERM_PROGRAM": "vscode"})
    def test_detect_vscode(self) -> None:
        """Test detection of VSCode terminal."""
        result = detect_terminal()
        assert result == Terminal.VSCODE

    @patch.dict(os.environ, {"TERM_PROGRAM": "vscode", "VSCODE_IPC_HOOK_CLI": "cursor"})
    def test_detect_cursor(self) -> None:
        """Test detection of Cursor terminal."""
        result = detect_terminal()
        assert result == Terminal.CURSOR

    @patch.dict(os.environ, {"TERM_PROGRAM": "iterm.app"})
    def test_detect_iterm2(self) -> None:
        """Test detection of iTerm2 terminal."""
        result = detect_terminal()
        assert result == Terminal.ITERM2

    @patch.dict(os.environ, {"TERM_PROGRAM": "wezterm"})
    def test_detect_wezterm(self) -> None:
        """Test detection of WezTerm terminal."""
        result = detect_terminal()
        assert result == Terminal.WEZTERM

    @patch.dict(os.environ, {"TERM_PROGRAM": "ghostty"})
    def test_detect_ghostty(self) -> None:
        """Test detection of Ghostty terminal."""
        result = detect_terminal()
        assert result == Terminal.GHOSTTY

    @patch.dict(os.environ, {}, clear=True)
    def test_detect_unknown(self) -> None:
        """Test detection of unknown terminal."""
        result = detect_terminal()
        assert result == Terminal.UNKNOWN

    @patch.dict(os.environ, {"WEZTERM_PANE": "1"})
    def test_detect_wezterm_by_env_var(self) -> None:
        """Test detection of WezTerm via environment variable."""
        result = detect_terminal()
        assert result == Terminal.WEZTERM

    @patch.dict(os.environ, {"GHOSTTY_RESOURCES_DIR": "/some/path"})
    def test_detect_ghostty_by_env_var(self) -> None:
        """Test detection of Ghostty via environment variable."""
        result = detect_terminal()
        assert result == Terminal.GHOSTTY


class TestIsCursor:
    """Test Cursor detection helper."""

    @patch.dict(os.environ, {"VSCODE_IPC_HOOK_CLI": "cursor"})
    def test_is_cursor_true(self) -> None:
        """Test Cursor detection when environment variable contains 'cursor'."""
        assert _is_cursor() is True

    @patch.dict(os.environ, {"VSCODE_IPC_HOOK_CLI": "vscode"})
    def test_is_cursor_false(self) -> None:
        """Test Cursor detection when environment variable doesn't contain 'cursor'."""
        assert _is_cursor() is False

    @patch.dict(os.environ, {}, clear=True)
    def test_is_cursor_no_env_vars(self) -> None:
        """Test Cursor detection with no relevant environment variables."""
        assert _is_cursor() is False


class TestKeybindingsPath:
    """Test keybindings path resolution."""

    @patch("platform.system", return_value="Darwin")
    def test_get_vscode_keybindings_path_darwin(self, mock_platform: MagicMock) -> None:
        """Test VSCode keybindings path on macOS."""
        result = _get_vscode_keybindings_path()
        assert result == Path.home() / "Library" / "Application Support" / "Code" / "User" / "keybindings.json"

    @patch("platform.system", return_value="Linux")
    def test_get_vscode_keybindings_path_linux(self, mock_platform: MagicMock) -> None:
        """Test VSCode keybindings path on Linux."""
        result = _get_vscode_keybindings_path()
        assert result == Path.home() / ".config" / "Code" / "User" / "keybindings.json"

    @patch("platform.system", return_value="Windows")
    @patch.dict(os.environ, {"APPDATA": "C:\\Users\\Test\\AppData\\Roaming"})
    def test_get_vscode_keybindings_path_windows(self, mock_platform: MagicMock) -> None:
        """Test VSCode keybindings path on Windows."""
        result = _get_vscode_keybindings_path()
        assert result == Path("C:\\Users\\Test\\AppData\\Roaming") / "Code" / "User" / "keybindings.json"

    @patch("platform.system", return_value="UnknownOS")
    def test_get_vscode_keybindings_path_unknown_os(self, mock_platform: MagicMock) -> None:
        """Test VSCode keybindings path on unknown OS."""
        result = _get_vscode_keybindings_path()
        assert result is None

    @patch("platform.system", return_value="Windows")
    @patch.dict(os.environ, {}, clear=True)
    def test_get_vscode_keybindings_path_windows_no_appdata(self, mock_platform: MagicMock) -> None:
        """Test VSCode keybindings path on Windows without APPDATA."""
        result = _get_vscode_keybindings_path()
        assert result is None

    @patch("platform.system", return_value="Darwin")
    def test_get_cursor_keybindings_path_darwin(self, mock_platform: MagicMock) -> None:
        """Test Cursor keybindings path on macOS."""
        result = _get_cursor_keybindings_path()
        assert result == Path.home() / "Library" / "Application Support" / "Cursor" / "User" / "keybindings.json"

    @patch("platform.system", return_value="Linux")
    def test_get_cursor_keybindings_path_linux(self, mock_platform: MagicMock) -> None:
        """Test Cursor keybindings path on Linux."""
        result = _get_cursor_keybindings_path()
        assert result == Path.home() / ".config" / "Cursor" / "User" / "keybindings.json"


class TestParseKeybindings:
    """Test keybindings parsing."""

    def test_parse_keybindings_valid_json(self) -> None:
        """Test parsing valid JSON keybindings."""
        content = '[{"key": "ctrl+s", "command": "save"}]'
        result = _parse_keybindings(content)
        assert len(result) == 1
        assert result[0]["key"] == "ctrl+s"

    def test_parse_keybindings_with_comments(self) -> None:
        """Test parsing keybindings with comments."""
        content = '// Comment\n[{"key": "ctrl+s", "command": "save"}]'
        result = _parse_keybindings(content)
        # Comments are stripped, so this should return empty list
        assert result == []

    def test_parse_keybindings_empty(self) -> None:
        """Test parsing empty content."""
        result = _parse_keybindings("")
        assert result == []

    def test_parse_keybindings_comment_only(self) -> None:
        """Test parsing content with only comments."""
        result = _parse_keybindings("// Only a comment")
        assert result == []

    def test_parse_keybindings_invalid_json(self) -> None:
        """Test parsing invalid JSON."""
        result = _parse_keybindings("{invalid json}")
        assert result == []

    def test_parse_keybindings_whitespace(self) -> None:
        """Test parsing content with leading/trailing whitespace."""
        content = '  [{"key": "ctrl+s"}]  '
        result = _parse_keybindings(content)
        assert len(result) == 1


class TestReadExistingKeybindings:
    """Test reading existing keybindings."""

    def test_read_existing_keybindings_file_exists(self, tmp_path: Path) -> None:
        """Test reading keybindings from existing file."""
        keybindings_file = tmp_path / "keybindings.json"
        keybindings_file.write_text('[{"key": "ctrl+s"}]')

        result = _read_existing_keybindings(keybindings_file)
        assert len(result) == 1

    def test_read_existing_keybindings_file_not_exists(self, tmp_path: Path) -> None:
        """Test reading keybindings when file doesn't exist."""
        keybindings_file = tmp_path / "keybindings.json"

        result = _read_existing_keybindings(keybindings_file)
        assert result == []

    def test_read_existing_keybindings_invalid_content(self, tmp_path: Path) -> None:
        """Test reading keybindings with invalid content."""
        keybindings_file = tmp_path / "keybindings.json"
        keybindings_file.write_text("{invalid json}")

        result = _read_existing_keybindings(keybindings_file)
        assert result == []


class TestHasShiftEnterBinding:
    """Test Shift+Enter binding detection."""

    def test_has_shift_enter_binding_true(self) -> None:
        """Test detection of existing Shift+Enter binding."""
        keybindings = [
            {
                "key": "shift+enter",
                "command": "workbench.action.terminal.sendSequence",
                "args": {"text": "\\u001b[13;2u"},
                "when": "terminalFocus",
            }
        ]
        assert _has_shift_enter_binding(keybindings) is True

    def test_has_shift_enter_binding_false(self) -> None:
        """Test detection when Shift+Enter binding doesn't exist."""
        keybindings = [{"key": "ctrl+s", "command": "save"}]
        assert _has_shift_enter_binding(keybindings) is False

    def test_has_shift_enter_binding_partial_match(self) -> None:
        """Test detection with partial matching."""
        keybindings = [
            {"key": "shift+enter", "command": "save"},  # Missing command match
            {"key": "ctrl+enter", "command": "workbench.action.terminal.sendSequence"},  # Missing key match
        ]
        assert _has_shift_enter_binding(keybindings) is False


class TestSetupVSCodeLikeTerminal:
    """Test VSCode/Cursor terminal setup."""

    @patch("vibe.cli.terminal_setup._get_vscode_keybindings_path")
    @patch("vibe.cli.terminal_setup._read_existing_keybindings")
    @patch("vibe.cli.terminal_setup._has_shift_enter_binding")
    def test_setup_vscode_success(
        self,
        mock_has_binding: MagicMock,
        mock_read: MagicMock,
        mock_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test successful VSCode setup."""
        keybindings_file = tmp_path / "keybindings.json"
        mock_path.return_value = keybindings_file
        mock_read.return_value = []
        mock_has_binding.return_value = False

        result = _setup_vscode_like_terminal(Terminal.VSCODE)

        assert result.success is True
        assert result.terminal == Terminal.VSCODE
        assert result.requires_restart is True
        assert keybindings_file.exists()

    @patch("vibe.cli.terminal_setup._get_vscode_keybindings_path", return_value=None)
    def test_setup_vscode_no_path(self, mock_path: MagicMock) -> None:
        """Test VSCode setup when path cannot be determined."""
        result = _setup_vscode_like_terminal(Terminal.VSCODE)

        assert result.success is False
        assert result.terminal == Terminal.VSCODE
        assert "Could not determine keybindings path" in result.message

    @patch("vibe.cli.terminal_setup._get_vscode_keybindings_path")
    @patch("vibe.cli.terminal_setup._read_existing_keybindings")
    @patch("vibe.cli.terminal_setup._has_shift_enter_binding", return_value=True)
    def test_setup_vscode_already_configured(
        self,
        mock_has_binding: MagicMock,
        mock_read: MagicMock,
        mock_path: MagicMock,
    ) -> None:
        """Test VSCode setup when already configured."""
        result = _setup_vscode_like_terminal(Terminal.VSCODE)

        assert result.success is True
        assert result.terminal == Terminal.VSCODE
        assert "already configured" in result.message
        assert result.requires_restart is False

    @patch("vibe.cli.terminal_setup._get_vscode_keybindings_path")
    @patch("vibe.cli.terminal_setup._read_existing_keybindings")
    @patch("vibe.cli.terminal_setup._has_shift_enter_binding")
    def test_setup_vscode_exception(
        self,
        mock_has_binding: MagicMock,
        mock_read: MagicMock,
        mock_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test VSCode setup with exception."""
        keybindings_file = tmp_path / "keybindings.json"
        mock_path.return_value = keybindings_file
        mock_read.return_value = []
        mock_has_binding.return_value = False
        keybindings_file.parent.mkdir(parents=True, exist_ok=True)
        keybindings_file.write_text("")
        keybindings_file.chmod(0o000)  # Make file read-only

        result = _setup_vscode_like_terminal(Terminal.VSCODE)

        assert result.success is False
        assert result.terminal == Terminal.VSCODE
        assert "Failed to configure" in result.message


class TestSetupITerm2:
    """Test iTerm2 terminal setup."""

    @patch("platform.system", return_value="Darwin")
    @patch("subprocess.run")
    def test_setup_iterm2_success(
        self,
        mock_run: MagicMock,
        mock_platform: MagicMock,
    ) -> None:
        """Test successful iTerm2 setup."""
        mock_run.return_value = MagicMock(stdout="", stderr="")

        result = _setup_iterm2()

        assert result.success is True
        assert result.terminal == Terminal.ITERM2
        assert result.requires_restart is True

    @patch("platform.system", return_value="Darwin")
    @patch("subprocess.run")
    def test_setup_iterm2_already_configured(
        self,
        mock_run: MagicMock,
        mock_platform: MagicMock,
    ) -> None:
        """Test iTerm2 setup when already configured."""
        mock_run.return_value = MagicMock(
            stdout='...0xd-0x20000-0x24...',
            stderr="",
        )

        result = _setup_iterm2()

        assert result.success is True
        assert result.terminal == Terminal.ITERM2
        assert "already configured" in result.message
        assert result.requires_restart is False

    @patch("platform.system", return_value="Linux")
    def test_setup_iterm2_not_macos(self, mock_platform: MagicMock) -> None:
        """Test iTerm2 setup on non-macOS system."""
        result = _setup_iterm2()

        assert result.success is False
        assert result.terminal == Terminal.ITERM2
        assert "only available on macOS" in result.message

    @patch("platform.system", return_value="Darwin")
    @patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "cmd"))
    def test_setup_iterm2_exception(
        self,
        mock_run: MagicMock,
        mock_platform: MagicMock,
    ) -> None:
        """Test iTerm2 setup with exception."""
        result = _setup_iterm2()

        assert result.success is False
        assert result.terminal == Terminal.ITERM2
        assert "Failed to configure iTerm2" in result.message


class TestSetupWezTerm:
    """Test WezTerm terminal setup."""

    def test_setup_wezterm_success_new_file(self, tmp_path: Path) -> None:
        """Test successful WezTerm setup with new config file."""
        wezterm_config = tmp_path / ".wezterm.lua"
        with patch("vibe.cli.terminal_setup.Path.home", return_value=tmp_path):
            result = _setup_wezterm()

        assert result.success is True
        assert result.terminal == Terminal.WEZTERM
        assert result.requires_restart is True
        assert wezterm_config.exists()

    def test_setup_wezterm_success_existing_file(self, tmp_path: Path) -> None:
        """Test successful WezTerm setup with existing config file."""
        wezterm_config = tmp_path / ".wezterm.lua"
        wezterm_config.write_text("local wezterm = require 'wezterm'\nreturn {keys = {}}")
        with patch("vibe.cli.terminal_setup.Path.home", return_value=tmp_path):
            result = _setup_wezterm()

        assert result.success is True
        assert result.terminal == Terminal.WEZTERM
        assert result.requires_restart is True

    def test_setup_wezterm_already_configured(self, tmp_path: Path) -> None:
        """Test WezTerm setup when already configured."""
        wezterm_config = tmp_path / ".wezterm.lua"
        wezterm_config.write_text(
            "local wezterm = require 'wezterm'\nreturn {\n  keys = {\n    {\n      key = \"Enter\",\n      mods = \"SHIFT\",\n      action = wezterm.action.SendString(\"\\\\x1b[13;2u\")\n    },\n  },\n}\n"
        )
        with patch("vibe.cli.terminal_setup.Path.home", return_value=tmp_path):
            result = _setup_wezterm()

        assert result.success is True
        assert result.terminal == Terminal.WEZTERM
        assert "already configured" in result.message
        assert result.requires_restart is False

    def test_setup_wezterm_no_keys_section(self, tmp_path: Path) -> None:
        """Test WezTerm setup when config has no keys section."""
        wezterm_config = tmp_path / ".wezterm.lua"
        wezterm_config.write_text("local wezterm = require 'wezterm'\nreturn {}")
        with patch("vibe.cli.terminal_setup.Path.home", return_value=tmp_path):
            result = _setup_wezterm()

        # When there's no keys section, it should return False with a manual setup message
        assert result.success is False
        assert result.terminal == Terminal.WEZTERM
        assert "manually add" in result.message

    def test_setup_wezterm_exception(self, tmp_path: Path) -> None:
        """Test WezTerm setup with exception."""
        wezterm_config = tmp_path / ".wezterm.lua"
        wezterm_config.write_text("")
        wezterm_config.chmod(0o000)  # Make file read-only
        with patch("vibe.cli.terminal_setup.Path.home", return_value=tmp_path):
            result = _setup_wezterm()

        assert result.success is False
        assert result.terminal == Terminal.WEZTERM
        assert "Failed to configure WezTerm" in result.message


class TestSetupGhostty:
    """Test Ghostty terminal setup."""

    @patch("platform.system", return_value="Darwin")
    def test_setup_ghostty_success_new_file(self, mock_platform: MagicMock, tmp_path: Path) -> None:
        """Test successful Ghostty setup with new config file."""
        config_dir = tmp_path / "Library" / "Application Support" / "com.mitchellh.ghostty"
        config_dir.mkdir(parents=True)
        with patch("vibe.cli.terminal_setup.Path.home", return_value=tmp_path):
            result = _setup_ghostty()

        assert result.success is True
        assert result.terminal == Terminal.GHOSTTY
        assert result.requires_restart is True

    @patch("platform.system", return_value="Darwin")
    def test_setup_ghostty_success_existing_file(self, mock_platform: MagicMock, tmp_path: Path) -> None:
        """Test successful Ghostty setup with existing config file."""
        config_dir = tmp_path / "Library" / "Application Support" / "com.mitchellh.ghostty"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "config"
        config_path.write_text("# Existing config\n")
        with patch("vibe.cli.terminal_setup.Path.home", return_value=tmp_path):
            result = _setup_ghostty()

        assert result.success is True
        assert result.terminal == Terminal.GHOSTTY
        assert result.requires_restart is True

    @patch("platform.system", return_value="Darwin")
    def test_setup_ghostty_already_configured(self, mock_platform: MagicMock, tmp_path: Path) -> None:
        """Test Ghostty setup when already configured."""
        config_dir = tmp_path / "Library" / "Application Support" / "com.mitchellh.ghostty"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "config"
        config_path.write_text("keybind = shift+enter=text:...\n")
        with patch("vibe.cli.terminal_setup.Path.home", return_value=tmp_path):
            result = _setup_ghostty()

        assert result.success is True
        assert result.terminal == Terminal.GHOSTTY
        assert "already configured" in result.message
        assert result.requires_restart is False

    @patch("platform.system", return_value="Linux")
    def test_setup_ghostty_linux_path(self, mock_platform: MagicMock, tmp_path: Path) -> None:
        """Test Ghostty setup on Linux."""
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / ".config")}):
            result = _setup_ghostty()
        assert result.success is True

    @patch("platform.system", return_value="UnknownOS")
    def test_setup_ghostty_unknown_os(self, mock_platform: MagicMock) -> None:
        """Test Ghostty setup on unknown OS."""
        result = _setup_ghostty()

        assert result.success is False
        assert result.terminal == Terminal.GHOSTTY
        assert "unknown for this OS" in result.message

    @patch("platform.system", return_value="Darwin")
    def test_setup_ghostty_exception(self, mock_platform: MagicMock, tmp_path: Path) -> None:
        """Test Ghostty setup with exception."""
        config_dir = tmp_path / "Library" / "Application Support" / "com.mitchellh.ghostty" / "config"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "config"
        config_path.write_text("")
        config_path.chmod(0o000)  # Make file read-only
        with patch("vibe.cli.terminal_setup.Path.home", return_value=tmp_path):
            result = _setup_ghostty()

        assert result.success is False
        assert result.terminal == Terminal.GHOSTTY
        assert "Failed to configure Ghostty" in result.message


class TestSetupTerminal:
    """Test main setup_terminal function."""

    @patch("vibe.cli.terminal_setup.detect_terminal", return_value=Terminal.VSCODE)
    @patch("vibe.cli.terminal_setup._setup_vscode_like_terminal")
    def test_setup_terminal_vscode(
        self,
        mock_setup: MagicMock,
        mock_detect: MagicMock,
    ) -> None:
        """Test setup for VSCode terminal."""
        mock_setup.return_value = SetupResult(
            success=True,
            terminal=Terminal.VSCODE,
            message="Configured",
        )

        result = setup_terminal()

        assert result.success is True
        assert result.terminal == Terminal.VSCODE

    @patch("vibe.cli.terminal_setup.detect_terminal", return_value=Terminal.CURSOR)
    @patch("vibe.cli.terminal_setup._setup_vscode_like_terminal")
    def test_setup_terminal_cursor(
        self,
        mock_setup: MagicMock,
        mock_detect: MagicMock,
    ) -> None:
        """Test setup for Cursor terminal."""
        mock_setup.return_value = SetupResult(
            success=True,
            terminal=Terminal.CURSOR,
            message="Configured",
        )

        result = setup_terminal()

        assert result.success is True
        assert result.terminal == Terminal.CURSOR

    @patch("vibe.cli.terminal_setup.detect_terminal", return_value=Terminal.ITERM2)
    @patch("vibe.cli.terminal_setup._setup_iterm2")
    def test_setup_terminal_iterm2(
        self,
        mock_setup: MagicMock,
        mock_detect: MagicMock,
    ) -> None:
        """Test setup for iTerm2 terminal."""
        mock_setup.return_value = SetupResult(
            success=True,
            terminal=Terminal.ITERM2,
            message="Configured",
        )

        result = setup_terminal()

        assert result.success is True
        assert result.terminal == Terminal.ITERM2

    @patch("vibe.cli.terminal_setup.detect_terminal", return_value=Terminal.WEZTERM)
    @patch("vibe.cli.terminal_setup._setup_wezterm")
    def test_setup_terminal_wezterm(
        self,
        mock_setup: MagicMock,
        mock_detect: MagicMock,
    ) -> None:
        """Test setup for WezTerm terminal."""
        mock_setup.return_value = SetupResult(
            success=True,
            terminal=Terminal.WEZTERM,
            message="Configured",
        )

        result = setup_terminal()

        assert result.success is True
        assert result.terminal == Terminal.WEZTERM

    @patch("vibe.cli.terminal_setup.detect_terminal", return_value=Terminal.GHOSTTY)
    @patch("vibe.cli.terminal_setup._setup_ghostty")
    def test_setup_terminal_ghostty(
        self,
        mock_setup: MagicMock,
        mock_detect: MagicMock,
    ) -> None:
        """Test setup for Ghostty terminal."""
        mock_setup.return_value = SetupResult(
            success=True,
            terminal=Terminal.GHOSTTY,
            message="Configured",
        )

        result = setup_terminal()

        assert result.success is True
        assert result.terminal == Terminal.GHOSTTY

    @patch("vibe.cli.terminal_setup.detect_terminal", return_value=Terminal.UNKNOWN)
    def test_setup_terminal_unknown(self, mock_detect: MagicMock) -> None:
        """Test setup for unknown terminal."""
        result = setup_terminal()

        assert result.success is False
        assert result.terminal == Terminal.UNKNOWN
        assert "Could not detect terminal" in result.message


class TestSetupResult:
    """Test SetupResult dataclass."""

    def test_setup_result_default_values(self) -> None:
        """Test SetupResult with default values."""
        result = SetupResult(success=True, terminal=Terminal.VSCODE, message="Test")

        assert result.success is True
        assert result.terminal == Terminal.VSCODE
        assert result.message == "Test"
        assert result.requires_restart is False

    def test_setup_result_with_requires_restart(self) -> None:
        """Test SetupResult with requires_restart=True."""
        result = SetupResult(
            success=True,
            terminal=Terminal.VSCODE,
            message="Test",
            requires_restart=True,
        )

        assert result.requires_restart is True
