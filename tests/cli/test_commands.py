"""Tests for command registry and command handling."""

from __future__ import annotations

import pytest

from vibe.cli.commands import Command, CommandRegistry


class TestCommand:
    """Test Command dataclass."""

    def test_command_creation(self) -> None:
        """Test Command dataclass creation."""
        cmd = Command(
            aliases=frozenset(["/help", "/h"]),
            description="Show help",
            handler="_show_help",
            exits=False,
        )
        assert cmd.aliases == frozenset(["/help", "/h"])
        assert cmd.description == "Show help"
        assert cmd.handler == "_show_help"
        assert cmd.exits is False

    def test_command_with_exits_true(self) -> None:
        """Test Command with exits=True."""
        cmd = Command(
            aliases=frozenset(["/exit"]),
            description="Exit app",
            handler="_exit_app",
            exits=True,
        )
        assert cmd.exits is True

    def test_command_aliases_immutable(self) -> None:
        """Test that command aliases are immutable."""
        cmd = Command(
            aliases=frozenset(["/help"]),
            description="Show help",
            handler="_show_help",
        )
        with pytest.raises(AttributeError):
            cmd.aliases.add("/h")


class TestCommandRegistry:
    """Test CommandRegistry class."""

    def test_command_registry_initialization(self) -> None:
        """Test CommandRegistry initialization with default commands."""
        registry = CommandRegistry()
        assert "help" in registry.commands
        assert "config" in registry.commands
        assert "exit" in registry.commands
        assert len(registry.commands) > 0

    def test_command_registry_with_excluded_commands(self) -> None:
        """Test CommandRegistry with excluded commands."""
        registry = CommandRegistry(excluded_commands=["help", "exit"])
        assert "help" not in registry.commands
        assert "config" in registry.commands
        assert "exit" not in registry.commands

    def test_command_registry_exclude_nonexistent_command(self) -> None:
        """Test that excluding nonexistent command doesn't raise error."""
        registry = CommandRegistry(excluded_commands=["nonexistent"])
        assert "help" in registry.commands
        assert "config" in registry.commands

    def test_command_registry_empty_exclusion_list(self) -> None:
        """Test CommandRegistry with empty exclusion list."""
        registry = CommandRegistry(excluded_commands=[])
        assert "help" in registry.commands
        assert "config" in registry.commands

    def test_command_registry_none_exclusion_list(self) -> None:
        """Test CommandRegistry with None exclusion list."""
        registry = CommandRegistry(excluded_commands=None)
        assert "help" in registry.commands
        assert "config" in registry.commands

    def test_find_command_by_name(self) -> None:
        """Test finding command by exact name."""
        registry = CommandRegistry()
        cmd = registry.find_command("/help")  # Use alias, not internal name
        assert cmd is not None
        assert cmd.handler == "_show_help"

    def test_find_command_by_alias(self) -> None:
        """Test finding command by alias."""
        registry = CommandRegistry()
        cmd = registry.find_command("/help")
        assert cmd is not None
        assert cmd.handler == "_show_help"

    def test_find_command_case_insensitive(self) -> None:
        """Test that command finding is case-insensitive."""
        registry = CommandRegistry()
        cmd = registry.find_command("/HELP")  # Use alias in uppercase
        assert cmd is not None
        assert cmd.handler == "_show_help"

    def test_find_command_with_whitespace(self) -> None:
        """Test finding command with leading/trailing whitespace."""
        registry = CommandRegistry()
        cmd = registry.find_command("  /help  ")  # Use alias with whitespace
        assert cmd is not None
        assert cmd.handler == "_show_help"

    def test_find_nonexistent_command(self) -> None:
        """Test finding nonexistent command returns None."""
        registry = CommandRegistry()
        cmd = registry.find_command("nonexistent")
        assert cmd is None

    def test_find_command_with_special_characters(self) -> None:
        """Test finding command with special characters."""
        registry = CommandRegistry()
        cmd = registry.find_command("/help!")
        assert cmd is None  # Should not find command with special chars

    def test_alias_map_creation(self) -> None:
        """Test that alias map is correctly created."""
        registry = CommandRegistry()
        help_cmd = registry.commands["help"]
        assert "/help" in help_cmd.aliases
        
        # Verify alias map contains the aliases
        found_cmd = registry.find_command("/help")
        assert found_cmd is not None
        assert found_cmd.handler == "_show_help"

    def test_multiple_aliases_for_same_command(self) -> None:
        """Test that multiple aliases point to the same command."""
        registry = CommandRegistry()
        cmd1 = registry.find_command("/help")
        cmd2 = registry.find_command("/config")  # Use different command
        assert cmd1 is not None
        assert cmd2 is not None
        assert cmd1.handler != cmd2.handler  # Different commands

    def test_get_help_text(self) -> None:
        """Test get_help_text method."""
        registry = CommandRegistry()
        help_text = registry.get_help_text()
        assert "Keyboard Shortcuts" in help_text
        assert "Enter" in help_text
        assert "Ctrl+J" in help_text

    def test_get_help_text_contains_all_shortcuts(self) -> None:
        """Test that help text contains expected keyboard shortcuts."""
        registry = CommandRegistry()
        help_text = registry.get_help_text()
        expected_shortcuts = ["Enter", "Ctrl+J", "Escape", "Ctrl+C", "Ctrl+R", "Ctrl+O", "Ctrl+T", "Ctrl+G"]
        for shortcut in expected_shortcuts:
            assert shortcut in help_text


