"""Tests for interrupt handling during question popup in TUI.

These tests verify that when a user interrupts during a question popup,
the input form is properly restored.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vibe.cli.textual_ui.app import PendingPopupState, VibeApp
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
async def test_interrupt_during_question_popup_restores_input_form() -> None:
    """Test that interrupt during question popup restores input form."""
    app = _create_mock_app()
    app._agent_running = True
    app._interrupt_requested = True
    app._agent_task = None

    # Set up pending question
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
    pending_question = PendingPopupState()
    pending_question.future = asyncio.Future()
    pending_question.popup_id = "question_test_123"
    app._pending_question = pending_question

    # Mock event_handler
    mock_event_handler = MagicMock()
    mock_event_handler.stop_current_tool_call = MagicMock()
    mock_event_handler.stop_current_compact = MagicMock()
    mock_event_handler.finalize_streaming = AsyncMock()
    app.event_handler = mock_event_handler  # type: ignore

    # Track switch_to_input_app calls
    switch_to_input_called = False

    original_switch = app._switch_to_input_app

    async def mock_switch_to_input() -> None:
        nonlocal switch_to_input_called
        switch_to_input_called = True
        await original_switch()

    app._switch_to_input_app = mock_switch_to_input  # type: ignore

    # Mock TUI widgets
    mock_loading_area = MagicMock()
    mock_loading_area.remove_children = AsyncMock()
    app._cached_loading_area = mock_loading_area  # type: ignore

    # Mock _mount_and_scroll
    app._mount_and_scroll = AsyncMock()  # type: ignore

    # Mock query_one to simulate question app existing
    mock_question_app = MagicMock()
    mock_question_app.parent = MagicMock()
    mock_question_app.remove = AsyncMock()

    def mock_query_one(selector: str):
        if selector == "#question-app":
            return mock_question_app
        raise Exception(f"Widget not found: {selector}")

    app.query_one = mock_query_one  # type: ignore

    await app._interrupt_agent_loop()

    # Verify question was cleared
    assert app._pending_question.future is None
    assert app._pending_question.popup_id is None

    # Verify input form was restored
    assert switch_to_input_called is True


@pytest.mark.asyncio
async def test_interrupt_during_approval_popup_restores_input_form() -> None:
    """Test that interrupt during approval popup restores input form."""
    app = _create_mock_app()
    app._agent_running = True
    app._interrupt_requested = True
    app._agent_task = None

    # Set up pending approval
    pending_approval = PendingPopupState()
    pending_approval.future = asyncio.Future()
    pending_approval.popup_id = "approval_test_123"
    app._pending_approval = pending_approval

    # Mock event_handler
    mock_event_handler = MagicMock()
    mock_event_handler.stop_current_tool_call = MagicMock()
    mock_event_handler.stop_current_compact = MagicMock()
    mock_event_handler.finalize_streaming = AsyncMock()
    app.event_handler = mock_event_handler  # type: ignore

    # Track switch_to_input_app calls
    switch_to_input_called = False

    original_switch = app._switch_to_input_app

    async def mock_switch_to_input() -> None:
        nonlocal switch_to_input_called
        switch_to_input_called = True
        await original_switch()

    app._switch_to_input_app = mock_switch_to_input  # type: ignore

    # Mock TUI widgets
    mock_loading_area = MagicMock()
    mock_loading_area.remove_children = AsyncMock()
    app._cached_loading_area = mock_loading_area  # type: ignore

    # Mock _mount_and_scroll
    app._mount_and_scroll = AsyncMock()  # type: ignore

    # Mock query_one to simulate approval app existing
    mock_approval_app = MagicMock()
    mock_approval_app.parent = MagicMock()
    mock_approval_app.remove = AsyncMock()

    def mock_query_one(selector: str):
        if selector == "#approval-app":
            return mock_approval_app
        raise Exception(f"Widget not found: {selector}")

    app.query_one = mock_query_one  # type: ignore

    await app._interrupt_agent_loop()

    # Verify approval was cleared
    assert app._pending_approval.future is None
    assert app._pending_approval.popup_id is None

    # Verify input form was restored
    assert switch_to_input_called is True


@pytest.mark.asyncio
async def test_interrupt_with_both_popups_restores_input_form() -> None:
    """Test that interrupt with both question and approval popups restores input form."""
    app = _create_mock_app()
    app._agent_running = True
    app._interrupt_requested = True
    app._agent_task = None

    # Set up both pending approval and question
    pending_approval = PendingPopupState()
    pending_approval.future = asyncio.Future()
    pending_approval.popup_id = "approval_test_123"
    app._pending_approval = pending_approval

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
    pending_question = PendingPopupState()
    pending_question.future = asyncio.Future()
    pending_question.popup_id = "question_test_123"
    app._pending_question = pending_question

    # Mock event_handler
    mock_event_handler = MagicMock()
    mock_event_handler.stop_current_tool_call = MagicMock()
    mock_event_handler.stop_current_compact = MagicMock()
    mock_event_handler.finalize_streaming = AsyncMock()
    app.event_handler = mock_event_handler  # type: ignore

    # Track switch_to_input_app calls
    switch_to_input_call_count = 0

    original_switch = app._switch_to_input_app

    async def mock_switch_to_input() -> None:
        nonlocal switch_to_input_call_count
        switch_to_input_call_count += 1
        await original_switch()

    app._switch_to_input_app = mock_switch_to_input  # type: ignore

    # Mock TUI widgets
    mock_loading_area = MagicMock()
    mock_loading_area.remove_children = AsyncMock()
    app._cached_loading_area = mock_loading_area  # type: ignore

    # Mock _mount_and_scroll
    app._mount_and_scroll = AsyncMock()  # type: ignore

    # Mock query_one to simulate both apps existing
    mock_approval_app = MagicMock()
    mock_approval_app.parent = MagicMock()
    mock_approval_app.remove = AsyncMock()

    mock_question_app = MagicMock()
    mock_question_app.parent = MagicMock()
    mock_question_app.remove = AsyncMock()

    def mock_query_one(selector: str):
        if selector == "#approval-app":
            return mock_approval_app
        if selector == "#question-app":
            return mock_question_app
        raise Exception(f"Widget not found: {selector}")

    app.query_one = mock_query_one  # type: ignore

    await app._interrupt_agent_loop()

    # Verify both were cleared
    assert app._pending_approval.future is None
    assert app._pending_question.future is None

    # Verify input form was restored (called twice - once for each popup)
    assert switch_to_input_call_count == 2


@pytest.mark.asyncio
async def test_interrupt_no_popups_no_switch_to_input() -> None:
    """Test that interrupt without popups doesn't call switch_to_input_app."""
    app = _create_mock_app()
    app._agent_running = True
    app._interrupt_requested = True
    app._agent_task = None
    # Popups are already initialized as PendingPopupState() in _initialize_web_broadcast_state
    # Just ensure they're empty (no active future)
    assert app._pending_approval.future is None
    assert app._pending_question.future is None

    # Mock event_handler
    mock_event_handler = MagicMock()
    mock_event_handler.stop_current_tool_call = MagicMock()
    mock_event_handler.stop_current_compact = MagicMock()
    mock_event_handler.finalize_streaming = AsyncMock()
    app.event_handler = mock_event_handler  # type: ignore

    # Track switch_to_input_app calls
    switch_to_input_called = False

    original_switch = app._switch_to_input_app

    async def mock_switch_to_input() -> None:
        nonlocal switch_to_input_called
        switch_to_input_called = True
        await original_switch()

    app._switch_to_input_app = mock_switch_to_input  # type: ignore

    # Mock TUI widgets
    mock_loading_area = MagicMock()
    mock_loading_area.remove_children = AsyncMock()
    app._cached_loading_area = mock_loading_area  # type: ignore

    # Mock _mount_and_scroll
    app._mount_and_scroll = AsyncMock()  # type: ignore

    await app._interrupt_agent_loop()

    # Verify switch_to_input_app was not called (no popups to clean up)
    assert switch_to_input_called is False
