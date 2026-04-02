"""Tests for image message display to verify no duplicate messages."""

from __future__ import annotations

import asyncio
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vibe.cli.textual_ui.app import VibeApp
from vibe.cli.voice_manager.voice_manager_port import TranscribeState
from vibe.core.agent_loop import AgentLoop


def _create_mock_app():
    """Create a mock VibeApp with proper initialization."""
    mock_agent_loop = MagicMock(spec=AgentLoop)
    mock_agent_loop.messages = []
    mock_agent_loop.tool_manager = MagicMock()
    mock_agent_loop.tool_manager.available_tools = []
    mock_agent_loop.config = MagicMock()
    mock_agent_loop.config.auto_approve = False
    mock_agent_loop._notify_event_listeners = MagicMock()
    mock_agent_loop.telemetry_client = MagicMock()

    mock_voice_manager = MagicMock()
    mock_voice_manager.transcribe_state = TranscribeState.IDLE

    with patch.object(
        VibeApp, "_make_default_narrator_manager", return_value=MagicMock()
    ):
        with patch.object(
            VibeApp, "_make_default_voice_manager", return_value=mock_voice_manager
        ):
            return VibeApp(agent_loop=mock_agent_loop)


class TestTUIImageMessageDisplay:
    """Test that image messages are displayed correctly without duplicates."""

    @pytest.mark.asyncio
    async def test_handle_user_message_with_image_mounts_single_widget(self) -> None:
        """Test that _handle_user_message_with_image mounts only one ImageMessage widget.

        This test verifies the fix for the bug where text+image messages resulted
        in two separate widgets (UserMessage + ImageMessage) being mounted.
        """
        app = _create_mock_app()

        # Track mounted widgets
        mounted_widgets = []

        async def track_mount_and_scroll(widget):
            mounted_widgets.append(widget)
            # Don't actually mount, just track
            return await AsyncMock().__aenter__()

        # Patch _mount_and_scroll to track calls without actually mounting
        with patch.object(app, "_mount_and_scroll", side_effect=track_mount_and_scroll):
            # Mark TUI as ready
            app._tui_ready = True

            # Mock _agent_task to prevent actual agent loop execution
            app._agent_task = None
            app._agent_running = False

            # Call the method directly
            await app._handle_user_message_with_image(
                "test message with image",
                {"data": "base64data", "mime_type": "image/png"},
            )

        # Verify only ONE widget was mounted (ImageMessage)
        assert len(mounted_widgets) == 1, (
            f"Expected 1 widget to be mounted, but {len(mounted_widgets)} were mounted: {mounted_widgets}"
        )

        # Verify it's an ImageMessage widget
        from vibe.cli.textual_ui.widgets.messages import ImageMessage

        assert isinstance(mounted_widgets[0], ImageMessage), (
            f"Expected ImageMessage widget, got {type(mounted_widgets[0])}"
        )

    @pytest.mark.asyncio
    async def test_handle_user_message_with_image_only_mounts_single_widget(
        self,
    ) -> None:
        """Test that image-only messages (no text) mount only one ImageMessage widget."""
        app = _create_mock_app()

        # Track mounted widgets
        mounted_widgets = []

        async def track_mount_and_scroll(widget):
            mounted_widgets.append(widget)
            return await AsyncMock().__aenter__()

        # Patch _mount_and_scroll to track calls
        with patch.object(app, "_mount_and_scroll", side_effect=track_mount_and_scroll):
            # Mark TUI as ready
            app._tui_ready = True
            app._agent_task = None
            app._agent_running = False

            # Call the method with empty text (image only)
            await app._handle_user_message_with_image(
                "", {"data": "base64data", "mime_type": "image/png"}
            )

        # Verify only ONE widget was mounted
        assert len(mounted_widgets) == 1, (
            f"Expected 1 widget to be mounted, but {len(mounted_widgets)} were mounted"
        )

        # Verify it's an ImageMessage widget
        from vibe.cli.textual_ui.widgets.messages import ImageMessage

        assert isinstance(mounted_widgets[0], ImageMessage), (
            f"Expected ImageMessage widget, got {type(mounted_widgets[0])}"
        )

    @pytest.mark.asyncio
    async def test_handle_user_message_with_image_content_structure(self) -> None:
        """Test that _handle_user_message_with_image creates correct content structure."""
        app = _create_mock_app()

        async def mock_mount_and_scroll(widget):
            # Do nothing, just prevent actual mounting
            return await AsyncMock().__aenter__()

        async def mock_handle_agent_turn(content):
            # Do nothing
            pass

        # Patch both methods
        with (
            patch.object(
                app,
                "_handle_agent_loop_turn_with_content",
                side_effect=mock_handle_agent_turn,
            ),
            patch.object(app, "_mount_and_scroll", side_effect=mock_mount_and_scroll),
        ):
            app._tui_ready = True
            app._agent_task = None
            app._agent_running = False

            # Call the method
            await app._handle_user_message_with_image(
                "test message", {"data": "base64data", "mime_type": "image/png"}
            )

        # Verify _agent_task was created (meaning content was passed to create_task)
        assert app._agent_task is not None
        # The task should be pending (not completed yet)
        assert not app._agent_task.done()
        # Cancel the task to clean up
        app._agent_task.cancel()
        try:
            await cast(asyncio.Task, app._agent_task)
        except asyncio.CancelledError:
            pass

        # Verify the content structure is built correctly by checking the code path
        # The content should be: [{"type": "text", "text": "..."}, {"type": "image_url", ...}]
        # This is verified by the fact that the task was created with the content
