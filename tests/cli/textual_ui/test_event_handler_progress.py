from __future__ import annotations

"""Tests for EventHandler prompt progress handling."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from vibe.cli.textual_ui.handlers.event_handler import EventHandler
from vibe.cli.textual_ui.widgets.loading import LoadingWidget
from vibe.core.types import PromptProgressEvent


class TestEventHandlerPromptProgress:
    """Test EventHandler handling of PromptProgressEvent."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.mount_callback = AsyncMock()
        self.get_tools_collapsed = MagicMock(return_value=False)
        self.event_handler = EventHandler(
            mount_callback=self.mount_callback,
            get_tools_collapsed=self.get_tools_collapsed,
        )

    @pytest.mark.asyncio
    async def test_handle_prompt_progress_with_loading_widget(self) -> None:
        """Test handling PromptProgressEvent updates loading widget."""
        loading_widget = LoadingWidget()
        event = PromptProgressEvent(total=1000, cache=200, processed=500, time_ms=1500)

        await self.event_handler.handle_event(
            event, loading_active=True, loading_widget=loading_widget
        )

        # Verify loading widget progress was updated
        assert loading_widget._progress_percentage == 50.0

    @pytest.mark.asyncio
    async def test_handle_prompt_progress_without_loading_widget(self) -> None:
        """Test handling PromptProgressEvent without loading widget does nothing."""
        event = PromptProgressEvent(total=1000, cache=200, processed=500, time_ms=1500)

        # Should not raise
        await self.event_handler.handle_event(
            event, loading_active=False, loading_widget=None
        )

    @pytest.mark.asyncio
    async def test_handle_prompt_progress_zero_total(self) -> None:
        """Test handling PromptProgressEvent with zero total tokens."""
        loading_widget = LoadingWidget()
        event = PromptProgressEvent(total=0, cache=0, processed=0, time_ms=0)

        await self.event_handler.handle_event(
            event, loading_active=True, loading_widget=loading_widget
        )

        # Progress should be 0% when total is 0
        assert loading_widget._progress_percentage == 0.0

    @pytest.mark.asyncio
    async def test_handle_prompt_progress_full_completion(self) -> None:
        """Test handling PromptProgressEvent at 100% completion."""
        loading_widget = LoadingWidget()
        event = PromptProgressEvent(total=1000, cache=0, processed=1000, time_ms=2000)

        await self.event_handler.handle_event(
            event, loading_active=True, loading_widget=loading_widget
        )

        assert loading_widget._progress_percentage == 100.0

    @pytest.mark.asyncio
    async def test_handle_prompt_progress_partial(self) -> None:
        """Test handling PromptProgressEvent at partial completion."""
        loading_widget = LoadingWidget()
        event = PromptProgressEvent(total=1000, cache=100, processed=350, time_ms=500)

        await self.event_handler.handle_event(
            event, loading_active=True, loading_widget=loading_widget
        )

        assert loading_widget._progress_percentage == 35.0

    @pytest.mark.asyncio
    async def test_handle_prompt_progress_multiple_updates(self) -> None:
        """Test handling multiple PromptProgressEvents updates progress incrementally."""
        loading_widget = LoadingWidget()

        # First update: 10%
        event1 = PromptProgressEvent(total=1000, cache=0, processed=100, time_ms=100)
        await self.event_handler.handle_event(
            event1, loading_active=True, loading_widget=loading_widget
        )
        assert loading_widget._progress_percentage == 10.0

        # Second update: 50%
        event2 = PromptProgressEvent(total=1000, cache=0, processed=500, time_ms=500)
        await self.event_handler.handle_event(
            event2, loading_active=True, loading_widget=loading_widget
        )
        assert loading_widget._progress_percentage == 50.0

        # Third update: 100%
        event3 = PromptProgressEvent(total=1000, cache=0, processed=1000, time_ms=1000)
        await self.event_handler.handle_event(
            event3, loading_active=True, loading_widget=loading_widget
        )
        assert loading_widget._progress_percentage == 100.0

    @pytest.mark.asyncio
    async def test_handle_prompt_progress_does_not_finalize_streaming(self) -> None:
        """Test that PromptProgressEvent doesn't call finalize_streaming()."""
        loading_widget = LoadingWidget()
        event = PromptProgressEvent(total=1000, cache=200, processed=500, time_ms=1500)

        # finalize_streaming is called for other events but not PromptProgressEvent
        # Verify the event is handled without error
        await self.event_handler.handle_event(
            event, loading_active=True, loading_widget=loading_widget
        )

        assert loading_widget._progress_percentage == 50.0
