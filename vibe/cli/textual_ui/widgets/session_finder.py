from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Any

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container
from textual.message import Message
from textual.widgets import Input, ListItem, ListView, Static
from textual import events

from vibe.core.utils import logger

if TYPE_CHECKING:
    from vibe.core.config import VibeConfig
    from vibe.core.types import LLMMessage


class SessionEntry:
    """Represents a saved session with metadata."""

    def __init__(self, session_id: str, session_path: Path) -> None:
        self.session_id = session_id
        self.session_path = session_path
        self.timestamp = self._parse_timestamp()
        self.messages = self._load_messages()
        self.message_count = len(self.messages)

    def _parse_timestamp(self) -> datetime | None:
        """Parse timestamp from session filename."""
        try:
            # Session files are named like: session_2024-01-01_12-34-56.json
            # or session_2024-01-01_12-34-56_hash.json
            filename = self.session_path.name
            # Extract timestamp part (between session_ and .json)
            timestamp_str = filename.replace("session_", "").replace(".json", "")
            # Remove hash if present (everything after second underscore)
            if "_" in timestamp_str:
                parts = timestamp_str.split("_")
                if len(parts) >= 3:
                    timestamp_str = "_".join(parts[:3])
            return datetime.strptime(timestamp_str, "%Y-%m-%d_%H-%M-%S")
        except (ValueError, AttributeError):
            return None

    def _load_messages(self) -> list[LLMMessage]:
        """Load messages from session file using InteractionLogger for consistency."""
        try:
            from vibe.core.interaction_logger import InteractionLogger
            from vibe.core.types import LLMMessage
            
            # Use the standard InteractionLogger.load_session method for consistency
            # This ensures we load all message types including tool calls and system messages
            messages, metadata = InteractionLogger.load_session(self.session_path)
            
            logger.info(f"Loaded {len(messages)} messages from session {self.session_id}")
            return messages
            
        except (FileNotFoundError, OSError) as e:
            logger.warning(f"Failed to load session {self.session_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error loading session {self.session_id}: {e}")
            return []

    def get_preview(self, max_length: int = 100) -> str:
        """Get a preview of the first message."""
        if not self.messages:
            return "(No messages)"
        first_message = self.messages[0]
        content = first_message.content or ""
        return content[:max_length] + "..." if len(content) > max_length else content

    def get_display_text(self) -> str:
        """Get formatted display text for the session list."""
        timestamp_str = self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else "Unknown time"
        return f"[{timestamp_str}] {self.session_id} ({self.message_count} messages)"


