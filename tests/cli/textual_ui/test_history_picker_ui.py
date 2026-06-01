from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import Input, OptionList

from vibe.cli.textual_ui.widgets.history_picker import HistoryPickerApp


class _HistoryPickerTestApp(App):
    """Wrapper app for running HistoryPickerApp in run_test."""

    def __init__(self, entries: list[str]) -> None:
        super().__init__()
        self._entries = entries
        self._selected: list[str] = []
        self._cancelled: list[bool] = []

    def on_mount(self) -> None:
        self.mount(HistoryPickerApp(entries=self._entries))

    def on_history_picker_app_history_selected(
        self, event: HistoryPickerApp.HistorySelected
    ) -> None:
        self._selected.append(event.text)

    def on_history_picker_app_cancelled(
        self, event: HistoryPickerApp.Cancelled
    ) -> None:
        self._cancelled.append(True)


@pytest.fixture
def sample_entries() -> list[str]:
    return [
        "Help me fix this bug in auth.py",
        "Refactor the database connection pool",
        "Add unit tests for the API endpoints",
        "Update the README with new instructions",
        "Fix the git commit message formatting",
    ]


@pytest.mark.asyncio
async def test_ui_type_in_search_filters_options(sample_entries: list[str]) -> None:
    """Typing in the search input filters the option list."""
    app = _HistoryPickerTestApp(sample_entries)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        picker = app.query_one(HistoryPickerApp)
        search_input = picker.query_one(Input)
        option_list = picker.query_one(OptionList)

        await pilot.pause()
        assert len(option_list.options) == len(sample_entries)

        await pilot.press(*"auth")
        await pilot.pause()

        assert search_input.value == "auth"
        filtered = [opt for opt in option_list.options if opt.id != "_no_match"]
        assert len(filtered) >= 1
        assert "auth" in str(filtered[0]._visual).lower()


@pytest.mark.asyncio
async def test_ui_navigate_with_arrows(sample_entries: list[str]) -> None:
    """Arrow up/down navigates the option list cursor."""
    app = _HistoryPickerTestApp(sample_entries)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        picker = app.query_one(HistoryPickerApp)
        option_list = picker.query_one(OptionList)

        # Tab from search input to option list
        await pilot.press("tab")
        await pilot.pause()
        assert option_list.has_focus
        assert option_list.highlighted == 0

        await pilot.press("down")
        await pilot.pause()
        assert option_list.highlighted == 1

        await pilot.press("down")
        await pilot.pause()
        assert option_list.highlighted == 2

        await pilot.press("up")
        await pilot.pause()
        assert option_list.highlighted == 1


@pytest.mark.asyncio
async def test_ui_select_with_enter_emits_history_selected(
    sample_entries: list[str],
) -> None:
    """Pressing Enter on a selected option emits HistorySelected."""
    app = _HistoryPickerTestApp(sample_entries)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        picker = app.query_one(HistoryPickerApp)
        option_list = picker.query_one(OptionList)

        # Tab from search input to option list
        await pilot.press("tab")
        await pilot.pause()
        assert option_list.has_focus

        await pilot.press("down")
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        assert option_list.highlighted == 2

        await pilot.press("enter")
        await pilot.pause()

        assert len(app._selected) == 1
        assert app._selected[0] == sample_entries[2]


@pytest.mark.asyncio
async def test_ui_search_navigate_select_full_workflow(
    sample_entries: list[str],
) -> None:
    """Full workflow: type query, navigate results, select with Enter."""
    app = _HistoryPickerTestApp(sample_entries)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        picker = app.query_one(HistoryPickerApp)
        search_input = picker.query_one(Input)
        option_list = picker.query_one(OptionList)

        await pilot.press(*"database")
        await pilot.pause()
        assert search_input.value == "database"

        # Tab to option list, then navigate
        await pilot.press("tab")
        await pilot.pause()
        assert option_list.has_focus

        await pilot.press("down")
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        assert len(app._selected) == 1
        assert "database" in app._selected[0].lower()


@pytest.mark.asyncio
async def test_ui_escape_from_search_input_emits_cancelled(
    sample_entries: list[str],
) -> None:
    """Pressing Escape while focused on search input emits Cancelled."""
    app = _HistoryPickerTestApp(sample_entries)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        picker = app.query_one(HistoryPickerApp)
        search_input = picker.query_one(Input)

        assert search_input.has_focus
        await pilot.press("escape")
        await pilot.pause()

        assert len(app._cancelled) == 1


@pytest.mark.asyncio
async def test_ui_escape_from_option_list_emits_cancelled(
    sample_entries: list[str],
) -> None:
    """Pressing Escape while focused on option list emits Cancelled."""
    app = _HistoryPickerTestApp(sample_entries)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        picker = app.query_one(HistoryPickerApp)
        option_list = picker.query_one(OptionList)

        # Tab from search input to option list
        await pilot.press("tab")
        await pilot.pause()
        assert option_list.has_focus

        await pilot.press("escape")
        await pilot.pause()

        assert len(app._cancelled) == 1


@pytest.mark.asyncio
async def test_ui_slash_focuses_search_input(sample_entries: list[str]) -> None:
    """Pressing / moves focus from option list to search input."""
    app = _HistoryPickerTestApp(sample_entries)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        picker = app.query_one(HistoryPickerApp)
        search_input = picker.query_one(Input)
        option_list = picker.query_one(OptionList)

        # Tab from search input to option list
        await pilot.press("tab")
        await pilot.pause()
        assert option_list.has_focus

        await pilot.press("/")
        await pilot.pause()

        assert search_input.has_focus


