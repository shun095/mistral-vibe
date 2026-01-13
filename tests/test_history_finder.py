"""Tests for the history finder feature."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from vibe.cli.history_manager import HistoryManager
from vibe.cli.textual_ui.widgets.history_finder import HistoryFinderApp, HistoryEntry
from vibe.core.autocompletion.fuzzy import fuzzy_match


class TestHistoryEntry:
    """Test the HistoryEntry class."""

    def test_short_text(self) -> None:
        """Test that short text is not truncated."""
        entry = HistoryEntry("Short text")
        assert entry.display_text == "Short text"
        assert entry.text == "Short text"

    def test_long_text_no_truncation(self) -> None:
        """Test that long text is not truncated."""
        long_text = "A" * 150  # 150 characters
        entry = HistoryEntry(long_text)
        assert entry.display_text == long_text
        assert entry.text == long_text  # Original should be preserved

    def test_exact_length_text(self) -> None:
        """Test text that is exactly 100 characters."""
        exact_text = "A" * 100
        entry = HistoryEntry(exact_text)
        assert entry.display_text == exact_text
        assert not entry.display_text.endswith("...")


class TestHistoryFinderApp:
    """Test the HistoryFinderApp class."""

    def test_load_history_empty_file(self, tmp_path: Path) -> None:
        """Test loading from an empty history file."""
        empty_file = tmp_path / "empty_history.jsonl"
        empty_file.touch()

        history_manager = HistoryManager(empty_file)
        app = HistoryFinderApp(history_manager)
        assert len(app._entries) == 0
        assert len(app._filtered_entries) == 0

    def test_load_history_with_entries(self, tmp_path: Path) -> None:
        """Test loading history entries from a file."""
        history_file = tmp_path / "history.jsonl"
        test_entries = [
            "Python programming tips",
            "How to use fuzzy search",
            "Best practices for clean code",
            "Tell me about machine learning",
            "JavaScript best practices"
        ]

        # Write test entries
        with history_file.open("w", encoding="utf-8") as f:
            for entry in test_entries:
                f.write(json.dumps(entry) + "\n")

        history_manager = HistoryManager(history_file)
        app = HistoryFinderApp(history_manager)
        assert len(app._entries) == len(test_entries)
        
        # Check that entries are properly loaded
        for i, entry in enumerate(app._entries):
            assert entry.text == test_entries[i]

    def test_load_history_filters_commands(self, tmp_path: Path) -> None:
        """Test that commands (starting with /) are filtered out."""
        history_file = tmp_path / "history.jsonl"
        entries = [
            "/config",  # Should be filtered
            "Hello world",  # Should be kept
            "/history",  # Should be filtered
            "Python programming"  # Should be kept
        ]

        with history_file.open("w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        history_manager = HistoryManager(history_file)
        app = HistoryFinderApp(history_manager)
        # Should only have the non-command entries
        assert len(app._entries) == 2
        assert all(not entry.text.startswith("/") for entry in app._entries)

    def test_filter_entries_empty_search(self, tmp_path: Path) -> None:
        """Test filtering with empty search text."""
        history_file = tmp_path / "history.jsonl"
        test_entries = ["Python", "JavaScript", "Rust"]

        with history_file.open("w", encoding="utf-8") as f:
            for entry in test_entries:
                f.write(json.dumps(entry) + "\n")

        history_manager = HistoryManager(history_file)
        app = HistoryFinderApp(history_manager)
        app._filter_entries("")
        
        # Empty search should return all entries in reverse order (latest first)
        assert len(app._filtered_entries) == len(test_entries)
        # Check that entries are reversed (Rust should be first since it's the latest)
        assert app._filtered_entries[0].text == "Rust"
        assert app._filtered_entries[1].text == "JavaScript"
        assert app._filtered_entries[2].text == "Python"

    def test_filter_entries_fuzzy_match(self, tmp_path: Path) -> None:
        """Test fuzzy matching functionality."""
        history_file = tmp_path / "history.jsonl"
        test_entries = [
            "Python programming tips",
            "JavaScript best practices",
            "How to use fuzzy search",
            "Software development methodologies",
            "Machine learning basics"
        ]

        with history_file.open("w", encoding="utf-8") as f:
            for entry in test_entries:
                f.write(json.dumps(entry) + "\n")

        history_manager = HistoryManager(history_file)
        app = HistoryFinderApp(history_manager)

        # Test various search patterns
        test_cases = [
            ("py", ["Python programming tips"]),
            ("dev", ["Software development methodologies"]),
            ("search", ["How to use fuzzy search"]),
            ("best", ["JavaScript best practices"]),
        ]

        for search_term, expected_matches in test_cases:
            app._filter_entries(search_term)
            assert len(app._filtered_entries) > 0
            
            # Check that expected entry is in the results
            found_texts = [entry.text for entry in app._filtered_entries]
            for expected in expected_matches:
                assert expected in found_texts, f"Expected '{expected}' in results for '{search_term}'"

    def test_filter_entries_no_matches(self, tmp_path: Path) -> None:
        """Test filtering when no entries match."""
        history_file = tmp_path / "history.jsonl"
        test_entries = ["Python", "JavaScript", "Rust"]

        with history_file.open("w", encoding="utf-8") as f:
            for entry in test_entries:
                f.write(json.dumps(entry) + "\n")

        history_manager = HistoryManager(history_file)
        app = HistoryFinderApp(history_manager)
        app._filter_entries("xyz123")  # Should not match anything
        
        assert len(app._filtered_entries) == 0

    def test_filter_entries_case_insensitive(self, tmp_path: Path) -> None:
        """Test that fuzzy matching is case insensitive."""
        history_file = tmp_path / "history.jsonl"
        test_entries = ["Python Programming", "javaScript basics"]

        with history_file.open("w", encoding="utf-8") as f:
            for entry in test_entries:
                f.write(json.dumps(entry) + "\n")

        history_manager = HistoryManager(history_file)
        app = HistoryFinderApp(history_manager)
        
        # Search with lowercase
        app._filter_entries("python")
        assert len(app._filtered_entries) == 1
        assert app._filtered_entries[0].text == "Python Programming"
        
        # Search with uppercase
        app._filter_entries("JAVASCRIPT")
        assert len(app._filtered_entries) == 1
        assert app._filtered_entries[0].text == "javaScript basics"


class TestFuzzyMatching:
    """Test fuzzy matching functionality directly."""

    def test_exact_match(self) -> None:
        """Test exact matching."""
        result = fuzzy_match("python", "python")
        assert result.matched
        assert result.score > 0

    def test_prefix_match(self) -> None:
        """Test prefix matching gets higher score."""
        exact_result = fuzzy_match("py", "python")
        substring_result = fuzzy_match("hon", "python")
        
        assert exact_result.matched
        assert substring_result.matched
        assert exact_result.score > substring_result.score

    def test_no_match(self) -> None:
        """Test non-matching patterns."""
        result = fuzzy_match("xyz", "python")
        assert not result.matched
        assert result.score == 0

    def test_subsequence_match(self) -> None:
        """Test subsequence matching."""
        result = fuzzy_match("pto", "python")
        assert result.matched
        assert result.score > 0


class TestHistoryFinderKeybindings:
    """Test the keybindings for the history finder."""

    def test_focus_search_action(self, tmp_path: Path) -> None:
        """Test the focus_search action."""
        history_file = tmp_path / "history.jsonl"
        history_file.touch()
        
        history_manager = HistoryManager(history_file)
        app = HistoryFinderApp(history_manager)
        
        # Create mock widgets
        search_widget = Mock()
        list_widget = Mock()
        
        # Set up the mock widgets
        app._search_input = search_widget
        app._list_view = list_widget
        
        # Test focus_search action
        app.action_focus_search()
        # The action should call focus on the search input
        search_widget.focus.assert_called_once()
        list_widget.focus.assert_not_called()
        
    def test_focus_list_action(self, tmp_path: Path) -> None:
        """Test the focus_list action."""
        history_file = tmp_path / "history.jsonl"
        history_file.touch()
        
        history_manager = HistoryManager(history_file)
        app = HistoryFinderApp(history_manager)
        
        # Create mock widgets
        search_widget = Mock()
        list_widget = Mock()
        
        # Set up the mock widgets
        app._search_input = search_widget
        app._list_view = list_widget
        
        # Test focus_list action
        app.action_focus_list()
        # The action should call focus on the list view
        list_widget.focus.assert_called_once()
        search_widget.focus.assert_not_called()
        
    def test_toggle_focus_action(self, tmp_path: Path) -> None:
        """Test the toggle_focus action."""
        history_file = tmp_path / "history.jsonl"
        history_file.touch()
        
        history_manager = HistoryManager(history_file)
        app = HistoryFinderApp(history_manager)
        
        # Create mock widgets
        search_widget = Mock()
        list_widget = Mock()
        
        # Set up the mock widgets
        app._search_input = search_widget
        app._list_view = list_widget
        
        # Initially, search has focus
        search_widget.has_focus = True
        list_widget.has_focus = False
        
        # First toggle should focus the list
        app.action_toggle_focus()
        list_widget.focus.assert_called_once()
        search_widget.focus.assert_not_called()
        
        # For second test, create new mocks
        search_widget2 = Mock()
        list_widget2 = Mock()
        app._search_input = search_widget2
        app._list_view = list_widget2
        
        # Now list has focus
        search_widget2.has_focus = False
        list_widget2.has_focus = True
        
        # Second toggle should focus the search
        app.action_toggle_focus()
        search_widget2.focus.assert_called_once()
        list_widget2.focus.assert_not_called()


@pytest.fixture
def mock_history_file(tmp_path: Path) -> Path:
    """Create a mock history file for testing."""
    history_file = tmp_path / "mock_history.jsonl"
    entries = [
        "Python programming tips",
        "How to use fuzzy search effectively",
        "Best practices for clean code",
        "Tell me about machine learning",
        "JavaScript best practices",
        "Software development methodologies",
        "Web development frameworks comparison",
        "Database optimization techniques"
    ]
    
    with history_file.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
    
    return history_file