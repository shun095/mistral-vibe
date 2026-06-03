from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import (
    build_test_agent_loop,
    build_test_vibe_config,
    make_test_models,
)
from tests.mock.utils import mock_llm_chunk
from tests.stubs.fake_backend import FakeBackend
from vibe.core.config import ModelConfig
from vibe.core.types import (
    AssistantEvent,
    CompactEndEvent,
    CompactStartEvent,
    Content,
    LLMMessage,
    Role,
    UserMessageEvent,
)


def _get_auto_compact_properties(
    telemetry_events: list[dict[str, object]],
) -> dict[str, object]:
    auto_compact = [
        event
        for event in telemetry_events
        if event.get("event_name") == "vibe.auto_compact_triggered"
    ]
    assert len(auto_compact) == 1
    return cast(dict[str, object], auto_compact[0]["properties"])


@pytest.mark.asyncio
async def test_auto_compact_emits_correct_events(telemetry_events: list[dict]) -> None:
    backend = FakeBackend([
        [mock_llm_chunk(content="<summary>")],
        [mock_llm_chunk(content="<final>")],
    ])
    cfg = build_test_vibe_config(models=make_test_models(auto_compact_threshold=1))
    agent = build_test_agent_loop(config=cfg, backend=backend)
    agent.stats.context_tokens = 2
    old_session_id = agent.session_id

    events = [ev async for ev in agent.act("Hello")]

    assert len(events) == 4
    assert isinstance(events[0], UserMessageEvent)
    assert isinstance(events[1], CompactStartEvent)
    assert isinstance(events[2], CompactEndEvent)
    assert isinstance(events[3], AssistantEvent)
    start: CompactStartEvent = events[1]
    end: CompactEndEvent = events[2]
    final: AssistantEvent = events[3]
    assert start.current_context_tokens == 2
    assert start.threshold == 1
    assert isinstance(end, CompactEndEvent)
    assert final.content == "<final>"

    properties = _get_auto_compact_properties(telemetry_events)
    assert properties["nb_context_tokens_before"] == 2
    assert properties["auto_compact_threshold"] == 1
    assert properties["status"] == "success"
    assert properties["session_id"] == old_session_id
    assert properties["parent_session_id"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("side_effect", "expected_exception", "match", "expected_status"),
    [
        pytest.param(
            RuntimeError("boom"), RuntimeError, "boom", "failure", id="failure"
        ),
        pytest.param(
            asyncio.CancelledError(),
            asyncio.CancelledError,
            None,
            "cancelled",
            id="cancelled",
        ),
    ],
)
async def test_auto_compact_emits_terminal_telemetry(
    side_effect: BaseException,
    expected_exception: type[BaseException],
    match: str | None,
    expected_status: str,
    telemetry_events: list[dict],
) -> None:
    backend = FakeBackend([[mock_llm_chunk(content="<final>")]])
    cfg = build_test_vibe_config(models=make_test_models(auto_compact_threshold=1))
    agent = build_test_agent_loop(config=cfg, backend=backend)
    agent.stats.context_tokens = 2
    old_session_id = agent.session_id

    events = []
    with patch.object(agent, "compact", AsyncMock(side_effect=side_effect)):
        if match is None:
            with pytest.raises(expected_exception):
                async for event in agent.act("Hello"):
                    events.append(event)
        else:
            with pytest.raises(expected_exception, match=match):
                async for event in agent.act("Hello"):
                    events.append(event)

    assert isinstance(events[0], UserMessageEvent)
    assert isinstance(events[1], CompactStartEvent)
    if expected_status == "failure":
        assert len(events) == 3
        assert isinstance(events[2], CompactEndEvent)
        assert events[2].error == "boom"
    else:
        assert len(events) == 2

    properties = _get_auto_compact_properties(telemetry_events)
    assert properties["nb_context_tokens_before"] == 2
    assert properties["auto_compact_threshold"] == 1
    assert properties["status"] == expected_status
    assert properties["session_id"] == old_session_id
    assert properties["parent_session_id"] is None


