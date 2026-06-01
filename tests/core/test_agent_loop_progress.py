from __future__ import annotations

"""Tests for AgentLoop prompt progress event streaming."""

from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest

from tests.conftest import build_test_vibe_config
from vibe.core.agent_loop import AgentLoop
from vibe.core.types import (
    LLMChunk,
    LLMMessage,
    PromptProgress,
    PromptProgressEvent,
    Role,
)

pytestmark = pytest.mark.asyncio


class TestAgentLoopPromptProgress:
    """Test AgentLoop yields PromptProgressEvent when progress data is available."""

    @pytest.fixture
    def agent_loop(self) -> AgentLoop:
        """Create AgentLoop with test config."""
        config = build_test_vibe_config(system_prompt_id="tests")
        return AgentLoop(config=config)

    async def test_stream_assistant_events_yields_prompt_progress(
        self, agent_loop: AgentLoop
    ) -> None:
        """Test that _stream_assistant_events yields PromptProgressEvent when chunk has progress."""

        # Mock _chat_streaming to return chunks with prompt_progress
        async def mock_chat_streaming() -> AsyncGenerator[LLMChunk, None]:
            # First chunk with progress
            progress = PromptProgress(
                total=1000, cache=200, processed=500, time_ms=1500
            )
            chunk1 = LLMChunk(
                message=LLMMessage(role=Role.assistant, content="", message_id="msg-1"),
                prompt_progress=progress,
            )
            yield chunk1

            # Second chunk without progress
            chunk2 = LLMChunk(
                message=LLMMessage(
                    role=Role.assistant, content="Hello", message_id="msg-1"
                )
            )
            yield chunk2

        with patch.object(agent_loop, "_chat_streaming", mock_chat_streaming):
            events = []
            async for event in agent_loop._stream_assistant_events():
                events.append(event)

        # Should have yielded PromptProgressEvent first, then AssistantEvent
        assert len(events) == 2
        assert isinstance(events[0], PromptProgressEvent)
        assert events[0].total == 1000
        assert events[0].cache == 200
        assert events[0].processed == 500
        assert events[0].time_ms == 1500

    async def test_stream_assistant_events_no_progress_when_none(
        self, agent_loop: AgentLoop
    ) -> None:
        """Test that _stream_assistant_events doesn't yield PromptProgressEvent when chunk has no progress."""

        async def mock_chat_streaming() -> AsyncGenerator[LLMChunk, None]:
            # Chunk without prompt_progress
            chunk = LLMChunk(
                message=LLMMessage(
                    role=Role.assistant, content="Hello", message_id="msg-1"
                )
            )
            yield chunk

        with patch.object(agent_loop, "_chat_streaming", mock_chat_streaming):
            events = []
            async for event in agent_loop._stream_assistant_events():
                events.append(event)

        # Should only have AssistantEvent, no PromptProgressEvent
        assert len(events) == 1
        assert not any(isinstance(e, PromptProgressEvent) for e in events)

    async def test_stream_assistant_events_multiple_progress_updates(
        self, agent_loop: AgentLoop
    ) -> None:
        """Test that _stream_assistant_events yields multiple PromptProgressEvents."""

        async def mock_chat_streaming() -> AsyncGenerator[LLMChunk, None]:
            # Progress update 1: 10%
            progress1 = PromptProgress(total=1000, cache=0, processed=100, time_ms=100)
            yield LLMChunk(
                message=LLMMessage(role=Role.assistant, content="", message_id="msg-1"),
                prompt_progress=progress1,
            )

            # Progress update 2: 50%
            progress2 = PromptProgress(total=1000, cache=0, processed=500, time_ms=500)
            yield LLMChunk(
                message=LLMMessage(role=Role.assistant, content="", message_id="msg-1"),
                prompt_progress=progress2,
            )

            # Progress update 3: 100%
            progress3 = PromptProgress(
                total=1000, cache=0, processed=1000, time_ms=1000
            )
            yield LLMChunk(
                message=LLMMessage(
                    role=Role.assistant, content="Done", message_id="msg-1"
                ),
                prompt_progress=progress3,
            )

        with patch.object(agent_loop, "_chat_streaming", mock_chat_streaming):
            events = []
            async for event in agent_loop._stream_assistant_events():
                events.append(event)

        # Should have 3 PromptProgressEvents and 1 AssistantEvent
        assert len(events) == 4

        progress_events = [e for e in events if isinstance(e, PromptProgressEvent)]
        assert len(progress_events) == 3
        assert progress_events[0].processed == 100
        assert progress_events[1].processed == 500
        assert progress_events[2].processed == 1000

    async def test_stream_assistant_events_progress_before_content(
        self, agent_loop: AgentLoop
    ) -> None:
        """Test that PromptProgressEvent is yielded before AssistantEvent for same chunk."""

        async def mock_chat_streaming() -> AsyncGenerator[LLMChunk, None]:
            # Chunk with both progress and content
            progress = PromptProgress(total=1000, cache=0, processed=500, time_ms=500)
            yield LLMChunk(
                message=LLMMessage(
                    role=Role.assistant, content="Hello", message_id="msg-1"
                ),
                prompt_progress=progress,
            )

        with patch.object(agent_loop, "_chat_streaming", mock_chat_streaming):
            events = []
            async for event in agent_loop._stream_assistant_events():
                events.append(event)

        # PromptProgressEvent should come before AssistantEvent
        assert len(events) == 2
        assert isinstance(events[0], PromptProgressEvent)
        assert events[0].processed == 500

        from vibe.core.types import AssistantEvent

        assert isinstance(events[1], AssistantEvent)
        assert events[1].content == "Hello"
