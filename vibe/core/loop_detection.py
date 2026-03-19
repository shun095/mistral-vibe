"""Tool call loop detection module.

This module provides utilities to detect when an LLM backend gets stuck in a loop
by calling the same tool with identical arguments repeatedly across multiple turns.

Key design principle: Loop detection tracks consecutive identical calls ACROSS TURNS,
not within a single turn. Parallel tool calls within a turn are legitimate and should
not trigger loop detection.
"""

from __future__ import annotations

from typing import Any

from vibe.core.config import VibeConfig
from vibe.core.types import ToolCallSignature


def normalize_args(args: dict[str, Any]) -> dict[str, Any]:
    """Normalize arguments for comparison by sorting keys and converting lists to tuples.

    This ensures that arguments with the same content but different key orders
    or list formats are treated as equivalent for loop detection purposes.

    Args:
        args: The arguments dictionary to normalize

    Returns:
        A normalized dictionary with sorted keys and lists converted to tuples
    """
    normalized: dict[str, Any] = {}
    for key in sorted(args.keys()):
        value = args[key]
        if isinstance(value, dict):
            normalized[key] = normalize_args(value)
        elif isinstance(value, list):
            normalized[key] = tuple(
                normalize_args(item) if isinstance(item, dict) else item
                for item in value
            )
        else:
            normalized[key] = value
    return normalized


def create_signature(
    tool_name: str, args: dict[str, Any], call_id: str
) -> ToolCallSignature:
    """Create a ToolCallSignature from tool details.

    Args:
        tool_name: The name of the tool being called
        args: The arguments dictionary passed to the tool
        call_id: The unique identifier for this tool call

    Returns:
        A ToolCallSignature with normalized arguments
    """
    normalized = normalize_args(args)
    return ToolCallSignature(
        tool_name=tool_name, normalized_args=normalized, call_id=call_id
    )


class ToolCallLoopDetector:
    """Detects when an LLM backend gets stuck in a tool call loop across turns.

    The detector tracks the last completed call signature from each turn and
    compares it with the first call of the next turn. This ensures that parallel
    tool calls within a single turn do not trigger false positives.

    Design:
    - At turn start: Compare first call with previous turn's last call
    - Within turn: No tracking (parallel calls are legitimate)
    - At turn end: Store last call signature for next turn comparison
    """

    def __init__(self, threshold: int = 3) -> None:
        """Initialize the detector with an optional threshold.

        Args:
            threshold: Number of consecutive turns with identical tool calls that triggers
                      loop detection. Default is 3.
        """
        self.threshold = threshold
        self._last_turn_signature: ToolCallSignature | None = None
        self._consecutive_turns = 0

    def check_first_call_of_turn(self, signature: ToolCallSignature) -> bool:
        """Check if the first call of a new turn indicates a loop.

        This should be called once per turn, for the first tool call.
        It compares the current call with the last call from the previous turn.

        Args:
            signature: The ToolCallSignature of the first call in this turn

        Returns:
            True if a loop is detected (threshold exceeded), False otherwise
        """
        if self._last_turn_signature == signature:
            self._consecutive_turns += 1
        else:
            self._last_turn_signature = signature
            self._consecutive_turns = 1

        if self._consecutive_turns >= self.threshold:
            return True

        return False

    def record_last_call_of_turn(self, signature: ToolCallSignature) -> None:
        """Record the last call signature of the current turn.

        This should be called once per turn, after all tool calls complete.
        The recorded signature will be compared with the first call of the next turn.

        Args:
            signature: The ToolCallSignature of the last call in this turn
        """
        self._last_turn_signature = signature

    def reset(self) -> None:
        """Reset the detector state.

        This should be called when loop detection needs to be cleared,
        e.g., after a user intervention or configuration change.
        """
        self._last_turn_signature = None
        self._consecutive_turns = 0


class ToolCallLoopHandler:
    """Handles tool call loop detection and error reporting.

    This class encapsulates the loop detection logic and the associated
    error handling, making it reusable across different parts of the codebase.

    Usage pattern:
    1. At turn start: call check_first_call() for the first tool call
    2. At turn end: call record_last_call() with the last tool call signature
    3. If loop detected: handle the error and reset
    """

    def __init__(self, config: VibeConfig) -> None:
        """Initialize the handler with a config.

        Args:
            config: The VibeConfig instance containing loop detection settings
        """
        loop_detection_enabled = config.loop_detection_enabled
        loop_detection_threshold = config.loop_detection_threshold

        if loop_detection_enabled:
            self._detector = ToolCallLoopDetector(threshold=loop_detection_threshold)
        else:
            self._detector = None

    def reset(self) -> None:
        """Reset the loop detector state.

        This should be called when loop detection needs to be cleared.
        """
        if self._detector is not None:
            self._detector.reset()

    def check_first_call(
        self, tool_call: Any, TOOL_ERROR_TAG: str
    ) -> tuple[bool, str | None]:
        """Check if the first call of a turn indicates a loop.

        Args:
            tool_call: The tool call object with tool_name, args_dict, and call_id attributes
            TOOL_ERROR_TAG: The error tag string for formatting error messages

        Returns:
            A tuple of (is_loop_detected, error_message_or_none)
            If a loop is detected, returns (True, error_message).
            If no loop is detected, returns (False, None).
        """
        if self._detector is None:
            return False, None

        signature = ToolCallSignature(
            tool_name=tool_call.tool_name,
            normalized_args=tool_call.args_dict,
            call_id=tool_call.call_id,
        )

        if self._detector.check_first_call_of_turn(signature):
            self._detector.reset()
            error_msg = f"<{TOOL_ERROR_TAG}>Tool '{tool_call.tool_name}' is being called repeatedly with the same arguments. This appears to be an infinite loop. Please try a different approach.</{TOOL_ERROR_TAG}>"
            return True, error_msg

        return False, None

    def record_last_call(self, tool_call: Any) -> None:
        """Record the last call of a turn for future loop detection.

        Args:
            tool_call: The tool call object with tool_name, args_dict, and call_id attributes
        """
        if self._detector is None:
            return

        signature = ToolCallSignature(
            tool_name=tool_call.tool_name,
            normalized_args=tool_call.args_dict,
            call_id=tool_call.call_id,
        )

        self._detector.record_last_call_of_turn(signature)
