from __future__ import annotations

from typing import Any

from pydantic import ValidationError
import pytest

from vibe.core.loop_detection import ToolCallLoopDetector, create_signature
from vibe.core.types import ToolCallSignature


def test_tool_call_signature_is_frozen() -> None:
    """Test that ToolCallSignature is immutable."""
    sig = ToolCallSignature(
        tool_name="todo", normalized_args={"action": "read"}, call_id="call_1"
    )
    with pytest.raises(ValidationError):
        sig.tool_name = "different"


def test_tool_call_signature_creates_correctly() -> None:
    """Test that ToolCallSignature can be created with correct values."""
    sig = ToolCallSignature(
        tool_name="todo", normalized_args={"action": "read"}, call_id="call_1"
    )
    assert sig.tool_name == "todo"
    assert sig.normalized_args == {"action": "read"}
    assert sig.call_id == "call_1"


def test_tool_call_signature_equality() -> None:
    """Test that two identical signatures are equal."""
    sig1 = ToolCallSignature(
        tool_name="todo", normalized_args={"action": "read"}, call_id="call_1"
    )
    sig2 = ToolCallSignature(
        tool_name="todo", normalized_args={"action": "read"}, call_id="call_1"
    )
    assert sig1 == sig2


def test_tool_call_signature_different_tool_names() -> None:
    """Test that different tool names make signatures different."""
    sig1 = ToolCallSignature(
        tool_name="todo", normalized_args={"action": "read"}, call_id="call_1"
    )
    sig2 = ToolCallSignature(
        tool_name="bash", normalized_args={"command": "ls"}, call_id="call_2"
    )
    assert sig1 != sig2


def test_tool_call_signature_different_args() -> None:
    """Test that different args make signatures different."""
    sig1 = ToolCallSignature(
        tool_name="todo", normalized_args={"action": "read"}, call_id="call_1"
    )
    sig2 = ToolCallSignature(
        tool_name="todo", normalized_args={"action": "add"}, call_id="call_2"
    )
    assert sig1 != sig2


