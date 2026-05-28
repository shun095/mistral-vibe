"""Shared fixtures and utilities for web_ui tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from vibe.cli.web_ui.config import AUTH_COOKIE_NAME
from vibe.core.tools.base import BaseTool


class MockToolManager:
    """Mock tool manager for testing."""

    def __init__(self, tools: dict[str, type[BaseTool] | BaseTool] | None = None):
        self.available_tools: dict[str, type[BaseTool] | BaseTool] = tools or {}

    def get(self, name: str):
        if name in self.available_tools:
            return self.available_tools[name]
        raise ValueError(f"Unknown tool: {name}")


@pytest.fixture
def web_ui_app():
    """Create a WebUI app for testing."""
    from vibe.cli.web_ui.server import create_app

    return create_app(token="test-token")


@pytest.fixture
def client(web_ui_app):
    """Create a test client for the WebUI app."""
    return TestClient(web_ui_app)


@pytest.fixture
def authenticated_client(web_ui_app):
    """Create a test client with authentication cookie set.

    Use this fixture instead of manually setting cookies in each test.
    """
    client = TestClient(web_ui_app)
    client.cookies.set(AUTH_COOKIE_NAME, "test-token")
    return client
