"""Tests for the history manager."""

from __future__ import annotations

from pathlib import Path

import pytest

from vibe.cli.history_manager import HistoryManager


@pytest.fixture
def temp_history_file(tmp_path: Path) -> Path:
    """Create a temporary history file."""
    return tmp_path / "test_history"


@pytest.fixture
def history_manager(temp_history_file: Path) -> HistoryManager:
    """Create a HistoryManager with a temporary file."""
    return HistoryManager(temp_history_file, max_entries=100)


class TestHistoryManagerAdd:
    """Test the add method of HistoryManager."""

    def test_add_regular_text(self, history_manager: HistoryManager) -> None:
        """Test adding regular text to history."""
        history_manager.add("hello world")
        assert history_manager._entries == ["hello world"]

    def test_add_strips_whitespace(self, history_manager: HistoryManager) -> None:
        """Test that whitespace is stripped from added text."""
        history_manager.add("  trimmed text  ")
        assert history_manager._entries == ["trimmed text"]

    def test_add_empty_text_ignored(self, history_manager: HistoryManager) -> None:
        """Test that empty text is not added."""
        history_manager.add("")
        assert history_manager._entries == []

    def test_add_whitespace_only_ignored(self, history_manager: HistoryManager) -> None:
        """Test that whitespace-only text is not added."""
        history_manager.add("   ")
        assert history_manager._entries == []

    def test_add_duplicate_ignored(self, history_manager: HistoryManager) -> None:
        """Test that duplicate entries are not added."""
        history_manager.add("first")
        history_manager.add("first")
        assert history_manager._entries == ["first"]

    def test_add_command_with_no_args_ignored(
        self, history_manager: HistoryManager
    ) -> None:
        """Test that slash commands with no arguments are ignored."""
        history_manager.add("/edit")
        assert history_manager._entries == []

        history_manager.add("/compact")
        assert history_manager._entries == []

    def test_add_command_with_args_saves_args(
        self, history_manager: HistoryManager
    ) -> None:
        """Test that slash commands save only their arguments."""
        history_manager.add("/edit my edited prompt")
        assert history_manager._entries == ["my edited prompt"]

        history_manager.add("/compact summary")
        assert history_manager._entries == ["my edited prompt", "summary"]

    def test_add_command_preserves_multiple_spaces(
        self, history_manager: HistoryManager
    ) -> None:
        """Test that multiple spaces in command args are preserved."""
        history_manager.add("/edit hello   world")
        assert history_manager._entries == ["hello   world"]

    def test_add_command_with_special_chars(
        self, history_manager: HistoryManager
    ) -> None:
        """Test that special characters in command args are preserved."""
        history_manager.add("/edit test with $VAR and `command`")
        assert history_manager._entries == ["test with $VAR and `command`"]

    def test_add_command_duplicate_args_ignored(
        self, history_manager: HistoryManager
    ) -> None:
        """Test that duplicate command arguments are not added."""
        history_manager.add("/edit same text")
        history_manager.add("/edit same text")
        assert history_manager._entries == ["same text"]

    def test_add_command_args_different_from_regular(
        self, history_manager: HistoryManager
    ) -> None:
        """Test that command args are treated same as regular text for duplicates."""
        history_manager.add("regular text")
        history_manager.add("/edit regular text")
        # Should not add duplicate
        assert history_manager._entries == ["regular text"]


class TestHistoryManagerPersistence:
    """Test that history is persisted to file."""

    def test_history_saved_to_file(
        self, history_manager: HistoryManager, temp_history_file: Path
    ) -> None:
        """Test that history is saved to file."""
        history_manager.add("entry 1")
        history_manager.add("entry 2")

        assert temp_history_file.exists()
        content = temp_history_file.read_text()
        assert "entry 1" in content
        assert "entry 2" in content

    def test_command_args_saved_to_file(
        self, history_manager: HistoryManager, temp_history_file: Path
    ) -> None:
        """Test that command arguments are saved to file (not the full command)."""
        history_manager.add("/edit my prompt")

        content = temp_history_file.read_text().strip()
        # History is saved as JSON, so quotes are expected
        assert content == '"my prompt"'
        assert "/edit" not in content

    def test_history_loaded_from_file(self, temp_history_file: Path) -> None:
        """Test that history is loaded from file on initialization."""
        # Create a history file with existing entries
        temp_history_file.write_text('{"entry": "1"}\n{"entry": "2"}\n')

        # Create new manager - should load existing history
        manager = HistoryManager(temp_history_file)
        # JSON is parsed and re-serialized with single quotes
        assert manager._entries == ["{'entry': '1'}", "{'entry': '2'}"]


class TestHistoryManagerMaxEntries:
    """Test the max_entries limit."""

    def test_max_entries_enforced(self, temp_history_file: Path) -> None:
        """Test that max_entries limit is enforced."""
        manager = HistoryManager(temp_history_file, max_entries=3)

        manager.add("entry 1")
        manager.add("entry 2")
        manager.add("entry 3")
        manager.add("entry 4")

        assert len(manager._entries) == 3
        assert manager._entries == ["entry 2", "entry 3", "entry 4"]


class TestHistoryManagerIntegration:
    """Integration tests for HistoryManager with UI-like scenarios."""

    def test_edit_command_history_integration(self, temp_history_file: Path) -> None:
        """Test that /edit command arguments are saved like user would expect.

        Simulates user workflow:
        1. User types "hello world" -> saved
        2. User types "/edit modified hello" -> "modified hello" saved
        3. User navigates history -> sees both entries
        """
        manager = HistoryManager(temp_history_file)

        # User types regular message
        manager.add("hello world")
        assert manager._entries == ["hello world"]

        # User edits with /edit command
        manager.add("/edit modified hello")
        assert manager._entries == ["hello world", "modified hello"]

        # Navigate back should get "modified hello"
        previous = manager.get_previous("")
        assert previous == "modified hello"

        # Navigate back again should get "hello world"
        previous = manager.get_previous("")
        assert previous == "hello world"

    def test_multiple_edit_commands(self, temp_history_file: Path) -> None:
        """Test multiple /edit commands are all saved correctly."""
        manager = HistoryManager(temp_history_file)

        manager.add("/edit first edit")
        manager.add("/edit second edit")
        manager.add("/edit third edit")

        assert manager._entries == ["first edit", "second edit", "third edit"]

    def test_mixed_commands_and_messages(self, temp_history_file: Path) -> None:
        """Test mixing regular messages with slash commands."""
        manager = HistoryManager(temp_history_file)

        manager.add("regular message 1")
        manager.add("/edit edited version")
        manager.add("regular message 2")
        manager.add("/compact summarize this")

        assert manager._entries == [
            "regular message 1",
            "edited version",
            "regular message 2",
            "summarize this",
        ]
