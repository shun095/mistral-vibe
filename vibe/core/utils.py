from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable, Coroutine
import concurrent.futures
from datetime import UTC, datetime
from enum import Enum, auto
from fnmatch import fnmatch
import functools
from pathlib import Path
import re
import sys
from typing import Any

import httpx

from vibe import __version__
from vibe.core.config import Backend
from vibe.core.types import BaseEvent, LLMRetryEvent, ToolResultEvent

CANCELLATION_TAG = "user_cancellation"
TOOL_ERROR_TAG = "tool_error"
VIBE_STOP_EVENT_TAG = "vibe_stop_event"
VIBE_WARNING_TAG = "vibe_warning"

KNOWN_TAGS = [CANCELLATION_TAG, TOOL_ERROR_TAG, VIBE_STOP_EVENT_TAG, VIBE_WARNING_TAG]


class TaggedText:
    _TAG_PATTERN = re.compile(
        rf"<({'|'.join(re.escape(tag) for tag in KNOWN_TAGS)})>(.*?)</\1>",
        flags=re.DOTALL,
    )

    def __init__(self, message: str, tag: str = "") -> None:
        self.message = message
        self.tag = tag

    def __str__(self) -> str:
        if not self.tag:
            return self.message
        return f"<{self.tag}>{self.message}</{self.tag}>"

    @staticmethod
    def from_string(text: str) -> TaggedText:
        found_tag = ""
        result = text

        def replace_tag(match: re.Match[str]) -> str:
            nonlocal found_tag
            tag_name = match.group(1)
            content = match.group(2)
            if not found_tag:
                found_tag = tag_name
            return content

        result = TaggedText._TAG_PATTERN.sub(replace_tag, text)

        if found_tag:
            return TaggedText(result, found_tag)

        return TaggedText(text, "")


class CancellationReason(Enum):
    OPERATION_CANCELLED = auto()
    TOOL_INTERRUPTED = auto()
    TOOL_NO_RESPONSE = auto()
    TOOL_SKIPPED = auto()


def get_user_cancellation_message(
    cancellation_reason: CancellationReason, tool_name: str | None = None
) -> TaggedText:
    match cancellation_reason:
        case CancellationReason.OPERATION_CANCELLED:
            return TaggedText("User cancelled the operation.", CANCELLATION_TAG)
        case CancellationReason.TOOL_INTERRUPTED:
            return TaggedText("Tool execution interrupted by user.", CANCELLATION_TAG)
        case CancellationReason.TOOL_NO_RESPONSE:
            return TaggedText(
                "Tool execution interrupted - no response available", CANCELLATION_TAG
            )
        case CancellationReason.TOOL_SKIPPED:
            return TaggedText(
                tool_name or "Tool execution skipped by user.", CANCELLATION_TAG
            )


def is_user_cancellation_event(event: BaseEvent) -> bool:
    if not isinstance(event, ToolResultEvent):
        return False
    return event.cancelled


def is_dangerous_directory(path: Path | str = ".") -> tuple[bool, str]:
    """Check if the current directory is a dangerous folder that would cause
    issues if we were to run the tool there.

    Args:
        path: Path to check (defaults to current directory)

    Returns:
        tuple[bool, str]: (is_dangerous, reason) where reason explains why it's dangerous
    """
    path = Path(path).resolve()

    home_dir = Path.home()

    dangerous_paths = {
        home_dir: "home directory",
        home_dir / "Documents": "Documents folder",
        home_dir / "Desktop": "Desktop folder",
        home_dir / "Downloads": "Downloads folder",
        home_dir / "Pictures": "Pictures folder",
        home_dir / "Movies": "Movies folder",
        home_dir / "Music": "Music folder",
        home_dir / "Library": "Library folder",
        Path("/Applications"): "Applications folder",
        Path("/System"): "System folder",
        Path("/Library"): "System Library folder",
        Path("/usr"): "System usr folder",
        Path("/private"): "System private folder",
    }

    for dangerous_path, description in dangerous_paths.items():
        try:
            if path == dangerous_path:
                return True, f"You are in the {description}"
        except (OSError, ValueError):
            continue
    return False, ""


def get_user_agent(backend: Backend | None) -> str:
    user_agent = f"Mistral-Vibe/{__version__}"
    if backend == Backend.MISTRAL:
        mistral_sdk_prefix = "mistral-client-python/"
        user_agent = f"{mistral_sdk_prefix}{user_agent}"
    return user_agent


