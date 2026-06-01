from __future__ import annotations

"""Tests for AgentLoop resume system prompt behavior."""

from unittest.mock import patch

import pytest

from tests.conftest import build_test_agent_loop


class TestResumeSystemPrompt:
    """Test that _resume_system_prompt prevents system prompt recalculation."""

    def test_resume_system_prompt_skips_get_universal_in_complete_init(self) -> None:
        agent_loop = build_test_agent_loop()
        agent_loop._resume_system_prompt = "saved prompt"

        with patch("vibe.core.agent_loop.get_universal_system_prompt") as mock_get:
            agent_loop._complete_init()
            mock_get.assert_not_called()

        assert agent_loop.messages[0].content == "saved prompt"

    def test_complete_init_calls_get_universal_without_resume_prompt(self) -> None:
        agent_loop = build_test_agent_loop()
        assert agent_loop._resume_system_prompt is None

        with patch(
            "vibe.core.agent_loop.get_universal_system_prompt",
            return_value="calculated prompt",
        ) as mock_get:
            agent_loop._complete_init()
            mock_get.assert_called_once()

        assert agent_loop.messages[0].content == "calculated prompt"

    @pytest.mark.asyncio
    async def test_reload_with_initial_messages_uses_resume_prompt(self) -> None:
        from vibe.core.config import VibeConfig

        agent_loop = build_test_agent_loop()
        agent_loop._resume_system_prompt = "saved prompt"

        with patch("vibe.core.agent_loop.get_universal_system_prompt") as mock_get:
            with patch.object(VibeConfig, "load", return_value=agent_loop.config):
                await agent_loop.reload_with_initial_messages()
                mock_get.assert_not_called()

        assert agent_loop.messages[0].content == "saved prompt"

    @pytest.mark.asyncio
    async def test_reload_does_not_emit_event(self) -> None:
        """reload_with_initial_messages must NOT emit SystemPromptRegeneratedEvent
        since it is called on every mode cycle and agent switch.
        """
        from vibe.core.config import VibeConfig
        from vibe.core.ui_events import SystemPromptRegeneratedEvent

        agent_loop = build_test_agent_loop()
        events_received: list[object] = []
        agent_loop.add_event_listener(events_received.append)

        with patch(
            "vibe.core.agent_loop.get_universal_system_prompt",
            return_value="new prompt",
        ):
            with patch.object(VibeConfig, "load", return_value=agent_loop.config):
                await agent_loop.reload_with_initial_messages()

        regenerated_events = [
            e for e in events_received if isinstance(e, SystemPromptRegeneratedEvent)
        ]
        assert len(regenerated_events) == 0

    @pytest.mark.asyncio
    async def test_refresh_system_prompt_emits_event(self) -> None:
        """refresh_system_prompt MUST emit SystemPromptRegeneratedEvent
        since it is a user-initiated action (/mcp refresh).
        """
        from vibe.core.ui_events import SystemPromptRegeneratedEvent

        agent_loop = build_test_agent_loop()
        events_received: list[object] = []
        agent_loop.add_event_listener(events_received.append)

        await agent_loop.refresh_system_prompt()

        regenerated_events = [
            e for e in events_received if isinstance(e, SystemPromptRegeneratedEvent)
        ]
        assert len(regenerated_events) == 1
