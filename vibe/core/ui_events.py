"""UI-specific events for popup and notification handling.

This module contains events that are specific to UI interactions,
separating them from core agent loop events in types.py.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from vibe.core.types import BaseEvent


class ApprovalPopupEvent(BaseEvent):
    """Event broadcast when approval popup is shown."""

    popup_id: str = Field(description="Unique ID for this popup instance")
    tool_name: str = Field(description="Name of the tool requiring approval")
    tool_args: dict = Field(description="Serialized tool arguments")
    timestamp: float = Field(description="Timestamp when popup was created")


class QuestionPopupEvent(BaseEvent):
    """Event broadcast when question popup is shown."""

    popup_id: str = Field(description="Unique ID for this popup instance")
    questions: list[dict] = Field(
        description="Serialized AskUserQuestionArgs.questions"
    )
    content_preview: str | None = Field(
        default=None, description="Optional preview content"
    )
    timestamp: float = Field(description="Timestamp when popup was created")


class PopupResponseEvent(BaseEvent):
    """Event broadcast when popup is answered."""

    popup_id: str = Field(description="Unique ID of the popup being answered")
    response_type: Literal["approval", "question"] = Field(
        description="Type of popup response"
    )
    response_data: dict = Field(description="Serialized response data")
    cancelled: bool = Field(description="Whether the popup was cancelled")


class MessageResetEvent(BaseEvent):
    """Event broadcast when message history is reset.

    Triggered by /clear, /compact, /resume, or auto-compact operations.
    """

    reason: Literal["clear", "compact", "resume", "auto_compact"] = Field(
        description="Reason for the message reset"
    )


__all__ = [
    "ApprovalPopupEvent",
    "MessageResetEvent",
    "PopupResponseEvent",
    "QuestionPopupEvent",
]
