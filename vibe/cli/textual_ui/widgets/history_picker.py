from __future__ import annotations

from typing import Any, ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container, Vertical
from textual.css.query import NoMatches
from textual.events import Key
from textual.message import Message
from textual.widgets import Input, OptionList
from textual.widgets.option_list import Option

from vibe.cli.textual_ui.widgets.no_markup_static import NoMarkupStatic
from vibe.core.fuzzy import fuzzy_match_batch


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
            except NoMatches:
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
        if self.query_one(OptionList).options:
            self.query_one(OptionList).highlighted = 0

    def action_navigate_up(self) -> None:
        self.query_one(OptionList).action_cursor_up()

    def action_navigate_down(self) -> None:
        self.query_one(OptionList).action_cursor_down()

    def action_focus_search(self) -> None:
        self.query_one(Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        # Defer options update to avoid modifying OptionList during event handling
        self.call_later(self._update_options, event.value)

    def _update_options(self, query: str) -> None:
        option_list = self.query_one(OptionList)
        options: list[Option] = []

        if query:
            previews = [e.replace("\n", " ") for e in self._entries]
            results = fuzzy_match_batch(query, previews)
            scored: list[tuple[float, int, str, list[int]]] = []
            for idx, (score, matches) in enumerate(results):
                if matches is not None and score > 0:
                    scored.append((score, idx, previews[idx], matches))
            scored.sort(key=lambda x: x[0], reverse=True)

            if scored:
                for _score, idx, preview, matches in scored[:50]:
                    display = Text(preview, no_wrap=True)
                    for pos in matches:
                        display.stylize("bold yellow", pos, pos + 1)
                    options.append(Option(display, id=str(idx)))
            else:
                options.append(Option(Text("No matches", style="dim"), id="_no_match"))
        else:
            for idx, entry in enumerate(self._entries):
                preview = entry.replace("\n", " ")
                display = Text(preview, no_wrap=True)
                options.append(Option(display, id=str(idx)))

        option_list.clear_options()
        option_list.add_options(options)
        if options and options[0].id != "_no_match":
            option_list.highlighted = 0

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id is not None and event.option.id != "_no_match":
            idx = int(event.option.id)
            self.post_message(self.HistorySelected(self._entries[idx]))

    def action_cancel(self) -> None:
        self.post_message(self.Cancelled())
