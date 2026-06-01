"""Tests for retry toast notifications in TUI."""

from __future__ import annotations

import pytest
from textual.widgets._toast import Toast

from vibe.cli.textual_ui.app import VibeApp
from vibe.core.types import LLMRetryEvent


@pytest.mark.asyncio
async def test_retry_notification_shows_toast_with_provider(vibe_app: VibeApp) -> None:
    """Test that retry notification creates a toast with provider info."""
    async with vibe_app.run_test(notifications=True) as pilot:
        # Create a retry event with provider
        event = LLMRetryEvent(
            attempt=2,
            max_attempts=10,
            error_message="Connection timeout",
            delay_seconds=1.0,
            provider="mistral",
            model="mistral-large",
        )

        # Call the notification method via web_broadcast_manager
        vibe_app._web_broadcast_manager._show_retry_notification(event)

        # Give the app a moment to process the notification
        await pilot.pause()

        # Query the Toast widget (external behavior - what user sees)
        toasts = list(vibe_app.query(Toast))
        assert len(toasts) == 1

        toast = toasts[0]
        renderable = toast.render()
        render_text = str(renderable)

        # Verify toast content (what user would see)
        assert "attempt 2/10" in render_text
        assert "mistral" in render_text
        assert "Retrying" in render_text


@pytest.mark.asyncio
async def test_retry_notification_shows_toast_without_provider(
    vibe_app: VibeApp,
) -> None:
    """Test that retry notification creates a toast without provider info."""
    async with vibe_app.run_test(notifications=True) as pilot:
        # Create a retry event without provider
        event = LLMRetryEvent(
            attempt=1,
            max_attempts=10,
            error_message="Rate limit exceeded",
            delay_seconds=2.0,
            provider=None,
            model=None,
        )

        # Call the notification method via web_broadcast_manager
        vibe_app._web_broadcast_manager._show_retry_notification(event)

        # Give the app a moment to process the notification
        await pilot.pause()

        # Query the Toast widget
        toasts = list(vibe_app.query(Toast))
        assert len(toasts) == 1

        toast = toasts[0]
        renderable = toast.render()
        render_text = str(renderable)

        # Verify toast content (no provider in message)
        assert "attempt 1/10" in render_text
        assert "Retrying" in render_text
        assert "(mistral)" not in render_text


@pytest.mark.asyncio
async def test_multiple_retry_notifications_accumulate(vibe_app: VibeApp) -> None:
    """Test that multiple retry notifications accumulate."""
    async with vibe_app.run_test(notifications=True) as pilot:
        # Create multiple retry events
        event1 = LLMRetryEvent(
            attempt=1,
            max_attempts=10,
            error_message="Connection timeout",
            delay_seconds=1.0,
            provider="mistral",
            model=None,
        )

        event2 = LLMRetryEvent(
            attempt=2,
            max_attempts=10,
            error_message="Connection timeout",
            delay_seconds=2.0,
            provider="mistral",
            model=None,
        )

        # Call the notification method for both events via web_broadcast_manager
        vibe_app._web_broadcast_manager._show_retry_notification(event1)
        await pilot.pause()

        vibe_app._web_broadcast_manager._show_retry_notification(event2)
        await pilot.pause()

        # Query Toast widgets
        toasts = list(vibe_app.query(Toast))
        assert len(toasts) == 2

        # Verify both toasts contain expected content
        toast_texts = [str(toast.render()) for toast in toasts]

        # Find the toast for attempt 1
        attempt1_toast = next((t for t in toast_texts if "attempt 1/10" in t), None)
        assert attempt1_toast is not None
        assert "Retrying" in attempt1_toast

        # Find the toast for attempt 2
        attempt2_toast = next((t for t in toast_texts if "attempt 2/10" in t), None)
        assert attempt2_toast is not None
        assert "Retrying" in attempt2_toast
