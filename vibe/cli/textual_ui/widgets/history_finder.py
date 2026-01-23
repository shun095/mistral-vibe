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
        self.display_text = text


class HistoryFinderApp(Container):
    can_focus = True
    can_focus_children = True  # Allow children to receive focus

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("escape", "close", "Close", show=False),
        Binding("enter", "select", "Select", show=False),
        Binding("ctrl+f", "focus_search", "Focus Search", show=False),
        Binding("ctrl+l", "focus_list", "Focus List", show=False),
        Binding("tab", "toggle_focus", "Toggle Focus", show=False),
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
        
        yield Static("Press Enter to select, Esc to close | Ctrl+F to focus search, Ctrl+L to focus list, Tab to toggle", id="instructions")

    def on_mount(self) -> None:
        if self._search_input:
            self._search_input.focus()
        if self._list_view is not None:
            self._update_list()

    def _load_history_from_manager(self) -> None:
        """Load history entries directly from the HistoryManager."""
        if not self.history_manager:
            # If no history manager, create an empty list
            self._entries = []
            return

        # Get entries from the HistoryManager (already filtered and processed)
        entries = []
        for entry in self.history_manager._entries:
            if entry and not entry.startswith("/"):
                entries.append(HistoryEntry(entry))
        
        # Limit to most recent 50 entries to avoid overwhelming the user
        self._entries = entries[-50:]

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

        for i, entry in enumerate(self._filtered_entries):
            # Add cursor indicator for the first item (default selection)
            cursor_indicator = "> " if i == 0 else "  "
            display_text = f"{cursor_indicator}{entry.display_text}"
            
            list_item = ListItem(Static(display_text))
            list_item.index_in_list = i  # Store the index for cursor updates
            list_item.entry = entry  # Store entry reference for cursor updates
            self._list_view.append(list_item)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if self._search_input and event.input.id == "search-input":
            self._filter_entries(event.value)
            self._update_list()

    def _update_cursor_indicators(self) -> None:
        """Update cursor indicators to show which item is selected."""
        if not self._list_view:
            return
        
        current_index = self._list_view.index
        if current_index is None:
            return
            
        # Update all list items to show the correct cursor indicator
        for i, child in enumerate(self._list_view.children):
            if hasattr(child, 'children') and len(child.children) > 0:
                static_widget = child.children[0]
                if hasattr(static_widget, 'update'):
                    cursor_indicator = "> " if i == current_index else "  "
                    entry = getattr(child, 'entry', None)
                    if entry:
                        display_text = f"{cursor_indicator}{entry.display_text}"
                        static_widget.update(display_text)

    def action_move_up(self) -> None:
        """Move selection up in the list."""
        if self._list_view:
            self._list_view.action_cursor_up()
            self._update_cursor_indicators()

    def action_move_down(self) -> None:
        """Move selection down in the list."""
        if self._list_view:
            self._list_view.action_cursor_down()
            self._update_cursor_indicators()

    def action_select(self) -> None:
        """Select the currently highlighted entry."""
        if self._list_view:
            index = self._list_view.index
            if 0 <= index < len(self._filtered_entries):
                selected_entry = self._filtered_entries[index]
                self.post_message(self.HistorySelected(selected_entry.text))
                self.post_message(self.HistoryClosed())

    def action_close(self) -> None:
        """Close the history finder."""
        self.post_message(self.HistoryClosed())

    def action_focus_search(self) -> None:
        """Focus the search input."""
        if self._search_input:
            self._search_input.focus()

    def action_focus_list(self) -> None:
        """Focus the list view."""
        if self._list_view:
            self._list_view.focus()

    def action_toggle_focus(self) -> None:
        """Toggle focus between search input and list view."""
        if not self._search_input or not self._list_view:
            return
            
        # Check which widget currently has focus
        if self._search_input.has_focus:
            self._list_view.focus()
        else:
            self._search_input.focus()

    def focus(self) -> None:
        """Focus the search input for immediate typing."""
        if self._search_input:
            self._search_input.focus()
        elif self._list_view:
            self._list_view.focus()

    def on_key(self, event: events.Key) -> None:
        """Handle key events."""
        if event.key == "enter":
            self.action_select()