def _is_retryable_backend_error(e: Exception) -> bool:  # noqa: PLR0911
    """Check if an exception is retryable for LLM backend operations.

    Handles both HTTP status errors and network/transport errors.
    """
    # HTTP status code errors (retry on server errors and rate limits)
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code in {408, 409, 425, 429, 500, 502, 503, 504}

    # Network/transport errors (retry on transient network issues)
    if isinstance(e, httpx.RequestError):
        error_str = str(e).lower()
        if "readtimeout" in error_str:
            return True
        # Incomplete chunked read (the specific error we need to fix)
        if "server disconnected without sending a response" in error_str:
            return True
        # Incomplete chunked read (the specific error we need to fix)
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
            tries = config.get("tries", 3)
            delay_seconds = config.get("delay_seconds", 0.5)
            backoff_factor = config.get("backoff_factor", 2.0)
            is_retryable = config.get("is_retryable", _is_retryable_backend_error)

            last_exc: Exception | None = None
            for attempt in range(tries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    # Don't retry on last attempt or if error is not retryable
                    if attempt >= tries - 1 or not is_retryable(e):
                        break

                    current_delay = (delay_seconds * (backoff_factor**attempt)) + (
                        0.05 * attempt
                    )
                    on_retry = config.get("on_retry")
                    if on_retry is not None:
                        retry_event = LLMRetryEvent(
                            attempt=attempt + 1,
                            max_attempts=tries,
                            error_message=str(e),
                            delay_seconds=current_delay,
                            provider=config.get("provider"),
                            model=config.get("model"),
                        )
                        on_retry(retry_event)
                    await asyncio.sleep(current_delay)

            # Re-raise the original error to preserve error type
            if last_exc is not None:
                raise last_exc
            raise RuntimeError("Unreachable")

        return wrapper

    return decorator


def apply_retry_decorator(
    obj: Any, method_name: str, config: dict[str, Any], is_streaming: bool = False
) -> None:
    """Apply retry decorator to a method dynamically.

    Args:
        obj: Object instance containing the method to decorate.
        method_name: Name of the method to apply retry logic to.
        config: Retry configuration dict.
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
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> AsyncGenerator[T]:  # type: ignore[misc]
            tries = config.get("tries", 3)
            delay_seconds = config.get("delay_seconds", 0.5)
            backoff_factor = config.get("backoff_factor", 2.0)
            is_retryable = config.get("is_retryable", _is_retryable_backend_error)

            from vibe.core.logger import logger

            last_exc: Exception | None = None
            for attempt in range(tries):
                try:
                    async for item in func(*args, **kwargs):
                        yield item
                    return
                except Exception as e:
                    logger.debug(f"Retrying... Attempt: {attempt}")
                    last_exc = e
                    # Don't retry on last attempt or if error is not retryable
                    if attempt >= tries - 1 or not is_retryable(e):
                        break

                    current_delay = (delay_seconds * (backoff_factor**attempt)) + (
                        0.05 * attempt
                    )
                    on_retry = config.get("on_retry")
                    if on_retry is not None:
                        retry_event = LLMRetryEvent(
                            attempt=attempt + 1,
                            max_attempts=tries,
                            error_message=str(e),
                            delay_seconds=current_delay,
                            provider=config.get("provider"),
                            model=config.get("model"),
                        )
                        on_retry(retry_event)  # Call callback to broadcast event
                    await asyncio.sleep(current_delay)

            # Re-raise the original error to preserve error type
            if last_exc is not None:
                raise last_exc
            raise RuntimeError("Unreachable")

        return wrapper

    return decorator


class ConversationLimitException(Exception):
    pass


def run_sync[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine synchronously, handling nested event loops.

    If called from within an async context (running event loop), runs the
    coroutine in a thread pool executor. Otherwise, uses asyncio.run().

    This mirrors the pattern used by ToolManager for MCP integration.
    """
    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    except RuntimeError:
        return asyncio.run(coro)


def is_windows() -> bool:
    return sys.platform == "win32"


@functools.lru_cache(maxsize=256)
def _compile_icase(expr: str) -> re.Pattern[str] | None:
    try:
        return re.compile(expr, re.IGNORECASE)
    except re.error:
        return None


def name_matches(name: str, patterns: list[str]) -> bool:
    """Check if a name matches any of the provided patterns.

    Supports two forms (case-insensitive):
    - Glob wildcards using fnmatch (e.g., 'serena_*')
    - Regex when prefixed with 're:' (e.g., 're:serena.*')
    """
    n = name.lower()
    for raw in patterns:
        if not (p := (raw or "").strip()):
            continue

        if p.startswith("re:"):
            rx = _compile_icase(p.removeprefix("re:"))
            if rx is not None and rx.fullmatch(name) is not None:
                return True
        elif fnmatch(n, p.lower()):
            return True

    return False


class AsyncExecutor:
    """Run sync functions in a thread pool with timeout. Supports async context manager."""

    def __init__(
        self, max_workers: int = 4, timeout: float = 60.0, name: str = "async-executor"
    ) -> None:
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix=name
        )
        self._timeout = timeout

    async def __aenter__(self) -> AsyncExecutor:
        return self

    async def __aexit__(self, *_: object) -> None:
        self.shutdown(wait=False)

    async def run[T](self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(
            self._executor, functools.partial(fn, *args, **kwargs)
        )
        try:
            return await asyncio.wait_for(future, timeout=self._timeout)
        except TimeoutError as e:
            raise TimeoutError(f"Operation timed out after {self._timeout}s") from e

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait)


def compact_reduction_display(old_tokens: int | None, new_tokens: int | None) -> str:
    if old_tokens is None or new_tokens is None:
        return "Compaction complete"

    reduction = old_tokens - new_tokens
    reduction_pct = (reduction / old_tokens * 100) if old_tokens > 0 else 0
    return (
        f"Compaction complete: {old_tokens:,} → "
        f"{new_tokens:,} tokens ({-reduction_pct:+#0.2g}%)"
    )


def get_server_url_from_api_base(api_base: str) -> str | None:
    match = re.match(r"(https?://[^/]+)(/v.*)", api_base)
    return match.group(1) if match else None


def utc_now() -> datetime:
    return datetime.now(UTC)
