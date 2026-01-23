"""Test prompt enhancement loading widget behavior."""

# Apply mock at module level to ensure it's available before any imports
import sys
from unittest.mock import MagicMock, patch
from tests.stubs.fake_backend import FakeBackend
from vibe.core.types import LLMChunk, LLMMessage, Role

# Create chunks that will be yielded with a delay
chunks = [
    LLMChunk(message=LLMMessage(role=Role.assistant, content='enhanced ')),
    LLMChunk(message=LLMMessage(role=Role.assistant, content='prompt'))
]

fake_backend = FakeBackend(chunks=chunks)

# Make FakeBackend async context managed
from unittest.mock import AsyncMock
fake_backend.__aenter__ = AsyncMock(return_value=fake_backend)
fake_backend.__aexit__ = AsyncMock(return_value=None)

# Mock the dictionary access
mock_factory = MagicMock()
mock_factory.__getitem__ = MagicMock(return_value=fake_backend)
mock_factory.__getitem__.side_effect = lambda key: fake_backend

# Apply the patch at the module level
patcher = patch('vibe.core.llm.backend.factory.BACKEND_FACTORY', mock_factory)
patcher.start()

# Also patch the module directly to ensure it's available
if 'vibe.core.llm.backend.factory' in sys.modules:
    import vibe.core.llm.backend.factory
    vibe.core.llm.backend.factory.BACKEND_FACTORY = mock_factory

# Keep the patcher in module scope so it's not garbage collected
_MOCK_PATCHER = patcher

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.stubs.fake_backend import FakeBackend
from vibe.cli.textual_ui.app import VibeApp
from vibe.cli.textual_ui.widgets.chat_input.container import ChatInputContainer
from vibe.core.config import SessionLoggingConfig, VibeConfig
from vibe.core.types import LLMChunk, LLMMessage, Role


@pytest.fixture
def vibe_config() -> VibeConfig:
    return VibeConfig(session_logging=SessionLoggingConfig(enabled=False))


@pytest.fixture
def vibe_app(vibe_config: VibeConfig) -> VibeApp:
    from unittest.mock import MagicMock, patch
    from tests.stubs.fake_backend import FakeBackend
    from vibe.core.types import LLMChunk, LLMMessage, Role
    from vibe.core.utils import logger
    import sys
    
    # Apply mock before creating the app to ensure it's available for agent initialization
    logger.info("VIBE_APP FIXTURE: Applying patch to BACKEND_FACTORY")
    
    # Create chunks that will be yielded with a delay
    chunks = [
        LLMChunk(message=LLMMessage(role=Role.assistant, content='enhanced ')),
        LLMChunk(message=LLMMessage(role=Role.assistant, content='prompt'))
    ]
    
    fake_backend = FakeBackend(chunks=chunks)
    
    # Make FakeBackend async context managed
    from unittest.mock import AsyncMock
    fake_backend.__aenter__ = AsyncMock(return_value=fake_backend)
    fake_backend.__aexit__ = AsyncMock(return_value=None)
    
    # Mock the dictionary access to return the FakeBackend class
    mock_factory = MagicMock()
    mock_factory.__getitem__ = MagicMock(return_value=FakeBackend)
    mock_factory.__getitem__.side_effect = lambda key: FakeBackend
    
    logger.info(f"VIBE_APP FIXTURE: Created fake_backend: {fake_backend}")
    
    # Apply the patch at the module level before importing agent
    patcher = patch('vibe.core.llm.backend.factory.BACKEND_FACTORY', mock_factory)
    patcher.start()
    
    # Also patch the module directly to ensure it's available
    if 'vibe.core.llm.backend.factory' in sys.modules:
        import vibe.core.llm.backend.factory
        vibe.core.llm.backend.factory.BACKEND_FACTORY = mock_factory
        logger.info(f"VIBE_APP FIXTURE: Patched module directly to {mock_factory}")
        logger.info(f"VIBE_APP FIXTURE: Module BACKEND_FACTORY is now {vibe.core.llm.backend.factory.BACKEND_FACTORY}")
    else:
        logger.info("VIBE_APP FIXTURE: Module not loaded yet")
    
    logger.info("VIBE_APP FIXTURE: Patch applied")
    
    # Keep the patcher in module scope so it's not garbage collected
    # and the patch remains active after the fixture yields
    import tests.test_prompt_enhancement_loading_widget as test_module
    test_module._vibe_app_patcher = patcher
    
    app = VibeApp(config=vibe_config)
    yield app
    
    # Note: We don't stop the patcher here because the agent is created in on_mount
    # which happens after the test starts. The patcher will be stopped after all tests.
    logger.info("VIBE_APP FIXTURE: Patch will be removed after all tests")





