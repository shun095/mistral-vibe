from __future__ import annotations

from datetime import UTC, datetime
import time

_SECONDS_IN_MINUTE = 60


def utc_now() -> datetime:
    return datetime.now(UTC)


def monotonic_now() -> float:
    """Return the current monotonic clock time.

    Wrapper around ``time.monotonic()`` to allow mocking in tests
    for deterministic snapshot comparisons.
    """
    return time.monotonic()


def format_duration(seconds: float) -> str:
    """Format elapsed seconds into a human-readable string.

    Args:
        seconds: Elapsed time in seconds (non-negative).

    Returns:
        Formatted string: "0.5s", "2.3s", "1m 0.0s", "1m 23.4s".
    """
    if seconds < _SECONDS_IN_MINUTE:
        return f"{seconds:.1f}s"
    minutes = int(seconds // _SECONDS_IN_MINUTE)
    remaining = seconds % _SECONDS_IN_MINUTE
    return f"{minutes}m {remaining:.1f}s"
