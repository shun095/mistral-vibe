"""Shared fixtures and utilities for web_ui tests."""

from __future__ import annotations


class MockToolManager:
    """Mock tool manager for testing."""

    def __init__(self, tools: dict[str, object] | None = None):
        self._tools = tools or {}

    def get(self, name: str):
        if name in self._tools:
            return self._tools[name]
        raise ValueError(f"Unknown tool: {name}")
