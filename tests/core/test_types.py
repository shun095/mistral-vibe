from __future__ import annotations

"""Tests for core types including WebNotificationEvent."""

import pytest

from vibe.core.types import WebNotificationEvent


class TestWebNotificationEvent:
    """Test WebNotificationEvent serialization and validation."""

    def test_action_required_context(self) -> None:
        """Test creating event with action_required context."""
        event = WebNotificationEvent(
            context="action_required",
            title="Action Required",
            message="Tool 'bash' needs approval",
        )
        assert event.context == "action_required"
        assert event.title == "Action Required"
        assert event.message == "Tool 'bash' needs approval"

    def test_complete_context(self) -> None:
        """Test creating event with complete context."""
        event = WebNotificationEvent(
            context="complete",
            title="Task Complete",
            message="Assistant has finished processing",
        )
        assert event.context == "complete"
        assert event.title == "Task Complete"
        assert event.message == "Assistant has finished processing"

    def test_message_optional(self) -> None:
        """Test that message field is optional."""
        event = WebNotificationEvent(context="complete", title="Task Complete")
        assert event.message is None

    def test_serialization(self) -> None:
        """Test event serializes correctly for JSON transmission."""
        event = WebNotificationEvent(
            context="action_required", title="Action Required", message="Test message"
        )
        data = event.model_dump(mode="json", exclude_none=True)
        assert data == {
            "context": "action_required",
            "title": "Action Required",
            "message": "Test message",
        }

    def test_serialization_excludes_none_message(self) -> None:
        """Test that None message is excluded from serialization."""
        event = WebNotificationEvent(
            context="complete", title="Task Complete", message=None
        )
        data = event.model_dump(mode="json", exclude_none=True)
        assert "message" not in data
        assert data == {"context": "complete", "title": "Task Complete"}

    def test_invalid_context_fails(self) -> None:
        """Test that invalid context value raises validation error."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            WebNotificationEvent(
                context="invalid_context",  # type: ignore
                title="Test",
            )
        assert "context" in str(exc_info.value)
