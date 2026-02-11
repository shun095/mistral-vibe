from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import pytest
import tomli_w

from vibe.core.paths import global_paths
from vibe.core.paths.config_paths import unlock_config_paths


def get_base_config() -> dict[str, Any]:
    return {
        "active_model": "devstral-latest",
        "providers": [
            {
                "name": "mistral",
                "api_base": "https://api.mistral.ai/v1",
                "api_key_env_var": "MISTRAL_API_KEY",
                "backend": "mistral",
            }
        ],
        "models": [
            {
                "name": "mistral-vibe-cli-latest",
                "provider": "mistral",
                "alias": "devstral-latest",
            }
        ],
        "enable_auto_update": False,
    }


@pytest.fixture(autouse=True)
def tmp_working_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    tmp_working_directory = tmp_path_factory.mktemp("test_cwd")
    monkeypatch.chdir(tmp_working_directory)
    return tmp_working_directory


@pytest.fixture(autouse=True)
def config_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    tmp_path = tmp_path_factory.mktemp("vibe")
    config_dir = tmp_path / ".vibe"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.toml"
    config_file.write_text(tomli_w.dumps(get_base_config()), encoding="utf-8")

    monkeypatch.setattr(global_paths, "_DEFAULT_VIBE_HOME", config_dir)
    return config_dir


@pytest.fixture(autouse=True)
def _unlock_config_paths():
    unlock_config_paths()


@pytest.fixture(autouse=True)
def _mock_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "mock")


@pytest.fixture(autouse=True)
def _mock_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock platform to be Linux with /bin/sh shell for consistent test behavior.

    This ensures that platform-specific system prompt generation is consistent
    across all tests regardless of the actual platform running the tests.
    """
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("SHELL", "/bin/sh")


@pytest.fixture(autouse=True)
def _mock_update_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vibe.cli.update_notifier.update.UPDATE_COMMANDS", ["true"])


@pytest.fixture(autouse=True)
def _cleanup_lsp_client_manager() -> None:
    """Clean up LSPClientManager state between tests.
    
    This fixture ensures that the class-level state of LSPClientManager
    is reset between tests to prevent test pollution.
    """
    from vibe.core.lsp.client_manager import LSPClientManager
    
    # Store the current state
    clients_before = LSPClientManager._clients.copy()
    handles_before = LSPClientManager._handles.copy()
    config_before = LSPClientManager._config.copy()
    
    yield
    
    # Clean up any clients that were created during the test
    for server_name in list(LSPClientManager._clients.keys()):
        if server_name not in clients_before:
            del LSPClientManager._clients[server_name]
    
    for server_name in list(LSPClientManager._handles.keys()):
        if server_name not in handles_before:
            del LSPClientManager._handles[server_name]
    
    for server_name in list(LSPClientManager._config.keys()):
        if server_name not in config_before:
            del LSPClientManager._config[server_name]
