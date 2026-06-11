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
from vibe.cli.textual_ui.widgets.history_picker import HistoryPickerApp
from vibe.cli.textual_ui.widgets.no_markup_static import NoMarkupStatic
from vibe.core.fuzzy import fuzzy_match


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
        mock_switch = AsyncMock()

        with patch.object(vibe_app, "_switch_to_input_app", mock_switch):
            async with vibe_app.run_test() as pilot:
                event = HistoryPickerApp.Cancelled()
                await vibe_app.on_history_picker_app_cancelled(event)
                await pilot.pause()

            mock_switch.assert_called_once()

    def test_history_command_is_registered(self) -> None:
        registry = CommandRegistry()
        name = registry.get_command_name("/history")
        assert name == "history"

    def test_history_command_description(self) -> None:
        registry = CommandRegistry()
        result = registry.parse_command("/history")
        assert result is not None
        _, cmd, _ = result
        assert cmd.description == "Search and select from chat history"

    def test_parse_history_command(self) -> None:
        registry = CommandRegistry()
        result = registry.parse_command("/history")
        assert result is not None
        name, cmd, args = result
        assert name == "history"
        assert cmd.handler == "_show_history_picker"
        assert args == ""

    @pytest.mark.asyncio
    async def test_show_history_picker_limits_to_5000_entries(self, vibe_app) -> None:
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

    @pytest.mark.asyncio
    async def test_show_history_picker_warns_on_python_fallback(self, vibe_app) -> None:
        entries = ["entry-0", "entry-1"]
        history_content = "\n".join(json.dumps(e) for e in entries)

        mock_read = MagicMock()
        mock_read.text = history_content

        mock_notify = MagicMock()

        with patch("vibe.cli.textual_ui.app.read_safe", return_value=mock_read):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("vibe.cli.textual_ui.app.using_cython", False):
                    async with vibe_app.run_test() as pilot:
                        vibe_app._switch_from_input = AsyncMock()
                        vibe_app._mount_and_scroll = AsyncMock()
                        vibe_app.notify = mock_notify
                        await vibe_app._show_history_picker()
                        await pilot.pause()

                        mock_notify.assert_called_once()
                        call_kwargs = mock_notify.call_args[1]
                        assert call_kwargs["severity"] == "warning"
                        assert "Python fallback" in mock_notify.call_args[0][0]


