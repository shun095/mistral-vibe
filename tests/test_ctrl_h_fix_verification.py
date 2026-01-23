"""Test to verify the Ctrl+H animation persistence fix."""

import pytest
from unittest.mock import MagicMock, patch

from vibe.cli.textual_ui.widgets.chat_input.container import ChatInputContainer
from vibe.cli.textual_ui.widgets.chat_input.body import ChatInputBody


@pytest.mark.asyncio
async def test_enhancement_loading_widget_hidden_immediately():
    """Test that the enhancement loading widget is hidden immediately after completion."""
    
    # Create the container with mocked dependencies
    container = ChatInputContainer(
        history_file=None,
        safety="normal"
    )
    
    # Mock the body
    mock_body = MagicMock()
    container._body = mock_body
    
    # Mock the loading widget
    mock_loading_widget = MagicMock()
    mock_loading_widget.add_class = MagicMock()
    mock_loading_widget.remove_class = MagicMock()
    mock_loading_widget.start_spinner_timer = MagicMock()
    mock_loading_widget.stop_spinning = MagicMock()
    mock_loading_widget._spinner_timer = MagicMock()
    container._enhancement_loading_widget = mock_loading_widget
    
    # Test: Simulate enhancement request and completion
    print("Simulating enhancement request...")
    event = ChatInputBody.PromptEnhancementRequested(original_text="test prompt")
    container.on_chat_input_body_prompt_enhancement_requested(event)
    
    print("Simulating enhancement completion...")
    completion_event = ChatInputContainer.PromptEnhancementCompleted(success=True)
    container.on_chat_input_body_prompt_enhancement_completed(completion_event)
    
    # Verify spinner was stopped
    mock_loading_widget.stop_spinning.assert_called_with(success=True)
    print("✓ Spinner stopped correctly")
    
    # Verify the widget was hidden immediately (no timer delay)
    # The _hide_enhancement_loading_widget method should have been called directly
    assert mock_loading_widget.add_class.call_count >= 1
    # Check if the hidden class was added
    calls = [call for call in mock_loading_widget.add_class.call_args_list]
    hidden_calls = [call for call in calls if call[0] and call[0][0] == "enhancement-loading-hidden"]
    assert len(hidden_calls) >= 1
    print("✓ Widget hidden immediately after completion (no timer delay)")
    
    print("SUCCESS: Animation persistence issue is fixed!")


@pytest.mark.asyncio
async def test_enhancement_loading_widget_hidden_immediately_on_error():
    """Test that the enhancement loading widget is hidden immediately after error."""
    
    # Create the container with mocked dependencies
    container = ChatInputContainer(
        history_file=None,
        safety="normal"
    )
    
    # Mock the body
    mock_body = MagicMock()
    container._body = mock_body
    
    # Mock the loading widget
    mock_loading_widget = MagicMock()
    mock_loading_widget.add_class = MagicMock()
    mock_loading_widget.remove_class = MagicMock()
    mock_loading_widget.start_spinner_timer = MagicMock()
    mock_loading_widget.stop_spinning = MagicMock()
    mock_loading_widget._spinner_timer = MagicMock()
    container._enhancement_loading_widget = mock_loading_widget
    
    # Test: Simulate enhancement request and error completion
    print("Simulating enhancement request...")
    event = ChatInputBody.PromptEnhancementRequested(original_text="test prompt")
    container.on_chat_input_body_prompt_enhancement_requested(event)
    
    print("Simulating enhancement error...")
    error_event = ChatInputContainer.PromptEnhancementCompleted(success=False)
    container.on_chat_input_body_prompt_enhancement_completed(error_event)
    
    # Verify spinner was stopped with error state
    mock_loading_widget.stop_spinning.assert_called_with(success=False)
    print("✓ Spinner stopped correctly for error case")
    
    # Verify the widget was hidden immediately (no timer delay)
    assert mock_loading_widget.add_class.call_count >= 1
    # Check if the hidden class was added
    calls = [call for call in mock_loading_widget.add_class.call_args_list]
    hidden_calls = [call for call in calls if call[0] and call[0][0] == "enhancement-loading-hidden"]
    assert len(hidden_calls) >= 1
    print("✓ Widget hidden immediately after error (no timer delay)")
    
    print("SUCCESS: Animation persistence issue is fixed for error cases too!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])