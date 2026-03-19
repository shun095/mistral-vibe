"""Tests for image attachment functionality in WebSocket endpoint."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient as StarletteTestClient


@pytest.fixture(scope="function")
def app_with_token():
    """Create app with token for testing."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token")
    return app, "test-token"


class TestWebSocketImageAttachment:
    """Test image attachment handling in WebSocket messages."""

    @pytest.mark.timeout(5)
    def test_websocket_message_with_image_and_text(self, app_with_token: tuple) -> None:
        """Test that WebSocket handler correctly extracts and forwards image data with text."""
        app, token = app_with_token
        client = StarletteTestClient(app)

        # Create mock TUI app with proper defaults to avoid popup re-emit errors
        mock_tui_app = MagicMock()
        mock_tui_app._pending_approval_id = None
        mock_tui_app._pending_question_id = None
        app.state.tui_app = mock_tui_app

        with client.websocket_connect(f"/ws?token={token}") as websocket:
            # Skip connected message
            websocket.receive_json()

            # Send message with image and text
            message = {
                "type": "user_message",
                "content": "test text message",
                "image": {"data": "base64encodeddata", "mime_type": "image/png"},
            }
            websocket.send_json(message)

            # Give the handler time to process the message
            time.sleep(0.1)

            # Verify submit_message_from_web was called with correct parameters
            mock_tui_app.submit_message_from_web.assert_called_once_with(
                "test text message",
                {"data": "base64encodeddata", "mime_type": "image/png"},
            )

    @pytest.mark.timeout(5)
    def test_websocket_message_with_image_only(self, app_with_token: tuple) -> None:
        """Test that WebSocket handler forwards image-only messages (empty content)."""
        app, token = app_with_token
        client = StarletteTestClient(app)

        # Create mock TUI app with proper defaults
        mock_tui_app = MagicMock()
        mock_tui_app._pending_approval_id = None
        mock_tui_app._pending_question_id = None
        app.state.tui_app = mock_tui_app

        with client.websocket_connect(f"/ws?token={token}") as websocket:
            # Skip connected message
            websocket.receive_json()

            # Send message with only image (empty content)
            message = {
                "type": "user_message",
                "content": "",
                "image": {"data": "base64encodeddata", "mime_type": "image/jpeg"},
            }
            websocket.send_json(message)

            # Give the handler time to process the message
            time.sleep(0.1)

            # Verify submit_message_from_web was called with empty string and image
            mock_tui_app.submit_message_from_web.assert_called_once_with(
                "", {"data": "base64encodeddata", "mime_type": "image/jpeg"}
            )

    @pytest.mark.timeout(5)
    def test_websocket_message_without_image(self, app_with_token: tuple) -> None:
        """Test backward compatibility: messages without image still work."""
        app, token = app_with_token
        client = StarletteTestClient(app)

        # Create mock TUI app with proper defaults
        mock_tui_app = MagicMock()
        mock_tui_app._pending_approval_id = None
        mock_tui_app._pending_question_id = None
        app.state.tui_app = mock_tui_app

        with client.websocket_connect(f"/ws?token={token}") as websocket:
            # Skip connected message
            websocket.receive_json()

            # Send message without image
            message = {"type": "user_message", "content": "text only message"}
            websocket.send_json(message)

            # Give the handler time to process the message
            time.sleep(0.1)

            # Verify submit_message_from_web was called with None for image
            mock_tui_app.submit_message_from_web.assert_called_once_with(
                "text only message", None
            )

    @pytest.mark.timeout(5)
    def test_websocket_empty_message_without_image_ignored(
        self, app_with_token: tuple
    ) -> None:
        """Test that empty messages without image are ignored."""
        app, token = app_with_token
        client = StarletteTestClient(app)

        # Create mock TUI app with proper defaults
        mock_tui_app = MagicMock()
        mock_tui_app._pending_approval_id = None
        mock_tui_app._pending_question_id = None
        app.state.tui_app = mock_tui_app

        with client.websocket_connect(f"/ws?token={token}") as websocket:
            # Skip connected message
            websocket.receive_json()

            # Send empty message without image
            message = {"type": "user_message", "content": ""}
            websocket.send_json(message)

            # Give the handler time to process the message
            time.sleep(0.1)

            # Verify submit_message_from_web was NOT called
            mock_tui_app.submit_message_from_web.assert_not_called()

    @pytest.mark.timeout(5)
    def test_websocket_message_with_webp_image(self, app_with_token: tuple) -> None:
        """Test that WebSocket handler supports WEBP format."""
        app, token = app_with_token
        client = StarletteTestClient(app)

        # Create mock TUI app with proper defaults
        mock_tui_app = MagicMock()
        mock_tui_app._pending_approval_id = None
        mock_tui_app._pending_question_id = None
        app.state.tui_app = mock_tui_app

        with client.websocket_connect(f"/ws?token={token}") as websocket:
            # Skip connected message
            websocket.receive_json()

            # Send message with WEBP image
            message = {
                "type": "user_message",
                "content": "webp image test",
                "image": {"data": "webpbase64data", "mime_type": "image/webp"},
            }
            websocket.send_json(message)

            # Give the handler time to process the message
            time.sleep(0.1)

            # Verify submit_message_from_web was called with WEBP image
            mock_tui_app.submit_message_from_web.assert_called_once_with(
                "webp image test", {"data": "webpbase64data", "mime_type": "image/webp"}
            )

    @pytest.mark.timeout(5)
    def test_websocket_no_tui_app_message_ignored(self, app_with_token: tuple) -> None:
        """Test that messages are ignored when TUI app is not available."""
        app, token = app_with_token
        client = StarletteTestClient(app)

        # Don't set tui_app on app.state

        with client.websocket_connect(f"/ws?token={token}") as websocket:
            # Skip connected message
            websocket.receive_json()

            # Send message with image
            message = {
                "type": "user_message",
                "content": "test message",
                "image": {"data": "base64data", "mime_type": "image/png"},
            }
            websocket.send_json(message)

            # Should not raise any errors
            assert True


