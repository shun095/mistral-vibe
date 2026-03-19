"""Tests for message utility functions."""

from __future__ import annotations

from vibe.core.llm.message_utils import merge_consecutive_user_messages
from vibe.core.types import LLMMessage, Role


class TestMergeConsecutiveUserMessages:
    """Test merge_consecutive_user_messages function."""

    def test_merge_two_string_messages(self) -> None:
        """Test merging two consecutive user messages with string content."""
        msg1 = LLMMessage(role=Role.user, content="Hello")
        msg2 = LLMMessage(role=Role.user, content="World")

        merged = merge_consecutive_user_messages([msg1, msg2])

        assert len(merged) == 1
        assert merged[0].content == "Hello\n\nWorld"

    def test_merge_string_with_image_message(self) -> None:
        """Test merging string message with multi-part content containing image."""
        msg1 = LLMMessage(role=Role.user, content="Hello")
        msg2 = LLMMessage(
            role=Role.user,
            content=[
                {"type": "text", "text": "test message"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,abcdefg"},
                },
            ],
        )

        merged = merge_consecutive_user_messages([msg1, msg2])

        assert len(merged) == 1
        assert isinstance(merged[0].content, list)
        assert len(merged[0].content) == 3
        assert merged[0].content[0] == {"type": "text", "text": "Hello"}
        assert merged[0].content[1] == {"type": "text", "text": "test message"}
        assert merged[0].content[2]["type"] == "image_url"
        assert merged[0].content[2]["image_url"]["url"] == "data:image/png;base64,abcdefg"

    def test_merge_image_with_string_message(self) -> None:
        """Test merging multi-part content with image and string message."""
        msg1 = LLMMessage(
            role=Role.user,
            content=[
                {"type": "text", "text": "test message"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,abcdefg"},
                },
            ],
        )
        msg2 = LLMMessage(role=Role.user, content="Hello")

        merged = merge_consecutive_user_messages([msg1, msg2])

        assert len(merged) == 1
        assert isinstance(merged[0].content, list)
        assert len(merged[0].content) == 3
        assert merged[0].content[0] == {"type": "text", "text": "test message"}
        assert merged[0].content[1]["type"] == "image_url"
        assert merged[0].content[1]["image_url"]["url"] == "data:image/png;base64,abcdefg"
        assert merged[0].content[2] == {"type": "text", "text": "Hello"}

    def test_merge_two_image_messages(self) -> None:
        """Test merging two consecutive user messages both with multi-part content."""
        msg1 = LLMMessage(
            role=Role.user,
            content=[
                {"type": "text", "text": "first message"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,image1"},
                },
            ],
        )
        msg2 = LLMMessage(
            role=Role.user,
            content=[
                {"type": "text", "text": "second message"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/jpeg;base64,image2"},
                },
            ],
        )

        merged = merge_consecutive_user_messages([msg1, msg2])

        assert len(merged) == 1
        assert isinstance(merged[0].content, list)
        assert len(merged[0].content) == 4
        assert merged[0].content[0] == {"type": "text", "text": "first message"}
        assert merged[0].content[1]["type"] == "image_url"
        assert merged[0].content[1]["image_url"]["url"] == "data:image/png;base64,image1"
        assert merged[0].content[2] == {"type": "text", "text": "second message"}
        assert merged[0].content[3]["type"] == "image_url"
        assert merged[0].content[3]["image_url"]["url"] == "data:image/jpeg;base64,image2"

    def test_no_merge_different_roles(self) -> None:
        """Test that messages with different roles are not merged."""
        msg1 = LLMMessage(role=Role.user, content="User message")
        msg2 = LLMMessage(role=Role.assistant, content="Assistant message")
        msg3 = LLMMessage(role=Role.user, content="Another user message")

        merged = merge_consecutive_user_messages([msg1, msg2, msg3])

        assert len(merged) == 3
        assert merged[0].content == "User message"
        assert merged[1].content == "Assistant message"
        assert merged[2].content == "Another user message"

    def test_preserve_message_id(self) -> None:
        """Test that message_id is preserved from the first message."""
        msg1 = LLMMessage(role=Role.user, content="Hello", message_id="msg-123")
        msg2 = LLMMessage(role=Role.user, content="World", message_id="msg-456")

        merged = merge_consecutive_user_messages([msg1, msg2])

        assert len(merged) == 1
        assert merged[0].message_id == "msg-123"

    def test_merge_with_empty_string(self) -> None:
        """Test merging with empty string content."""
        msg1 = LLMMessage(role=Role.user, content="Hello")
        msg2 = LLMMessage(role=Role.user, content="")

        merged = merge_consecutive_user_messages([msg1, msg2])

        assert len(merged) == 1
        assert merged[0].content == "Hello"

    def test_merge_image_only_message(self) -> None:
        """Test merging message with only image (no text)."""
        msg1 = LLMMessage(role=Role.user, content="Hello")
        msg2 = LLMMessage(
            role=Role.user,
            content=[
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,abcdefg"},
                }
            ],
        )

        merged = merge_consecutive_user_messages([msg1, msg2])

        assert len(merged) == 1
        assert isinstance(merged[0].content, list)
        assert len(merged[0].content) == 2
        assert merged[0].content[0] == {"type": "text", "text": "Hello"}
        assert merged[0].content[1]["type"] == "image_url"

    def test_merge_three_consecutive_user_messages(self) -> None:
        """Test merging three consecutive user messages."""
        msg1 = LLMMessage(role=Role.user, content="First")
        msg2 = LLMMessage(role=Role.user, content="Second")
        msg3 = LLMMessage(role=Role.user, content="Third")

        merged = merge_consecutive_user_messages([msg1, msg2, msg3])

        assert len(merged) == 1
        assert merged[0].content == "First\n\nSecond\n\nThird"

    def test_merge_mixed_content_three_messages(self) -> None:
        """Test merging three messages with mixed content types."""
        msg1 = LLMMessage(role=Role.user, content="First")
        msg2 = LLMMessage(
            role=Role.user,
            content=[
                {"type": "text", "text": "Second"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,img"},
                },
            ],
        )
        msg3 = LLMMessage(role=Role.user, content="Third")

        merged = merge_consecutive_user_messages([msg1, msg2, msg3])

        assert len(merged) == 1
        assert isinstance(merged[0].content, list)
        assert len(merged[0].content) == 4
        assert merged[0].content[0] == {"type": "text", "text": "First"}
        assert merged[0].content[1] == {"type": "text", "text": "Second"}
        assert merged[0].content[2]["type"] == "image_url"
        assert merged[0].content[3] == {"type": "text", "text": "Third"}
