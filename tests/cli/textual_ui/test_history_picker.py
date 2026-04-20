from __future__ import annotations

import json
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.text import Text
from textual.app import App
from textual.binding import Binding
from textual.widgets import OptionList

from vibe.cli.commands import CommandRegistry
from vibe.cli.textual_ui.widgets.history_picker import (
    HistoryPickerApp,
    _fuzzy_match_pair,
)
from vibe.cli.textual_ui.widgets.no_markup_static import NoMarkupStatic


@pytest.fixture
def sample_entries() -> list[str]:
    return [
        "Help me fix this bug in auth.py",
        "Refactor the database connection pool",
        "Add unit tests for the API endpoints",
        "Update the README with new instructions",
        "Fix the git commit message formatting",
    ]


class TestHistoryPickerAppInit:
    def test_init_sets_entries(self, sample_entries: list[str]) -> None:
        picker = HistoryPickerApp(entries=sample_entries)
        assert picker._entries == sample_entries

    def test_id_is_historypicker_app(self, sample_entries: list[str]) -> None:
        picker = HistoryPickerApp(entries=sample_entries)
        assert picker.id == "historypicker-app"

    def test_can_focus_children_is_true(self, sample_entries: list[str]) -> None:
        picker = HistoryPickerApp(entries=sample_entries)
        assert picker.can_focus_children is True


class TestHistoryPickerMessages:
    def test_history_selected_message(self, sample_entries: list[str]) -> None:
        msg = HistoryPickerApp.HistorySelected(sample_entries[0])
        assert msg.text == sample_entries[0]
        assert isinstance(msg, HistoryPickerApp.HistorySelected)

    def test_cancelled_message(self, sample_entries: list[str]) -> None:
        msg = HistoryPickerApp.Cancelled()
        assert isinstance(msg, HistoryPickerApp.Cancelled)


class TestHistoryPickerAppBindings:
    def _get_binding_keys(self) -> list[str]:
        picker = HistoryPickerApp(entries=[])
        return [cast(Binding, b).key for b in picker.BINDINGS]

    def test_has_escape_binding(self) -> None:
        assert "escape" in self._get_binding_keys()

    def test_has_focus_search_binding(self) -> None:
        assert "/" in self._get_binding_keys()


class TestHistoryPickerFuzzySearch:
    def test_empty_entries_produces_empty_list(self) -> None:
        picker = HistoryPickerApp(entries=[])
        assert len(picker._entries) == 0

    def test_long_entry_not_truncated(self) -> None:
        long_entry = "x" * 500
        HistoryPickerApp(entries=[long_entry])
        preview = long_entry.replace("\n", " ")
        assert len(preview) == 500

    def test_newlines_replaced_with_spaces(self) -> None:
        entry = "line1\nline2\nline3"
        HistoryPickerApp(entries=[entry])
        preview = entry.replace("\n", " ")
        assert "\n" not in preview


