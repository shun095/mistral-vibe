"""WebUI-specific events for browser notifications.

This module contains events that are specific to the WebUI,
separating them from shared UI events in vibe.core.ui_events.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from vibe.core.types import BaseEvent, DownloadableContentEvent


class WebNotificationEvent(BaseEvent):
    """Event broadcast to trigger browser notifications in WebUI.

    Triggered when user interaction is required or task completes.
    """

    context: Literal["action_required", "complete"] = Field(
        description="Context for the notification"
    )
    title: str = Field(description="Notification title")
    message: str | None = Field(
        default=None, description="Optional notification message"
    )


__all__ = ["DownloadableContentEvent", "WebNotificationEvent"]