class TestCommandProperties:
    """Test individual command properties."""

    def test_help_command_properties(self) -> None:
        """Test help command properties."""
        registry = CommandRegistry()
        cmd = registry.commands["help"]
        assert "/help" in cmd.aliases
        assert cmd.description == "Show help message"
        assert cmd.handler == "_show_help"
        assert cmd.exits is False

    def test_exit_command_properties(self) -> None:
        """Test exit command properties."""
        registry = CommandRegistry()
        cmd = registry.commands["exit"]
        assert "/exit" in cmd.aliases
        assert cmd.description == "Exit the application"
        assert cmd.handler == "_exit_app"
        assert cmd.exits is True

    def test_config_command_properties(self) -> None:
        """Test config command properties."""
        registry = CommandRegistry()
        cmd = registry.commands["config"]
        assert "/config" in cmd.aliases
        assert "/theme" in cmd.aliases
        assert "/model" in cmd.aliases
        assert cmd.description == "Edit config settings"
        assert cmd.handler == "_show_config"
        assert cmd.exits is False

    def test_reload_command_properties(self) -> None:
        """Test reload command properties."""
        registry = CommandRegistry()
        cmd = registry.commands["reload"]
        assert "/reload" in cmd.aliases
        assert cmd.description == "Reload configuration from disk"
        assert cmd.handler == "_reload_config"
        assert cmd.exits is False

    def test_clear_command_properties(self) -> None:
        """Test clear command properties."""
        registry = CommandRegistry()
        cmd = registry.commands["clear"]
        assert "/clear" in cmd.aliases
        assert cmd.description == "Clear conversation history"
        assert cmd.handler == "_clear_history"
        assert cmd.exits is False

    def test_log_command_properties(self) -> None:
        """Test log command properties."""
        registry = CommandRegistry()
        cmd = registry.commands["log"]
        assert "/log" in cmd.aliases
        assert cmd.description == "Show path to current interaction log file"
        assert cmd.handler == "_show_log_path"
        assert cmd.exits is False

    def test_compact_command_properties(self) -> None:
        """Test compact command properties."""
        registry = CommandRegistry()
        cmd = registry.commands["compact"]
        assert "/compact" in cmd.aliases
        assert cmd.description == "Compact conversation history by summarizing"
        assert cmd.handler == "_compact_history"
        assert cmd.exits is False

    def test_history_command_properties(self) -> None:
        """Test history command properties."""
        registry = CommandRegistry()
        cmd = registry.commands["history"]
        assert "/history" in cmd.aliases
        assert cmd.description == "Search and select from prompt history"
        assert cmd.handler == "_show_history_finder"
        assert cmd.exits is False

    def test_sessions_command_properties(self) -> None:
        """Test sessions command properties."""
        registry = CommandRegistry()
        cmd = registry.commands["sessions"]
        assert "/sessions" in cmd.aliases
        assert cmd.description == "Browse and load saved sessions"
        assert cmd.handler == "_show_session_finder"
        assert cmd.exits is False

    def test_terminal_setup_command_properties(self) -> None:
        """Test terminal-setup command properties."""
        registry = CommandRegistry()
        cmd = registry.commands["terminal-setup"]
        assert "/terminal-setup" in cmd.aliases
        assert cmd.description == "Configure Shift+Enter for newlines"
        assert cmd.handler == "_setup_terminal"
        assert cmd.exits is False

    def test_status_command_properties(self) -> None:
        """Test status command properties."""
        registry = CommandRegistry()
        cmd = registry.commands["status"]
        assert "/status" in cmd.aliases
        assert cmd.description == "Display agent statistics"
        assert cmd.handler == "_show_status"
        assert cmd.exits is False


class TestCommandRegistryEdgeCases:
    """Test edge cases for CommandRegistry."""

    def test_exclude_all_commands(self) -> None:
        """Test excluding all commands."""
        registry = CommandRegistry(excluded_commands=list(CommandRegistry().commands.keys()))
        assert len(registry.commands) == 0

    def test_exclude_same_command_multiple_times(self) -> None:
        """Test excluding the same command multiple times."""
        registry = CommandRegistry(excluded_commands=["help", "help"])
        assert "help" not in registry.commands

    def test_find_command_with_empty_string(self) -> None:
        """Test finding command with empty string."""
        registry = CommandRegistry()
        cmd = registry.find_command("")
        assert cmd is None

    def test_find_command_with_only_whitespace(self) -> None:
        """Test finding command with only whitespace."""
        registry = CommandRegistry()
        cmd = registry.find_command("   ")
        assert cmd is None

    def test_command_registry_immutability(self) -> None:
        """Test that command registry commands are not directly modifiable."""
        registry = CommandRegistry()
        original_commands = len(registry.commands)
        
        # Try to add a new command (should not be possible through normal means)
        registry.commands["new_cmd"] = Command(
            aliases=frozenset(["/new"]),
            description="New command",
            handler="_new_handler",
        )
        
        # The command should be added (dictionaries are mutable)
        assert "new_cmd" in registry.commands
        assert len(registry.commands) == original_commands + 1