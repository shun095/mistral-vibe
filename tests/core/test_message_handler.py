"""Tests for message handler with multi-part content support."""

import pytest
from vibe.core.message_handler import (
    NewMessageHandler,
    HistoryReplayHandler,
    create_message_handler,
)
from vibe.core.types import LLMMessage, MessageList, Role


class TestNewMessageHandler:
    """Tests for NewMessageHandler with multi-part content."""

    def test_prepare_message_with_string(self):
        """Test preparing a regular string message."""
        handler = NewMessageHandler()
        messages = MessageList()
        user_msg = "Hello, world!"

        content, message_id = handler.prepare_message(messages, user_msg)

        assert content == user_msg
        assert message_id is not None
        assert len(messages) == 1
        assert messages[0].role == Role.user
        assert messages[0].content == user_msg

    def test_prepare_message_with_multi_part_content(self):
        """Test preparing a multi-part content message (text + image)."""
        handler = NewMessageHandler()
        messages = MessageList()
        user_msg = [
            {"type": "text", "text": "What is in this image?"},
            {
                "type": "image_url",
                "image_url": {"url": "data:image/png;base64,abc123"},
            },
        ]

        content, message_id = handler.prepare_message(messages, user_msg)

        assert content == user_msg
        assert message_id is not None
        assert len(messages) == 1
        assert messages[0].role == Role.user
        assert messages[0].content == user_msg

    def test_prepare_message_with_image_only(self):
        """Test preparing an image-only message."""
        handler = NewMessageHandler()
        messages = MessageList()
        user_msg = [
            {
                "type": "image_url",
                "image_url": {"url": "data:image/jpeg;base64,xyz789"},
            }
        ]

        content, message_id = handler.prepare_message(messages, user_msg)

        assert content == user_msg
        assert message_id is not None
        assert len(messages) == 1
        assert messages[0].role == Role.user
        assert messages[0].content == user_msg

    def test_prepare_message_with_none_raises_error(self):
        """Test that None message raises ValueError."""
        handler = NewMessageHandler()
        messages = MessageList()

        with pytest.raises(ValueError, match="requires a user message"):
            handler.prepare_message(messages, None)

    def test_should_increment_steps(self):
        """Test that new messages increment steps."""
        handler = NewMessageHandler()
        assert handler.should_increment_steps() is True


class TestHistoryReplayHandler:
    """Tests for HistoryReplayHandler with multi-part content."""

    def test_prepare_message_with_string_in_history(self):
        """Test replaying a string message from history."""
        handler = HistoryReplayHandler()
        messages = MessageList(
            [
                LLMMessage(role=Role.user, content="Previous message"),
                LLMMessage(role=Role.assistant, content="Response"),
            ]
        )

        content, message_id = handler.prepare_message(messages, None)

        assert content == "Previous message"
        assert message_id == messages[0].message_id

    def test_prepare_message_with_multi_part_in_history(self):
        """Test replaying a multi-part message from history."""
        original_content = [
            {"type": "text", "text": "What is this?"},
            {
                "type": "image_url",
                "image_url": {"url": "data:image/png;base64,test123"},
            },
        ]
        handler = HistoryReplayHandler()
        messages = MessageList(
            [
                LLMMessage(role=Role.user, content=original_content),
                LLMMessage(role=Role.assistant, content="Response"),
            ]
        )

        content, message_id = handler.prepare_message(messages, None)

        # Should preserve the original multi-part structure
        assert content == original_content
        assert message_id == messages[0].message_id

    def test_prepare_message_with_new_message_raises_error(self):
        """Test that providing a new message raises ValueError."""
        handler = HistoryReplayHandler()
        messages = MessageList()

        with pytest.raises(
            ValueError, match="should not receive a new message"
        ):
            handler.prepare_message(messages, "new message")

    def test_prepare_message_with_no_user_message_raises_error(self):
        """Test that missing user message raises ValueError."""
        handler = HistoryReplayHandler()
        messages = MessageList(
            [
                LLMMessage(role=Role.assistant, content="Response"),
            ]
        )

        with pytest.raises(ValueError, match="No user message found"):
            handler.prepare_message(messages, None)

    def test_prepare_message_with_none_content(self):
        """Test handling None content in history."""
        handler = HistoryReplayHandler()
        messages = MessageList(
            [
                LLMMessage(role=Role.user, content=None),
            ]
        )

        content, message_id = handler.prepare_message(messages, None)

        assert content == ""
        assert message_id == messages[0].message_id

    def test_should_increment_steps(self):
        """Test that history replay does not increment steps."""
        handler = HistoryReplayHandler()
        assert handler.should_increment_steps() is False


class TestCreateMessageHandler:
    """Tests for the factory function."""

    def test_create_handler_with_string_message(self):
        """Test creating handler with string message."""
        handler = create_message_handler("Hello")
        assert isinstance(handler, NewMessageHandler)

    def test_create_handler_with_multi_part_message(self):
        """Test creating handler with multi-part message."""
        user_msg = [
            {"type": "text", "text": "Hello"},
            {"type": "image_url", "image_url": {"url": "data:..."}},
        ]
        handler = create_message_handler(user_msg)
        assert isinstance(handler, NewMessageHandler)

    def test_create_handler_with_none_message(self):
        """Test creating handler with None message."""
        handler = create_message_handler(None)
        assert isinstance(handler, HistoryReplayHandler)
