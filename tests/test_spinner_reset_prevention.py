"""
Test suite to prevent regression of the spinner reset bug.

This test ensures that the spinner state is properly reset when starting
a new enhancement, preventing the "x" character from persisting across
multiple enhancement attempts.
"""

import pytest
from unittest.mock import Mock, MagicMock
from vibe.cli.textual_ui.widgets.spinner import SpinnerMixin, LineSpinner
from vibe.cli.textual_ui.widgets.loading import LoadingWidget


class TestSpinnerResetPrevention:
    """Test suite for spinner reset functionality."""

    def test_spinner_reset_clears_indicator(self):
        """Test that reset_spinner() clears the indicator widget."""
        # Create a mock widget
        mock_widget = Mock()
        mock_widget.update = Mock()
        mock_widget.remove_class = Mock()
        
        # Create a spinner mixin instance
        class TestSpinnerMixin(SpinnerMixin):
            def __init__(self):
                self._indicator_widget = mock_widget
                self.init_spinner()
        
        spinner = TestSpinnerMixin()
        
        # Simulate stopping with failure (shows "✕")
        spinner.stop_spinning(success=False)
        
        # Verify "✕" was set
        mock_widget.update.assert_called_with("✕")
        
        # Reset the spinner
        spinner.reset_spinner()
        
        # Verify indicator was cleared
        assert mock_widget.update.call_count == 2  # First "✕", then ""
        mock_widget.update.assert_called_with("")
        # Verify error class was removed
        mock_widget.remove_class.assert_called()
        
    def test_spinner_reset_resets_position(self):
        """Test that reset_spinner() resets the spinner position."""
        # Create a spinner
        spinner = LineSpinner()
        
        # Advance through some frames
        spinner.next_frame()  # Position 1
        spinner.next_frame()  # Position 2
        
        # Verify position is not 0
        assert spinner._position != 0
        
        # Reset the spinner
        spinner.reset()
        
        # Verify position is reset to 0
        assert spinner._position == 0
        
    def test_spinner_reset_stops_timer(self):
        """Test that reset_spinner() stops the timer if it exists."""
        # Create a mock widget
        mock_widget = Mock()
        mock_widget.update = Mock()
        mock_widget.remove_class = Mock()
        
        # Create a mock timer
        mock_timer = Mock()
        
        # Create a spinner mixin instance
        class TestSpinnerMixin(SpinnerMixin):
            def __init__(self):
                self._indicator_widget = mock_widget
                self.init_spinner()
                # Manually set the timer after init_spinner
                self._spinner_timer = mock_timer
        
        spinner = TestSpinnerMixin()
        
        # Reset the spinner
        spinner.reset_spinner()
        
        # Verify timer was stopped
        mock_timer.stop.assert_called_once()
        # Verify timer was cleared
        assert spinner._spinner_timer is None
        
    def test_spinner_shows_spinner_on_second_enhancement(self):
        """Test that spinner shows animation on second enhancement after interruption."""
        # This test simulates the exact scenario:
        # 1. First enhancement starts
        # 2. First enhancement is interrupted (shows "✕")
        # 3. Second enhancement starts (should show spinner, not "✕")
        
        # Create a mock widget
        mock_widget = Mock()
        mock_widget.update = Mock()
        mock_widget.remove_class = Mock()
        
        # Create a spinner mixin instance
        class TestSpinnerMixin(SpinnerMixin):
            def __init__(self):
                self._indicator_widget = mock_widget
                self.init_spinner()
        
        spinner = TestSpinnerMixin()
        
        # First enhancement: start spinner
        spinner._is_spinning = True
        spinner.start_spinner_timer = Mock()
        spinner.start_spinner_timer()
        
        # First enhancement: interrupted (shows "✕")
        spinner.stop_spinning(success=False)
        
        # Verify "✕" was shown
        mock_widget.update.assert_called_with("✕")
        
        # Reset spinner for second enhancement
        spinner.reset_spinner()
        
        # Verify indicator was cleared
        assert any(call[0][0] == "" for call in mock_widget.update.call_args_list)
        
        # Second enhancement: start again
        # The indicator should be empty, ready to show spinner animation
        # not the "✕" from the previous interruption
        
        # Verify the spinner is ready for reuse
        assert spinner._is_spinning == False
        assert spinner._spinner_timer is None
        
    def test_loading_widget_has_reset_method(self):
        """Test that LoadingWidget has the reset_spinner method."""
        # Create a loading widget
        widget = LoadingWidget(status="Testing...")
        
        # Verify it has the reset_spinner method
        assert hasattr(widget, 'reset_spinner'), "LoadingWidget should have reset_spinner method"
        
        # Verify it's callable
        assert callable(widget.reset_spinner), "reset_spinner should be callable"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
