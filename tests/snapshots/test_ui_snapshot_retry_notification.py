"""Snapshot tests for LLM retry toast notifications."""

from __future__ import annotations

from textual.pilot import Pilot

from tests.snapshots.base_snapshot_test_app import BaseSnapshotTestApp
from tests.snapshots.snap_compare import SnapCompare
from vibe.core.types import LLMRetryEvent


class RetryNotificationApp(BaseSnapshotTestApp):
    """Test app that shows retry notifications."""

    async def on_mount(self) -> None:
        """Show retry notifications on mount."""
        await super().on_mount()

        # Show first retry notification
        event1 = LLMRetryEvent(
            attempt=1,
            max_attempts=3,
            error_message="Connection timeout",
            delay_seconds=1.0,
            provider="mistral",
            model="mistral-large",
        )
        self._web_broadcast_manager._show_retry_notification(event1)

        # Show second retry notification
        event2 = LLMRetryEvent(
            attempt=2,
            max_attempts=3,
            error_message="Connection timeout",
            delay_seconds=2.0,
            provider="mistral",
            model="mistral-large",
        )
        self._web_broadcast_manager._show_retry_notification(event2)


def test_snapshot_shows_retry_notification_with_provider(
    snap_compare: SnapCompare,
) -> None:
    """Test snapshot shows retry notification with provider info."""

    async def run_before(pilot: Pilot) -> None:
        # Wait for notifications to be rendered
        await pilot.pause(0.3)

    assert snap_compare(
        "test_ui_snapshot_retry_notification.py:RetryNotificationApp",
        terminal_size=(120, 36),
        run_before=run_before,
    )


class RetryNotificationNoProviderApp(BaseSnapshotTestApp):
    """Test app that shows retry notifications without provider."""

    async def on_mount(self) -> None:
        """Show retry notification on mount."""
        await super().on_mount()

        # Show retry notification without provider
        event = LLMRetryEvent(
            attempt=1,
            max_attempts=3,
            error_message="Rate limit exceeded",
            delay_seconds=1.0,
            provider=None,
            model=None,
        )
        self._web_broadcast_manager._show_retry_notification(event)


def test_snapshot_shows_retry_notification_without_provider(
    snap_compare: SnapCompare,
) -> None:
    """Test snapshot shows retry notification without provider info."""

    async def run_before(pilot: Pilot) -> None:
        # Wait for notifications to be rendered
        await pilot.pause(0.3)

    assert snap_compare(
        "test_ui_snapshot_retry_notification.py:RetryNotificationNoProviderApp",
        terminal_size=(120, 36),
        run_before=run_before,
    )
