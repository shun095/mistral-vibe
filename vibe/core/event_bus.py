"""Async event bus for broadcasting events to multiple listeners.

This module provides a proper async event bus implementation with:
- Async event dispatching
- Error handling per listener
- Listener lifecycle management
- Logging of listener errors
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import inspect
import logging

from vibe.core.types import BaseEvent

logger = logging.getLogger(__name__)


class EventBus:
    """Async event bus for broadcasting events to multiple listeners.

    The event bus allows multiple listeners to subscribe to events and
    handles errors gracefully without stopping the dispatch loop.

    Usage:
        bus = EventBus()
        bus.add_listener(my_listener)
        await bus.dispatch(event)
    """

    def __init__(self, logger_override: logging.Logger | None = None) -> None:
        """Initialize the event bus.

        Args:
            logger_override: Optional logger for debugging. Defaults to module logger.
        """
        self._listeners: list[Callable[[BaseEvent], None]] = []
        self._logger = logger_override or logger

    def add_listener(self, listener: Callable[[BaseEvent], None]) -> None:
        """Add an event listener.

        Args:
            listener: Callback function to be called when events are broadcast.
                      Should accept a single BaseEvent argument.
        """
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[BaseEvent], None]) -> bool:
        """Remove an event listener.

        Args:
            listener: The listener to remove.

        Returns:
            True if the listener was found and removed, False otherwise.
        """
        if listener in self._listeners:
            self._listeners.remove(listener)
            return True
        return False

    def clear_listeners(self) -> None:
        """Remove all event listeners."""
        self._listeners.clear()

    def get_listener_count(self) -> int:
        """Get the number of registered listeners.

        Returns:
            The number of listeners currently registered.
        """
        return len(self._listeners)

    async def dispatch(self, event: BaseEvent) -> None:
        """Dispatch an event to all registered listeners asynchronously.

        Each listener is called in a separate task to prevent one slow
        listener from blocking others. Errors in individual listeners
        are caught and logged without stopping the dispatch loop.

        Args:
            event: The event to broadcast to all listeners.
        """
        if not self._listeners:
            return

        # Create tasks for all listeners
        tasks = [
            asyncio.create_task(self._call_listener(listener, event))
            for listener in self._listeners
        ]

        # Wait for all tasks to complete, ignoring exceptions
        # (exceptions are handled in _call_listener)
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _call_listener(
        self, listener: Callable[[BaseEvent], None], event: BaseEvent
    ) -> None:
        """Call a single listener with error handling.

        Args:
            listener: The listener callback to call.
            event: The event to pass to the listener.
        """
        try:
            if inspect.iscoroutinefunction(listener):
                # Listener is async, await it directly
                await listener(event)
            else:
                # Listener is sync, call it directly
                listener(event)
        except Exception as e:
            # Log the error but don't propagate it
            listener_name = getattr(listener, "__name__", str(listener))
            self._logger.debug(
                "Error in event listener '%s': %s", listener_name, e, exc_info=True
            )

    def dispatch_sync(self, event: BaseEvent) -> None:
        """Dispatch an event to all registered listeners synchronously.

        This is a convenience method for cases where async dispatch
        is not available. Each listener is called in sequence.

        Args:
            event: The event to broadcast to all listeners.
        """
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                listener_name = getattr(listener, "__name__", str(listener))
                self._logger.debug(
                    "Error in event listener '%s': %s", listener_name, e, exc_info=True
                )
