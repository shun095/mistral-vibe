"""Tests for compact widget."""

from __future__ import annotations

import pytest

from vibe.cli.textual_ui.widgets.compact import CompactMessage


class TestCompactMessage:
    """Test CompactMessage widget."""

    def test_compact_message_initialization(self) -> None:
        """Test that CompactMessage initializes correctly."""
        widget = CompactMessage()
        
        assert widget.old_tokens is None
        assert widget.new_tokens is None
        assert widget.error_message is None

    def test_compact_message_get_content_spinning(self) -> None:
        """Test get_content when spinning."""
        widget = CompactMessage()
        widget._is_spinning = True
        
        content = widget.get_content()
        assert content == "Compacting conversation history..."

    def test_compact_message_get_content_with_error(self) -> None:
        """Test get_content when there's an error."""
        widget = CompactMessage()
        widget._is_spinning = False
        widget.error_message = "Something went wrong"
        
        content = widget.get_content()
        assert content == "Error: Something went wrong"

    def test_compact_message_get_content_with_tokens(self) -> None:
        """Test get_content with old and new tokens."""
        widget = CompactMessage()
        widget._is_spinning = False
        widget.old_tokens = 1000
        widget.new_tokens = 500
        
        content = widget.get_content()
        # The numbers are formatted with commas (1,000)
        assert "1,000" in content or "1000" in content
        assert "500" in content
        assert "-50.0%" in content
        assert "Compaction complete" in content

    def test_compact_message_get_content_with_zero_old_tokens(self) -> None:
        """Test get_content when old_tokens is 0."""
        widget = CompactMessage()
        widget._is_spinning = False
        widget.old_tokens = 0
        widget.new_tokens = 100
        
        content = widget.get_content()
        assert "0 → 100 tokens" in content

    def test_compact_message_get_content_complete(self) -> None:
        """Test get_content when complete without tokens."""
        widget = CompactMessage()
        widget._is_spinning = False
        
        content = widget.get_content()
        assert content == "Compaction complete"

    def test_compact_message_set_complete(self) -> None:
        """Test set_complete method."""
        widget = CompactMessage()
        
        # Mock post_message
        widget.post_message = lambda msg: None  # type: ignore
        
        # Call set_complete
        widget.set_complete(old_tokens=1000, new_tokens=500)
        
        # Verify attributes are set
        assert widget.old_tokens == 1000
        assert widget.new_tokens == 500

    def test_compact_message_set_error(self) -> None:
        """Test set_error method."""
        widget = CompactMessage()
        
        # Call set_error
        widget.set_error("Test error")
        
        # Verify error_message is set
        assert widget.error_message == "Test error"

    def test_compact_completed_message(self) -> None:
        """Test CompactMessage.Completed message."""
        widget = CompactMessage()
        message = CompactMessage.Completed(widget)
        
        assert message.compact_widget is widget
