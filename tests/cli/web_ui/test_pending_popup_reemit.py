"""Tests for pending popup re-emission on WebSocket connect.

This test ensures that when a web client connects via WebSocket,
any pending approval or question popups are re-emitted to the client.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient as StarletteTestClient

from vibe.cli.textual_ui.app import PendingPopupState


def _create_active_pending_state(
    popup_id: str, tool_name: str | None = None, args: dict | None = None
) -> PendingPopupState:
    """Create a PendingPopupState with an active future.

    Args:
        popup_id: The popup ID to set.
        tool_name: Optional tool name.
        args: Optional arguments dict.

    Returns:
        A PendingPopupState with an active (non-done) future.
    """
    loop = asyncio.new_event_loop()
    future = loop.create_future()

    state = PendingPopupState()
    state.future = future
    state.popup_id = popup_id
    state.tool_name = tool_name
    state.args = args or {}

    return state


@pytest.fixture
def mock_tui_app_with_pending_approval() -> tuple:
    """Create a mock TUI app with a pending approval popup.

    Returns:
        Tuple of (mock_tui_app, expected_popup_id)
    """
    mock_tui_app = MagicMock()
    # Create real PendingPopupState with active future
    approval_state = _create_active_pending_state(
        popup_id="approval_test_123",
        tool_name="bash",
        args={"command": "ls -la", "timeout": 30},
    )

    # Mock the public method to return our state
    mock_tui_app.get_pending_approval_state = MagicMock(return_value=approval_state)
    mock_tui_app.get_pending_question_state = MagicMock(return_value=None)

    return mock_tui_app, "approval_test_123"


@pytest.fixture
def mock_tui_app_with_pending_question() -> tuple:
    """Create a mock TUI app with a pending question popup.

    Returns:
        Tuple of (mock_tui_app, expected_popup_id)
    """
    mock_tui_app = MagicMock()
    # Create real PendingPopupState with active future
    question_state = _create_active_pending_state(
        popup_id="question_test_456",
        args={
            "questions": [
                {"question": "What is your name?", "header": "Name", "options": []}
            ]
        },
    )

    # Mock the public method to return our state
    mock_tui_app.get_pending_approval_state = MagicMock(return_value=None)
    mock_tui_app.get_pending_question_state = MagicMock(return_value=question_state)

    return mock_tui_app, "question_test_456"


@pytest.mark.timeout(5)
def test_websocket_receives_pending_approval_popup_on_connect(
    mock_tui_app_with_pending_approval: tuple,
) -> None:
    """Test that pending approval popup is re-emitted on WebSocket connect."""
    from vibe.cli.web_ui.server import create_app

    mock_tui_app, expected_popup_id = mock_tui_app_with_pending_approval

    app = create_app(token="test-token", tui_app=mock_tui_app)
    client = StarletteTestClient(app)

    with client.websocket_connect(
        "/ws", headers={"Cookie": "vibe_auth=test-token"}
    ) as websocket:
        # Receive connected message
        connected_msg = websocket.receive_json()
        assert connected_msg["type"] == "connected"

        # Receive approval popup event
        popup_msg = websocket.receive_json()
        assert popup_msg["type"] == "event"
        assert popup_msg["event"]["__type"] == "ApprovalPopupEvent"

        event_data = popup_msg["event"]
        assert event_data["popup_id"] == expected_popup_id
        assert event_data["tool_name"] == "bash"
        assert event_data["tool_args"]["command"] == "ls -la"


@pytest.mark.timeout(5)
def test_websocket_receives_pending_question_popup_on_connect(
    mock_tui_app_with_pending_question: tuple,
) -> None:
    """Test that pending question popup is re-emitted on WebSocket connect."""
    from vibe.cli.web_ui.server import create_app

    mock_tui_app, expected_popup_id = mock_tui_app_with_pending_question

    app = create_app(token="test-token", tui_app=mock_tui_app)
    client = StarletteTestClient(app)

    with client.websocket_connect(
        "/ws", headers={"Cookie": "vibe_auth=test-token"}
    ) as websocket:
        # Receive connected message
        connected_msg = websocket.receive_json()
        assert connected_msg["type"] == "connected"

        # Receive question popup event
        popup_msg = websocket.receive_json()
        assert popup_msg["type"] == "event"
        assert popup_msg["event"]["__type"] == "QuestionPopupEvent"

        event_data = popup_msg["event"]
        assert event_data["popup_id"] == expected_popup_id
        assert len(event_data.get("questions", [])) == 1


@pytest.mark.timeout(5)
def test_websocket_no_popup_when_none_pending() -> None:
    """Test that no popup events are sent when there are no pending popups."""
    from vibe.cli.web_ui.server import create_app

    mock_tui_app = MagicMock()
    # Mock the public methods to return None (no pending popups)
    mock_tui_app.get_pending_approval_state = MagicMock(return_value=None)
    mock_tui_app.get_pending_question_state = MagicMock(return_value=None)

    app = create_app(token="test-token", tui_app=mock_tui_app)
    client = StarletteTestClient(app)

    with client.websocket_connect(
        "/ws", headers={"Cookie": "vibe_auth=test-token"}
    ) as websocket:
        # Receive connected message
        connected_msg = websocket.receive_json()
        assert connected_msg["type"] == "connected"
        # No more messages should be sent
