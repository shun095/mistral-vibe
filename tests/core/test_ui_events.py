from __future__ import annotations

"""Tests for UI-specific events."""

from vibe.core.types import BaseEvent
from vibe.core.ui_events import SystemPromptRegeneratedEvent


class TestSystemPromptRegeneratedEvent:
    """Test SystemPromptRegeneratedEvent creation and inheritance."""

    def test_event_is_base_event(self) -> None:
        event = SystemPromptRegeneratedEvent()
        assert isinstance(event, BaseEvent)