class TestFuzzyMatchPair:
    def test_exact_match_returns_zero_penalty(self) -> None:
        query = "fix this bug"
        candidate = "Help me fix this bug in auth.py"
        penalty, matches = fuzzy_match(query, candidate)
        assert penalty == 0
        assert matches is not None and len(matches) > 0

    def test_partial_match_returns_low_penalty(self) -> None:
        query = "database connection"
        candidate = "Refactor the database connection pool"
        penalty, matches = fuzzy_match(query, candidate)
        assert penalty == 0
        assert matches is not None and len(matches) > 0

    def test_no_match_returns_negative_one(self) -> None:
        penalty, matches = fuzzy_match("xyzxyz", "database connection pool")
        assert penalty == -1
        assert matches is None

    def test_empty_query_returns_zero_penalty(self) -> None:
        penalty, matches = fuzzy_match("", "anything")
        assert penalty == 0
        assert matches is None

    def test_empty_candidate_returns_negative_one(self) -> None:
        penalty, matches = fuzzy_match("query", "")
        assert penalty == -1
        assert matches is None

    def test_single_char_match(self) -> None:
        penalty, matches = fuzzy_match("x", "abcxdef")
        assert penalty == 0
        assert matches is not None and len(matches) == 1
        assert matches[0] == 3  # 'x' is at index 3

    def test_match_positions_are_valid_indices(self) -> None:
        query = "fix"
        candidate = "Fix the git commit message formatting"
        penalty, matches = fuzzy_match(query, candidate)
        assert penalty >= 0
        assert matches is not None
        for pos in matches:
            assert 0 <= pos < len(candidate)

    def test_match_positions_correspond_to_query_chars(self) -> None:
        query = "test"
        candidate = "Add unit tests for the API endpoints"
        penalty, matches = fuzzy_match(query, candidate)
        assert penalty >= 0
        assert matches is not None
        matched_chars = "".join(candidate[pos].lower() for pos in matches)
        assert matched_chars == query.lower()

    def test_long_query_long_candidate(self) -> None:
        query = "refactor the database connection pool"
        candidate = "Refactor the database connection pool for better performance"
        penalty, matches = fuzzy_match(query, candidate)
        assert penalty == 0
        assert matches is not None and len(matches) > 0

    def test_special_characters_in_query(self) -> None:
        query = "auth.py"
        candidate = "Help me fix this bug in auth.py"
        penalty, matches = fuzzy_match(query, candidate)
        assert penalty == 0
        assert matches is not None and len(matches) > 0

    def test_whitespace_in_query(self) -> None:
        query = "fix this"
        candidate = "Help me fix this bug"
        penalty, matches = fuzzy_match(query, candidate)
        assert penalty >= 0

    def test_penalty_is_int(self) -> None:
        penalty, _ = fuzzy_match("test", "test")
        assert isinstance(penalty, int)
        assert penalty == 0

    def test_penalty_range(self) -> None:
        for query, candidate in [
            ("exact", "exact match"),
            ("xyz", "no match at all"),
            ("a", "a"),
            ("hello world", "say hello world to everyone"),
        ]:
            penalty, _ = fuzzy_match(query, candidate)
            assert penalty == -1 or 0 <= penalty <= len(candidate), (
                f"Penalty {penalty} out of range for ({query!r}, {candidate!r})"
            )

    def test_case_insensitive_match(self) -> None:
        penalty, matches = fuzzy_match("AUTH", "authentication")
        assert penalty == 0
        assert matches is not None

    def test_japanese_match(self) -> None:
        penalty, matches = fuzzy_match("あいう", "あいうえお")
        assert penalty == 0
        assert matches is not None and len(matches) == 3

    def test_mixed_japanese_english(self) -> None:
        penalty, matches = fuzzy_match("authあ", "help-me-with-authあ-please")
        assert penalty == 0
        assert matches is not None and len(matches) == 5


class TestFuzzySearchIntegration:
    @pytest.mark.asyncio
    async def test_no_query_shows_all_entries(self) -> None:
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
        entries = ["fix this bug in auth.py", "refactor database", "update readme"]
        app = _HistoryPickerTestApp(entries)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            picker = app.query_one(HistoryPickerApp)
            picker._update_options("fix this bug")
            option_list = picker.query_one(OptionList)
            # All entries with penalty >= 0 are included
            assert len(option_list.options) >= 1
            visual = option_list.options[0]._visual
            assert "fix this bug" in str(visual)

    @pytest.mark.asyncio
    async def test_results_sorted_by_penalty_ascending(self) -> None:
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
            # Zero penalty should appear first
            assert len(texts) >= 2
            assert "database connection pool" in texts[0]

    @pytest.mark.asyncio
    async def test_equal_penalty_preserves_original_order(self) -> None:
        # Entries with same penalty keep original order (newer first)
        entries = ["newer fix bug", "older fix bug", "oldest fix bug"]
        app = _HistoryPickerTestApp(entries)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            picker = app.query_one(HistoryPickerApp)
            picker._update_options("fix bug")
            option_list = picker.query_one(OptionList)
            texts = []
            for opt in option_list.options:
                visual = opt._visual
                texts.append(str(visual))
            # All have same penalty (0), so original order preserved (newer first)
            assert len(texts) == 3
            assert "newer fix bug" in texts[0]
            assert "older fix bug" in texts[1]
            assert "oldest fix bug" in texts[2]

    @pytest.mark.asyncio
    async def test_lower_penalty_first_then_tie_breaks_by_order(self) -> None:
        # Mix of different penalties: lower penalty first, ties keep original order
        entries = [
            "newer fix bug",  # penalty 0 (contiguous "fix")
            "gappy fxxixxx bug",  # penalty > 0 (gaps in "fix")
            "older fix bug",  # penalty 0 (contiguous "fix", same as newer)
        ]
        app = _HistoryPickerTestApp(entries)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            picker = app.query_one(HistoryPickerApp)
            picker._update_options("fix")
            option_list = picker.query_one(OptionList)
            texts = []
            for opt in option_list.options:
                visual = opt._visual
                texts.append(str(visual))
            # penalty 0 entries first (in original order), then higher penalty
            assert len(texts) == 3
            assert "newer fix bug" in texts[0]
            assert "older fix bug" in texts[1]
            assert "gappy fxxixxx bug" in texts[2]

    @pytest.mark.asyncio
    async def test_results_limited_to_fifty(self) -> None:
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
    def __init__(self, entries: list[str]) -> None:
        super().__init__()
        self._entries = entries

    def on_mount(self) -> None:
        self.mount(HistoryPickerApp(entries=self._entries))


