"""Message handling strategies for the agent loop.

This module provides strategy classes for handling different types of
message operations in the conversation loop.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from vibe.core.types import Content, LLMMessage, MessageList, Role


class MessageHandlerStrategy(ABC):
    """Base strategy for handling user messages in the conversation loop."""

    @abstractmethod
    def prepare_message(
        self, messages: MessageList, user_msg: Content | None
    ) -> tuple[Content, str]:
        """Prepare the message content and ID for the conversation loop.

        Args:
            messages: The message history.
            user_msg: New user message (if any), can be string or multi-part content.

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

    def __init__(self, client_message_id: str | None = None) -> None:
        self.client_message_id = client_message_id

    def prepare_message(
        self, messages: MessageList, user_msg: Content | None
    ) -> tuple[Content, str]:
        if user_msg is None:
            raise ValueError("NewMessageHandler requires a user message")

        user_message = LLMMessage(
            role=Role.user, content=user_msg, message_id=self.client_message_id
        )
        messages.append(user_message)

        if user_message.message_id is None:
            raise ValueError("User message must have a message_id")

        return user_msg, user_message.message_id

    def should_increment_steps(self) -> bool:
        return True


class HistoryReplayHandler(MessageHandlerStrategy):
    """Handler for replaying existing messages from history (e.g., after editing)."""

    def prepare_message(
        self, messages: MessageList, user_msg: Content | None
    ) -> tuple[Content, str]:
        if user_msg is not None:
            raise ValueError("HistoryReplayHandler should not receive a new message")

        # Filter out system messages
        history_messages = [msg for msg in messages if msg.role != Role.system]
        last_user_message: LLMMessage | None = None

        for msg in reversed(history_messages):
            if msg.role == Role.user:
                last_user_message = msg
                break

        if last_user_message is None:
            raise ValueError("No user message found in history")

        # Get content from the last user message (preserve type)
        msg_content = last_user_message.content
        if msg_content is None:
            msg_content = ""

        return msg_content, last_user_message.message_id  # type: ignore[return-value]

    def should_increment_steps(self) -> bool:
        return False


def create_message_handler(
    user_msg: Content | None, client_message_id: str | None = None
) -> MessageHandlerStrategy:
    """Factory function to create the appropriate message handler.

    Args:
        user_msg: New user message (if any), can be string or multi-part content.
            If None, uses history replay.
        client_message_id: Optional message ID from the client for tracking.

    Returns:
        The appropriate MessageHandlerStrategy instance.
    """
    if user_msg is not None:
        return NewMessageHandler(client_message_id=client_message_id)
    return HistoryReplayHandler()
