from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
import functools
from typing import Any

import httpx

from vibe.core.types import LLMRetryEvent


def _is_retryable_http_error(e: Exception) -> bool:  # noqa: PLR0911
    """Check if an exception is retryable for LLM backend operations.

    Handles both HTTP status code errors and network/transport errors.
    """
    # HTTP status code errors (retry on server errors and rate limits)
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code in {408, 409, 425, 429, 500, 502, 503, 504, 529}

    # Network/transport errors (retry on transient network issues)
    if isinstance(e, httpx.RequestError):
        error_str = str(e).lower()
        if "readtimeout" in error_str:
            return True
        # Incomplete chunked read
        if "server disconnected without sending a response" in error_str:
            return True
        if "incomplete chunked read" in error_str:
            return True
        # Peer closed connection
        if "peer closed connection" in error_str:
            return True
        # Other common network errors
        if any(
            keyword in error_str for keyword in ["network", "connection", "timeout"]
        ):
            return True

    return False


def async_retry[T, **P](
    config: dict[str, Any],
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Retry decorator for async functions using mutable config.

    Uses a mutable config dict to allow dynamic injection of on_retry callback.

    Args:
        config: Configuration dict with keys:
            - tries: Number of retry attempts (default: 3)
            - delay_seconds: Initial delay between retries in seconds (default: 0.5)
            - backoff_factor: Multiplier for delay on each retry (default: 2.0)
            - is_retryable: Function to determine if an exception should trigger a retry
            - on_retry: Optional callback invoked before each retry with LLMRetryEvent
            - provider: Optional provider name for the retry event
            - model: Optional model name for the retry event

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exc = None
            tries = config.get("tries", 3)
            delay_seconds = config.get("delay_seconds", 0.5)
            backoff_factor = config.get("backoff_factor", 2.0)
            is_retryable = config.get("is_retryable", _is_retryable_http_error)
            on_retry = config.get("on_retry")
            provider = config.get("provider")
            model = config.get("model")

            for attempt in range(tries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if attempt < tries - 1 and is_retryable(e):
                        current_delay = (delay_seconds * (backoff_factor**attempt)) + (
                            0.05 * attempt
                        )

                        # Invoke on_retry callback if provided
                        if on_retry is not None:
                            retry_event = LLMRetryEvent(
                                attempt=attempt + 1,
                                max_attempts=tries,
                                error_message=str(last_exc),
                                delay_seconds=current_delay,
                                provider=provider,
                                model=model,
                            )
                            on_retry(retry_event)

                        await asyncio.sleep(current_delay)
                        continue
                    raise e
            raise RuntimeError(
                f"Retries exhausted. Last error: {last_exc}"
            ) from last_exc

        return wrapper

    return decorator


def apply_retry_decorator(
    obj: Any, method_name: str, config: dict[str, Any], is_streaming: bool = False
) -> None:
    """Apply retry decorator to a method dynamically.

    Args:
        obj: Object instance containing the method to decorate.
        method_name: Name of the method to apply retry logic to.
        config: Retry configuration dict with keys:
            - tries: Number of retry attempts
            - delay_seconds: Initial delay between retries
            - backoff_factor: Multiplier for delay on each retry
            - is_retryable: Function to determine if exception should trigger retry
            - on_retry: Optional callback invoked before each retry
            - provider: Optional provider name for retry event
            - model: Optional model name for retry event
        is_streaming: Whether the method is an async generator.

    """
    original = getattr(obj, method_name)
    if is_streaming:
        decorated = async_generator_retry(config)(original)
    else:
        decorated = async_retry(config)(original)
    setattr(obj, method_name, decorated)  # type: ignore[misc]


def async_generator_retry[T, **P](
    config: dict[str, Any],
) -> Callable[[Callable[P, AsyncGenerator[T]]], Callable[P, AsyncGenerator[T]]]:
    """Retry decorator for async generators using mutable config.

    Uses a mutable config dict to allow dynamic injection of on_retry callback.

    Args:
        config: Configuration dict with keys:
            - tries: Number of retry attempts (default: 3)
            - delay_seconds: Initial delay between retries in seconds (default: 0.5)
            - backoff_factor: Multiplier for delay on each retry (default: 2.0)
            - is_retryable: Function to determine if an exception should trigger a retry
            - on_retry: Optional callback invoked before each retry with LLMRetryEvent
            - provider: Optional provider name for the retry event
            - model: Optional model name for the retry event

    Returns:
        Decorated async generator function with retry logic
    """

    def decorator(
        func: Callable[P, AsyncGenerator[T]],
    ) -> Callable[P, AsyncGenerator[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> AsyncGenerator[T]:
            last_exc = None
            tries = config.get("tries", 3)
            delay_seconds = config.get("delay_seconds", 0.5)
            backoff_factor = config.get("backoff_factor", 2.0)
            is_retryable = config.get("is_retryable", _is_retryable_http_error)
            on_retry = config.get("on_retry")
            provider = config.get("provider")
            model = config.get("model")

            for attempt in range(tries):
                try:
                    async for item in func(*args, **kwargs):
                        yield item
                    return
                except Exception as e:
                    last_exc = e
                    if attempt < tries - 1 and is_retryable(e):
                        current_delay = (delay_seconds * (backoff_factor**attempt)) + (
                            0.05 * attempt
                        )

                        # Invoke on_retry callback if provided
                        if on_retry is not None:
                            retry_event = LLMRetryEvent(
                                attempt=attempt + 1,
                                max_attempts=tries,
                                error_message=str(last_exc),
                                delay_seconds=current_delay,
                                provider=provider,
                                model=model,
                            )
                            on_retry(retry_event)

                        await asyncio.sleep(current_delay)
                        continue
                    raise e
            raise RuntimeError(
                f"Retries exhausted. Last error: {last_exc}"
            ) from last_exc

        return wrapper

    return decorator
