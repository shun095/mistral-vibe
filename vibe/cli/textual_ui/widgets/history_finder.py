from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Any

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container
from textual.message import Message
from textual.widgets import Input, ListItem, ListView, Static
from textual import events

from vibe.cli.history_manager import HistoryManager
from vibe.core.autocompletion.fuzzy import fuzzy_match

if TYPE_CHECKING:
    from pathlib import Path


class HistoryEntry:
    def __init__(self, text: str, timestamp: str | None = None) -> None:
        self.text = text
        self.timestamp = timestamp
        self.display_text = text if len(text) <= 100 else text[:97] + "..."


class HistoryFinderApp(Container):
    can_focus = True
    can_focus_children = True  # Allow children to receive focus

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("escape", "close", "Close", show=False),
        Binding("enter", "select", "Select", show=False),
    ]

    class HistorySelected(Message):
        def __init__(self, entry: str) -> None:
            super().__init__()
            self.entry = entry

    class HistoryClosed(Message):
        def __init__(self) -> None:
            super().__init__()

    def __init__(self, history_manager: HistoryManager | None = None, **kwargs: Any) -> None:
        super().__init__(id="history-finder", **kwargs)
        self.history_manager = history_manager
        self._entries: list[HistoryEntry] = []
        self._filtered_entries: list[HistoryEntry] = []
        self._search_input: Input | None = None
        self._list_view: ListView | None = None
        self._load_history_from_manager()
        # Initialize filtered entries with all entries (latest first for empty search)
        self._filtered_entries = self._entries[::-1]

    def compose(self) -> ComposeResult:
        yield Static("History Finder", id="title")
        self._search_input = Input(
            placeholder="Search history...",
            id="search-input"
        )
        yield self._search_input
        
        # ListView handles its own scrolling
        self._list_view = ListView(id="history-list")
        yield self._list_view
        
        yield Static("Press Enter to select, Esc to close", id="instructions")

    def on_mount(self) -> None:
        if self._search_input:
            self._search_input.focus()
        if self._list_view is not None:
            self._update_list()

    def _load_history_from_manager(self) -> None:
        """Load history entries directly from the HistoryManager."""
        if not self.history_manager:
            # If no history manager, create an empty list
            print("DEBUG: No history manager provided")
            self._entries = []
            return

        # Get entries from the HistoryManager (already filtered and processed)
        entries = []
        print(f"DEBUG: Loading history from manager with {len(self.history_manager._entries)} entries")
        for entry in self.history_manager._entries:
            if entry and not entry.startswith("/"):
                entries.append(HistoryEntry(entry))
                print(f"DEBUG: Added entry: {entry[:50]}...")
        
        # Limit to most recent 50 entries to avoid overwhelming the user
        self._entries = entries[-50:]
        print(f"DEBUG: Loaded {len(self._entries)} history entries")

    def _filter_entries(self, search_text: str) -> None:
        """Filter history entries based on fuzzy search."""
        if not search_text:
            # When search is empty, show latest entries first (reverse order)
            self._filtered_entries = self._entries[::-1]
            return

        search_lower = search_text.lower()
        scored_entries = []
        
        for entry in self._entries:
            match = fuzzy_match(search_text, entry.text, entry.text.lower())
            if match.matched:
                scored_entries.append((match.score, entry))
        
        # Sort by score (descending)
        scored_entries.sort(key=lambda x: x[0], reverse=True)
        self._filtered_entries = [entry for _, entry in scored_entries]

    def _update_list(self) -> None:
        """Update the list view with filtered entries."""
        if self._list_view is None:
            return

        self._list_view.clear()
        
        if not self._filtered_entries:
            self._list_view.append(ListItem(Static("(No matching history entries)")))
            return

        for entry in self._filtered_entries:
            self._list_view.append(ListItem(Static(entry.display_text)))

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if self._search_input and event.input.id == "search-input":
            self._filter_entries(event.value)
            self._update_list()

    def action_move_up(self) -> None:
        """Move selection up in the list."""
        if self._list_view:
            self._list_view.action_cursor_up()

    def action_move_down(self) -> None:
        """Move selection down in the list."""
        if self._list_view:
            self._list_view.action_cursor_down()

    def action_select(self) -> None:
        """Select the currently highlighted entry."""
        print("DEBUG: action_select called")  # Debug
        if self._list_view:
            index = self._list_view.index
            print(f"DEBUG: index={index}, filtered_entries={len(self._filtered_entries)}")  # Debug
            if 0 <= index < len(self._filtered_entries):
                selected_entry = self._filtered_entries[index]
                print(f"DEBUG: About to post HistorySelected message")  # Debug
                self.post_message(self.HistorySelected(selected_entry.text))
                print(f"DEBUG: About to post HistoryClosed message")  # Debug
                self.post_message(self.HistoryClosed())
                print(f"DEBUG: Messages posted: {selected_entry.text[:50]}...")  # Debug
            else:
                print(f"DEBUG: Index {index} is out of range")  # Debug
        else:
            print("DEBUG: _list_view is None")  # Debug

    def action_close(self) -> None:
        """Close the history finder."""
        self.post_message(self.HistoryClosed())

    def focus(self) -> None:
        """Focus the list view for better navigation."""
        if self._list_view:
            self._list_view.focus()
        elif self._search_input:
            self._search_input.focus()

    def on_key(self, event: events.Key) -> None:
        """Handle key events."""
        print(f"DEBUG: Key event received: {event.key}")  # Debug
        if event.key == "enter":
            print("DEBUG: Enter key pressed")  # Debug
            self.action_select()