class SessionFinderApp(Container):
    can_focus = True
    can_focus_children = True

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("enter", "select", "Select", show=False),
        Binding("escape", "close", "Close", show=False),
    ]

    class SessionSelected(Message):
        def __init__(self, session_path: Path, messages: list[LLMMessage], metadata: dict[str, Any]) -> None:
            super().__init__()
            self.session_path = session_path
            self.messages = messages
            self.metadata = metadata

    class SessionClosed(Message):
        def __init__(self) -> None:
            super().__init__()

    def __init__(self, config: VibeConfig, **kwargs: Any) -> None:
        super().__init__(id="session-finder", **kwargs)
        self.config = config
        self._sessions: list[SessionEntry] = []
        self._filtered_sessions: list[SessionEntry] = []
        self._search_input: Input | None = None
        self._list_view: ListView | None = None

    def compose(self) -> ComposeResult:
        """Compose the session finder UI."""
        logger.info("SessionFinderApp compose called")
        yield Static("Session Finder", id="title")
        self._search_input = Input(placeholder="Search sessions...", id="search-input")
        yield self._search_input

        self._list_view = ListView(id="session-list")
        logger.info(f"Created list view: {self._list_view}")
        yield self._list_view

        yield Static(
            "Press Enter to select, Esc to close", id="session-instructions"
        )
        logger.info("SessionFinderApp compose completed")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        logger.info(f"Search input changed: {event.input.id} = {event.input.value}")
        if event.input.id == "search-input":
            search_text = event.input.value
            logger.info(f"Filtering sessions with: '{search_text}'")
            self._filter_sessions(search_text)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in search input - focus the list view."""
        logger.info(f"Search input submitted: {event.input.id} = {event.input.value}")
        if event.input.id == "search-input":
            # When Enter is pressed in search input, focus the list view
            # so that the next Enter key will select a session
            self.call_after_refresh(self._focus_list_view)

    async def on_mount(self) -> None:
        """Load sessions and set up the UI on mount."""
        logger.info("SessionFinderApp on_mount called")
        await self._load_sessions()
        logger.info(f"After _load_sessions: {len(self._sessions)} sessions loaded")
        
        logger.info(f"Search input: {self._search_input}")
        logger.info(f"List view: {self._list_view}")
        
        if self._search_input:
            logger.info("Focusing search input")
            self._search_input.focus()
        else:
            logger.warning("No search input found")
        
        # Use call_after_refresh to ensure the list view is properly mounted
        self.call_after_refresh(self._update_list_after_mount)
        
        # Focus the list view after the UI is fully mounted
        self.call_after_refresh(self._focus_list_view)
        
        logger.info(f"Loaded {len(self._sessions)} sessions total, {len(self._filtered_sessions)} filtered")

    async def _update_list_after_mount(self) -> None:
        """Update the list after the widget is fully mounted."""
        logger.info("_update_list_after_mount called")
        # Query the list view from the DOM to ensure we get the mounted instance
        try:
            list_view = self.query_one("#session-list", ListView)
            logger.info(f"Query list view: {list_view}")
            logger.info(f"List view is None: {list_view is None}")
            if list_view is not None:
                self._list_view = list_view
                logger.info("Calling _update_list from _update_list_after_mount")
                await self._update_list()
            else:
                logger.warning("No list view found in DOM")
        except Exception as e:
            logger.error(f"Error querying list view: {e}")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        logger.info(f"Search input changed: {event.input.id} = {event.input.value}")
        if event.input.id == "search-input":
            search_text = event.input.value
            logger.info(f"Filtering sessions with: '{search_text}'")
            self._filter_sessions(search_text)

    async def _load_sessions(self) -> None:
        """Load saved sessions from the sessions directory."""
        sessions_dir = Path(self.config.session_logging.save_dir)
        if not sessions_dir.exists():
            logger.info(f"No sessions directory found at {sessions_dir}")
            self._sessions = []
            return

        session_files = list(sessions_dir.glob("session_*.json"))
        
        # Sort session files by filename (which contains timestamp) to get latest first
        # Session files are named like: session_2024-01-01_12-34-56.json
        session_files.sort(reverse=True)
        
        # Only load the latest 20 sessions to reduce memory usage
        max_sessions = 20
        total_sessions = len(session_files)
        session_files = session_files[:max_sessions]
        logger.info(f"Loading {len(session_files)} of {total_sessions} total sessions (limited to {max_sessions})")
        
        self._sessions = []

        for session_file in session_files:
            try:
                session_id = session_file.stem.replace("session_", "")
                session_entry = SessionEntry(session_id, session_file)
                self._sessions.append(session_entry)
            except Exception as e:
                logger.warning(f"Failed to load session {session_file}: {e}")

        # Sort by timestamp (newest first), handle None timestamps
        self._sessions.sort(key=lambda s: s.timestamp.timestamp() if s.timestamp else 0, reverse=True)
        self._filtered_sessions = self._sessions.copy()

    def _filter_sessions(self, search_text: str) -> None:
        """Filter sessions based on search text."""
        logger.info(f"Filtering sessions with search text: '{search_text}'")
        if not search_text:
            self._filtered_sessions = self._sessions.copy()
            logger.info(f"No search text, showing all {len(self._filtered_sessions)} sessions")
        else:
            search_lower = search_text.lower()
            self._filtered_sessions = [
                s for s in self._sessions
                if search_lower in s.session_id.lower()
                or search_lower in s.get_preview().lower()
            ]
            logger.info(f"Filtered to {len(self._filtered_sessions)} sessions")
        self.call_after_refresh(self._update_list)

    async def _update_list(self) -> None:
        """Update the session list view with current sessions."""
        logger.info(f"_update_list called with {len(self._filtered_sessions)} filtered sessions")
        
        # Query the list view from the DOM to ensure we get the mounted instance
        try:
            list_view = self.query_one("#session-list", ListView)
            logger.info(f"_update_list query list view: {list_view}")
            logger.info(f"_update_list list view is None: {list_view is None}")
            if list_view is None:
                logger.warning("_update_list: No list view available in DOM")
                return
            self._list_view = list_view
            logger.info(f"List view children before clear: {len(list(list_view.children))}")
        except Exception as e:
            logger.error(f"Error querying list view in _update_list: {e}")
            return

        # Clear the list view by removing all children
        for child in list(list_view.children):
            await child.remove()
        
        logger.info(f"List view children after clear: {len(list(list_view.children))}")

        if not self._filtered_sessions:
            logger.info(f"No sessions found to display")
            # Create a placeholder item
            placeholder = ListItem(Static("No sessions found"))
            await list_view.mount(placeholder)
            logger.info(f"List view children after placeholder: {len(list(list_view.children))}")
            return

        logger.info(f"Displaying {len(self._filtered_sessions)} sessions")
        for i, session in enumerate(self._filtered_sessions):
            if i < 5:  # Only log first 5 to avoid spam
                logger.info(f"Adding session: {session.get_display_text()}")
            
            # Add cursor indicator for the first item (default selection)
            cursor_indicator = "> " if i == 0 else "  "
            display_text = f"{cursor_indicator}{session.get_display_text()}"
            
            list_item = ListItem(
                Static(display_text, id=f"session-{session.session_id}")
            )
            list_item.session = session  # Store reference for selection
            list_item.index_in_list = i  # Store the index for cursor updates
            try:
                await list_view.mount(list_item)
                logger.info(f"Successfully mounted session {i}, total children: {len(list(list_view.children))}")
                if i < 3:  # Log details for first few items
                    logger.info(f"Session {i} display text: '{session.get_display_text()}'")
                    logger.info(f"Session {i} list_item: {list_item}")
                    logger.info(f"Session {i} list_item children: {len(list(list_item.children))}")
                    # Check if the list_item has any content
                    if list(list_item.children):
                        child = list(list_item.children)[0]
                        logger.info(f"Session {i} child: {child}")
                        logger.info(f"Session {i} child content: {getattr(child, 'renderable', str(child))}")
            except Exception as e:
                logger.error(f"Error mounting session {i}: {e}")
        
        logger.info(f"Final list view children count: {len(list(list_view.children))}")
        logger.info(f"List view size: {list_view.size}")
        logger.info(f"List view styles: {list_view.styles}")
        logger.info(f"List view virtual_size: {list_view.virtual_size}")
        logger.info(f"List view region: {list_view.region}")
        
        # Debug: Check if the list view is actually displaying the items
        logger.info(f"List view children: {list(list_view.children)}")
        if list(list_view.children):
            first_child = list(list_view.children)[0]
            logger.info(f"First child: {first_child}")
            logger.info(f"First child type: {type(first_child)}")
            logger.info(f"First child children: {list(first_child.children)}")
        
        # Refresh the list view to ensure it updates its display
        logger.info("Refreshing list view")
        list_view.refresh()
        
        # Also refresh the parent container to ensure proper layout
        logger.info("Refreshing session finder container")
        self.refresh()

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
                    session = getattr(child, 'session', None)
                    if session:
                        display_text = f"{cursor_indicator}{session.get_display_text()}"
                        static_widget.update(display_text)

    def _focus_list_view(self) -> None:
        """Focus the list view after the UI is fully mounted."""
        if self._list_view:
            self._list_view.focus()
            # Ensure the cursor is at the first item
            if self._list_view.index is None and len(self._filtered_sessions) > 0:
                self._list_view.index = 0

    def action_move_up(self) -> None:
        """Move selection up in the session list."""
        if self._list_view:
            self._list_view.action_cursor_up()
            self._update_cursor_indicators()

    def action_move_down(self) -> None:
        """Move selection down in the session list."""
        if self._list_view:
            self._list_view.action_cursor_down()
            self._update_cursor_indicators()

    def action_select(self) -> None:
        """Select the currently highlighted session."""
        if not self._list_view:
            return

        index = self._list_view.index
        if index is not None and 0 <= index < len(self._filtered_sessions):
            session = self._filtered_sessions[index]
            self.post_message(
                self.SessionSelected(
                    session_path=session.session_path,
                    messages=session.messages,
                    metadata={
                        "session_id": session.session_id,
                        "timestamp": session.timestamp,
                        "message_count": session.message_count,
                    }
                )
            )

    def action_close(self) -> None:
        """Close the session finder."""
        self.post_message(self.SessionClosed())