@pytest.mark.asyncio
async def test_auto_compact_observer_sees_user_msg_not_summary() -> None:
    """Observer sees the original user message and final response.

    Compact internals (summary request, LLM summary) are invisible
    to the observer because they happen inside silent() / reset().
    """
    observed: list[tuple[Role, Content | None]] = []

    def observer(msg: LLMMessage) -> None:
        observed.append((msg.role, msg.content))

    backend = FakeBackend([
        [mock_llm_chunk(content="<summary>")],
        [mock_llm_chunk(content="<final>")],
    ])
    cfg = build_test_vibe_config(models=make_test_models(auto_compact_threshold=1))
    agent = build_test_agent_loop(
        config=cfg, message_observer=observer, backend=backend
    )
    agent.stats.context_tokens = 2

    [_ async for _ in agent.act("Hello")]

    roles = [r for r, _ in observed]
    assert roles == [Role.system, Role.user, Role.assistant]
    assert observed[1][1] == "Hello"
    assert observed[2][1] == "<final>"


@pytest.mark.asyncio
async def test_auto_compact_observer_does_not_see_summary_request() -> None:
    """The compact summary request and LLM response must not leak to observer."""
    observed: list[tuple[Role, Content | None]] = []

    def observer(msg: LLMMessage) -> None:
        observed.append((msg.role, msg.content))

    backend = FakeBackend([
        [mock_llm_chunk(content="<summary>")],
        [mock_llm_chunk(content="<final>")],
    ])
    cfg = build_test_vibe_config(models=make_test_models(auto_compact_threshold=1))
    agent = build_test_agent_loop(
        config=cfg, message_observer=observer, backend=backend
    )
    agent.stats.context_tokens = 2

    [_ async for _ in agent.act("Hello")]

    contents = [c for _, c in observed]
    assert "<summary>" not in contents
    assert all("compact" not in (str(c) if c else "").lower() for c in contents)


@pytest.mark.asyncio
async def test_compact_replaces_messages_with_summary() -> None:
    """After compact, messages list contains only system + summary."""
    backend = FakeBackend([
        [mock_llm_chunk(content="<summary>")],
        [mock_llm_chunk(content="<final>")],
    ])
    cfg = build_test_vibe_config(models=make_test_models(auto_compact_threshold=1))
    agent = build_test_agent_loop(config=cfg, backend=backend)
    agent.stats.context_tokens = 2

    [_ async for _ in agent.act("Hello")]

    # After compact + final response: system, summary, final
    assert agent.messages[0].role == Role.system
    assert agent.messages[-1].role == Role.assistant
    assert agent.messages[-1].content == "<final>"


class _ModelTrackingBackend(FakeBackend):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.requested_models: list[ModelConfig] = []

    async def complete(self, *, model, **kwargs):
        self.requested_models.append(model)
        return await super().complete(model=model, **kwargs)

    async def complete_streaming(self, *, model, **kwargs):
        self.requested_models.append(model)
        async for chunk in super().complete_streaming(model=model, **kwargs):
            yield chunk


@pytest.mark.asyncio
async def test_compact_uses_compaction_model() -> None:
    """When compaction_model is set, compact() uses it instead of active_model."""
    compaction = ModelConfig(
        name="compaction-model",
        provider="mistral",
        alias="compaction",
        auto_compact_threshold=1,
    )
    backend = _ModelTrackingBackend([
        [mock_llm_chunk(content="<summary>")],
        [mock_llm_chunk(content="<final>")],
    ])
    cfg = build_test_vibe_config(
        models=make_test_models(auto_compact_threshold=1), compaction_model=compaction
    )
    agent = build_test_agent_loop(config=cfg, backend=backend)
    agent.stats.context_tokens = 2

    [_ async for _ in agent.act("Hello")]

    assert backend.requested_models[0].name == "compaction-model"
    assert backend.requested_models[1].name != "compaction-model"


@pytest.mark.asyncio
async def test_compact_uses_active_model_when_no_compaction_model() -> None:
    """Without compaction_model, compact() falls back to the active model."""
    backend = _ModelTrackingBackend([
        [mock_llm_chunk(content="<summary>")],
        [mock_llm_chunk(content="<final>")],
    ])
    cfg = build_test_vibe_config(models=make_test_models(auto_compact_threshold=1))
    agent = build_test_agent_loop(config=cfg, backend=backend)
    agent.stats.context_tokens = 2

    [_ async for _ in agent.act("Hello")]

    active = cfg.get_active_model()
    assert backend.requested_models[0].name == active.name
    assert backend.requested_models[1].name == active.name


