"""Tests for LLM error event broadcasting from TUI."""

from __future__ import annotations

from unittest.mock import MagicMock


class TestLLMErrorBroadcasting:
    """Test LLM error broadcasting from TUI."""

    def test_broadcast_llm_error_event_with_rate_limit_error(self) -> None:
        """Test that _broadcast_llm_error_event sends LLMErrorEvent for RateLimitError."""
        from vibe.cli.textual_ui.app import VibeApp
        from vibe.core.types import LLMErrorEvent, RateLimitError

        # Create mock app with proper method delegation
        app = MagicMock(spec=VibeApp)
        app.agent_loop = MagicMock()
        app.agent_loop._notify_event_listeners = MagicMock()
        app._extract_error_provider = lambda e: getattr(e, "provider", None)
        app._extract_error_model = lambda e: getattr(e, "model", None)

        # Create RateLimitError
        error = RateLimitError(provider="mistral", model="mistral-large-latest")

        # Call the method
        VibeApp._broadcast_llm_error_event(app, error)

        # Verify event was sent
        assert app.agent_loop._notify_event_listeners.called
        event = app.agent_loop._notify_event_listeners.call_args[0][0]

        assert isinstance(event, LLMErrorEvent)
        assert "Rate limits exceeded" in event.error_message
        assert event.error_type == "RateLimitError"
        assert event.provider == "mistral"
        assert event.model == "mistral-large-latest"

    def test_broadcast_llm_error_event_with_backend_error(self) -> None:
        """Test that _broadcast_llm_error_event sends LLMErrorEvent for BackendError."""
        from vibe.cli.textual_ui.app import VibeApp
        from vibe.core.llm.exceptions import BackendError
        from vibe.core.types import LLMErrorEvent

        # Create BackendError
        error = BackendError(
            provider="anthropic",
            endpoint="https://api.anthropic.com/v1/messages",
            status=401,
            reason="Unauthorized",
            headers={"x-request-id": "req_123"},
            body_text="Invalid API key",
            parsed_error="Invalid API key",
            model="claude-3-5-sonnet",
            payload_summary=MagicMock(),
        )

        # Create mock app with proper method delegation
        app = MagicMock(spec=VibeApp)
        app.agent_loop = MagicMock()
        app.agent_loop._notify_event_listeners = MagicMock()
        app._extract_error_provider = lambda e: getattr(e, "provider", None)
        app._extract_error_model = lambda e: getattr(e, "model", None)

        # Call the method
        VibeApp._broadcast_llm_error_event(app, error)

        # Verify event was sent
        assert app.agent_loop._notify_event_listeners.called
        event = app.agent_loop._notify_event_listeners.call_args[0][0]

        assert isinstance(event, LLMErrorEvent)
        assert "Invalid API key" in event.error_message
        assert event.error_type == "BackendError"
        assert event.provider == "anthropic"
        assert event.model == "claude-3-5-sonnet"

    def test_broadcast_llm_error_event_with_agent_loop_llm_response_error(self) -> None:
        """Test that _broadcast_llm_error_event sends LLMErrorEvent for AgentLoopLLMResponseError."""
        from vibe.cli.textual_ui.app import VibeApp
        from vibe.core.agent_loop import AgentLoopLLMResponseError
        from vibe.core.types import LLMErrorEvent

        # Create AgentLoopLLMResponseError
        error = AgentLoopLLMResponseError(
            "Usage data missing in non-streaming completion response"
        )

        # Create mock app with proper method delegation
        app = MagicMock(spec=VibeApp)
        app.agent_loop = MagicMock()
        app.agent_loop._notify_event_listeners = MagicMock()
        app._extract_error_provider = lambda e: None
        app._extract_error_model = lambda e: None

        # Call the method
        VibeApp._broadcast_llm_error_event(app, error)

        # Verify event was sent
        assert app.agent_loop._notify_event_listeners.called
        event = app.agent_loop._notify_event_listeners.call_args[0][0]

        assert isinstance(event, LLMErrorEvent)
        assert "Usage data missing" in event.error_message
        assert event.error_type == "AgentLoopLLMResponseError"
        assert event.provider is None
        assert event.model is None

    def test_broadcast_llm_error_event_with_runtime_error(self) -> None:
        """Test that _broadcast_llm_error_event sends LLMErrorEvent for RuntimeError."""
        from vibe.cli.textual_ui.app import VibeApp
        from vibe.core.types import LLMErrorEvent

        # Create RuntimeError with provider/model in message
        error = RuntimeError(
            "API error from openai (model: gpt-4o): Connection timeout"
        )

        # Create mock app with proper method delegation
        app = MagicMock(spec=VibeApp)
        app.agent_loop = MagicMock()
        app.agent_loop._notify_event_listeners = MagicMock()
        app._extract_error_provider = lambda e: "openai"
        app._extract_error_model = lambda e: "gpt-4o"

        # Call the method
        VibeApp._broadcast_llm_error_event(app, error)

        # Verify event was sent
        assert app.agent_loop._notify_event_listeners.called
        event = app.agent_loop._notify_event_listeners.call_args[0][0]

        assert isinstance(event, LLMErrorEvent)
        assert "API error from openai" in event.error_message
        assert event.error_type == "RuntimeError"
        assert event.provider == "openai"
        assert event.model == "gpt-4o"

    def test_broadcast_llm_error_event_with_generic_exception(self) -> None:
        """Test that _broadcast_llm_error_event sends LLMErrorEvent for generic exceptions."""
        from vibe.cli.textual_ui.app import VibeApp
        from vibe.core.types import LLMErrorEvent

        # Create generic exception
        error = ValueError("Something went wrong")

        # Create mock app with proper method delegation
        app = MagicMock(spec=VibeApp)
        app.agent_loop = MagicMock()
        app.agent_loop._notify_event_listeners = MagicMock()
        app._extract_error_provider = lambda e: None
        app._extract_error_model = lambda e: None

        # Call the method
        VibeApp._broadcast_llm_error_event(app, error)

        # Verify event was sent
        assert app.agent_loop._notify_event_listeners.called
        event = app.agent_loop._notify_event_listeners.call_args[0][0]

        assert isinstance(event, LLMErrorEvent)
        assert event.error_message == "Something went wrong"
        assert event.error_type == "ValueError"
        assert event.provider is None
        assert event.model is None

    def test_broadcast_llm_error_event_handles_notification_error(self) -> None:
        """Test that _broadcast_llm_error_event handles errors gracefully."""
        from vibe.cli.textual_ui.app import VibeApp
        from vibe.core.types import RateLimitError

        # Create mock app with failing agent_loop
        app = MagicMock(spec=VibeApp)
        app.agent_loop = MagicMock()
        app.agent_loop._notify_event_listeners.side_effect = Exception(
            "Notification failed"
        )
        app._extract_error_provider = lambda e: "test"
        app._extract_error_model = lambda e: "test-model"

        # Create RateLimitError
        error = RateLimitError(provider="test", model="test-model")

        # Call the method - should not raise
        result = VibeApp._broadcast_llm_error_event(app, error)

        # Should return None (no exception raised)
        assert result is None
        # But should have attempted to notify
        assert app.agent_loop._notify_event_listeners.called


