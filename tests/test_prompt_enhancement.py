"""Test prompt enhancement functionality."""

from __future__ import annotations

import pytest
from textual.widgets import TextArea

from vibe.cli.textual_ui.app import VibeApp
from vibe.cli.textual_ui.widgets.chat_input.container import ChatInputContainer
from vibe.cli.textual_ui.widgets.chat_input.text_area import ChatTextArea
from vibe.core.config import SessionLoggingConfig, VibeConfig


@pytest.fixture
def vibe_config() -> VibeConfig:
    return VibeConfig(session_logging=SessionLoggingConfig(enabled=False))


@pytest.fixture
def vibe_app(vibe_config: VibeConfig) -> VibeApp:
    return VibeApp(config=vibe_config)


@pytest.mark.asyncio
async def test_ctrl_h_triggers_prompt_enhancement_request(vibe_app: VibeApp) -> None:
    """Test that Ctrl+Y keybinding triggers prompt enhancement request."""
    async with vibe_app.run_test() as pilot:
        chat_input = vibe_app.query_one(ChatInputContainer)
        input_widget = chat_input.input_widget
        
        # Type some text
        await pilot.press("h", "e", "l", "l", "o", " ", "w", "o", "r", "l", "d")
        
        # Verify text is in the input
        assert input_widget.text == "hello world"
        
        # Press Ctrl+Y
        await pilot.press("ctrl+y")
        
        # Verify enhancement mode is set
        assert vibe_app._enhancement_mode is True
        assert vibe_app._original_prompt_for_enhancement == "hello world"


@pytest.mark.asyncio
async def test_prompt_enhancement_with_mode_prefix(vibe_app: VibeApp) -> None:
    """Test that prompt enhancement works with mode prefixes."""
    async with vibe_app.run_test() as pilot:
        chat_input = vibe_app.query_one(ChatInputContainer)
        input_widget = chat_input.input_widget
        
        # Type some text with / mode
        await pilot.press("/", "c", "l", "e", "a", "r")
        
        # Verify mode and text
        assert input_widget.input_mode == "/"
        assert input_widget.text == "clear"
        
        # Press Ctrl+Y
        await pilot.press("ctrl+y")
        
        # Verify enhancement mode is set with full text (including mode prefix)
        assert vibe_app._enhancement_mode is True
        assert vibe_app._original_prompt_for_enhancement == "/clear"


@pytest.mark.asyncio
async def test_prompt_enhancement_empty_input(vibe_app: VibeApp) -> None:
    """Test that prompt enhancement doesn't trigger with empty input."""
    async with vibe_app.run_test() as pilot:
        chat_input = vibe_app.query_one(ChatInputContainer)
        
        # Press Ctrl+Y with empty input
        await pilot.press("ctrl+y")
        
        # Verify enhancement mode is not set
        assert vibe_app._enhancement_mode is False
        assert vibe_app._original_prompt_for_enhancement == ""


@pytest.mark.asyncio
async def test_enhancement_mode_reset(vibe_app: VibeApp) -> None:
    """Test that enhancement mode is reset after use."""
    async with vibe_app.run_test() as pilot:
        chat_input = vibe_app.query_one(ChatInputContainer)
        input_widget = chat_input.input_widget
        
        # Type some text
        await pilot.press("h", "e", "l", "l", "o")
        
        # Press Ctrl+Y
        await pilot.press("ctrl+y")
        
        # Verify enhancement mode is set
        assert vibe_app._enhancement_mode is True
        
        # Reset enhancement mode
        vibe_app._reset_enhancement_mode()
        
        # Verify enhancement mode is reset
        assert vibe_app._enhancement_mode is False
        assert vibe_app._original_prompt_for_enhancement == ""


@pytest.mark.asyncio
async def test_replace_input_with_enhanced_prompt(vibe_app: VibeApp) -> None:
    """Test that input text is replaced with enhanced prompt."""
    async with vibe_app.run_test() as pilot:
        chat_input = vibe_app.query_one(ChatInputContainer)
        input_widget = chat_input.input_widget
        
        # Type some text
        await pilot.press("h", "e", "l", "l", "o")
        
        # Replace with enhanced prompt
        enhanced_text = "enhanced hello"
        vibe_app._replace_input_with_enhanced_prompt(enhanced_text)
        
        # Verify input text is replaced
        assert chat_input.value == "enhanced hello"
        assert input_widget.text == "enhanced hello"


@pytest.mark.asyncio
async def test_replace_input_with_enhanced_prompt_removes_mode_prefix(vibe_app: VibeApp) -> None:
    """Test that mode prefix is removed when replacing with enhanced prompt."""
    async with vibe_app.run_test() as pilot:
        chat_input = vibe_app.query_one(ChatInputContainer)
        input_widget = chat_input.input_widget
        
        # Type some text with mode prefix
        await pilot.press("!", "h", "e", "l", "l", "o")
        
        # Replace with enhanced prompt that includes mode prefix
        enhanced_text = "!enhanced hello"
        vibe_app._replace_input_with_enhanced_prompt(enhanced_text)
        
        # Verify mode prefix is removed and only content remains
        assert chat_input.value == "enhanced hello"
        assert input_widget.text == "enhanced hello"
        assert input_widget.input_mode == ">"  # Should be reset to default mode