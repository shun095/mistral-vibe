from __future__ import annotations

"""Tests for EventHandler TaskCompletedEvent handling."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from vibe.cli.textual_ui.handlers.event_handler import EventHandler
from vibe.cli.textual_ui.widgets.messages import UserCommandMessage
from vibe.core.types import TaskCompletedEvent


class TestEventHandlerTaskCompleted:
    def setup_method(self) -> None:
        self.mount_callback = AsyncMock()
        self.get_tools_collapsed = MagicMock(return_value=False)
        self.event_handler = EventHandler(
            mount_callback=self.mount_callback,
            get_tools_collapsed=self.get_tools_collapsed,
        )

    @pytest.mark.asyncio
    async def test_handle_task_completed_mounts_user_command_message(self) -> None:
        event = TaskCompletedEvent(elapsed_text="Task completed in 5s.")

        self.event_handler.handle_event(event)
        await self.event_handler._await_pending_command()

        assert self.mount_callback.call_count == 1
        widget = self.mount_callback.call_args[0][0]
        assert isinstance(widget, UserCommandMessage)

    @pytest.mark.asyncio
    async def test_task_completed_orders_after_finalize_streaming(self) -> None:
        call_order: list[str] = []

        async def tracking_mount(widget) -> None:
            call_order.append(widget.__class__.__name__)

        self.event_handler = EventHandler(
            mount_callback=AsyncMock(side_effect=tracking_mount),
            get_tools_collapsed=self.get_tools_collapsed,
        )

        self.event_handler.finalize_streaming()
        self.event_handler.handle_event(
            TaskCompletedEvent(elapsed_text="Task completed in 0s.")
        )
        await self.event_handler._await_pending_command()

        assert "UserCommandMessage" in call_order