@pytest.mark.asyncio
async def test_loading_widget_hides_on_escape(vibe_app: VibeApp) -> None:
    """Test that loading widget hides when ESC is pressed during enhancement."""
    
    async with vibe_app.run_test() as pilot:
        # Wait for agent to be initialized
        import asyncio
        await asyncio.sleep(0.1)
        
        # Replace the agent's backend with a fake backend after the app is mounted
        # This needs to be done before the enhancement starts
        # Create a fake backend with a slow streaming response to allow time for ESC press
        fake_backend = FakeBackend(
            chunks=[
                LLMChunk(message=LLMMessage(role=Role.assistant, content='enhanced ')),
                LLMChunk(message=LLMMessage(role=Role.assistant, content='prompt'))
            ]
        )
        fake_backend.__aenter__ = AsyncMock(return_value=fake_backend)
        fake_backend.__aexit__ = AsyncMock(return_value=None)
        
        # Override complete_streaming to add delays between chunks
        async def slow_complete_streaming(*args, **kwargs):
            import asyncio
            chunks = [
                LLMChunk(message=LLMMessage(role=Role.assistant, content='enhanced ')),
                LLMChunk(message=LLMMessage(role=Role.assistant, content='prompt'))
            ]
            for chunk in chunks:
                yield chunk
                await asyncio.sleep(0.5)  # Longer delay between chunks to allow time for ESC
        
        fake_backend.complete_streaming = slow_complete_streaming
        
        # Replace the backend
        original_backend = vibe_app.agent.backend
        vibe_app.agent.backend = fake_backend
        
        try:
            # Type some text
            await pilot.press("h", "e", "l", "l", "o")
            
            # Give the app a moment to settle
            import asyncio
            await asyncio.sleep(0.1)
            
            # Press Ctrl+Y to start enhancement
            await pilot.press("ctrl+y")
            
            # Give the enhancement a moment to start
            await asyncio.sleep(0.3)
            
            # Get the chat input container
            input_container = vibe_app.query_one(ChatInputContainer)
            
            # Check that loading widget is visible (not hidden)
            assert input_container._enhancement_loading_widget is not None
            
            # Check that the loading widget is NOT hidden (no hidden class)
            has_hidden_class = "enhancement-loading-hidden" in input_container._enhancement_loading_widget.classes
            assert not has_hidden_class, "Loading widget should be visible during enhancement"
            
            # Press ESC to cancel
            await pilot.press("escape")
            
            # Give time for the event to be processed and handler to run
            await asyncio.sleep(0.5)
            
            # Check that loading widget is now hidden
            if input_container._enhancement_loading_widget:
                has_hidden_class = "enhancement-loading-hidden" in input_container._enhancement_loading_widget.classes
                assert has_hidden_class, "Loading widget should be hidden after cancellation"
                
                # Verify enhancement is cancelled
                assert vibe_app._prompt_enhancement_in_progress is False
                assert vibe_app._enhancement_mode is False
        finally:
            # Restore the original backend
            vibe_app.agent.backend = original_backend


@pytest.mark.asyncio
async def test_loading_widget_hides_on_ctrl_c(vibe_app: VibeApp) -> None:
    """Test that loading widget hides when CTRL+C is pressed during enhancement."""
    
    async with vibe_app.run_test() as pilot:
        # Wait for agent to be initialized
        import asyncio
        await asyncio.sleep(0.1)
        
        # Replace the agent's backend with a fake backend after the app is mounted
        # This needs to be done before the enhancement starts
        # Create a fake backend with a slow streaming response to allow time for CTRL+C press
        fake_backend = FakeBackend(
            chunks=[
                LLMChunk(message=LLMMessage(role=Role.assistant, content='enhanced ')),
                LLMChunk(message=LLMMessage(role=Role.assistant, content='prompt'))
            ]
        )
        fake_backend.__aenter__ = AsyncMock(return_value=fake_backend)
        fake_backend.__aexit__ = AsyncMock(return_value=None)
        
        # Override complete_streaming to add delays between chunks
        async def slow_complete_streaming(*args, **kwargs):
            import asyncio
            chunks = [
                LLMChunk(message=LLMMessage(role=Role.assistant, content='enhanced ')),
                LLMChunk(message=LLMMessage(role=Role.assistant, content='prompt'))
            ]
            for chunk in chunks:
                yield chunk
                await asyncio.sleep(0.2)  # Delay between chunks
        
        fake_backend.complete_streaming = slow_complete_streaming
        
        # Replace the backend
        original_backend = vibe_app.agent.backend
        vibe_app.agent.backend = fake_backend
        
        try:
            # Type some text
            await pilot.press("h", "e", "l", "l", "o")
            
            # Press Ctrl+Y to start enhancement
            await pilot.press("ctrl+y")
            
            # Give the enhancement a moment to start
            import asyncio
            await asyncio.sleep(0.2)
            
            # Get the chat input container
            input_container = vibe_app.query_one(ChatInputContainer)
            
            # Check that loading widget is visible (not hidden)
            assert input_container._enhancement_loading_widget is not None
            
            # Check that the loading widget is NOT hidden (no hidden class)
            has_hidden_class = "enhancement-loading-hidden" in input_container._enhancement_loading_widget.classes
            assert not has_hidden_class, "Loading widget should be visible during enhancement"
            
            # Press CTRL+C to cancel
            await pilot.press("ctrl+c")
            
            # Give a moment for the event to be processed
            await asyncio.sleep(0.1)
            
            # Check that loading widget is now hidden
            if input_container._enhancement_loading_widget:
                has_hidden_class = "enhancement-loading-hidden" in input_container._enhancement_loading_widget.classes
                assert has_hidden_class, "Loading widget should be hidden after cancellation"
            
            # Verify enhancement is cancelled
            assert vibe_app._prompt_enhancement_in_progress is False
            assert vibe_app._enhancement_mode is False
        finally:
            # Restore the original backend
            vibe_app.agent.backend = original_backend
