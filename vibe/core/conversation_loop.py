"""Conversation loop utilities for edit operations."""

from __future__ import annotations

from vibe.cli.textual_ui.windowing.history import (
    non_system_history_messages,
)
from vibe.core.llm.types import LLMMessage
from vibe.core.types import MessageList, Role


def extract_last_user_message(
    messages: MessageList,
) -> tuple[str | None, str | None]:
    """Extract the last user message from history.

    Args:
        messages: List of messages in conversation history.

    Returns:
        Tuple of (content, message_id). Returns (None, None) if not found.
    """
    history_messages = non_system_history_messages(messages)
    last_user_message: LLMMessage | None = None

    for msg in reversed(history_messages):
        if msg.role == Role.user:
            last_user_message = msg
            break

    if last_user_message is None:
        return None, None

    # Get content from the last user message
    msg_content = last_user_message.content
    if isinstance(msg_content, list):
        msg_content = "".join(str(item) for item in msg_content)
    elif msg_content is None:
        msg_content = ""

    return msg_content, last_user_message.message_id
