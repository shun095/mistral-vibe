"""Event bridge for synchronizing AgentLoop events with web UI."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from vibe.core.types import BaseEvent

if TYPE_CHECKING:
    from vibe.core.agent_loop import AgentLoop


class EventBridge:
    """Bridge between AgentLoop and web UI for event synchronization.

    This class manages event listeners and broadcasts events from AgentLoop
    to registered listeners (e.g., WebSocket connections).
    """

    def __init__(self, agent_loop: AgentLoop | dict) -> None:
        """Initialize the EventBridge.

        Args:
            agent_loop: The AgentLoop instance to listen to.
        """
        self.agent_loop = agent_loop
        self._event_listeners: list[Callable[[BaseEvent], None]] = []

    def add_event_listener(self, listener: Callable[[BaseEvent], None]) -> None:
        """Add an event listener.

        Args:
            listener: Callback function to receive events.
        """
        if listener not in self._event_listeners:
            self._event_listeners.append(listener)

    def remove_event_listener(self, listener: Callable[[BaseEvent], None]) -> None:
        """Remove an event listener.

        Args:
            listener: The listener callback to remove.
        """
        if listener in self._event_listeners:
            self._event_listeners.remove(listener)

    def on_event(self, event: BaseEvent) -> None:
        """Notify all registered listeners of an event.

        Args:
            event: The event to broadcast.
        """
        for listener in self._event_listeners:
            try:
                listener(event)
            except Exception:
                # Don't let one listener fail affect others
                pass
