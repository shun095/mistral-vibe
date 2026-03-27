"""Tests for LLM error event broadcasting from TUI."""

from __future__ import annotations

from unittest.mock import MagicMock


class TestLLMErrorBroadcasting:
    """Test LLM error broadcasting from TUI."""

    def test_broadcast_llm_error_event_with_rate_limit_error(self) -> None:
        """Test that _broadcast_llm_error_event sends LLMErrorEvent for RateLimitError."""
        from vibe.cli.textual_ui.web_broadcast_manager import WebBroadcastManager
        from vibe.core.agent_loop import AgentLoop
        from vibe.core.types import LLMErrorEvent, RateLimitError

        # Create mock agent_loop to capture events
        mock_agent_loop = MagicMock(spec=AgentLoop)
        mock_agent_loop._notify_event_listeners = MagicMock()

        # Create manager with real implementation
        manager = WebBroadcastManager(
            agent_loop=mock_agent_loop, config=MagicMock(), notify_callback=None
        )

        # Create RateLimitError
        error = RateLimitError(provider="mistral", model="mistral-large-latest")

        # Call the method directly on manager
        manager._broadcast_llm_error_event(error)

        # Verify event was sent
        assert mock_agent_loop._notify_event_listeners.called
        event = mock_agent_loop._notify_event_listeners.call_args[0][0]

        assert isinstance(event, LLMErrorEvent)
        assert "Rate limits exceeded" in event.error_message
        assert event.error_type == "RateLimitError"
        assert event.provider == "mistral"
        assert event.model == "mistral-large-latest"

    def test_broadcast_llm_error_event_with_backend_error(self) -> None:
        """Test that _broadcast_llm_error_event sends LLMErrorEvent for BackendError."""
        from vibe.cli.textual_ui.web_broadcast_manager import WebBroadcastManager
        from vibe.core.agent_loop import AgentLoop
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

        # Create mock agent_loop to capture events
        mock_agent_loop = MagicMock(spec=AgentLoop)
        mock_agent_loop._notify_event_listeners = MagicMock()

        # Create manager with real implementation
        manager = WebBroadcastManager(
            agent_loop=mock_agent_loop, config=MagicMock(), notify_callback=None
        )

        # Call the method directly on manager
        manager._broadcast_llm_error_event(error)

        # Verify event was sent
        assert mock_agent_loop._notify_event_listeners.called
        event = mock_agent_loop._notify_event_listeners.call_args[0][0]

        assert isinstance(event, LLMErrorEvent)
        assert "Invalid API key" in event.error_message
        assert event.error_type == "BackendError"
        assert event.provider == "anthropic"
        assert event.model == "claude-3-5-sonnet"

    def test_broadcast_llm_error_event_with_agent_loop_llm_response_error(self) -> None:
        """Test that _broadcast_llm_error_event sends LLMErrorEvent for AgentLoopLLMResponseError."""
        from vibe.cli.textual_ui.web_broadcast_manager import WebBroadcastManager
        from vibe.core.agent_loop import AgentLoop, AgentLoopLLMResponseError
        from vibe.core.types import LLMErrorEvent

        # Create AgentLoopLLMResponseError
        error = AgentLoopLLMResponseError(
            "Usage data missing in non-streaming completion response"
        )

        # Create mock agent_loop to capture events
        mock_agent_loop = MagicMock(spec=AgentLoop)
        mock_agent_loop._notify_event_listeners = MagicMock()

        # Create manager with real implementation
        manager = WebBroadcastManager(
            agent_loop=mock_agent_loop, config=MagicMock(), notify_callback=None
        )

        # Call the method directly on manager
        manager._broadcast_llm_error_event(error)

        # Verify event was sent
        assert mock_agent_loop._notify_event_listeners.called
        event = mock_agent_loop._notify_event_listeners.call_args[0][0]

        assert isinstance(event, LLMErrorEvent)
        assert "Usage data missing" in event.error_message
        assert event.error_type == "AgentLoopLLMResponseError"
        assert event.provider is None
        assert event.model is None

    def test_broadcast_llm_error_event_with_runtime_error(self) -> None:
        """Test that _broadcast_llm_error_event sends LLMErrorEvent for RuntimeError."""
        from vibe.cli.textual_ui.web_broadcast_manager import WebBroadcastManager
        from vibe.core.agent_loop import AgentLoop
        from vibe.core.types import LLMErrorEvent

        # Create RuntimeError with provider/model in message
        error = RuntimeError(
            "API error from openai (model: gpt-4o): Connection timeout"
        )

        # Create mock agent_loop to capture events
        mock_agent_loop = MagicMock(spec=AgentLoop)
        mock_agent_loop._notify_event_listeners = MagicMock()

        # Create manager with real implementation
        manager = WebBroadcastManager(
            agent_loop=mock_agent_loop, config=MagicMock(), notify_callback=None
        )

        # Call the method directly on manager
        manager._broadcast_llm_error_event(error)

        # Verify event was sent
        assert mock_agent_loop._notify_event_listeners.called
        event = mock_agent_loop._notify_event_listeners.call_args[0][0]

        assert isinstance(event, LLMErrorEvent)
        assert "API error from openai" in event.error_message
        assert event.error_type == "RuntimeError"
        assert event.provider == "openai"
        assert event.model == "gpt-4o"

    def test_broadcast_llm_error_event_with_generic_exception(self) -> None:
        """Test that _broadcast_llm_error_event sends LLMErrorEvent for generic exceptions."""
        from vibe.cli.textual_ui.web_broadcast_manager import WebBroadcastManager
        from vibe.core.agent_loop import AgentLoop
        from vibe.core.types import LLMErrorEvent

        # Create generic exception
        error = ValueError("Something went wrong")

        # Create mock agent_loop to capture events
        mock_agent_loop = MagicMock(spec=AgentLoop)
        mock_agent_loop._notify_event_listeners = MagicMock()

        # Create manager with real implementation
        manager = WebBroadcastManager(
            agent_loop=mock_agent_loop, config=MagicMock(), notify_callback=None
        )

        # Call the method directly on manager
        manager._broadcast_llm_error_event(error)

        # Verify event was sent
        assert mock_agent_loop._notify_event_listeners.called
        event = mock_agent_loop._notify_event_listeners.call_args[0][0]

        assert isinstance(event, LLMErrorEvent)
        assert event.error_message == "Something went wrong"
        assert event.error_type == "ValueError"
        assert event.provider is None
        assert event.model is None

    def test_broadcast_llm_error_event_handles_notification_error(self) -> None:
        """Test that _broadcast_llm_error_event handles errors gracefully."""
        from vibe.cli.textual_ui.web_broadcast_manager import WebBroadcastManager
        from vibe.core.agent_loop import AgentLoop
        from vibe.core.types import RateLimitError

        # Create mock agent_loop that raises on notification
        mock_agent_loop = MagicMock(spec=AgentLoop)
        mock_agent_loop._notify_event_listeners.side_effect = Exception(
            "Notification failed"
        )

        # Create manager with real implementation
        manager = WebBroadcastManager(
            agent_loop=mock_agent_loop, config=MagicMock(), notify_callback=None
        )

        # Create RateLimitError
        error = RateLimitError(provider="test", model="test-model")

        # Call the method - should not raise
        result = manager._broadcast_llm_error_event(error)

        # Should return None (no exception raised)
        assert result is None
        # Should still have attempted to notify
        assert mock_agent_loop._notify_event_listeners.called
