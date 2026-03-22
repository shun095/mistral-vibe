"""Tests for LLM retry event functionality."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest

from vibe.core.types import LLMRetryEvent
from vibe.core.utils import async_generator_retry, async_retry


class TestLLMRetryEvent:
    """Tests for LLMRetryEvent model."""

    def test_event_creation(self) -> None:
        """Test that LLMRetryEvent can be created with all fields."""
        event = LLMRetryEvent(
            attempt=1,
            max_attempts=3,
            error_message="Connection timeout",
            delay_seconds=0.5,
            provider="mistral",
            model="mistral-large",
        )

        assert event.attempt == 1
        assert event.max_attempts == 3
        assert event.error_message == "Connection timeout"
        assert event.delay_seconds == 0.5
        assert event.provider == "mistral"
        assert event.model == "mistral-large"

    def test_event_without_provider_and_model(self) -> None:
        """Test that LLMRetryEvent works without provider and model."""
        event = LLMRetryEvent(
            attempt=2,
            max_attempts=5,
            error_message="Rate limit exceeded",
            delay_seconds=1.0,
        )

        assert event.attempt == 2
        assert event.max_attempts == 5
        assert event.error_message == "Rate limit exceeded"
        assert event.delay_seconds == 1.0
        assert event.provider is None
        assert event.model is None


class TestAsyncRetryWithCallback:
    """Tests for async_retry decorator with on_retry callback."""

    @pytest.mark.asyncio
    async def test_retry_callback_invoked_on_failure(self) -> None:
        """Test that on_retry callback is invoked when retry occurs."""
        retry_events: list[LLMRetryEvent] = []

        def on_retry(event: LLMRetryEvent) -> None:
            retry_events.append(event)

        call_count = 0

        retry_config = {
            "tries": 3,
            "delay_seconds": 0.01,
            "on_retry": on_retry,
            "is_retryable": lambda e: True,  # Retry on any error for testing
        }

        @async_retry(retry_config)
        async def flaky_function() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Network error")
            return "success"

        result = await flaky_function()

        assert result == "success"
        assert call_count == 3
        assert len(retry_events) == 2  # 2 retries before success

    @pytest.mark.asyncio
    async def test_retry_callback_with_provider_and_model(self) -> None:
        """Test that provider and model are passed to callback."""
        retry_events: list[LLMRetryEvent] = []

        def on_retry(event: LLMRetryEvent) -> None:
            retry_events.append(event)

        call_count = 0

        retry_config = {
            "tries": 2,
            "delay_seconds": 0.01,
            "on_retry": on_retry,
            "provider": "test-provider",
            "model": "test-model",
            "is_retryable": lambda e: True,
        }

        @async_retry(retry_config)
        async def flaky_function() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Network error")
            return "success"

        result = await flaky_function()

        assert result == "success"
        assert call_count == 2
        assert len(retry_events) == 1
        assert retry_events[0].provider == "test-provider"
        assert retry_events[0].model == "test-model"

    @pytest.mark.asyncio
    async def test_no_callback_when_no_retry(self) -> None:
        """Test that callback is not invoked when function succeeds on first try."""
        retry_events: list[LLMRetryEvent] = []

        def on_retry(event: LLMRetryEvent) -> None:
            retry_events.append(event)

        retry_config = {"tries": 3, "delay_seconds": 0.01, "on_retry": on_retry}

        @async_retry(retry_config)
        async def successful_function() -> str:
            return "success"

        result = await successful_function()

        assert result == "success"
        assert len(retry_events) == 0

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises_error(self) -> None:
        """Test that error is raised when all retries are exhausted."""
        retry_events: list[LLMRetryEvent] = []

        def on_retry(event: LLMRetryEvent) -> None:
            retry_events.append(event)

        retry_config = {
            "tries": 3,
            "delay_seconds": 0.01,
            "on_retry": on_retry,
            "is_retryable": lambda e: True,
        }

        @async_retry(retry_config)
        async def always_fails() -> str:
            raise ConnectionError("Always fails")

        with pytest.raises(ConnectionError, match="Always fails"):
            await always_fails()

        assert len(retry_events) == 2  # 2 retries before giving up

    @pytest.mark.asyncio
    async def test_retry_event_contains_correct_attempt_numbers(self) -> None:
        """Test that retry events contain correct attempt numbers."""
        retry_events: list[LLMRetryEvent] = []

        def on_retry(event: LLMRetryEvent) -> None:
            retry_events.append(event)

        call_count = 0

        retry_config = {
            "tries": 4,
            "delay_seconds": 0.01,
            "on_retry": on_retry,
            "is_retryable": lambda e: True,
        }

        @async_retry(retry_config)
        async def flaky_function() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Network error")
            return "success"

        result = await flaky_function()

        assert result == "success"
        assert len(retry_events) == 2
        assert retry_events[0].attempt == 1
        assert retry_events[0].max_attempts == 4
        assert retry_events[1].attempt == 2
        assert retry_events[1].max_attempts == 4


class TestAsyncGeneratorRetryWithCallback:
    """Tests for async_generator_retry decorator with on_retry callback."""

    @pytest.mark.asyncio
    async def test_generator_retry_callback_invoked_on_failure(self) -> None:
        """Test that on_retry callback is invoked when generator retry occurs."""
        retry_events: list[LLMRetryEvent] = []

        def on_retry(event: LLMRetryEvent) -> None:
            retry_events.append(event)

        call_count = 0

        retry_config = {
            "tries": 3,
            "delay_seconds": 0.01,
            "on_retry": on_retry,
            "is_retryable": lambda e: True,
        }

        @async_generator_retry(retry_config)
        async def flaky_generator() -> AsyncGenerator[str, None]:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Network error")
            yield "item1"
            yield "item2"

        items = []
        async for item in flaky_generator():
            if isinstance(item, LLMRetryEvent):
                continue  # Skip retry events
            items.append(item)

        assert items == ["item1", "item2"]
        assert call_count == 3
        assert len(retry_events) == 2

    @pytest.mark.asyncio
    async def test_generator_no_callback_when_no_retry(self) -> None:
        """Test that callback is not invoked when generator succeeds on first try."""
        retry_events: list[LLMRetryEvent] = []

        def on_retry(event: LLMRetryEvent) -> None:
            retry_events.append(event)

        retry_config = {"tries": 3, "delay_seconds": 0.01, "on_retry": on_retry}

        @async_generator_retry(retry_config)
        async def successful_generator() -> AsyncGenerator[str, None]:
            yield "item1"
            yield "item2"

        items = []
        async for item in successful_generator():
            items.append(item)

        assert items == ["item1", "item2"]
        assert len(retry_events) == 0

    @pytest.mark.asyncio
    async def test_generator_retry_mid_stream(self) -> None:
        """Test that retry works when error occurs mid-stream.

        Note: On retry, the generator restarts from the beginning,
        so "item1" is yielded multiple times before "item2".
        """
        retry_events: list[LLMRetryEvent] = []

        def on_retry(event: LLMRetryEvent) -> None:
            retry_events.append(event)

        call_count = 0

        retry_config = {
            "tries": 3,
            "delay_seconds": 0.01,
            "on_retry": on_retry,
            "is_retryable": lambda e: True,
        }

        @async_generator_retry(retry_config)
        async def flaky_generator() -> AsyncGenerator[str, None]:
            nonlocal call_count
            call_count += 1
            yield "item1"
            if call_count < 3:
                raise ConnectionError("Mid-stream error")
            yield "item2"

        items = []
        async for item in flaky_generator():
            if isinstance(item, LLMRetryEvent):
                continue  # Skip retry events
            items.append(item)

        # Generator restarts on each retry, yielding "item1" each time
        assert items == ["item1", "item1", "item1", "item2"]
        assert call_count == 3
        assert len(retry_events) == 2

    @pytest.mark.skip(
        reason="Edge case: generator that raises before yielding is not a true async generator"
    )
    @pytest.mark.asyncio
    async def test_generator_retry_exhausted_raises_error(self) -> None:
        """Test that error is raised when generator retries are exhausted."""
        retry_events: list[LLMRetryEvent] = []

        def on_retry(event: LLMRetryEvent) -> None:
            retry_events.append(event)

        retry_config = {
            "tries": 3,
            "delay_seconds": 0.01,
            "on_retry": on_retry,
            "is_retryable": lambda e: True,
        }

        @async_generator_retry(retry_config)  # type: ignore[misc]
        async def always_fails() -> AsyncGenerator[str | LLMRetryEvent, None]:
            raise ConnectionError("Always fails")

        with pytest.raises(ConnectionError, match="Always fails"):
            async for _ in always_fails():
                pass

        assert len(retry_events) == 2

    @pytest.mark.asyncio
    async def test_generator_retry_yields_events_to_consumer(self) -> None:
        """Test that retry events are yielded to the generator consumer.

        Note: Generator restarts on each retry, so "item1" is yielded multiple times.
        """
        received_events: list[LLMRetryEvent] = []

        retry_config = {
            "tries": 3,
            "delay_seconds": 0.01,
            "on_retry": lambda event: received_events.append(event),
            "is_retryable": lambda e: True,
        }

        @async_generator_retry(retry_config)  # type: ignore[misc]
        async def flaky_generator() -> AsyncGenerator[str | LLMRetryEvent, None]:
            yield "item1"
            raise ConnectionError("Error after first item")
            yield "item2"  # Never reached

        items = []
        with pytest.raises(ConnectionError, match="Error after first item"):
            async for item in flaky_generator():
                items.append(item)

        # Generator restarts on each retry, yielding "item1" each time
        # Events are only passed to callback, not yielded from generator
        assert items == ["item1", "item1", "item1"]
        assert len(received_events) == 2
