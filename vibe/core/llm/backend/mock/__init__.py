"""Mock backend for E2E testing.

This package provides fake LLM backend and mock data store for E2E tests.
"""

from __future__ import annotations

from vibe.core.llm.backend.mock.mock_backend import MockBackend
from vibe.core.llm.backend.mock.mock_store import (
    MockDataStore,
    MockResponse,
    get_mock_store,
    reset_mock_store,
)

__all__ = [
    "MockBackend",
    "MockDataStore",
    "MockResponse",
    "get_mock_store",
    "reset_mock_store",
]
