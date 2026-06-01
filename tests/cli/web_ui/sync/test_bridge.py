"""Tests for EventBridge."""

from __future__ import annotations

import pytest

from vibe.core.types import AssistantEvent, BaseEvent, UserMessageEvent


@pytest.fixture
def mock_agent_loop() -> dict:
    """Create a mock AgentLoop for testing."""
    return {"events": []}


def test_bridge_creates_with_agent_loop(mock_agent_loop: dict) -> None:
    """Test that EventBridge can be created with an AgentLoop."""
    from vibe.cli.web_ui.sync.bridge import EventBridge

    bridge = EventBridge(agent_loop=mock_agent_loop)
    assert bridge is not None


def test_bridge_can_subscribe_event_listener(mock_agent_loop: dict) -> None:
    """Test that EventBridge can subscribe event listeners."""
    from vibe.cli.web_ui.sync.bridge import EventBridge

    bridge = EventBridge(agent_loop=mock_agent_loop)
    events_received: list[BaseEvent] = []

    def listener(event: BaseEvent) -> None:
        events_received.append(event)

    bridge.add_event_listener(listener)
    assert len(bridge._event_listeners) == 1


def test_bridge_calls_listener_on_event(mock_agent_loop: dict) -> None:
    """Test that EventBridge calls listeners when an event is received."""
    from vibe.cli.web_ui.sync.bridge import EventBridge

    bridge = EventBridge(agent_loop=mock_agent_loop)
    events_received: list[BaseEvent] = []

    def listener(event: BaseEvent) -> None:
        events_received.append(event)

    bridge.add_event_listener(listener)

    # Simulate an event
    test_event = AssistantEvent(content="Hello", message_id="1")
    bridge.on_event(test_event)

    assert len(events_received) == 1
    assert events_received[0] == test_event


def test_bridge_calls_multiple_listeners(mock_agent_loop: dict) -> None:
    """Test that EventBridge calls all registered listeners."""
    from vibe.cli.web_ui.sync.bridge import EventBridge

    bridge = EventBridge(agent_loop=mock_agent_loop)
    events1: list[BaseEvent] = []
    events2: list[BaseEvent] = []

    bridge.add_event_listener(lambda e: events1.append(e))
    bridge.add_event_listener(lambda e: events2.append(e))

    test_event = UserMessageEvent(content="Test", message_id="2")
    bridge.on_event(test_event)

    assert len(events1) == 1
    assert len(events2) == 1
    assert events1[0] == events2[0] == test_event


def test_bridge_can_remove_listener(mock_agent_loop: dict) -> None:
    """Test that EventBridge can remove event listeners."""
    from vibe.cli.web_ui.sync.bridge import EventBridge

    bridge = EventBridge(agent_loop=mock_agent_loop)
    events_received: list[BaseEvent] = []

    def listener(event: BaseEvent) -> None:
        events_received.append(event)

    bridge.add_event_listener(listener)
    assert len(bridge._event_listeners) == 1

    bridge.remove_event_listener(listener)
    assert len(bridge._event_listeners) == 0

    # Event should not be received after removal
    test_event = AssistantEvent(content="Hello", message_id="1")
    bridge.on_event(test_event)
    assert len(events_received) == 0
