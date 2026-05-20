"""Tests for new WebUI endpoints: models, config, mcp, rewind, thinking."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
import pytest

from vibe.cli.web_ui.config import AUTH_COOKIE_NAME


@dataclass
class FakeModel:
    """Simple model for JSON serialization."""

    alias: str
    name: str
    provider: str


@dataclass
class FakeActiveModel:
    thinking: str = "off"


@dataclass
class FakeServer:
    name: str
    transport: str = "stdio"
    disabled: bool = False


@pytest.fixture
def web_ui_app_with_tui():
    """Create a WebUI app with a mocked TUI that has config and agent_loop."""
    from vibe.cli.web_ui.server import create_app

    mock_tui = MagicMock()
    mock_tui.is_agent_running = MagicMock(return_value=False)
    mock_tui.submit_message_from_web = MagicMock()
    mock_tui.reload_config = MagicMock()

    # Mock config — use simple objects, not MagicMock, for JSON serializability
    mock_config = MagicMock()
    mock_config.models = [
        FakeModel(alias="mistral-large", name="mistral-large-2411", provider="mistral"),
        FakeModel(alias="codestral", name="codestral-latest", provider="mistral"),
    ]
    mock_config.active_model = "mistral-large"
    mock_config.autocopy_to_clipboard = True
    mock_config.file_watcher_for_autocomplete = False
    mock_config.voice_mode_enabled = False
    mock_config.narrator_enabled = False
    mock_config.auto_approve = False
    mock_config.enable_notifications = True
    mock_config.enable_web_notifications = True
    mock_config.loop_detection_enabled = True
    mock_config.context_warnings = False
    mock_config.mcp_servers = []
    mock_config.connectors = []
    mock_config.set_thinking = MagicMock()
    mock_tui.config = mock_config

    # Mock get_active_model
    mock_config.get_active_model = MagicMock(
        return_value=FakeActiveModel(thinking="off")
    )

    # Mock agent_loop
    mock_agent_loop = MagicMock()
    mock_agent_loop.rewind_manager = None
    mock_agent_loop.tool_manager = None
    mock_tui.agent_loop = mock_agent_loop

    # Mock commands registry
    mock_commands = MagicMock()
    mock_commands.commands = {}
    mock_tui.commands = mock_commands

    app = create_app(token="test-token", tui_app=mock_tui)
    return app


@pytest.fixture
def client(web_ui_app_with_tui):
    """Authenticated test client."""
    c = TestClient(web_ui_app_with_tui)
    c.cookies.set(AUTH_COOKIE_NAME, "test-token")
    return c


@pytest.fixture
def unauthenticated_client(web_ui_app_with_tui):
    """Unauthenticated test client."""
    return TestClient(web_ui_app_with_tui)


class TestListModels:
    def test_list_models_success(self, client):
        resp = client.get("/api/models")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["models"]) == 2
        assert data["active_model"] == "mistral-large"
        assert data["models"][0]["alias"] == "mistral-large"

    def test_list_models_no_auth(self, unauthenticated_client):
        resp = unauthenticated_client.get("/api/models")
        assert resp.status_code == 401


class TestSwitchModel:
    def test_switch_model_success(self, client, web_ui_app_with_tui):
        from vibe.core.config import VibeConfig

        saved_updates = {}

        def fake_save(updates):
            saved_updates.update(updates)

        with patch.object(VibeConfig, "save_updates", staticmethod(fake_save)):
            resp = client.post("/api/models/switch", json={"alias": "codestral"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["active_model"] == "codestral"
            assert saved_updates["active_model"] == "codestral"
            web_ui_app_with_tui.state.tui_app.reload_config.assert_called_once()

    def test_switch_model_no_alias(self, client):
        resp = client.post("/api/models/switch", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "alias" in data["error"].lower()

    def test_switch_model_no_auth(self, unauthenticated_client):
        resp = unauthenticated_client.post("/api/models/switch", json={"alias": "x"})
        assert resp.status_code == 401


class TestGetConfig:
    def test_get_config_success(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active_model"] == "mistral-large"
        assert data["thinking"] == "off"
        assert data["autocopy_to_clipboard"] is True
        assert data["file_watcher_for_autocomplete"] is False
        assert data["voice_mode_enabled"] is False
        assert data["auto_approve"] is False

    def test_get_config_no_auth(self, unauthenticated_client):
        resp = unauthenticated_client.get("/api/config")
        assert resp.status_code == 401


class TestSaveConfig:
    def test_save_config_success(self, client, web_ui_app_with_tui):
        from vibe.core.config import VibeConfig

        saved_updates = {}

        def fake_save(updates):
            saved_updates.update(updates)

        with patch.object(VibeConfig, "save_updates", staticmethod(fake_save)):
            resp = client.post(
                "/api/config",
                json={"autocopy_to_clipboard": False, "voice_mode_enabled": True},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert "autocopy_to_clipboard" in data["updated"]
            assert "voice_mode_enabled" in data["updated"]
            assert saved_updates["autocopy_to_clipboard"] is False
            assert saved_updates["voice_mode_enabled"] is True

    def test_save_config_ignores_invalid_keys(self, client):
        resp = client.post("/api/config", json={"invalid_key": True})
        data = resp.json()
        assert data["success"] is False

    def test_save_config_no_auth(self, unauthenticated_client):
        resp = unauthenticated_client.post(
            "/api/config", json={"voice_mode_enabled": True}
        )
        assert resp.status_code == 401


class TestSwitchThinking:
    def test_switch_thinking_success(self, client, web_ui_app_with_tui):
        resp = client.post("/api/thinking/switch", json={"level": "high"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["thinking"] == "high"
        web_ui_app_with_tui.state.tui_app.config.set_thinking.assert_called_with("high")

    def test_switch_thinking_no_level(self, client):
        resp = client.post("/api/thinking/switch", json={})
        data = resp.json()
        assert data["success"] is False

    def test_switch_thinking_no_auth(self, unauthenticated_client):
        resp = unauthenticated_client.post(
            "/api/thinking/switch", json={"level": "low"}
        )
        assert resp.status_code == 401


class TestListMcp:
    def test_list_mcp_empty(self, client):
        resp = client.get("/api/mcp")
        assert resp.status_code == 200
        data = resp.json()
        assert data["servers"] == []
        assert data["connectors"] == []

    def test_list_mcp_no_auth(self, unauthenticated_client):
        resp = unauthenticated_client.get("/api/mcp")
        assert resp.status_code == 401


class TestToggleMcp:
    def test_toggle_mcp_success(self, client, web_ui_app_with_tui):

        calls = []

        def fake_persist(config, *, name, is_connector, disabled, tool_name=None):
            calls.append({
                "name": name,
                "is_connector": is_connector,
                "disabled": disabled,
                "tool_name": tool_name,
            })

        with patch("vibe.cli.web_ui.routes.persist_mcp_toggle", fake_persist):
            resp = client.post(
                "/api/mcp/toggle",
                json={"name": "myserver", "is_connector": False, "disabled": True},
            )
            assert resp.status_code == 200
            assert resp.json()["success"] is True
            assert len(calls) == 1
            assert calls[0]["name"] == "myserver"
            assert calls[0]["disabled"] is True

    def test_toggle_mcp_no_name(self, client):
        resp = client.post("/api/mcp/toggle", json={})
        data = resp.json()
        assert data["success"] is False

    def test_toggle_mcp_no_auth(self, unauthenticated_client):
        resp = unauthenticated_client.post("/api/mcp/toggle", json={"name": "x"})
        assert resp.status_code == 401


class TestGetRewindState:
    def test_get_rewind_no_messages(self, client, web_ui_app_with_tui):
        # Mock query_one to raise since there's no real Textual app
        web_ui_app_with_tui.state.tui_app.query_one.side_effect = Exception(
            "no messages area"
        )
        resp = client.get("/api/rewind/state")
        data = resp.json()
        assert data["success"] is False

    def test_get_rewind_no_auth(self, unauthenticated_client):
        resp = unauthenticated_client.get("/api/rewind/state")
        assert resp.status_code == 401


class TestExecuteRewind:
    def test_execute_rewind_success(self, client, web_ui_app_with_tui):
        mock_rewind_mgr = MagicMock()
        mock_rewind_mgr.rewind_to_message = AsyncMock(return_value=("edit content", []))
        web_ui_app_with_tui.state.tui_app.agent_loop.rewind_manager = mock_rewind_mgr

        resp = client.post(
            "/api/rewind/execute", json={"message_index": 5, "restore_files": True}
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        mock_rewind_mgr.rewind_to_message.assert_called_once_with(5, restore_files=True)

    def test_execute_rewind_no_index(self, client):
        resp = client.post("/api/rewind/execute", json={})
        data = resp.json()
        assert data["success"] is False

    def test_execute_rewind_no_auth(self, unauthenticated_client):
        resp = unauthenticated_client.post(
            "/api/rewind/execute", json={"message_index": 0}
        )
        assert resp.status_code == 401