class TestTUIImageMessageHandling:
    """Test TUI app's image message handling methods."""

    @pytest.fixture
    def mock_tui_app(self):
        """Create a mock TUI app for testing."""
        from vibe.cli.textual_ui.app import VibeApp
        from vibe.core.agent_loop import AgentLoop

        # Create mock agent loop
        mock_agent_loop = MagicMock(spec=AgentLoop)

        # Create TUI app (but don't run it)
        app = VibeApp(agent_loop=mock_agent_loop)
        return app

    def test_submit_message_from_web_with_image(self, mock_tui_app) -> None:
        """Test that submit_message_from_web queues image messages correctly."""
        # Mark TUI as ready
        mock_tui_app._tui_ready = True

        # Submit message with image
        mock_tui_app.submit_message_from_web(
            "test message", {"data": "base64data", "mime_type": "image/png"}
        )

        # Verify message was queued correctly
        assert len(mock_tui_app._web_message_queue) == 1
        item = mock_tui_app._web_message_queue[0]
        assert item["message"] == "test message"
        assert item["image"] == {"data": "base64data", "mime_type": "image/png"}

    def test_submit_message_from_web_without_image(self, mock_tui_app) -> None:
        """Test that submit_message_from_web handles messages without images."""
        # Mark TUI as ready
        mock_tui_app._tui_ready = True

        # Submit message without image
        mock_tui_app.submit_message_from_web("test message", None)

        # Verify message was queued correctly
        assert len(mock_tui_app._web_message_queue) == 1
        item = mock_tui_app._web_message_queue[0]
        assert item["message"] == "test message"
        assert item["image"] is None

    def test_submit_message_from_web_not_ready(self, mock_tui_app) -> None:
        """Test that submit_message_from_web ignores messages when TUI not ready."""
        # TUI is not ready (default)
        assert not mock_tui_app._tui_ready

        # Submit message with image
        mock_tui_app.submit_message_from_web(
            "test message", {"data": "base64data", "mime_type": "image/png"}
        )

        # Verify message was NOT queued
        assert len(mock_tui_app._web_message_queue) == 0

    def test_submit_message_from_web_multiple_messages(self, mock_tui_app) -> None:
        """Test that multiple messages are queued in order."""
        # Mark TUI as ready
        mock_tui_app._tui_ready = True

        # Submit multiple messages
        mock_tui_app.submit_message_from_web(
            "message 1", {"data": "data1", "mime_type": "image/png"}
        )
        mock_tui_app.submit_message_from_web("message 2", None)
        mock_tui_app.submit_message_from_web(
            "message 3", {"data": "data3", "mime_type": "image/jpeg"}
        )

        # Verify all messages were queued in order
        assert len(mock_tui_app._web_message_queue) == 3
        assert mock_tui_app._web_message_queue[0]["message"] == "message 1"
        assert mock_tui_app._web_message_queue[0]["image"] is not None
        assert mock_tui_app._web_message_queue[1]["message"] == "message 2"
        assert mock_tui_app._web_message_queue[1]["image"] is None
        assert mock_tui_app._web_message_queue[2]["message"] == "message 3"
        assert mock_tui_app._web_message_queue[2]["image"] is not None