class TestExtractErrorProvider:
    """Test _extract_error_provider helper method."""

    def test_extract_provider_from_rate_limit_error(self) -> None:
        """Test provider extraction from RateLimitError."""
        from vibe.cli.textual_ui.app import VibeApp
        from vibe.core.types import RateLimitError

        app = VibeApp.__new__(VibeApp)  # Create instance without calling __init__
        error = RateLimitError(provider="mistral", model="mistral-large-latest")

        provider = VibeApp._extract_error_provider(app, error)

        assert provider == "mistral"

    def test_extract_provider_from_backend_error(self) -> None:
        """Test provider extraction from BackendError."""
        from vibe.cli.textual_ui.app import VibeApp
        from vibe.core.llm.exceptions import BackendError

        app = VibeApp.__new__(VibeApp)
        error = BackendError(
            provider="anthropic",
            endpoint="https://api.anthropic.com/v1/messages",
            status=401,
            reason="Unauthorized",
            headers={},
            body_text="Invalid API key",
            parsed_error="Invalid API key",
            model="claude-3-5-sonnet",
            payload_summary=MagicMock(),
        )

        provider = VibeApp._extract_error_provider(app, error)

        assert provider == "anthropic"

    def test_extract_provider_from_agent_loop_llm_response_error(self) -> None:
        """Test provider extraction from AgentLoopLLMResponseError returns None."""
        from vibe.cli.textual_ui.app import VibeApp
        from vibe.core.agent_loop import AgentLoopLLMResponseError

        app = VibeApp.__new__(VibeApp)
        error = AgentLoopLLMResponseError("Usage data missing")

        provider = VibeApp._extract_error_provider(app, error)

        assert provider is None

    def test_extract_provider_from_runtime_error(self) -> None:
        """Test provider extraction from RuntimeError."""
        from vibe.cli.textual_ui.app import VibeApp

        app = VibeApp.__new__(VibeApp)
        error = RuntimeError(
            "API error from openai (model: gpt-4o): Connection timeout"
        )

        provider = VibeApp._extract_error_provider(app, error)

        assert provider == "openai"

    def test_extract_provider_from_value_error(self) -> None:
        """Test provider extraction from ValueError returns None."""
        from vibe.cli.textual_ui.app import VibeApp

        app = VibeApp.__new__(VibeApp)
        error = ValueError("Something went wrong")

        provider = VibeApp._extract_error_provider(app, error)

        assert provider is None


