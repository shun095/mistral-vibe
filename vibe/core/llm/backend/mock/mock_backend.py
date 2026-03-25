"""Mock backend for E2E testing.

Provides mock LLM responses for testing without external dependencies.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Sequence
from types import TracebackType
from typing import TYPE_CHECKING

from vibe.core.llm.backend.mock.mock_store import get_mock_store
from vibe.core.types import (
    AvailableTool,
    FunctionCall,
    LLMChunk,
    LLMMessage,
    LLMUsage,
    Role,
    StrToolChoice,
    ToolCall,
)

if TYPE_CHECKING:
    from vibe.core.config import ModelConfig, ProviderConfig


class MockBackend:
    """Mock LLM backend for E2E testing.

    Returns pre-registered mock responses from the MockDataStore.
    Falls back to a default response if no mock is registered.

    Usage:
        from vibe.core.llm.backend.mock import get_mock_store

        # Register a mock response
        store = get_mock_store()
        store.register_response("Hello from mock backend!")

        # Use MockBackend - it will return the registered response
    """

    def __init__(
        self,
        *,
        provider: ProviderConfig,
        default_response: str = "This is a response from the mock backend.",
    ) -> None:
        """Initialize the mock backend.

        Args:
            provider: Provider configuration (ignored, but required for API compatibility).
            default_response: Default response when no mock is registered.
        """
        self._provider = provider
        self._default_response = default_response

    async def __aenter__(self) -> MockBackend:
        """Enter async context."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_val: BaseException | None = None,
        exc_tb: TracebackType | None = None,
    ) -> None:
        """Exit async context."""
        pass

    async def count_tokens(
        self,
        *,
        model: ModelConfig,
        messages: Sequence[LLMMessage],
        temperature: float | None = None,
        tools: list[AvailableTool] | None = None,
        tool_choice: StrToolChoice | AvailableTool | None = None,
        extra_headers: dict[str, str] | None = None,
        metadata: dict[str, str] | None = None,
    ) -> int:
        """Count tokens in messages (stub implementation).

        Args:
            model: Model configuration.
            messages: List of messages.
            temperature: Sampling temperature.
            tools: Available tools.
            tool_choice: Tool choice.
            extra_headers: Extra headers.
            metadata: Metadata.

        Returns:
            Approximate token count.
        """
        # Simple approximation: count words in all messages
        total_text = ""
        for msg in messages:
            if isinstance(msg.content, str):
                total_text += msg.content
            elif isinstance(msg.content, list):
                for item in msg.content:
                    if isinstance(item, dict) and "text" in item:
                        total_text += item["text"]
        return len(total_text.split()) * 13 // 10

    async def complete(
        self,
        *,
        model: ModelConfig,
        messages: Sequence[LLMMessage],
        temperature: float | None = None,
        tools: list[AvailableTool] | None = None,
        max_tokens: int | None = None,
        tool_choice: StrToolChoice | AvailableTool | None = None,
        extra_headers: dict[str, str] | None = None,
        metadata: dict[str, str] | None = None,
    ) -> LLMChunk:
        """Return a mock completion.

        Args:
            model: Model configuration (ignored).
            messages: Input messages (ignored).
            temperature: Temperature setting (ignored).
            tools: Available tools (used if mock includes tool calls).
            max_tokens: Max tokens (ignored).
            tool_choice: Tool choice (ignored).
            extra_headers: Extra headers (ignored).
            metadata: Metadata (ignored).

        Returns:
            LLMChunk with the mock response.
        """
        store = get_mock_store()
        mock = store.get_next_response()

        if mock is not None:
            # Build response with tool calls if registered
            if mock.tool_calls:
                tool_calls = [
                    ToolCall(
                        id=tc.get("id", f"call_{i}"),
                        index=i,
                        type="function",
                        function=FunctionCall(
                            name=tc.get("name", "unknown_tool"),
                            arguments=tc.get("arguments", "{}"),
                        ),
                    )
                    for i, tc in enumerate(mock.tool_calls)
                ]
                message = LLMMessage(
                    role=Role.assistant, content="", tool_calls=tool_calls
                )
            else:
                message = LLMMessage(role=Role.assistant, content=mock.response_text)

            return LLMChunk(message=message, usage=mock.usage)

        # Default response
        message = LLMMessage(role=Role.assistant, content=self._default_response)
        usage = LLMUsage(prompt_tokens=1, completion_tokens=1)
        return LLMChunk(message=message, usage=usage)

    async def complete_streaming(
        self,
        *,
        model: ModelConfig,
        messages: Sequence[LLMMessage],
        temperature: float | None = None,
        tools: list[AvailableTool] | None = None,
        max_tokens: int | None = None,
        tool_choice: StrToolChoice | AvailableTool | None = None,
        extra_headers: dict[str, str] | None = None,
        metadata: dict[str, str] | None = None,
        return_progress: bool = False,
    ) -> AsyncGenerator[LLMChunk, None]:
        """Return a mock streaming completion.

        Args:
            model: Model configuration (ignored).
            messages: Input messages (ignored).
            temperature: Temperature setting (ignored).
            tools: Available tools (ignored).
            max_tokens: Max tokens (ignored).
            tool_choice: Tool choice (ignored).
            extra_headers: Extra headers (ignored).
            metadata: Metadata (ignored).
            return_progress: Whether to return progress (ignored).

        Yields:
            LLMChunk objects simulating streaming response.
        """
        store = get_mock_store()
        mock = store.get_next_response()

        if mock is not None and mock.tool_calls:
            # Stream tool calls
            for i, tc in enumerate(mock.tool_calls):
                chunk = LLMChunk(
                    message=LLMMessage(
                        role=Role.assistant,
                        content="",
                        tool_calls=[
                            ToolCall(
                                id=tc.get("id", f"call_{i}"),
                                index=i,
                                type="function",
                                function=FunctionCall(
                                    name=tc.get("name", "unknown_tool"),
                                    arguments=tc.get("arguments", "{}"),
                                ),
                            )
                        ],
                    ),
                    usage=None,
                )
                yield chunk

            # Final chunk with usage
            yield LLMChunk(
                message=LLMMessage(role=Role.assistant, content=""), usage=mock.usage
            )
        else:
            # Stream text response character by character
            response_text = mock.response_text if mock else self._default_response
            usage = (
                mock.usage if mock else LLMUsage(prompt_tokens=1, completion_tokens=1)
            )

            for char in response_text:
                chunk = LLMChunk(
                    message=LLMMessage(role=Role.assistant, content=char), usage=None
                )
                yield chunk

            # Final chunk with usage
            yield LLMChunk(
                message=LLMMessage(role=Role.assistant, content=""), usage=usage
            )
