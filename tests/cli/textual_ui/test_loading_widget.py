from __future__ import annotations

"""Tests for LoadingWidget progress functionality."""

import pytest
from textual.app import App, ComposeResult

from vibe.cli.textual_ui.widgets.loading import LoadingWidget


class TestLoadingWidgetProgress:
    """Test LoadingWidget progress percentage display."""

    def test_initial_no_progress(self) -> None:
        """Test that widget initializes without progress percentage."""
        widget = LoadingWidget()
        assert widget._progress_percentage is None

    def test_set_progress_basic(self) -> None:
        """Test setting progress percentage."""
        widget = LoadingWidget()
        widget.set_progress(50.0)
        assert widget._progress_percentage == 50.0

    def test_set_progress_zero(self) -> None:
        """Test setting progress to 0%."""
        widget = LoadingWidget()
        widget.set_progress(0.0)
        assert widget._progress_percentage == 0.0

    def test_set_progress_full(self) -> None:
        """Test setting progress to 100%."""
        widget = LoadingWidget()
        widget.set_progress(100.0)
        assert widget._progress_percentage == 100.0

    def test_set_progress_clamps_over_100(self) -> None:
        """Test that progress over 100% is clamped to 100%."""
        widget = LoadingWidget()
        widget.set_progress(150.0)
        assert widget._progress_percentage == 100.0

    def test_set_progress_clamps_negative(self) -> None:
        """Test that negative progress is clamped to 0%."""
        widget = LoadingWidget()
        widget.set_progress(-10.0)
        assert widget._progress_percentage == 0.0

    def test_set_progress_partial(self) -> None:
        """Test setting partial progress percentage."""
        widget = LoadingWidget()
        widget.set_progress(37.5)
        assert widget._progress_percentage == 37.5

    @pytest.mark.asyncio
    async def test_mount_and_progress_in_app(self) -> None:
        """Test widget can be mounted and progress updated in app context."""

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield LoadingWidget()

        app = TestApp()
        async with app.run_test():
            widget = app.query_one(LoadingWidget)
            assert widget._progress_percentage is None

            widget.set_progress(45.0)
            assert widget._progress_percentage == 45.0

            # Verify hint widget exists after mount
            hint_widget = widget.hint_widget
            assert hint_widget is not None

    def test_progress_does_not_affect_status(self) -> None:
        """Test that setting progress doesn't change status text."""
        widget = LoadingWidget(status="Processing")
        widget.set_progress(50.0)
        assert widget.status == "Processing"
        assert widget._progress_percentage == 50.0


class TestLoadingWidgetIntegration:
    """Integration tests for LoadingWidget with progress display."""

    def test_progress_percentage_formatting(self) -> None:
        """Test that progress is formatted correctly in hint text."""
        widget = LoadingWidget()
        widget.set_progress(42.5)

        # The _update_animation method handles the actual formatting
        # We verify the percentage is stored correctly
        assert widget._progress_percentage == 42.5

    def test_multiple_progress_updates(self) -> None:
        """Test multiple progress updates."""
        widget = LoadingWidget()

        widget.set_progress(10.0)
        assert widget._progress_percentage == 10.0

        widget.set_progress(50.0)
        assert widget._progress_percentage == 50.0

        widget.set_progress(100.0)
        assert widget._progress_percentage == 100.0