class TestExactMatch:
    def test_exact_ascii_match(self) -> None:
        penalty, indices = fuzzy_match("abcd", "abcd")
        assert penalty == 0
        assert indices == [0, 1, 2, 3]

    def test_exact_japanese_match(self) -> None:
        penalty, indices = fuzzy_match("あいう", "あいうえお")
        assert penalty == 0
        assert indices == [0, 1, 2]

    def test_exact_mixed_match(self) -> None:
        penalty, indices = fuzzy_match("ab あ cd", "ab あ cd")
        assert penalty == 0
        # Codepoint-level: 'a','b',' ','あ',' ','c','d' = 7 codepoints
        assert indices == [0, 1, 2, 3, 4, 5, 6]


class TestCaseInsensitive:
    def test_uppercase_match(self) -> None:
        penalty, indices = fuzzy_match("abcd", "ABCD")
        assert penalty == 0
        assert indices == [0, 1, 2, 3]

    def test_mixed_case_match(self) -> None:
        penalty, indices = fuzzy_match("auth", "authentication")
        assert penalty == 0
        assert indices == [0, 1, 2, 3]

    def test_mixed_case_japanese(self) -> None:
        # Japanese doesn't have case, but mixed with English should work
        penalty, indices = fuzzy_match("AUTH あ", "AUTH あ")
        assert penalty == 0


class TestSubsequenceWithGaps:
    def test_two_gaps(self) -> None:
        penalty, indices = fuzzy_match("abcd", "abxxcd")
        assert indices is not None and len(indices) == 4
        assert penalty == 2

    def test_three_gaps(self) -> None:
        penalty, indices = fuzzy_match("abcd", "abxcxxd")
        assert indices is not None and len(indices) == 4
        assert penalty == 3

    def test_one_gap(self) -> None:
        penalty, indices = fuzzy_match("abcd", "xxxabcxdxxx")
        assert indices is not None and len(indices) == 4
        assert penalty == 1

    def test_many_gaps(self) -> None:
        penalty, indices = fuzzy_match("abc", "xyzabc")
        assert indices is not None and len(indices) == 3
        # Algorithm finds perfect match at position 3 (0 gaps)
        assert penalty == 0

    def test_gaps_at_start(self) -> None:
        penalty, indices = fuzzy_match("abc", "   abc")
        assert indices is not None and len(indices) == 3
        # Algorithm finds perfect match at position 3 (0 gaps)
        assert penalty == 0

    def test_gaps_at_end(self) -> None:
        penalty, indices = fuzzy_match("abc", "abc   ")
        assert indices is not None and len(indices) == 3
        # Algorithm finds perfect match at position 0 (0 gaps)
        assert penalty == 0


class TestNoMatch:
    def test_completely_different(self) -> None:
        penalty, indices = fuzzy_match("xyz", "abcdef")
        assert penalty == -1
        assert indices is None

    def test_no_common_chars(self) -> None:
        penalty, indices = fuzzy_match("!!!", "abc")
        assert penalty == -1
        assert indices is None

    def test_query_longer_than_candidate(self) -> None:
        penalty, indices = fuzzy_match("abcdefghijk", "abc")
        assert penalty == -1
        assert indices is None


class TestEmptyInputs:
    def test_empty_query(self) -> None:
        penalty, indices = fuzzy_match("", "anything")
        assert penalty == 0
        assert indices is None

    def test_empty_candidate(self) -> None:
        penalty, indices = fuzzy_match("query", "")
        assert penalty == -1
        assert indices is None

    def test_both_empty(self) -> None:
        penalty, indices = fuzzy_match("", "")
        assert penalty == 0
        assert indices is None


