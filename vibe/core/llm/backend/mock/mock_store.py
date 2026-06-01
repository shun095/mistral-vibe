"""Mock data store for E2E testing.

Provides thread-safe storage for test-specific mock responses.
"""

from __future__ import annotations

import threading
from typing import Any

from vibe.core.types import LLMUsage


class MockResponse:
    """A mock response for a specific message pattern."""

    def __init__(
        self,
        response_text: str,
        tool_calls: list[dict[str, Any]] | None = None,
        usage: LLMUsage | None = None,
    ) -> None:
        self.response_text = response_text
        self.tool_calls = tool_calls or []
        self.usage = usage or LLMUsage(prompt_tokens=1, completion_tokens=1)


class MockDataStore:
    """Thread-safe store for mock responses in E2E tests.

    Allows tests to register mock responses that will be returned
    by the MockBackend when specific message patterns are matched.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._responses: list[MockResponse] = []
        self._response_index = 0

    def register_response(
        self,
        response_text: str,
        tool_calls: list[dict[str, Any]] | None = None,
        usage: LLMUsage | None = None,
    ) -> None:
        """Register a mock response.

        Args:
            response_text: The text response to return.
            tool_calls: Optional list of tool calls to include.
            usage: Optional token usage data.
        """
        with self._lock:
            self._responses.append(
                MockResponse(
                    response_text=response_text, tool_calls=tool_calls, usage=usage
                )
            )

    def get_next_response(self) -> MockResponse | None:
        """Get the next mock response in sequence.

        Returns:
            The next MockResponse, or None if no more responses.
        """
        with self._lock:
            if self._response_index < len(self._responses):
                response = self._responses[self._response_index]
                self._response_index += 1
                return response
            return None

    def reset(self) -> None:
        """Clear all mock responses and reset the index."""
        with self._lock:
            self._responses.clear()
            self._response_index = 0

    def get_usage(self) -> dict[str, int]:
        """Get usage statistics for registered responses.

        Returns:
            Dictionary with count of registered and consumed responses.
        """
        with self._lock:
            return {
                "registered": len(self._responses),
                "consumed": self._response_index,
                "remaining": len(self._responses) - self._response_index,
            }


# Global instance for E2E tests
_global_store: MockDataStore | None = None
_global_lock = threading.Lock()


def get_mock_store() -> MockDataStore:
    """Get the global mock data store instance.

    Returns:
        The global MockDataStore instance, creating it if necessary.
    """
    global _global_store
    with _global_lock:
        if _global_store is None:
            _global_store = MockDataStore()
        return _global_store


def reset_mock_store() -> None:
    """Reset the global mock data store.

    Useful for cleaning up between tests.
    """
    global _global_store
    with _global_lock:
        if _global_store is not None:
            _global_store.reset()
