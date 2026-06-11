from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
import functools
import logging
from typing import Any

import httpx

logger = logging.getLogger("vibe")

_RETRYABLE_REQUEST_ERRORS: tuple[type[httpx.RequestError], ...] = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.WriteError,
    httpx.RemoteProtocolError,
)

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
        # Fast path: known retryable error types
        if isinstance(e, _RETRYABLE_REQUEST_ERRORS):
            return True
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
    tries: int = 3,
    delay_seconds: float = 0.5,
    backoff_factor: float = 2.0,
    is_retryable: Callable[[Exception], bool] = _is_retryable_http_error,
    on_retry: Callable[[LLMRetryEvent], None] | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Args:
        tries: Number of retry attempts
        delay_seconds: Initial delay between retries in seconds
        backoff_factor: Multiplier for delay on each retry
        is_retryable: Function to determine if an exception should trigger a retry
        on_retry: Optional callback invoked before each retry with LLMRetryEvent
        provider: Optional provider name for the retry event
        model: Optional model name for the retry event

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exc = None
            for attempt in range(tries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if attempt < tries - 1 and is_retryable(e):
                        current_delay = (delay_seconds * (backoff_factor**attempt)) + (
                            0.05 * attempt
                        )
                        if on_retry is not None:
                            on_retry(
                                LLMRetryEvent(
                                    attempt=attempt + 1,
                                    max_attempts=tries,
                                    error_message=str(last_exc),
                                    delay_seconds=current_delay,
                                    provider=provider,
                                    model=model,
                                )
                            )
                        logger.warning(
                            "Retrying %s after error attempt=%d/%d delay=%.2fs error=%r",
                            func.__qualname__,
                            attempt + 1,
                            tries,
                            current_delay,
                            e,
                        )
                        await asyncio.sleep(current_delay)
                        continue
                    raise e
            raise RuntimeError(
                f"Retries exhausted. Last error: {last_exc}"
            ) from last_exc

        return wrapper

    return decorator


def wrap_with_retry(
    obj: Any,
    method_name: str,
    *,
    is_streaming: bool = False,
    tries: int = 3,
    delay_seconds: float = 0.5,
    backoff_factor: float = 2.0,
    on_retry: Callable[[LLMRetryEvent], None] | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> None:
    """Apply retry decorator to a method dynamically."""
    original = getattr(obj, method_name)
    if is_streaming:
        decorated = async_generator_retry(
            tries=tries,
            delay_seconds=delay_seconds,
            backoff_factor=backoff_factor,
            on_retry=on_retry,
            provider=provider,
            model=model,
        )(original)
    else:
        decorated = async_retry(
            tries=tries,
            delay_seconds=delay_seconds,
            backoff_factor=backoff_factor,
            on_retry=on_retry,
            provider=provider,
            model=model,
        )(original)
    setattr(obj, method_name, decorated)  # type: ignore[misc]


def async_generator_retry[T, **P](
    tries: int = 3,
    delay_seconds: float = 0.5,
    backoff_factor: float = 2.0,
    is_retryable: Callable[[Exception], bool] = _is_retryable_http_error,
    on_retry: Callable[[LLMRetryEvent], None] | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> Callable[[Callable[P, AsyncGenerator[T]]], Callable[P, AsyncGenerator[T]]]:
    """Retry decorator for async generators.

    Args:
        tries: Number of retry attempts
        delay_seconds: Initial delay between retries in seconds
        backoff_factor: Multiplier for delay on each retry
        is_retryable: Function to determine if an exception should trigger a retry
        on_retry: Optional callback invoked before each retry with LLMRetryEvent
        provider: Optional provider name for the retry event
        model: Optional model name for the retry event

    Returns:
        Decorated async generator function with retry logic
    """

    def decorator(
        func: Callable[P, AsyncGenerator[T]],
    ) -> Callable[P, AsyncGenerator[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> AsyncGenerator[T]:
            last_exc = None
            for attempt in range(tries):
                generator = func(*args, **kwargs)
                try:
                    first_item = await anext(generator)
                except StopAsyncIteration:
                    return
                except Exception as e:
                    last_exc = e
                    await generator.aclose()
                    if attempt < tries - 1 and is_retryable(e):
                        current_delay = (delay_seconds * (backoff_factor**attempt)) + (
                            0.05 * attempt
                        )
                        if on_retry is not None:
                            on_retry(
                                LLMRetryEvent(
                                    attempt=attempt + 1,
                                    max_attempts=tries,
                                    error_message=str(last_exc),
                                    delay_seconds=current_delay,
                                    provider=provider,
                                    model=model,
                                )
                            )
                        logger.warning(
                            "Retrying %s after error attempt=%d/%d delay=%.2fs error=%r",
                            func.__qualname__,
                            attempt + 1,
                            tries,
                            current_delay,
                            e,
                        )
                        await asyncio.sleep(current_delay)
                        continue
                    raise
                yield first_item
                async for item in generator:
                    yield item
                return
            raise RuntimeError(
                f"Retries exhausted. Last error: {last_exc}"
            ) from last_exc

        return wrapper

    return decorator
