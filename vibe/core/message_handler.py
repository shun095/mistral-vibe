"""Message handling strategies for the agent loop.

This module provides strategy classes for handling different types of
message operations in the conversation loop.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from vibe.core.types import LLMMessage, MessageList, Role


class MessageHandlerStrategy(ABC):
    """Base strategy for handling user messages in the conversation loop."""

    @abstractmethod
    def prepare_message(
        self, messages: MessageList, user_msg: str | None
    ) -> tuple[str, str]:
        """Prepare the message content and ID for the conversation loop.

        Args:
            messages: The message history.
            user_msg: New user message (if any).

        Returns:
            Tuple of (content, message_id).

        Raises:
            ValueError: If no valid message can be prepared.
        """
        pass

    @abstractmethod
    def should_increment_steps(self) -> bool:
        """Whether this operation should increment the step counter."""
        pass


class NewMessageHandler(MessageHandlerStrategy):
    """Handler for new user messages that should be added to history."""

    def prepare_message(
        self, messages: MessageList, user_msg: str | None
    ) -> tuple[str, str]:
        if user_msg is None:
            raise ValueError("NewMessageHandler requires a user message")

        user_message = LLMMessage(role=Role.user, content=user_msg)
        messages.append(user_message)

        if user_message.message_id is None:
            raise ValueError("User message must have a message_id")

        return user_msg, user_message.message_id

    def should_increment_steps(self) -> bool:
        return True


class HistoryReplayHandler(MessageHandlerStrategy):
    """Handler for replaying existing messages from history (e.g., after editing)."""

    def prepare_message(
        self, messages: MessageList, user_msg: str | None
    ) -> tuple[str, str]:
        if user_msg is not None:
            raise ValueError("HistoryReplayHandler should not receive a new message")

        from vibe.cli.textual_ui.windowing.history import non_system_history_messages

        history_messages = non_system_history_messages(messages)
        last_user_message: LLMMessage | None = None

        for msg in reversed(history_messages):
            if msg.role == Role.user:
                last_user_message = msg
                break

        if last_user_message is None:
            raise ValueError("No user message found in history")

        # Get content from the last user message
        msg_content = last_user_message.content
        if isinstance(msg_content, list):
            msg_content = "".join(str(item) for item in msg_content)
        elif msg_content is None:
            msg_content = ""

        return msg_content, last_user_message.message_id  # type: ignore[return-value]

    def should_increment_steps(self) -> bool:
        return False


def create_message_handler(
    user_msg: str | None,
) -> MessageHandlerStrategy:
    """Factory function to create the appropriate message handler.

    Args:
        user_msg: New user message (if any). If None, uses history replay.

    Returns:
        The appropriate MessageHandlerStrategy instance.
    """
    if user_msg is not None:
        return NewMessageHandler()
    return HistoryReplayHandler()
