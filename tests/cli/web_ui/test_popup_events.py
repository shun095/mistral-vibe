"""Tests for popup event serialization and handling in web UI."""

from __future__ import annotations


# Fake tool class for testing
class FakeTool:  # type: ignore
    pass


class TestApprovalPopupEventSerialization:
    """Test ApprovalPopupEvent serialization."""

    def test_serialize_approval_popup_event(self) -> None:
        """Test that ApprovalPopupEvent is properly serialized."""
        from vibe.cli.web_ui.server import serialize_event
        from vibe.core.types import ApprovalPopupEvent

        event = ApprovalPopupEvent(
            popup_id="approval_123",
            tool_name="bash",
            tool_args={"command": "rm -rf /", "timeout": 30},
            timestamp=1234567890.0,
        )

        data = serialize_event(event)

        # Check basic fields
        assert data["__type"] == "ApprovalPopupEvent"
        assert data["popup_id"] == "approval_123"
        assert data["tool_name"] == "bash"
        assert data["tool_args"]["command"] == "rm -rf /"
        assert data["tool_args"]["timeout"] == 30
        assert data["timestamp"] == 1234567890.0

    def test_serialize_approval_popup_event_empty_args(self) -> None:
        """Test that ApprovalPopupEvent with empty args is properly serialized."""
        from vibe.cli.web_ui.server import serialize_event
        from vibe.core.types import ApprovalPopupEvent

        event = ApprovalPopupEvent(
            popup_id="approval_456",
            tool_name="docker",
            tool_args={},
            timestamp=1234567891.0,
        )

        data = serialize_event(event)

        assert data["__type"] == "ApprovalPopupEvent"
        assert data["popup_id"] == "approval_456"
        assert data["tool_name"] == "docker"
        assert data["tool_args"] == {}


class TestQuestionPopupEventSerialization:
    """Test QuestionPopupEvent serialization."""

    def test_serialize_question_popup_event(self) -> None:
        """Test that QuestionPopupEvent is properly serialized."""
        from vibe.cli.web_ui.server import serialize_event
        from vibe.core.types import QuestionPopupEvent

        event = QuestionPopupEvent(
            popup_id="question_789",
            questions=[
                {
                    "question": "What is your name?",
                    "header": "Name",
                    "options": [
                        {"label": "Alice", "description": "A common name"},
                        {"label": "Bob", "description": "Another common name"},
                    ],
                    "multi_select": False,
                }
            ],
            content_preview="Please answer the following question",
            timestamp=1234567892.0,
        )

        data = serialize_event(event)

        assert data["__type"] == "QuestionPopupEvent"
        assert data["popup_id"] == "question_789"
        assert len(data["questions"]) == 1
        assert data["questions"][0]["question"] == "What is your name?"
        assert data["content_preview"] == "Please answer the following question"
        assert data["timestamp"] == 1234567892.0

    def test_serialize_question_popup_event_no_preview(self) -> None:
        """Test that QuestionPopupEvent without content_preview is properly serialized."""
        from vibe.cli.web_ui.server import serialize_event
        from vibe.core.types import QuestionPopupEvent

        event = QuestionPopupEvent(
            popup_id="question_999",
            questions=[
                {
                    "question": "Confirm action?",
                    "header": "Confirm",
                    "options": [
                        {"label": "Yes", "description": "Confirm"},
                        {"label": "No", "description": "Cancel"},
                    ],
                    "multi_select": False,
                }
            ],
            content_preview=None,
            timestamp=1234567893.0,
        )

        data = serialize_event(event)

        assert data["__type"] == "QuestionPopupEvent"
        assert data["popup_id"] == "question_999"
        # content_preview should not be present when None (exclude_none=True)
        assert "content_preview" not in data


class TestPopupResponseEventSerialization:
    """Test PopupResponseEvent serialization."""

    def test_serialize_approval_response_event(self) -> None:
        """Test that PopupResponseEvent for approval is properly serialized."""
        from vibe.cli.web_ui.server import serialize_event
        from vibe.core.types import PopupResponseEvent

        event = PopupResponseEvent(
            popup_id="approval_123",
            response_type="approval",
            response_data={"response": "y", "feedback": None},
            cancelled=False,
        )

        data = serialize_event(event)

        assert data["__type"] == "PopupResponseEvent"
        assert data["popup_id"] == "approval_123"
        assert data["response_type"] == "approval"
        assert data["response_data"]["response"] == "y"
        assert data["cancelled"] is False

    def test_serialize_question_response_event(self) -> None:
        """Test that PopupResponseEvent for question is properly serialized."""
        from vibe.cli.web_ui.server import serialize_event
        from vibe.core.types import PopupResponseEvent

        event = PopupResponseEvent(
            popup_id="question_789",
            response_type="question",
            response_data={"answers": [{"text": "Alice", "option_index": 0}]},
            cancelled=False,
        )

        data = serialize_event(event)

        assert data["__type"] == "PopupResponseEvent"
        assert data["popup_id"] == "question_789"
        assert data["response_type"] == "question"
        assert len(data["response_data"]["answers"]) == 1
        assert data["cancelled"] is False

    def test_serialize_cancelled_response_event(self) -> None:
        """Test that PopupResponseEvent with cancelled=True is properly serialized."""
        from vibe.cli.web_ui.server import serialize_event
        from vibe.core.types import PopupResponseEvent

        event = PopupResponseEvent(
            popup_id="approval_456",
            response_type="approval",
            response_data={"response": "n"},
            cancelled=True,
        )

        data = serialize_event(event)

        assert data["__type"] == "PopupResponseEvent"
        assert data["cancelled"] is True


class TestPopupEventTypes:
    """Test popup event type definitions."""

    def test_approval_popup_event_fields(self) -> None:
        """Test that ApprovalPopupEvent has required fields."""
        from vibe.core.types import ApprovalPopupEvent

        event = ApprovalPopupEvent(
            popup_id="test_id",
            tool_name="bash",
            tool_args={"command": "ls"},
            timestamp=1234567890.0,
        )

        assert event.popup_id == "test_id"
        assert event.tool_name == "bash"
        assert event.tool_args == {"command": "ls"}
        assert event.timestamp == 1234567890.0

    def test_question_popup_event_fields(self) -> None:
        """Test that QuestionPopupEvent has required fields."""
        from vibe.core.types import QuestionPopupEvent

        event = QuestionPopupEvent(
            popup_id="test_id",
            questions=[{"question": "Test?", "header": "Test", "options": [], "multi_select": False}],
            content_preview="Test preview",
            timestamp=1234567890.0,
        )

        assert event.popup_id == "test_id"
        assert len(event.questions) == 1
        assert event.content_preview == "Test preview"
        assert event.timestamp == 1234567890.0

    def test_popup_response_event_fields(self) -> None:
        """Test that PopupResponseEvent has required fields."""
        from vibe.core.types import PopupResponseEvent

        event = PopupResponseEvent(
            popup_id="test_id",
            response_type="approval",
            response_data={"response": "y"},
            cancelled=False,
        )

        assert event.popup_id == "test_id"
        assert event.response_type == "approval"
        assert event.response_data == {"response": "y"}
        assert event.cancelled is False