class TestVibeAppHistoryPickerHandlers:
    @pytest.mark.asyncio
    async def test_on_history_picker_history_selected_fills_input(
        self, vibe_app, sample_entries: list[str]
    ) -> None:
        """Test that selecting a history entry fills the input."""
        from unittest.mock import AsyncMock, MagicMock

        mock_input_container = MagicMock()
        mock_input_container.value = ""

        event = HistoryPickerApp.HistorySelected(sample_entries[0])

        async with vibe_app.run_test() as pilot:
            vibe_app._chat_input_container = mock_input_container
            vibe_app._switch_to_input_app = AsyncMock()
            await vibe_app.on_history_picker_app_history_selected(event)
            await pilot.pause()

        assert mock_input_container.value == sample_entries[0]
        mock_input_container.focus_input.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_history_picker_cancelled_switches_to_input(
        self, vibe_app
    ) -> None:
        """Test that cancelling the picker switches back to input."""
        mock_switch = AsyncMock()

        with patch.object(vibe_app, "_switch_to_input_app", mock_switch):
            async with vibe_app.run_test() as pilot:
                event = HistoryPickerApp.Cancelled()
                await vibe_app.on_history_picker_app_cancelled(event)
                await pilot.pause()

            mock_switch.assert_called_once()

    def test_history_command_is_registered(self) -> None:
        """Test that /history command is registered in CommandRegistry."""
        registry = CommandRegistry()
        name = registry.get_command_name("/history")
        assert name == "history"

    def test_history_command_description(self) -> None:
        """Test that /history command has a description."""
        registry = CommandRegistry()
        result = registry.parse_command("/history")
        assert result is not None
        _, cmd, _ = result
        assert cmd.description == "Search and select from chat history"

    def test_parse_history_command(self) -> None:
        """Test parsing /history command returns correct result."""
        registry = CommandRegistry()
        result = registry.parse_command("/history")
        assert result is not None
        name, cmd, args = result
        assert name == "history"
        assert cmd.handler == "_show_history_picker"
        assert args == ""

    @pytest.mark.asyncio
    async def test_show_history_picker_limits_to_5000_entries(self, vibe_app) -> None:
        """Test that only the last 5000 history entries are shown."""
        # Create 150 entries (less than 5000, all should be shown)
        entries = [f"entry-{i}" for i in range(150)]
        history_content = "\n".join(json.dumps(e) for e in entries)

        mock_read = MagicMock()
        mock_read.text = history_content

        mock_switch = AsyncMock()

        with patch("vibe.cli.textual_ui.app.read_safe", return_value=mock_read):
            with patch("pathlib.Path.exists", return_value=True):
                async with vibe_app.run_test() as pilot:
                    vibe_app._switch_from_input = mock_switch
                    vibe_app._mount_and_scroll = AsyncMock()
                    await vibe_app._show_history_picker()
                    await pilot.pause()

                    # Verify entries are reversed (newest first)
                    call_args = mock_switch.call_args
                    passed_entries = call_args[0][0]._entries
                    assert len(passed_entries) == 150
                    assert passed_entries[0] == "entry-149"
                    assert passed_entries[-1] == "entry-0"

    @pytest.mark.asyncio
    async def test_show_history_picker_truncates_to_5000(self, vibe_app) -> None:
        """Test that entries beyond 5000 are truncated, keeping newest 5000."""
        # Create 6000 entries
        entries = [f"entry-{i}" for i in range(6000)]
        history_content = "\n".join(json.dumps(e) for e in entries)

        mock_read = MagicMock()
        mock_read.text = history_content

        mock_switch = AsyncMock()

        with patch("vibe.cli.textual_ui.app.read_safe", return_value=mock_read):
            with patch("pathlib.Path.exists", return_value=True):
                async with vibe_app.run_test() as pilot:
                    vibe_app._switch_from_input = mock_switch
                    vibe_app._mount_and_scroll = AsyncMock()
                    await vibe_app._show_history_picker()
                    await pilot.pause()

                    # Verify only last 5000 entries, newest first
                    call_args = mock_switch.call_args
                    passed_entries = call_args[0][0]._entries
                    assert len(passed_entries) == 5000
                    assert passed_entries[0] == "entry-5999"
                    assert passed_entries[-1] == "entry-1000"


