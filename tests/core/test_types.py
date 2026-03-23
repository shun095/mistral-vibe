from __future__ import annotations

"""Tests for core types including WebNotificationEvent and PromptProgress."""

import pytest

from vibe.cli.web_ui.events import WebNotificationEvent
from vibe.core.types import PromptProgress, PromptProgressEvent


class TestPromptProgress:
    """Test PromptProgress model validation and calculations."""

    def test_basic_creation(self) -> None:
        """Test creating PromptProgress with valid data."""
        progress = PromptProgress(total=1000, cache=200, processed=500, time_ms=1500)
        assert progress.total == 1000
        assert progress.cache == 200
        assert progress.processed == 500
        assert progress.time_ms == 1500

    def test_zero_values(self) -> None:
        """Test PromptProgress with zero values."""
        progress = PromptProgress(total=0, cache=0, processed=0, time_ms=0)
        assert progress.total == 0
        assert progress.cache == 0
        assert progress.processed == 0
        assert progress.time_ms == 0


class TestPromptProgressEvent:
    """Test PromptProgressEvent validation and progress calculation."""

    def test_basic_creation(self) -> None:
        """Test creating PromptProgressEvent with valid data."""
        event = PromptProgressEvent(total=1000, cache=200, processed=500, time_ms=1500)
        assert event.total == 1000
        assert event.cache == 200
        assert event.processed == 500
        assert event.time_ms == 1500

    def test_progress_percentage_full(self) -> None:
        """Test progress percentage calculation at 100%."""
        event = PromptProgressEvent(total=1000, cache=0, processed=1000, time_ms=2000)
        assert event.progress_percentage == 100.0

    def test_progress_percentage_half(self) -> None:
        """Test progress percentage calculation at 50%."""
        event = PromptProgressEvent(total=1000, cache=0, processed=500, time_ms=1000)
        assert event.progress_percentage == 50.0

    def test_progress_percentage_with_cache(self) -> None:
        """Test progress percentage with cached tokens."""
        event = PromptProgressEvent(total=1000, cache=200, processed=600, time_ms=1500)
        # Overall progress is processed/total
        assert event.progress_percentage == 60.0

    def test_progress_percentage_zero_total(self) -> None:
        """Test progress percentage when total is zero (avoid division by zero)."""
        event = PromptProgressEvent(total=0, cache=0, processed=0, time_ms=0)
        assert event.progress_percentage == 0.0

    def test_progress_percentage_partial(self) -> None:
        """Test progress percentage with partial processing."""
        event = PromptProgressEvent(total=1000, cache=100, processed=350, time_ms=500)
        assert event.progress_percentage == 35.0

    def test_serialization(self) -> None:
        """Test event serializes correctly for JSON transmission."""
        event = PromptProgressEvent(total=1000, cache=200, processed=500, time_ms=1500)
        data = event.model_dump(mode="json")
        assert data == {"total": 1000, "cache": 200, "processed": 500, "time_ms": 1500}


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
