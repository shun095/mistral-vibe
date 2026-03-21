"""Tests for LLMErrorEvent serialization and handling."""

from __future__ import annotations


def test_serialize_llm_error_event_with_provider_and_model() -> None:
    """Test that LLMErrorEvent with provider and model is properly serialized."""
    from vibe.cli.web_ui.server import serialize_event
    from vibe.core.types import LLMErrorEvent

    event = LLMErrorEvent(
        error_message="Invalid API key. Please check your API key and try again.",
        error_type="BackendError",
        provider="mistral",
        model="mistral-large-latest",
    )

    data = serialize_event(event)

    # Check basic fields
    assert data["__type"] == "LLMErrorEvent"
    assert (
        data["error_message"]
        == "Invalid API key. Please check your API key and try again."
    )
    assert data["error_type"] == "BackendError"
    assert data["provider"] == "mistral"
    assert data["model"] == "mistral-large-latest"


def test_serialize_llm_error_event_without_provider_and_model() -> None:
    """Test that LLMErrorEvent without provider and model is properly serialized."""
    from vibe.cli.web_ui.server import serialize_event
    from vibe.core.types import LLMErrorEvent

    event = LLMErrorEvent(
        error_message="Usage data missing in non-streaming completion response",
        error_type="AgentLoopLLMResponseError",
    )

    data = serialize_event(event)

    # Check basic fields
    assert data["__type"] == "LLMErrorEvent"
    assert (
        data["error_message"]
        == "Usage data missing in non-streaming completion response"
    )
    assert data["error_type"] == "AgentLoopLLMResponseError"

    # Check provider and model are not present (exclude_none=True)
    assert "provider" not in data
    assert "model" not in data


def test_llm_error_event_model_validation() -> None:
    """Test that LLMErrorEvent model validates correctly."""
    from vibe.core.types import LLMErrorEvent

    # Valid event with all fields
    event1 = LLMErrorEvent(
        error_message="Test error",
        error_type="TestError",
        provider="test-provider",
        model="test-model",
    )
    assert event1.error_message == "Test error"
    assert event1.error_type == "TestError"
    assert event1.provider == "test-provider"
    assert event1.model == "test-model"

    # Valid event with only required fields
    event2 = LLMErrorEvent(error_message="Test error", error_type="TestError")
    assert event2.error_message == "Test error"
    assert event2.error_type == "TestError"
    assert event2.provider is None
    assert event2.model is None