class TestExtractErrorModel:
    """Test _extract_error_model helper method."""

    def test_extract_model_from_rate_limit_error(self) -> None:
        """Test model extraction from RateLimitError."""
        from vibe.cli.textual_ui.app import VibeApp
        from vibe.core.types import RateLimitError

        app = VibeApp.__new__(VibeApp)
        error = RateLimitError(provider="mistral", model="mistral-large-latest")

        model = VibeApp._extract_error_model(app, error)

        assert model == "mistral-large-latest"

    def test_extract_model_from_backend_error(self) -> None:
        """Test model extraction from BackendError."""
        from vibe.cli.textual_ui.app import VibeApp
        from vibe.core.llm.exceptions import BackendError

        app = VibeApp.__new__(VibeApp)
        error = BackendError(
            provider="anthropic",
            endpoint="https://api.anthropic.com/v1/messages",
            status=401,
            reason="Unauthorized",
            headers={},
            body_text="Invalid API key",
            parsed_error="Invalid API key",
            model="claude-3-5-sonnet",
            payload_summary=MagicMock(),
        )

        model = VibeApp._extract_error_model(app, error)

        assert model == "claude-3-5-sonnet"

    def test_extract_model_from_agent_loop_llm_response_error(self) -> None:
        """Test model extraction from AgentLoopLLMResponseError returns None."""
        from vibe.cli.textual_ui.app import VibeApp
        from vibe.core.agent_loop import AgentLoopLLMResponseError

        app = VibeApp.__new__(VibeApp)
        error = AgentLoopLLMResponseError("Usage data missing")

        model = VibeApp._extract_error_model(app, error)

        assert model is None

    def test_extract_model_from_runtime_error(self) -> None:
        """Test model extraction from RuntimeError."""
        from vibe.cli.textual_ui.app import VibeApp

        app = VibeApp.__new__(VibeApp)
        error = RuntimeError(
            "API error from openai (model: gpt-4o): Connection timeout"
        )

        model = VibeApp._extract_error_model(app, error)

        assert model == "gpt-4o"

    def test_extract_model_from_value_error(self) -> None:
        """Test model extraction from ValueError returns None."""
        from vibe.cli.textual_ui.app import VibeApp

        app = VibeApp.__new__(VibeApp)
        error = ValueError("Something went wrong")

        model = VibeApp._extract_error_model(app, error)

        assert model is None
