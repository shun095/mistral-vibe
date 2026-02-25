from __future__ import annotations

from typing import Any

import pytest

from pydantic import ValidationError

from vibe.core.loop_detection import ToolCallLoopDetector, create_signature
from vibe.core.types import ToolCallSignature


def test_tool_call_signature_is_frozen() -> None:
    """Test that ToolCallSignature is immutable."""
    sig = ToolCallSignature(
        tool_name="todo",
        normalized_args={"action": "read"},
        call_id="call_1"
    )
    with pytest.raises(ValidationError):
        sig.tool_name = "different"


def test_tool_call_signature_creates_correctly() -> None:
    """Test that ToolCallSignature can be created with correct values."""
    sig = ToolCallSignature(
        tool_name="todo",
        normalized_args={"action": "read"},
        call_id="call_1"
    )
    assert sig.tool_name == "todo"
    assert sig.normalized_args == {"action": "read"}
    assert sig.call_id == "call_1"


def test_tool_call_signature_equality() -> None:
    """Test that two identical signatures are equal."""
    sig1 = ToolCallSignature(
        tool_name="todo",
        normalized_args={"action": "read"},
        call_id="call_1"
    )
    sig2 = ToolCallSignature(
        tool_name="todo",
        normalized_args={"action": "read"},
        call_id="call_1"
    )
    assert sig1 == sig2


def test_tool_call_signature_different_tool_names() -> None:
    """Test that different tool names make signatures different."""
    sig1 = ToolCallSignature(
        tool_name="todo",
        normalized_args={"action": "read"},
        call_id="call_1"
    )
    sig2 = ToolCallSignature(
        tool_name="bash",
        normalized_args={"command": "ls"},
        call_id="call_2"
    )
    assert sig1 != sig2


def test_tool_call_signature_different_args() -> None:
    """Test that different args make signatures different."""
    sig1 = ToolCallSignature(
        tool_name="todo",
        normalized_args={"action": "read"},
        call_id="call_1"
    )
    sig2 = ToolCallSignature(
        tool_name="todo",
        normalized_args={"action": "add"},
        call_id="call_2"
    )
    assert sig1 != sig2


def test_tool_call_signature_different_call_ids() -> None:
    """Test that different call_ids do not affect signature equality.
    
    Since loop detection is based on tool_name + normalized_args only,
    different call_ids should result in equal signatures.
    """
    sig1 = ToolCallSignature(
        tool_name="todo",
        normalized_args={"action": "read"},
        call_id="call_1"
    )
    sig2 = ToolCallSignature(
        tool_name="todo",
        normalized_args={"action": "read"},
        call_id="call_2"
    )
    assert sig1 == sig2


# ============ normalize_args tests ============


def normalize_args(args: dict[str, Any]) -> dict[str, Any]:
    """Normalize arguments for comparison by sorting keys and converting lists to tuples."""
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


def test_normalize_args_simple_dict() -> None:
    """Test normalize_args with a simple dictionary."""
    args = {"b": 1, "a": 2}
    result = normalize_args(args)
    assert result == {"a": 2, "b": 1}


def test_normalize_args_nested_dict() -> None:
    """Test normalize_args with nested dictionaries."""
    args = {"z": {"b": 1, "a": 2}, "a": 3}
    result = normalize_args(args)
    assert result == {"a": 3, "z": {"a": 2, "b": 1}}


def test_normalize_args_with_list() -> None:
    """Test normalize_args with lists containing dicts."""
    args = {"items": [{"b": 1, "a": 2}]}
    result = normalize_args(args)
    # Dicts inside lists are normalized but remain as dicts, lists become tuples
    assert result == {"items": ({"a": 2, "b": 1},)}


def test_normalize_args_primitives() -> None:
    """Test normalize_args with primitive values."""
    args = {"str": "hello", "int": 42, "float": 3.14, "bool": True}
    result = normalize_args(args)
    assert result == {"bool": True, "float": 3.14, "int": 42, "str": "hello"}


def test_normalize_args_empty_dict() -> None:
    """Test normalize_args with empty dictionary."""
    args: dict[str, Any] = {}
    result = normalize_args(args)
    assert result == {}


def test_normalize_args_complex_nested() -> None:
    """Test normalize_args with complex nested structure."""
    args = {
        "z": [
            {"c": 3, "a": 1},
            {"b": 2}
        ],
        "a": 4,
        "m": {"nested": {"z": "last", "a": "first"}}
    }
    result = normalize_args(args)
    # Dicts inside lists remain as dicts, keys are sorted within each dict
    assert result == {
        "a": 4,
        "m": {"nested": {"a": "first", "z": "last"}},
        "z": ({"a": 1, "c": 3}, {"b": 2})
    }


# ============ ToolCallLoopDetector tests ============


def test_detector_initializes_with_default_threshold() -> None:
    """Test that ToolCallLoopDetector initializes with default threshold of 3."""
    detector = ToolCallLoopDetector()
    assert detector.threshold == 3


def test_detector_initializes_with_custom_threshold() -> None:
    """Test that ToolCallLoopDetector can be initialized with custom threshold."""
    detector = ToolCallLoopDetector(threshold=5)
    assert detector.threshold == 5