@pytest.mark.asyncio
async def test_ui_clear_search_shows_all_entries(sample_entries: list[str]) -> None:
    """Clearing the search input restores all entries."""
    app = _HistoryPickerTestApp(sample_entries)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        picker = app.query_one(HistoryPickerApp)
        search_input = picker.query_one(Input)
        option_list = picker.query_one(OptionList)

        await pilot.press(*"auth")
        await pilot.pause()
        filtered_count = len([o for o in option_list.options if o.id != "_no_match"])
        assert filtered_count < len(sample_entries)

        search_input.value = ""
        picker._update_options("")
        await pilot.pause()

        assert len(option_list.options) == len(sample_entries)


@pytest.mark.asyncio
async def test_ui_enter_on_empty_search_selects_first_option(
    sample_entries: list[str],
) -> None:
    """Pressing Enter without typing selects the first option."""
    app = _HistoryPickerTestApp(sample_entries)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        picker = app.query_one(HistoryPickerApp)
        search_input = picker.query_one(Input)

        assert search_input.has_focus
        assert search_input.value == ""

        await pilot.press("enter")
        await pilot.pause()

        assert len(app._selected) == 1
        assert app._selected[0] == sample_entries[0]


@pytest.mark.asyncio
async def test_ui_no_match_shows_placeholder(sample_entries: list[str]) -> None:
    """Searching with no matches shows a 'No matches' option."""
    app = _HistoryPickerTestApp(sample_entries)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        picker = app.query_one(HistoryPickerApp)
        option_list = picker.query_one(OptionList)

        await pilot.press(*"xyznonexistent")
        await pilot.pause()

        assert len(option_list.options) == 1
        assert option_list.options[0].id == "_no_match"
        assert "no match" in str(option_list.options[0]._visual).lower()


@pytest.mark.asyncio
async def test_ui_navigate_up_from_first_wraps_to_last(
    sample_entries: list[str],
) -> None:
    """Arrow up from the first option wraps to the last option."""
    app = _HistoryPickerTestApp(sample_entries)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        picker = app.query_one(HistoryPickerApp)
        option_list = picker.query_one(OptionList)

        # Tab from search input to option list
        await pilot.press("tab")
        await pilot.pause()
        assert option_list.has_focus
        assert option_list.highlighted == 0
        # Press up to wrap to last
        await pilot.press("up")
        await pilot.pause()
        assert option_list.highlighted == len(sample_entries) - 1


@pytest.mark.asyncio
async def test_ui_navigate_down_from_last_wraps_to_first(
    sample_entries: list[str],
) -> None:
    """Arrow down from the last option wraps to the first option."""
    app = _HistoryPickerTestApp(sample_entries)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        picker = app.query_one(HistoryPickerApp)
        option_list = picker.query_one(OptionList)

        # Tab from search input to option list
        await pilot.press("tab")
        await pilot.pause()
        assert option_list.has_focus
        # Navigate to last option
        for _ in range(len(sample_entries) - 1):
            await pilot.press("down")
            await pilot.pause()
        assert option_list.highlighted == len(sample_entries) - 1
        # Press down to wrap to first
        await pilot.press("down")
        await pilot.pause()
        assert option_list.highlighted == 0


@pytest.mark.asyncio
async def test_ui_search_then_navigate_selects_filtered_entry(
    sample_entries: list[str],
) -> None:
    """Search filters results, then navigate + select picks from filtered list."""
    app = _HistoryPickerTestApp(sample_entries)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        picker = app.query_one(HistoryPickerApp)
        option_list = picker.query_one(OptionList)

        await pilot.press(*"refactor")
        await pilot.pause()

        filtered = [opt for opt in option_list.options if opt.id != "_no_match"]
        assert len(filtered) >= 1

        # Tab to option list, then select
        await pilot.press("tab")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert len(app._selected) == 1
        assert "refactor" in app._selected[0].lower()


@pytest.mark.asyncio
async def test_ui_up_down_bindings_navigate_option_list(
    sample_entries: list[str],
) -> None:
    """The up/down bindings navigate the option list cursor."""
    app = _HistoryPickerTestApp(sample_entries)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        picker = app.query_one(HistoryPickerApp)
        option_list = picker.query_one(OptionList)

        # Tab from search input to option list
        await pilot.press("tab")
        await pilot.pause()
        assert option_list.has_focus
        assert option_list.highlighted == 0
        # Navigate to index 3
        await pilot.press("down")
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        assert option_list.highlighted == 3
        # Navigate up
        await pilot.press("up")
        await pilot.pause()
        assert option_list.highlighted == 2


@pytest.mark.asyncio
async def test_ui_slash_binding_focuses_search(sample_entries: list[str]) -> None:
    """The / binding moves focus to the search input."""
    app = _HistoryPickerTestApp(sample_entries)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        picker = app.query_one(HistoryPickerApp)
        search_input = picker.query_one(Input)
        picker.query_one(OptionList)

        # Tab from search input to option list
        await pilot.press("tab")
        await pilot.pause()

        await pilot.press("/")
        await pilot.pause()
        assert search_input.has_focus