class StreamingTrackingBackend(FakeBackend):
    """Backend that tracks whether streaming or non-streaming was used."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.streaming_calls: int = 0
        self.non_streaming_calls: int = 0

    async def complete(self, *, model, **kwargs):
        self.non_streaming_calls += 1
        return await super().complete(model=model, **kwargs)

    async def complete_streaming(self, *, model, **kwargs):
        self.streaming_calls += 1
        async for chunk in super().complete_streaming(model=model, **kwargs):
            yield chunk


@pytest.mark.asyncio
async def test_compact_uses_streaming() -> None:
    """Verify that compact() uses streaming instead of non-streaming complete()."""
    expected_summary = "<summary>"
    backend = StreamingTrackingBackend([
        [mock_llm_chunk(content=expected_summary)],
        [mock_llm_chunk(content="<final>")],
    ])
    cfg = build_test_vibe_config(models=make_test_models(auto_compact_threshold=1))
    agent = build_test_agent_loop(config=cfg, backend=backend)
    agent.stats.context_tokens = 2

    events = [ev async for ev in agent.act("Hello")]

    # Compact should use streaming (at least 1 streaming call for the summary)
    assert backend.streaming_calls >= 1, "Compact should use streaming"

    # Verify summary content is correctly aggregated from streaming chunks
    compact_end = [e for e in events if isinstance(e, CompactEndEvent)][0]
    assert compact_end.summary_content == expected_summary


@pytest.mark.asyncio
async def test_compact_aggregates_multiple_streaming_chunks() -> None:
    """Verify that compact() correctly aggregates multiple streaming chunks into summary."""
    chunk1 = "Summary: "
    chunk2 = "User asked about "
    chunk3 = "Python. "
    chunk4 = "Assistant explained "
    chunk5 = "the basics."
    expected_summary = chunk1 + chunk2 + chunk3 + chunk4 + chunk5

    backend = StreamingTrackingBackend([
        [
            mock_llm_chunk(content=chunk1),
            mock_llm_chunk(content=chunk2),
            mock_llm_chunk(content=chunk3),
            mock_llm_chunk(content=chunk4),
            mock_llm_chunk(content=chunk5),
        ],
        [mock_llm_chunk(content="<final>")],
    ])
    cfg = build_test_vibe_config(models=make_test_models(auto_compact_threshold=1))
    agent = build_test_agent_loop(config=cfg, backend=backend)
    agent.stats.context_tokens = 2

    events = [ev async for ev in agent.act("Hello")]

    # Compact should use streaming
    assert backend.streaming_calls >= 1, "Compact should use streaming"

    # Verify summary content is correctly aggregated from all chunks
    compact_end = [e for e in events if isinstance(e, CompactEndEvent)][0]
    assert compact_end.summary_content == expected_summary


@pytest.mark.asyncio
async def test_compact_appends_extra_instructions_to_prompt() -> None:
    backend = FakeBackend([[mock_llm_chunk(content="<summary>")]])
    cfg = build_test_vibe_config(models=make_test_models(auto_compact_threshold=999))
    agent = build_test_agent_loop(config=cfg, backend=backend)
    agent.messages.append(LLMMessage(role=Role.user, content="Hello"))
    agent.stats.context_tokens = 100

    await agent.compact(extra_instructions="focus on auth")

    compaction_prompt = backend.requests_messages[0][-1].content
    assert compaction_prompt is not None
    assert "## Additional Instructions" in compaction_prompt
    assert "focus on auth" in compaction_prompt


@pytest.mark.asyncio
async def test_compact_uses_configured_compaction_prompt(
    mock_prompts_dirs: tuple[Path, Path],
) -> None:
    project_prompts, _ = mock_prompts_dirs
    (project_prompts / "theorem_compact.md").write_text("Summarize theorem progress")

    backend = FakeBackend([[mock_llm_chunk(content="<summary>")]])
    cfg = build_test_vibe_config(
        models=make_test_models(auto_compact_threshold=999),
        compaction_prompt_id="theorem_compact",
    )
    agent = build_test_agent_loop(config=cfg, backend=backend)
    agent.messages.append(LLMMessage(role=Role.user, content="Hello"))
    agent.stats.context_tokens = 100

    await agent.compact()

    compaction_prompt = backend.requests_messages[0][-1].content
    assert compaction_prompt == "Summarize theorem progress"


@pytest.mark.asyncio
async def test_compact_without_extra_instructions_has_no_additional_section() -> None:
    backend = FakeBackend([[mock_llm_chunk(content="<summary>")]])
    cfg = build_test_vibe_config(models=make_test_models(auto_compact_threshold=999))
    agent = build_test_agent_loop(config=cfg, backend=backend)
    agent.messages.append(LLMMessage(role=Role.user, content="Hello"))
    agent.stats.context_tokens = 100

    await agent.compact()

    compaction_prompt = backend.requests_messages[0][-1].content
    assert compaction_prompt is not None
    assert "## Additional Instructions" not in compaction_prompt


@pytest.mark.asyncio
async def test_compact_resets_resume_system_prompt() -> None:
    """After compact, _resume_system_prompt is cleared so mode cycles
    recalculate the system prompt instead of using the stale saved one.
    """
    backend = FakeBackend([[mock_llm_chunk(content="<summary>")]])
    cfg = build_test_vibe_config(models=make_test_models(auto_compact_threshold=999))
    agent = build_test_agent_loop(config=cfg, backend=backend)
    agent._resume_system_prompt = "saved prompt"
    agent.messages.append(LLMMessage(role=Role.user, content="Hello"))
    agent.stats.context_tokens = 100

    await agent.compact()

    assert agent._resume_system_prompt is None


@pytest.mark.asyncio
async def test_compact_recalculates_system_prompt() -> None:
    """After compact, the system prompt is freshly calculated, not reused."""
    backend = FakeBackend([[mock_llm_chunk(content="<summary>")]])
    cfg = build_test_vibe_config(models=make_test_models(auto_compact_threshold=999))
    agent = build_test_agent_loop(config=cfg, backend=backend)
    old_content = cast(str, agent.messages[0].content)
    agent._resume_system_prompt = old_content  # Simulate resume state
    agent.messages.append(LLMMessage(role=Role.user, content="Hello"))
    agent.stats.context_tokens = 100

    await agent.compact()

    assert agent._resume_system_prompt is None
    assert agent.messages[0].role == Role.system
    assert agent.messages[0].content is not None
    assert agent.messages[0].content != agent._resume_system_prompt


@pytest.mark.asyncio
async def test_compact_emits_system_prompt_regenerated_event() -> None:
    """compact emits SystemPromptRegeneratedEvent."""
    from vibe.core.ui_events import SystemPromptRegeneratedEvent

    backend = FakeBackend([[mock_llm_chunk(content="<summary>")]])
    cfg = build_test_vibe_config(models=make_test_models(auto_compact_threshold=999))
    agent = build_test_agent_loop(config=cfg, backend=backend)
    agent.messages.append(LLMMessage(role=Role.user, content="Hello"))
    agent.stats.context_tokens = 100

    events_received: list[object] = []
    agent.add_event_listener(events_received.append)

    await agent.compact()

    assert any(isinstance(e, SystemPromptRegeneratedEvent) for e in events_received)


@pytest.mark.asyncio
async def test_compact_message_shape_preserves_prior_user_messages() -> None:
    from vibe.core.prompts import UtilityPrompt

    summary_prefix = UtilityPrompt.COMPACT_SUMMARY_PREFIX.read()
    backend = FakeBackend([[mock_llm_chunk(content="fresh summary body")]])
    cfg = build_test_vibe_config(models=make_test_models(auto_compact_threshold=999))
    agent = build_test_agent_loop(config=cfg, backend=backend)

    agent.messages.append(LLMMessage(role=Role.user, content="first real ask"))
    agent.messages.append(
        LLMMessage(role=Role.user, content="middleware ping", injected=True)
    )
    agent.messages.append(LLMMessage(role=Role.assistant, content="ack"))
    agent.messages.append(
        LLMMessage(role=Role.user, content=f"{summary_prefix}\nprior summary blob")
    )
    agent.messages.append(LLMMessage(role=Role.user, content="follow-up ask"))
    agent.stats.context_tokens = 100

    await agent.compact()

    final = list(agent.messages)
    assert len(final) == 4  # [system, prior_user_1, prior_user_2, wrapped_summary]
    assert final[0].role == Role.system  # system prompt regenerated on compact
    assert [m.role for m in final[1:]] == [Role.user, Role.user, Role.user]
    assert final[1].content == "first real ask"
    assert final[2].content == "follow-up ask"
    # Injected and prior-summary user messages must be filtered out.
    assert all("middleware ping" not in (m.content or "") for m in final)
    assert sum("prior summary blob" in (m.content or "") for m in final) == 0
    # Final message is the wrapped summary the next agent will read first.
    assert final[-1].content == f"{summary_prefix}\nfresh summary body"