def test_tool_call_signature_different_call_ids() -> None:
    """Test that different call_ids do not affect signature equality.

    Since loop detection is based on tool_name + normalized_args only,
    different call_ids should result in equal signatures.
    """
    sig1 = ToolCallSignature(
        tool_name="todo", normalized_args={"action": "read"}, call_id="call_1"
    )
    sig2 = ToolCallSignature(
        tool_name="todo", normalized_args={"action": "read"}, call_id="call_2"
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
            normalized[key] = tuple(
                normalize_args(item) if isinstance(item, dict) else item
                for item in value
            )
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
        "z": [{"c": 3, "a": 1}, {"b": 2}],
        "a": 4,
        "m": {"nested": {"z": "last", "a": "first"}},
    }
    result = normalize_args(args)
    # Dicts inside lists remain as dicts, keys are sorted within each dict
    assert result == {
        "a": 4,
        "m": {"nested": {"a": "first", "z": "last"}},
        "z": ({"a": 1, "c": 3}, {"b": 2}),
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
    """Test that detector detects a loop when threshold is exceeded across turns.

    The detector tracks consecutive turns with identical tool calls.
    """
    detector = ToolCallLoopDetector(threshold=3)

    sig = ToolCallSignature(
        tool_name="todo", normalized_args={"action": "read"}, call_id="call_1"
    )

    # Turn 1: First call - no loop
    assert not detector.check_first_call_of_turn(sig)
    detector.record_last_call_of_turn(sig)

    # Turn 2: First call - still no loop (2 consecutive turns, threshold is 3)
    assert not detector.check_first_call_of_turn(sig)
    detector.record_last_call_of_turn(sig)

    # Turn 3: First call - loop detected (3 consecutive turns equals threshold)
    assert detector.check_first_call_of_turn(sig)


def test_detector_resets_on_different_signature() -> None:
    """Test that detector resets when a different signature is detected across turns."""
    detector = ToolCallLoopDetector(threshold=3)

    sig1 = ToolCallSignature(
        tool_name="todo", normalized_args={"action": "read"}, call_id="call_1"
    )
    sig2 = ToolCallSignature(
        tool_name="todo", normalized_args={"action": "add"}, call_id="call_2"
    )

    # Turn 1: sig1
    detector.check_first_call_of_turn(sig1)
    detector.record_last_call_of_turn(sig1)

    # Turn 2: sig1 again
    detector.check_first_call_of_turn(sig1)
    detector.record_last_call_of_turn(sig1)

    # Turn 3: Different signature - resets counter
    detector.check_first_call_of_turn(sig2)
    detector.record_last_call_of_turn(sig2)

    # Turn 4: Back to sig1 - counter starts fresh
    assert not detector.check_first_call_of_turn(sig1)
    detector.record_last_call_of_turn(sig1)

    # Turn 5: sig1 again
    assert not detector.check_first_call_of_turn(sig1)
    detector.record_last_call_of_turn(sig1)

    # Turn 6: sig1 again - loop detected
    assert detector.check_first_call_of_turn(sig1)


def test_detector_with_threshold_2() -> None:
    """Test detector with threshold of 2 (loop detected after 2 consecutive turns)."""
    detector = ToolCallLoopDetector(threshold=2)

    sig = ToolCallSignature(
        tool_name="todo", normalized_args={"action": "read"}, call_id="call_1"
    )

    # Turn 1: no loop
    assert not detector.check_first_call_of_turn(sig)
    detector.record_last_call_of_turn(sig)

    # Turn 2: loop detected (2 consecutive turns equals threshold)
    assert detector.check_first_call_of_turn(sig)


def test_detector_with_threshold_1() -> None:
    """Test detector with threshold of 1 (loop detected on first turn)."""
    detector = ToolCallLoopDetector(threshold=1)

    sig = ToolCallSignature(
        tool_name="todo", normalized_args={"action": "read"}, call_id="call_1"
    )

    # With threshold=1, even the first call is detected as a loop
    assert detector.check_first_call_of_turn(sig)


def test_detector_handles_normalized_args_correctly() -> None:
    """Test that detector correctly handles normalized arguments across turns."""
    detector = ToolCallLoopDetector(threshold=2)

    # Create signatures with same content but different key orders
    sig1 = ToolCallSignature(
        tool_name="todo", normalized_args={"b": 1, "a": 2}, call_id="call_1"
    )
    sig2 = ToolCallSignature(
        tool_name="todo", normalized_args={"a": 2, "b": 1}, call_id="call_2"
    )

    # These should be treated as the same signature after normalization
    # Turn 1: sig1 - no loop
    assert not detector.check_first_call_of_turn(sig1)
    detector.record_last_call_of_turn(sig1)

    # Turn 2: sig2 (same normalized content) - loop detected
    assert detector.check_first_call_of_turn(sig2)  # Same normalized content


def test_detector_multiple_different_signatures() -> None:
    """Test detector with multiple different signatures across turns."""
    detector = ToolCallLoopDetector(threshold=3)

    sig1 = ToolCallSignature(
        tool_name="todo", normalized_args={"action": "read"}, call_id="call_1"
    )
    sig2 = ToolCallSignature(
        tool_name="todo", normalized_args={"action": "add"}, call_id="call_2"
    )
    sig3 = ToolCallSignature(
        tool_name="bash", normalized_args={"command": "ls"}, call_id="call_3"
    )

    # Turn 1: sig1
    detector.check_first_call_of_turn(sig1)
    detector.record_last_call_of_turn(sig1)

    # Turn 2: sig1 again
    detector.check_first_call_of_turn(sig1)
    detector.record_last_call_of_turn(sig1)

    # Turn 3: Switch to different signature - resets counter
    detector.check_first_call_of_turn(sig2)
    detector.record_last_call_of_turn(sig2)

    # Turn 4: sig2 again - still no loop (2 consecutive)
    assert not detector.check_first_call_of_turn(sig2)
    detector.record_last_call_of_turn(sig2)

    # Turn 5: Switch to sig3 - resets counter
    detector.check_first_call_of_turn(sig3)
    detector.record_last_call_of_turn(sig3)

    # Turn 6: sig3 again - still no loop (2 consecutive)
    assert not detector.check_first_call_of_turn(sig3)
    detector.record_last_call_of_turn(sig3)

    # Turn 7: After switching back to sig1, counter starts fresh
    detector.check_first_call_of_turn(sig1)
    detector.record_last_call_of_turn(sig1)

    # Turn 8: sig1 again - still no loop (2 consecutive)
    assert not detector.check_first_call_of_turn(sig1)
    detector.record_last_call_of_turn(sig1)

    # Turn 9: sig1 again - loop detected (3 consecutive)
    assert detector.check_first_call_of_turn(sig1)


# ============ Integration tests (with agent_loop) ============


def test_create_signature_function() -> None:
    """Test create_signature helper function."""
    sig = create_signature(
        tool_name="bash", args={"command": "ls -la"}, call_id="call_123"
    )

    assert sig.tool_name == "bash"
    assert sig.normalized_args == {"command": "ls -la"}
    assert sig.call_id == "call_123"


def test_create_signature_with_nested_args() -> None:
    """Test create_signature with nested arguments."""
    sig = create_signature(
        tool_name="bash",
        args={"options": {"recursive": True, "human": True}, "command": "ls"},
        call_id="call_456",
    )

    assert sig.tool_name == "bash"
    assert sig.normalized_args == {
        "command": "ls",
        "options": {"human": True, "recursive": True},
    }
