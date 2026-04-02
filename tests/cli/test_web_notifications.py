from __future__ import annotations

from typing import Any

from tests.conftest import build_test_vibe_app, build_test_vibe_config
from vibe.cli.web_ui.events import WebNotificationEvent


class TestBroadcastWebNotification:
    """Test _broadcast_web_notification method via web_broadcast_manager."""

    def test_broadcasts_event_when_enabled(self) -> None:
        """Test that notification event is broadcast when enabled."""
        config = build_test_vibe_config()
        config.enable_web_notifications = True
        app = build_test_vibe_app(config=config)

        events_received: list[WebNotificationEvent] = []

        def event_listener(event: Any) -> None:
            if isinstance(event, WebNotificationEvent):
                events_received.append(event)

        app.agent_loop.add_event_listener(event_listener)

        app._web_broadcast_manager._broadcast_web_notification(
            context="action_required",
            title="Action Required",
            message="Tool 'bash' needs approval",
        )

        assert len(events_received) == 1
        event = events_received[0]
        assert event.context == "action_required"
        assert event.title == "Action Required"
        assert event.message == "Tool 'bash' needs approval"

    def test_no_broadcast_when_disabled(self) -> None:
        """Test that no event is broadcast when notifications are disabled."""
        config = build_test_vibe_config()
        config.enable_web_notifications = False
        app = build_test_vibe_app(config=config)

        events_received: list[WebNotificationEvent] = []

        def event_listener(event: Any) -> None:
            if isinstance(event, WebNotificationEvent):
                events_received.append(event)

        app.agent_loop.add_event_listener(event_listener)

        app._web_broadcast_manager._broadcast_web_notification(
            context="action_required", title="Action Required", message="Test message"
        )

        assert len(events_received) == 0

    def test_broadcasts_complete_context(self) -> None:
        """Test broadcasting with complete context."""
        config = build_test_vibe_config()
        config.enable_web_notifications = True
        app = build_test_vibe_app(config=config)

        events_received: list[WebNotificationEvent] = []

        def event_listener(event: Any) -> None:
            if isinstance(event, WebNotificationEvent):
                events_received.append(event)

        app.agent_loop.add_event_listener(event_listener)

        app._web_broadcast_manager._broadcast_web_notification(
            context="complete",
            title="Task Complete",
            message="Assistant has finished processing",
        )

        assert len(events_received) == 1
        event = events_received[0]
        assert event.context == "complete"
        assert event.title == "Task Complete"
        assert event.message == "Assistant has finished processing"

    def test_broadcasts_without_message(self) -> None:
        """Test broadcasting without a message."""
        config = build_test_vibe_config()
        config.enable_web_notifications = True
        app = build_test_vibe_app(config=config)

        events_received: list[WebNotificationEvent] = []

        def event_listener(event: Any) -> None:
            if isinstance(event, WebNotificationEvent):
                events_received.append(event)

        app.agent_loop.add_event_listener(event_listener)

        app._web_broadcast_manager._broadcast_web_notification(
            context="complete", title="Task Complete"
        )

        assert len(events_received) == 1
        event = events_received[0]
        assert event.context == "complete"
        assert event.title == "Task Complete"
        assert event.message is None

    def test_multiple_broadcasts(self) -> None:
        """Test multiple broadcasts are all received."""
        config = build_test_vibe_config()
        config.enable_web_notifications = True
        app = build_test_vibe_app(config=config)

        events_received: list[WebNotificationEvent] = []

        def event_listener(event: Any) -> None:
            if isinstance(event, WebNotificationEvent):
                events_received.append(event)

        app.agent_loop.add_event_listener(event_listener)

        app._web_broadcast_manager._broadcast_web_notification(
            context="action_required",
            title="Action Required",
            message="First notification",
        )
        app._web_broadcast_manager._broadcast_web_notification(
            context="complete", title="Task Complete", message="Second notification"
        )

        assert len(events_received) == 2
        assert events_received[0].context == "action_required"
        assert events_received[1].context == "complete"