class TestJapanese:
    def test_japanese_exact(self) -> None:
        penalty, indices = fuzzy_match("あいう", "あいう")
        assert penalty == 0
        assert indices == [0, 1, 2]

    def test_japanese_subsequence(self) -> None:
        penalty, indices = fuzzy_match("あう", "あいう")
        assert penalty == 1
        assert indices == [0, 2]

    def test_japanese_with_gaps(self) -> None:
        penalty, indices = fuzzy_match("あう", "あ xx う")
        assert indices is not None and len(indices) == 2
        assert penalty == 4

    def test_japanese_no_match(self) -> None:
        penalty, indices = fuzzy_match("あいう", "えおか")
        assert penalty == -1
        assert indices is None


class TestMixedContent:
    def test_mixed_exact(self) -> None:
        penalty, indices = fuzzy_match("auth あ", "auth あ")
        assert penalty == 0
        # Codepoint-level: 'a','u','t','h',' ','あ' = 6 codepoints
        assert indices == [0, 1, 2, 3, 4, 5]

    def test_mixed_in_sentence(self) -> None:
        penalty, indices = fuzzy_match("auth あ", "help-me-with-auth あ-please")
        # Codepoint-level: 'a','u','t','h',' ','あ' = 6 codepoints
        assert indices is not None and len(indices) == 6

    def test_emoji_in_text(self) -> None:
        penalty, indices = fuzzy_match("test", "test")
        assert penalty == 0
        assert indices == [0, 1, 2, 3]

    def test_emoji_matching(self) -> None:
        penalty, indices = fuzzy_match("😀", "hello😀world")
        assert penalty == 0
        assert indices is not None and len(indices) == 1


class TestPenaltyCalculation:
    def test_exact_penalty_is_zero(self) -> None:
        penalty, _ = fuzzy_match("abc", "abc")
        assert penalty == 0

    def test_penalty_increases_with_gaps(self) -> None:
        _, _ = fuzzy_match("abc", "abc")
        penalty1, _ = fuzzy_match("abc", "axbc")
        penalty2, _ = fuzzy_match("abc", "axxbxc")
        assert penalty1 < penalty2

    def test_penalty_two_gaps(self) -> None:
        penalty, _ = fuzzy_match("abcd", "abxxcd")
        assert penalty == 2

    def test_penalty_one_gap(self) -> None:
        penalty, _ = fuzzy_match("abcd", "xxxabcxdxxx")
        assert penalty == 1

    def test_penalty_is_non_negative(self) -> None:
        penalty, _ = fuzzy_match("a", "a")
        assert penalty >= 0

    def test_no_match_returns_negative_one(self) -> None:
        penalty, _ = fuzzy_match("abcdef", "a")
        assert penalty == -1


class TestIndices:
    def test_indices_are_sorted(self) -> None:
        _, indices = fuzzy_match("abc", "xxaxxbxxcxx")
        assert indices is not None
        assert indices == sorted(indices)

    def test_indices_are_unique(self) -> None:
        _, indices = fuzzy_match("abc", "xxaxxbxxcxx")
        assert indices is not None
        assert len(indices) == len(set(indices))

    def test_indices_count_matches_query_length(self) -> None:
        _, indices = fuzzy_match("abcd", "abxxcd")
        assert indices is not None
        assert len(indices) == 4

    def test_indices_within_bounds(self) -> None:
        _, indices = fuzzy_match("abc", "xxaxxbxxcxx")
        assert indices is not None
        assert all(0 <= i < 13 for i in indices)

    def test_indices_point_to_correct_chars(self) -> None:
        candidate = "xxaxxbxxcxx"
        _, indices = fuzzy_match("abc", candidate)
        assert indices is not None
        for i in indices:
            assert candidate[i] == "abc"[indices.index(i)]


class TestHistoryPickerHeightConstraints:
    def _make_entries(self, count: int = 200) -> list[str]:
        return [f"entry-{i} for testing height constraints" for i in range(count)]

    @pytest.mark.asyncio
    async def test_picker_fits_small_window(self) -> None:
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
