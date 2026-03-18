"""Tests for slash command WebUI functionality."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def web_ui_app():
    """Create a WebUI app with mocked TUI."""
    from vibe.cli.web_ui.server import create_app

    # Create mock TUI app
    mock_tui = MagicMock()
    mock_tui.is_agent_running = MagicMock(return_value=False)
    mock_tui._clear_history = AsyncMock()
    mock_tui._restart_app = AsyncMock()
    mock_tui._show_config = AsyncMock()
    mock_tui._show_session_picker = AsyncMock()
    mock_tui.submit_message_from_web = MagicMock()
    
    # Mock command registry
    mock_commands = MagicMock()
    mock_commands.commands = {
        "clear": MagicMock(
            aliases=frozenset(["/clear"]),
            description="Clear conversation history",
        ),
        "compact": MagicMock(
            aliases=frozenset(["/compact"]),
            description="Compact conversation history by summarizing",
        ),
        "help": MagicMock(
            aliases=frozenset(["/help"]),
            description="Show help message",
        ),
        "restart": MagicMock(
            aliases=frozenset(["/restart"]),
            description="Restart the application",
        ),
        "config": MagicMock(
            aliases=frozenset(["/config", "/model"]),
            description="Edit config settings",
        ),
        "resume": MagicMock(
            aliases=frozenset(["/resume", "/continue"]),
            description="Browse and resume past sessions",
        ),
        "edit": MagicMock(
            aliases=frozenset(["/edit"]),
            description="Edit the last submitted message and restart conversation",
        ),
    }
    mock_tui.commands = mock_commands
    
    # Mock skill manager
    mock_skill_manager = MagicMock()
    mock_skill_manager.get_skill = MagicMock(return_value=None)
    mock_agent_loop = MagicMock()
    mock_agent_loop.skill_manager = mock_skill_manager
    mock_tui.agent_loop = mock_agent_loop

    app = create_app(token="test-token", tui_app=mock_tui)
    return app


@pytest.fixture
def web_ui_client(web_ui_app):
    """Create a test client for the WebUI app."""
    return TestClient(web_ui_app)


class TestListCommands:
    """Tests for /api/commands endpoint."""

    def test_list_commands_success(self, web_ui_client):
        """Test command listing endpoint returns commands."""
        response = web_ui_client.get(
            "/api/commands",
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "commands" in data
        assert len(data["commands"]) > 0

    def test_list_commands_has_clear(self, web_ui_client):
        """Test that /clear command is listed."""
        response = web_ui_client.get(
            "/api/commands",
            headers={"Authorization": "Bearer test-token"},
        )
        commands = response.json()["commands"]
        clear_cmd = next((c for c in commands if c["name"] == "clear"), None)
        assert clear_cmd is not None
        assert "/clear" in clear_cmd["aliases"]
        assert "Clear conversation history" in clear_cmd["description"]

    def test_list_commands_has_aliases(self, web_ui_client):
        """Test that commands with multiple aliases show all aliases."""
        response = web_ui_client.get(
            "/api/commands",
            headers={"Authorization": "Bearer test-token"},
        )
        commands = response.json()["commands"]
        config_cmd = next((c for c in commands if c["name"] == "config"), None)
        assert config_cmd is not None
        assert "/config" in config_cmd["aliases"]
        assert "/model" in config_cmd["aliases"]

    def test_list_commands_no_auth(self, web_ui_client):
        """Test command listing without authentication."""
        response = web_ui_client.get("/api/commands")
        assert response.status_code == 401


class TestExecuteCommand:
    """Tests for /api/command/execute endpoint."""

    def test_clean_command(self, web_ui_client, web_ui_app):
        """Test /clean command clears history."""
        response = web_ui_client.post(
            "/api/command/execute",
            json={"command": "clean", "args": ""},
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        web_ui_app.state.tui_app.submit_message_from_web.assert_called_once_with("/clean")

    def test_clear_command_alias(self, web_ui_client, web_ui_app):
        """Test /clear command (alias for clean)."""
        response = web_ui_client.post(
            "/api/command/execute",
            json={"command": "clear", "args": ""},
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        web_ui_app.state.tui_app.submit_message_from_web.assert_called_once_with("/clear")

    def test_restart_command(self, web_ui_client, web_ui_app):
        """Test /restart command."""
        response = web_ui_client.post(
            "/api/command/execute",
            json={"command": "restart", "args": ""},
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        web_ui_app.state.tui_app.submit_message_from_web.assert_called_once_with("/restart")

    def test_config_command(self, web_ui_client, web_ui_app):
        """Test /config command."""
        response = web_ui_client.post(
            "/api/command/execute",
            json={"command": "config", "args": ""},
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        web_ui_app.state.tui_app.submit_message_from_web.assert_called_once_with("/config")

    def test_resume_command(self, web_ui_client, web_ui_app):
        """Test /resume command."""
        response = web_ui_client.post(
            "/api/command/execute",
            json={"command": "resume", "args": ""},
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        web_ui_app.state.tui_app.submit_message_from_web.assert_called_once_with("/resume")

    def test_edit_command_with_content(self, web_ui_client, web_ui_app):
        """Test /edit command with content."""
        response = web_ui_client.post(
            "/api/command/execute",
            json={"command": "edit", "args": "new message content"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        web_ui_app.state.tui_app.submit_message_from_web.assert_called_once_with(
            "/edit new message content"
        )

    def test_edit_command_without_content(self, web_ui_client, web_ui_app):
        """Test /edit command without content."""
        response = web_ui_client.post(
            "/api/command/execute",
            json={"command": "edit", "args": ""},
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        web_ui_app.state.tui_app.submit_message_from_web.assert_called_once_with("/edit")

    def test_unknown_command(self, web_ui_client, web_ui_app):
        """Test handling of unknown commands."""
        response = web_ui_client.post(
            "/api/command/execute",
            json={"command": "unknown", "args": ""},
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        web_ui_app.state.tui_app.submit_message_from_web.assert_called_once_with("/unknown")

    def test_skill_command(self, web_ui_client, web_ui_app):
        """Test skill invocation command."""
        # Mock a skill
        mock_skill = MagicMock()
        mock_skill.user_invocable = True
        web_ui_app.state.tui_app.agent_loop.skill_manager.get_skill = MagicMock(
            return_value=mock_skill
        )

        response = web_ui_client.post(
            "/api/command/execute",
            json={"command": "fetch", "args": "https://example.com"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        web_ui_app.state.tui_app.submit_message_from_web.assert_called_once_with(
            "/fetch https://example.com"
        )

    def test_execute_command_no_auth(self, web_ui_client):
        """Test command execution without authentication."""
        response = web_ui_client.post(
            "/api/command/execute",
            json={"command": "clean", "args": ""},
        )
        assert response.status_code == 401
