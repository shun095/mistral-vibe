"""Tests for interrupt handling during question popup in TUI.

These tests verify that when a user interrupts during a question popup,
the pending state is properly cleared and the input form is restored.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vibe.cli.textual_ui.app import PopupMetadata, VibeApp
from vibe.cli.voice_manager.voice_manager_port import TranscribeState
from vibe.core.agent_loop import AgentLoop
from vibe.core.tools.builtins.ask_user_question import (
    AskUserQuestionArgs,
    Choice,
    Question,
)


def _create_mock_app():
    """Create a mock VibeApp with proper initialization."""
    mock_agent_loop = MagicMock(spec=AgentLoop)
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


@pytest.mark.asyncio
async def test_interrupt_during_question_popup_clears_state() -> None:
    """Test that interrupt during question popup clears pending state."""
    app = _create_mock_app()
    app._agent_running = True
    app._interrupt_requested = True
    app._agent_task = None

    # Set up pending question (Future + metadata)
    future = asyncio.Future()
    app._pending_question = future
    app._pending_question_meta = PopupMetadata(
        future=future, popup_id="question_test_123"
    )

    # Mock event_handler
    mock_event_handler = MagicMock()
    mock_event_handler.stop_current_tool_call = MagicMock()
    mock_event_handler.stop_current_compact = MagicMock()
    mock_event_handler.finalize_streaming = AsyncMock()
    app.event_handler = mock_event_handler  # type: ignore

    # Mock TUI widgets
    mock_loading_area = MagicMock()
    mock_loading_area.remove_children = AsyncMock()
    app._cached_loading_area = mock_loading_area  # type: ignore

    # Mock _mount_and_scroll
    app._mount_and_scroll = AsyncMock()  # type: ignore

    # Track switch_to_input_app calls
    switch_to_input_called = False

    original_switch = app._switch_to_input_app

    async def mock_switch_to_input() -> None:
        nonlocal switch_to_input_called
        switch_to_input_called = True
        await original_switch()

    app._switch_to_input_app = mock_switch_to_input  # type: ignore

    await app._interrupt_agent_loop()

    # Verify question was cleared
    assert app._pending_question is None
    assert app._pending_question_meta is None

    # Verify input form was restored
    assert switch_to_input_called is True

    # Verify event handler cleanup was called
    mock_event_handler.stop_current_tool_call.assert_called_once_with(success=False)
    mock_event_handler.stop_current_compact.assert_called_once()
    mock_event_handler.finalize_streaming.assert_called_once()

    # Verify agent running is set to False
    assert app._agent_running is False


@pytest.mark.asyncio
async def test_interrupt_during_approval_popup_clears_state() -> None:
    """Test that interrupt during approval popup clears pending state."""
    app = _create_mock_app()
    app._agent_running = True
    app._interrupt_requested = True
    app._agent_task = None

    # Set up pending approval (Future + metadata)
    future = asyncio.Future()
    app._pending_approval = future
    app._pending_approval_meta = PopupMetadata(
        future=future, popup_id="approval_test_123"
    )

    # Mock event_handler
    mock_event_handler = MagicMock()
    mock_event_handler.stop_current_tool_call = MagicMock()
    mock_event_handler.stop_current_compact = MagicMock()
    mock_event_handler.finalize_streaming = AsyncMock()
    app.event_handler = mock_event_handler  # type: ignore

    # Mock TUI widgets
    mock_loading_area = MagicMock()
    mock_loading_area.remove_children = AsyncMock()
    app._cached_loading_area = mock_loading_area  # type: ignore

    # Mock _mount_and_scroll
    app._mount_and_scroll = AsyncMock()  # type: ignore

    # Track switch_to_input_app calls
    switch_to_input_called = False

    original_switch = app._switch_to_input_app

    async def mock_switch_to_input() -> None:
        nonlocal switch_to_input_called
        switch_to_input_called = True
        await original_switch()

    app._switch_to_input_app = mock_switch_to_input  # type: ignore

    await app._interrupt_agent_loop()

    # Verify approval was cleared
    assert app._pending_approval is None
    assert app._pending_approval_meta is None

    # Verify input form was restored
    assert switch_to_input_called is True

    # Verify event handler cleanup was called
    mock_event_handler.stop_current_tool_call.assert_called_once_with(success=False)
    mock_event_handler.stop_current_compact.assert_called_once()
    mock_event_handler.finalize_streaming.assert_called_once()

    # Verify agent running is set to False
    assert app._agent_running is False


@pytest.mark.asyncio
async def test_interrupt_with_both_popups_clears_state() -> None:
    """Test that interrupt with both question and approval popups clears state."""
    app = _create_mock_app()
    app._agent_running = True
    app._interrupt_requested = True
    app._agent_task = None

    # Set up both pending approval and question (Future + metadata)
    approval_future = asyncio.Future()
    app._pending_approval = approval_future
    app._pending_approval_meta = PopupMetadata(
        future=approval_future, popup_id="approval_test_123"
    )

    _ = AskUserQuestionArgs(
        questions=[
            Question(
                question="Test question?",
                header="Test",
                options=[
                    Choice(label="Option 1", description="Desc 1"),
                    Choice(label="Option 2", description="Desc 2"),
                ],
                multi_select=False,
            )
        ]
    )
    question_future = asyncio.Future()
    app._pending_question = question_future
    app._pending_question_meta = PopupMetadata(
        future=question_future, popup_id="question_test_123"
    )

    # Mock event_handler
    mock_event_handler = MagicMock()
    mock_event_handler.stop_current_tool_call = MagicMock()
    mock_event_handler.stop_current_compact = MagicMock()
    mock_event_handler.finalize_streaming = AsyncMock()
    app.event_handler = mock_event_handler  # type: ignore

    # Mock TUI widgets
    mock_loading_area = MagicMock()
    mock_loading_area.remove_children = AsyncMock()
    app._cached_loading_area = mock_loading_area  # type: ignore

    # Mock _mount_and_scroll
    app._mount_and_scroll = AsyncMock()  # type: ignore

    # Track switch_to_input_app calls
    switch_to_input_call_count = 0

    original_switch = app._switch_to_input_app

    async def mock_switch_to_input() -> None:
        nonlocal switch_to_input_call_count
        switch_to_input_call_count += 1
        await original_switch()

    app._switch_to_input_app = mock_switch_to_input  # type: ignore

    await app._interrupt_agent_loop()

    # Verify both were cleared
    assert app._pending_approval is None
    assert app._pending_approval_meta is None
    assert app._pending_question is None
    assert app._pending_question_meta is None

    # Verify input form was restored (called twice - once for each popup)
    assert switch_to_input_call_count == 2

    # Verify agent running is set to False
    assert app._agent_running is False


@pytest.mark.asyncio
async def test_interrupt_no_popups_no_switch_to_input() -> None:
    """Test that interrupt without popups doesn't fail."""
    app = _create_mock_app()
    app._agent_running = True
    app._interrupt_requested = True
    app._agent_task = None
    # Popups are already initialized as None in _initialize_web_broadcast_state
    assert app._pending_approval is None
    assert app._pending_question is None

    # Mock event_handler
    mock_event_handler = MagicMock()
    mock_event_handler.stop_current_tool_call = MagicMock()
    mock_event_handler.stop_current_compact = MagicMock()
    mock_event_handler.finalize_streaming = AsyncMock()
    app.event_handler = mock_event_handler  # type: ignore

    # Mock TUI widgets
    mock_loading_area = MagicMock()
    mock_loading_area.remove_children = AsyncMock()
    app._cached_loading_area = mock_loading_area  # type: ignore

    # Mock _mount_and_scroll
    app._mount_and_scroll = AsyncMock()  # type: ignore

    await app._interrupt_agent_loop()

    # Verify event handler cleanup was still called
    mock_event_handler.stop_current_tool_call.assert_called_once_with(success=False)
    mock_event_handler.stop_current_compact.assert_called_once()
    mock_event_handler.finalize_streaming.assert_called_once()

    # Verify agent running is set to False
    assert app._agent_running is False