def test_detector_detects_loop_when_threshold_exceeded() -> None:
    """Test that detector detects a loop when threshold is exceeded."""
    detector = ToolCallLoopDetector(threshold=3)
    
    sig = ToolCallSignature(
        tool_name="todo",
        normalized_args={"action": "read"},
        call_id="call_1"
    )
    
    # First call - no loop
    assert not detector.detect_loop(sig)
    # Second call - still no loop (2 consecutive, threshold is 3)
    assert not detector.detect_loop(sig)
    # Third call - loop detected (3 consecutive equals threshold)
    assert detector.detect_loop(sig)


def test_detector_resets_on_different_signature() -> None:
    """Test that detector resets when a different signature is detected."""
    detector = ToolCallLoopDetector(threshold=3)
    
    sig1 = ToolCallSignature(
        tool_name="todo",
        normalized_args={"action": "read"},
        call_id="call_1"
    )
    sig2 = ToolCallSignature(
        tool_name="todo",
        normalized_args={"action": "add"},
        call_id="call_2"
    )
    
    # 2 consecutive calls to sig1
    detector.detect_loop(sig1)
    detector.detect_loop(sig1)
    
    # Different signature - resets counter
    detector.detect_loop(sig2)
    
    # Back to sig1 - counter starts fresh
    assert not detector.detect_loop(sig1)
    assert not detector.detect_loop(sig1)
    assert detector.detect_loop(sig1)


def test_detector_with_threshold_2() -> None:
    """Test detector with threshold of 2."""
    detector = ToolCallLoopDetector(threshold=2)
    
    sig = ToolCallSignature(
        tool_name="todo",
        normalized_args={"action": "read"},
        call_id="call_1"
    )
    
    assert not detector.detect_loop(sig)
    assert detector.detect_loop(sig)


def test_detector_with_threshold_1() -> None:
    """Test detector with threshold of 1 (detect on first occurrence)."""
    detector = ToolCallLoopDetector(threshold=1)
    
    sig = ToolCallSignature(
        tool_name="todo",
        normalized_args={"action": "read"},
        call_id="call_1"
    )
    
    # With threshold=1, any repeated call is detected
    assert not detector.detect_loop(sig)
    assert detector.detect_loop(sig)


def test_detector_handles_normalized_args_correctly() -> None:
    """Test that detector correctly handles normalized arguments."""
    detector = ToolCallLoopDetector(threshold=2)
    
    # Create signatures with same content but different key orders
    sig1 = ToolCallSignature(
        tool_name="todo",
        normalized_args={"b": 1, "a": 2},
        call_id="call_1"
    )
    sig2 = ToolCallSignature(
        tool_name="todo",
        normalized_args={"a": 2, "b": 1},
        call_id="call_2"
    )
    
    # These should be treated as the same signature after normalization
    # First call to sig1 (or sig2) - no loop
    assert not detector.detect_loop(sig1)
    # Second call to sig2 (same normalized content) - loop detected
    assert detector.detect_loop(sig2)  # Same normalized content


def test_detector_multiple_different_signatures() -> None:
    """Test detector with multiple different signatures."""
    detector = ToolCallLoopDetector(threshold=3)
    
    sig1 = ToolCallSignature(
        tool_name="todo",
        normalized_args={"action": "read"},
        call_id="call_1"
    )
    sig2 = ToolCallSignature(
        tool_name="todo",
        normalized_args={"action": "add"},
        call_id="call_2"
    )
    sig3 = ToolCallSignature(
        tool_name="bash",
        normalized_args={"command": "ls"},
        call_id="call_3"
    )
    
    # Call sig1 twice - no loop yet
    detector.detect_loop(sig1)
    detector.detect_loop(sig1)
    
    # Switch to different signature - resets counter
    detector.detect_loop(sig2)
    
    # Call sig2 once more - still no loop (2 consecutive)
    assert not detector.detect_loop(sig2)
    
    # Switch to sig3 - resets counter
    detector.detect_loop(sig3)
    
    # Call sig3 once more - still no loop (2 consecutive)
    assert not detector.detect_loop(sig3)
    
    # After switching back to sig1, it takes 3 calls to trigger loop
    detector.detect_loop(sig1)
    assert not detector.detect_loop(sig1)
    assert detector.detect_loop(sig1)


# ============ Integration tests (with agent_loop) ============


def test_create_signature_function() -> None:
    """Test create_signature helper function."""
    sig = create_signature(
        tool_name="bash",
        args={"command": "ls -la"},
        call_id="call_123"
    )
    
    assert sig.tool_name == "bash"
    assert sig.normalized_args == {"command": "ls -la"}
    assert sig.call_id == "call_123"


def test_create_signature_with_nested_args() -> None:
    """Test create_signature with nested arguments."""
    sig = create_signature(
        tool_name="bash",
        args={"options": {"recursive": True, "human": True}, "command": "ls"},
        call_id="call_456"
    )
    
    assert sig.tool_name == "bash"
    assert sig.normalized_args == {
        "command": "ls",
        "options": {"human": True, "recursive": True}
    }