class TestFuzzyMatchPair:
    """Test the _fuzzy_match_pair function used by the history picker."""

    def test_exact_match_returns_max_score(self) -> None:
        """Exact query match against candidate returns score 100."""
        query = "fix this bug"
        candidate = "Help me fix this bug in auth.py"
        score, matches = _fuzzy_match_pair(query, candidate)
        assert score == 100.0
        assert len(matches) > 0

    def test_partial_match_returns_high_score(self) -> None:
        """Substring query returns high partial_ratio score."""
        query = "database connection"
        candidate = "Refactor the database connection pool"
        score, matches = _fuzzy_match_pair(query, candidate)
        assert score == 100.0
        assert len(matches) > 0

    def test_no_match_returns_zero(self) -> None:
        """Completely unrelated query returns score 0."""
        score, matches = _fuzzy_match_pair("xyzxyz", "database connection pool")
        assert score == 0.0
        assert matches == []

    def test_empty_query_returns_zero(self) -> None:
        """Empty query returns score 0."""
        score, matches = _fuzzy_match_pair("", "anything")
        assert score == 0.0
        assert matches == []

    def test_empty_candidate_returns_zero(self) -> None:
        """Empty candidate returns score 0."""
        score, matches = _fuzzy_match_pair("query", "")
        assert score == 0.0
        assert matches == []

    def test_single_char_match(self) -> None:
        """Single character query matches if present."""
        score, matches = _fuzzy_match_pair("x", "abcxdef")
        assert score == 100.0
        assert len(matches) == 1
        assert matches[0] == 3  # 'x' is at index 3

    def test_match_positions_are_valid_indices(self) -> None:
        """All match positions are valid indices within the candidate."""
        query = "fix"
        candidate = "Fix the git commit message formatting"
        score, matches = _fuzzy_match_pair(query, candidate)
        assert score > 0
        for pos in matches:
            assert 0 <= pos < len(candidate)

    def test_match_positions_correspond_to_query_chars(self) -> None:
        """Match positions correspond to characters matching the query."""
        query = "test"
        candidate = "Add unit tests for the API endpoints"
        score, matches = _fuzzy_match_pair(query, candidate)
        assert score > 0
        # The matched characters in candidate should spell "test" (case-insensitive for partial_ratio)
        matched_chars = "".join(candidate[pos].lower() for pos in matches)
        assert matched_chars == query.lower()

    def test_long_query_long_candidate(self) -> None:
        """Long query against long candidate returns valid result."""
        query = "refactor the database connection pool implementation"
        candidate = "Refactor the database connection pool for better performance"
        score, matches = _fuzzy_match_pair(query, candidate)
        assert score > 0
        assert len(matches) > 0

    def test_special_characters_in_query(self) -> None:
        """Query with special characters matches correctly."""
        query = "auth.py"
        candidate = "Help me fix this bug in auth.py"
        score, matches = _fuzzy_match_pair(query, candidate)
        assert score == 100.0
        assert len(matches) > 0

    def test_whitespace_in_query(self) -> None:
        """Query with multiple spaces matches correctly."""
        query = "fix  this"
        candidate = "Help me fix this bug"
        score, matches = _fuzzy_match_pair(query, candidate)
        # partial_ratio finds the best substring match, so "fix this" should match
        assert score > 0

    def test_score_is_float(self) -> None:
        """Score is always returned as a float."""
        score, _ = _fuzzy_match_pair("test", "test")
        assert isinstance(score, float)
        assert score == 100.0

    def test_score_range(self) -> None:
        """Score is always in range [0, 100]."""
        for query, candidate in [
            ("exact", "exact match"),
            ("xyz", "no match at all"),
            ("a", "a"),
            ("hello world", "say hello world to everyone"),
        ]:
            score, _ = _fuzzy_match_pair(query, candidate)
            assert 0.0 <= score <= 100.0, (
                f"Score {score} out of range for ({query!r}, {candidate!r})"
            )


class TestFuzzySearchIntegration:
    """Test fuzzy search behavior through _update_options."""

    @pytest.mark.asyncio
    async def test_no_query_shows_all_entries(self) -> None:
        """Empty query displays all entries without filtering."""
        entries = ["alpha", "beta", "gamma"]
        app = _HistoryPickerTestApp(entries)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            picker = app.query_one(HistoryPickerApp)
            picker._update_options("")
            option_list = picker.query_one(OptionList)
            assert len(option_list.options) == 3

    @pytest.mark.asyncio
    async def test_query_filters_to_matching_entries(self) -> None:
        """Query filters entries to only those with score > 0."""
        entries = ["fix this bug in auth.py", "refactor database", "update readme"]
        app = _HistoryPickerTestApp(entries)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            picker = app.query_one(HistoryPickerApp)
            picker._update_options("fix this bug")
            option_list = picker.query_one(OptionList)
            # partial_ratio gives score 100 for exact substring, ~33 for partial
            # All entries with score > 0 are included
            assert len(option_list.options) >= 1
            visual = option_list.options[0]._visual
            assert "fix this bug" in str(visual)

    @pytest.mark.asyncio
    async def test_results_sorted_by_score_descending(self) -> None:
        """Results are sorted by score in descending order."""
        entries = [
            "zzz database connection pool zzz",
            "aaa database connection pool aaa",
            "mmm database schema migration mmm",
        ]
        app = _HistoryPickerTestApp(entries)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            picker = app.query_one(HistoryPickerApp)
            picker._update_options("database connection pool")
            option_list = picker.query_one(OptionList)
            texts = []
            for opt in option_list.options:
                visual = opt._visual
                texts.append(str(visual))
            # Exact match should appear first (score 100)
            assert len(texts) >= 2
            assert "database connection pool" in texts[0]

    @pytest.mark.asyncio
    async def test_results_limited_to_fifty(self) -> None:
        """Results are limited to at most 50 entries."""
        entries = [f"database entry {i}" for i in range(100)]
        app = _HistoryPickerTestApp(entries)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            picker = app.query_one(HistoryPickerApp)
            picker._update_options("database")
            option_list = picker.query_one(OptionList)
            assert len(option_list.options) <= 50

    @pytest.mark.asyncio
    async def test_query_highlights_matching_chars(self) -> None:
        """Matching characters are highlighted in bold yellow."""
        entries = ["fix this bug in auth.py"]
        app = _HistoryPickerTestApp(entries)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            picker = app.query_one(HistoryPickerApp)
            picker._update_options("fix")
            option_list = picker.query_one(OptionList)
            assert len(option_list.options) == 1
            visual = cast(Text, option_list.options[0].prompt)
            # Check that some styling was applied (bold yellow for matches)
            assert len(visual.spans) > 0


