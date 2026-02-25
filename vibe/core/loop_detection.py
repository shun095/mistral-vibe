"""Tool call loop detection module.

This module provides utilities to detect when an LLM backend gets stuck in a loop
by calling the same tool with identical arguments repeatedly.
"""

from __future__ import annotations

from typing import Any

from vibe.core.config import VibeConfig
from vibe.core.types import ToolCallSignature, ToolResultEvent


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
            normalized[key] = tuple(normalize_args(item) if isinstance(item, dict) else item for item in value)
        else:
            normalized[key] = value
    return normalized


def create_signature(tool_name: str, args: dict[str, Any], call_id: str) -> ToolCallSignature:
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
        tool_name=tool_name,
        normalized_args=normalized,
        call_id=call_id
    )


class ToolCallLoopDetector:
    """Detects when an LLM backend gets stuck in a tool call loop.
    
    The detector tracks consecutive tool calls with identical signatures
    and flags when the threshold is exceeded.
    """
    
    def __init__(self, threshold: int = 3) -> None:
        """Initialize the detector with an optional threshold.
        
        Args:
            threshold: Number of consecutive identical tool calls that triggers
                      loop detection. Default is 3.
        """
        self.threshold = threshold
        self._last_signature: ToolCallSignature | None = None
        self._consecutive_count = 0
    
    def detect_loop(self, signature: ToolCallSignature) -> bool:
        """Detect if a loop is occurring based on the signature.
        
        Args:
            signature: The ToolCallSignature to check
            
        Returns:
            True if a loop is detected (threshold exceeded), False otherwise
        """
        if self._last_signature == signature:
            self._consecutive_count += 1
            if self._consecutive_count >= self.threshold:
                return True
        else:
            self._last_signature = signature
            self._consecutive_count = 1
        
        return False
    
    def reset(self) -> None:
        """Reset the detector state."""
        self._last_signature = None
        self._consecutive_count = 0


class ToolCallLoopHandler:
    """Handles tool call loop detection and error reporting.
    
    This class encapsulates the loop detection logic and the associated
    error handling, making it reusable across different parts of the codebase.
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
    
    def check_and_handle_loop(
        self,
        tool_call: Any,
        TOOL_ERROR_TAG: str,
    ) -> tuple[bool, str | None]:
        """Check if a tool call loop is detected and handle it.
        
        Args:
            tool_call: The tool call object with tool_name, args_dict, and call_id attributes
            TOOL_ERROR_TAG: The error tag string for formatting error messages
            
        Returns:
            A tuple of (is_loop_detected, error_message_or_none)
            If a loop is detected, returns (True, error_message) and resets the detector.
            If no loop is detected, returns (False, None).
        """
        if self._detector is None:
            return False, None
        
        signature = ToolCallSignature(
            tool_name=tool_call.tool_name,
            normalized_args=tool_call.args_dict,
            call_id=tool_call.call_id
        )
        
        if self._detector.detect_loop(signature):
            self._detector.reset()
            error_msg = f"<{TOOL_ERROR_TAG}>Tool '{tool_call.tool_name}' is being called repeatedly with the same arguments. This appears to be an infinite loop. Please try a different approach.</{TOOL_ERROR_TAG}>"
            return True, error_msg
        
        return False, None
    
    def check_and_handle_loop_for_agent_loop(
        self,
        tool_call: Any,
        TOOL_ERROR_TAG: str,
        tool_class: Any,
        tool_call_id: str,
        handle_tool_response: Any,
    ) -> tuple[bool, Any]:
        """Check if a tool call loop is detected and handle it for AgentLoop.
        
        This method fully encapsulates the loop handling logic so AgentLoop
        only needs to check the return value.
        
        Args:
            tool_call: The tool call object with tool_name, args_dict, and call_id attributes
            TOOL_ERROR_TAG: The error tag string for formatting error messages
            tool_class: The tool class for the event
            tool_call_id: The tool call ID for the event
            handle_tool_response: The handle_tool_response method from AgentLoop
            
        Returns:
            A tuple of (is_loop_detected, event_or_none)
            If a loop is detected, returns (True, event_to_yield) and handles response.
            If no loop is detected, returns (False, None).
        """
        if self._detector is None:
            return False, None
        
        signature = ToolCallSignature(
            tool_name=tool_call.tool_name,
            normalized_args=tool_call.args_dict,
            call_id=tool_call.call_id
        )
        
        if self._detector.detect_loop(signature):
            self._detector.reset()
            error_msg = f"<{TOOL_ERROR_TAG}>Tool '{tool_call.tool_name}' is being called repeatedly with the same arguments. This appears to be an infinite loop. Please try a different approach.</{TOOL_ERROR_TAG}>"
            event = ToolResultEvent(
                tool_name=tool_call.tool_name,
                tool_class=tool_class,
                error=error_msg,
                tool_call_id=tool_call_id,
            )
            handle_tool_response(tool_call, error_msg, "failure")
            return True, event
        
        return False, None