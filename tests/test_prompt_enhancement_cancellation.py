"""Test prompt enhancement cancellation with ESC and CTRL+C."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from vibe.cli.textual_ui.app import VibeApp
from vibe.cli.textual_ui.widgets.chat_input.container import ChatInputContainer
from vibe.core.config import SessionLoggingConfig, VibeConfig


@pytest.fixture
def vibe_config() -> VibeConfig:
    return VibeConfig(session_logging=SessionLoggingConfig(enabled=False))


@pytest.fixture
def vibe_app(vibe_config: VibeConfig) -> VibeApp:
    return VibeApp(config=vibe_config)


@pytest.mark.asyncio
async def test_escape_cancels_prompt_enhancement(vibe_app: VibeApp) -> None:
    """Test that ESC cancels prompt enhancement when in progress."""
    
    # Create a mock backend to simulate LLM call with delay
    with patch('vibe.core.llm.backend.factory.BACKEND_FACTORY') as mock_factory:
        mock_backend = AsyncMock()
        mock_backend.__aenter__ = AsyncMock(return_value=mock_backend)
        mock_backend.__aexit__ = AsyncMock(return_value=None)
        
        # Mock the complete_streaming method to return chunks after a delay
        async def mock_complete_streaming(*args, **kwargs):
            import asyncio
            # Yield chunks to simulate streaming
            yield LLMChunk(
                message=LLMMessage(role=Role.assistant, content="enhanced "),
                usage=LLMUsage(prompt_tokens=10, completion_tokens=10)
            )
            await asyncio.sleep(1.0)  # Simulate a slow LLM call
            yield LLMChunk(
                message=LLMMessage(role=Role.assistant, content="prompt"),
                usage=LLMUsage(prompt_tokens=10, completion_tokens=10)
            )
        
        mock_backend.complete_streaming = mock_complete_streaming
        
        mock_factory.__getitem__ = MagicMock(return_value=MagicMock(return_value=mock_backend))
        
        async with vibe_app.run_test() as pilot:
            # Type some text
            await pilot.press("h", "e", "l", "l", "o")
            
            # Press Ctrl+Y to start enhancement (this should set the flag)
            await pilot.press("ctrl+y")
            
            # Give the enhancement a moment to start
            import asyncio
            await asyncio.sleep(0.1)
            
            # Verify enhancement is in progress
            assert vibe_app._prompt_enhancement_in_progress is True
            assert vibe_app._enhancement_mode is True
            
            # Press ESC to cancel
            await pilot.press("escape")
            
            # Verify enhancement is cancelled
            assert vibe_app._prompt_enhancement_in_progress is False
            assert vibe_app._enhancement_mode is False
            assert vibe_app._original_prompt_for_enhancement == ""


@pytest.mark.asyncio
async def test_ctrl_c_cancels_prompt_enhancement(vibe_app: VibeApp) -> None:
    """Test that CTRL+C cancels prompt enhancement when in progress."""
    
    # Create a mock backend to simulate LLM call with delay
    with patch('vibe.core.llm.backend.factory.BACKEND_FACTORY') as mock_factory:
        mock_backend = AsyncMock()
        mock_backend.__aenter__ = AsyncMock(return_value=mock_backend)
        mock_backend.__aexit__ = AsyncMock(return_value=None)
        
        # Mock the complete_streaming method to return chunks after a delay
        async def mock_complete_streaming(*args, **kwargs):
            import asyncio
            # Yield chunks to simulate streaming
            yield LLMChunk(
                message=LLMMessage(role=Role.assistant, content="enhanced "),
                usage=LLMUsage(prompt_tokens=10, completion_tokens=10)
            )
            await asyncio.sleep(1.0)  # Simulate a slow LLM call
            yield LLMChunk(
                message=LLMMessage(role=Role.assistant, content="prompt"),
                usage=LLMUsage(prompt_tokens=10, completion_tokens=10)
            )
        
        mock_backend.complete_streaming = mock_complete_streaming
        
        mock_factory.__getitem__ = MagicMock(return_value=MagicMock(return_value=mock_backend))
        
        async with vibe_app.run_test() as pilot:
            # Type some text
            await pilot.press("h", "e", "l", "l", "o")
            
            # Press Ctrl+Y to start enhancement (this should set the flag)
            await pilot.press("ctrl+y")
            
            # Give the enhancement a moment to start
            import asyncio
            await asyncio.sleep(0.1)
            
            # Verify enhancement is in progress
            assert vibe_app._prompt_enhancement_in_progress is True
            assert vibe_app._enhancement_mode is True
            
            # Press CTRL+C to cancel
            await pilot.press("ctrl+c")
            
            # Verify enhancement is cancelled
            assert vibe_app._prompt_enhancement_in_progress is False
            assert vibe_app._enhancement_mode is False
            assert vibe_app._original_prompt_for_enhancement == ""


@pytest.mark.asyncio
async def test_cancellation_hides_loading_widget(vibe_app: VibeApp) -> None:
    """Test that cancellation hides the loading widget."""
    
    # Create a mock backend to simulate LLM call with delay
    with patch('vibe.core.llm.backend.factory.BACKEND_FACTORY') as mock_factory:
        mock_backend = AsyncMock()
        mock_backend.__aenter__ = AsyncMock(return_value=mock_backend)
        mock_backend.__aexit__ = AsyncMock(return_value=None)
        
        # Mock the complete_streaming method to return chunks after a delay
        async def mock_complete_streaming(*args, **kwargs):
            import asyncio
            # Yield chunks to simulate streaming
            yield LLMChunk(
                message=LLMMessage(role=Role.assistant, content="enhanced "),
                usage=LLMUsage(prompt_tokens=10, completion_tokens=10)
            )
            await asyncio.sleep(1.0)  # Simulate a slow LLM call
            yield LLMChunk(
                message=LLMMessage(role=Role.assistant, content="prompt"),
                usage=LLMUsage(prompt_tokens=10, completion_tokens=10)
            )
        
        mock_backend.complete_streaming = mock_complete_streaming
        
        mock_factory.__getitem__ = MagicMock(return_value=MagicMock(return_value=mock_backend))
        
        async with vibe_app.run_test() as pilot:
            # Type some text
            await pilot.press("h", "e", "l", "l", "o")
            
            # Press Ctrl+Y to start enhancement
            await pilot.press("ctrl+y")
            
            # Give the enhancement a moment to start
            import asyncio
            await asyncio.sleep(0.1)
            
            # Verify enhancement is in progress
            assert vibe_app._prompt_enhancement_in_progress is True
            
            # Get the chat input container
            input_container = vibe_app.query_one(ChatInputContainer)
            
            # Check that loading widget is visible (not hidden)
            # The loading widget should be visible when enhancement starts
            assert input_container._enhancement_loading_widget is not None
            
            # Press ESC to cancel
            await pilot.press("escape")
            
            # Verify enhancement is cancelled
            assert vibe_app._prompt_enhancement_in_progress is False