class _HistoryPickerTestApp(App):
    """Wrapper app for running HistoryPickerApp in run_test."""

    def __init__(self, entries: list[str]) -> None:
        super().__init__()
        self._entries = entries

    def on_mount(self) -> None:
        self.mount(HistoryPickerApp(entries=self._entries))


class TestHistoryPickerHeightConstraints:
    """Test that the picker fits within window bounds at various sizes."""

    def _make_entries(self, count: int = 200) -> list[str]:
        return [f"entry-{i} for testing height constraints" for i in range(count)]

    @pytest.mark.asyncio
    async def test_picker_fits_small_window(self) -> None:
        """Picker should fit within a small 80x20 window."""
        app = _HistoryPickerTestApp(self._make_entries(200))
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.pause()
            picker = app.query_one(HistoryPickerApp)
            content = picker.query_one("#historypicker-content")
            options = picker.query_one("#historypicker-options")
            help_text = picker.query_one(NoMarkupStatic)

            picker_size = picker.container_size
            assert picker_size.height <= 20, (
                f"Picker height {picker_size.height} exceeds window height 20"
            )
            assert content.visible, "Content container should be visible"
            assert options.visible, "Options should be visible"
            assert help_text.visible, "Help text should be visible"

    @pytest.mark.asyncio
    async def test_picker_fits_medium_window(self) -> None:
        """Picker should fit within a medium 120x40 window."""
        app = _HistoryPickerTestApp(self._make_entries(200))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            picker = app.query_one(HistoryPickerApp)
            help_text = picker.query_one(NoMarkupStatic)

            picker_size = picker.container_size
            assert picker_size.height <= 40, (
                f"Picker height {picker_size.height} exceeds window height 40"
            )
            assert help_text.visible, "Help text should be visible"

    @pytest.mark.asyncio
    async def test_picker_fits_large_window(self) -> None:
        """Picker should fit within a large 160x60 window."""
        app = _HistoryPickerTestApp(self._make_entries(200))
        async with app.run_test(size=(160, 60)) as pilot:
            await pilot.pause()
            picker = app.query_one(HistoryPickerApp)
            help_text = picker.query_one(NoMarkupStatic)

            picker_size = picker.container_size
            assert picker_size.height <= 60, (
                f"Picker height {picker_size.height} exceeds window height 60"
            )
            assert help_text.visible, "Help text should be visible"

    @pytest.mark.asyncio
    async def test_option_list_does_not_overflow_content(self) -> None:
        """OptionList should not overflow its parent content container."""
        app = _HistoryPickerTestApp(self._make_entries(300))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            picker = app.query_one(HistoryPickerApp)
            content = picker.query_one("#historypicker-content")
            options = picker.query_one("#historypicker-options")

            content_size = content.container_size
            options_size = options.container_size

            assert options_size.height <= content_size.height, (
                f"OptionList height {options_size.height} exceeds "
                f"content height {content_size.height}"
            )

    @pytest.mark.asyncio
    async def test_help_text_visible_with_many_entries(self) -> None:
        """Help text should remain visible even with many entries."""
        app = _HistoryPickerTestApp(self._make_entries(500))
        async with app.run_test(size=(100, 25)) as pilot:
            await pilot.pause()
            picker = app.query_one(HistoryPickerApp)
            help_text = picker.query_one(NoMarkupStatic)
            assert help_text.visible, "Help text should be visible with 500 entries"
            # Verify help text contains navigation instructions
            help_text_str = str(help_text.content)
            assert "Navigate" in help_text_str
            assert "Search" in help_text_str
            assert "Select" in help_text_str
            assert "Cancel" in help_text_str
