from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, ClassVar

from rapidfuzz import fuzz
from rapidfuzz.distance import LCSseq
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container, Vertical
from textual.events import Key
from textual.message import Message
from textual.widgets import Input, OptionList
from textual.widgets.option_list import Option

from vibe.cli.textual_ui.widgets.no_markup_static import NoMarkupStatic


def _fuzzy_match_pair(query: str, candidate: str) -> tuple[float, list[int]]:
    """Single fuzzy match — runs in worker process."""
    score = fuzz.partial_ratio(query, candidate)
    if score == 0:
        return (0.0, [])
    opcodes = LCSseq.opcodes(query, candidate)
    matches = [
        dest_start
        for op in opcodes
        if op.tag == "equal"
        for dest_start in range(op.dest_start, op.dest_end)
    ]
    return (float(score), matches)


class _SearchInput(Input):
    """Search input that forwards ESC/Enter to parent app."""

    def on_key(self, event: Key) -> None:
        if event.key == "escape":
            self.post_message(HistoryPickerApp.Cancelled())
            event.stop()
        elif event.key == "enter":
            try:
                option_list = self.app.query_one(OptionList)
                if option_list.options:
                    option_list.action_select()
            except Exception:
                pass
            event.stop()


class HistoryPickerApp(Container):
    """History picker with fuzzy search for /history command."""

    can_focus_children = True

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("up", "navigate_up", "Up", show=False),
        Binding("down", "navigate_down", "Down", show=False),
        Binding("/", "focus_search", "Search", show=True),
    ]

    class HistorySelected(Message):
        text: str

        def __init__(self, text: str) -> None:
            self.text = text
            super().__init__()

    class Cancelled(Message):
        pass

    def __init__(self, entries: list[str], **kwargs: Any) -> None:
        super().__init__(id="historypicker-app", **kwargs)
        self._entries = entries

    def compose(self) -> ComposeResult:
        with Vertical(id="historypicker-content"):
            yield _SearchInput(
                placeholder="Search history...", id="historypicker-search"
            )
            yield OptionList(id="historypicker-options")
            yield NoMarkupStatic(
                "\u2191\u2193 Navigate  / Search  Enter Select  Esc Cancel",
                classes="historypicker-help",
            )

    def on_mount(self) -> None:
        self.query_one(Input).focus()
        self._update_options("")

    def action_navigate_up(self) -> None:
        self.query_one(OptionList).action_cursor_up()

    def action_navigate_down(self) -> None:
        self.query_one(OptionList).action_cursor_down()

    def action_focus_search(self) -> None:
        self.query_one(Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        self._update_options(event.value)

    def _update_options(self, query: str) -> None:
        option_list = self.query_one(OptionList)
        options: list[Option] = []

        if query:
            # Parallel fuzzy matching with ThreadPoolExecutor
            previews = [e.replace("\n", " ") for e in self._entries]
            pairs = [(query, preview) for preview in previews]
            with ThreadPoolExecutor(max_workers=4) as executor:
                results = list(
                    executor.map(_fuzzy_match_pair, *zip(*pairs, strict=False))
                )
            scored = [
                (score, idx, preview, matches)
                for idx, (preview, (score, matches)) in enumerate(
                    zip(previews, results, strict=False)
                )
                if score > 0
            ]
            scored.sort(key=lambda x: x[0], reverse=True)

            for _score, idx, preview, matches in scored[:50]:
                display = Text(preview, no_wrap=True)
                for pos in matches:
                    display.stylize("bold yellow", pos, pos + 1)
                options.append(Option(display, id=str(idx)))
        else:
            for idx, entry in enumerate(self._entries):
                preview = entry.replace("\n", " ")
                display = Text(preview, no_wrap=True)
                options.append(Option(display, id=str(idx)))

        option_list.clear_options()
        option_list.add_options(options)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id is not None:
            idx = int(event.option.id)
            self.post_message(self.HistorySelected(self._entries[idx]))

    def action_cancel(self) -> None:
        self.post_message(self.Cancelled())
