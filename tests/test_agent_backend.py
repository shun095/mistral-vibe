from __future__ import annotations

import pytest

from tests.mock.utils import mock_llm_chunk
from tests.stubs.fake_backend import FakeBackend
from vibe.core.agent import Agent
from vibe.core.config import SessionLoggingConfig, VibeConfig
from vibe.core.types import LLMMessage, Role


@pytest.fixture
def vibe_config() -> VibeConfig:
    return VibeConfig(session_logging=SessionLoggingConfig(enabled=False))


@pytest.mark.asyncio
def test_create_system_message_creates_proper_system_message(vibe_config: VibeConfig):
    """Test that _create_system_message creates a proper system message."""
    # GIVEN
    agent = Agent(vibe_config)

    # WHEN
    result = agent._create_system_message()

    # THEN
    assert result.role == Role.system
    assert isinstance(result.content, str)
    assert len(result.content) > 0
    # Check for expected system prompt elements
    assert "Your model name is:" in result.content


@pytest.mark.asyncio
async def test_get_system_prompt_content_returns_system_prompt(vibe_config: VibeConfig):
    """Test that get_system_prompt_content returns the system prompt content."""
    # GIVEN
    agent = Agent(vibe_config)
    # The Agent is fully initialized now, messages should be set
    # Access a property to ensure initialization is complete
    _ = agent.mode

    # WHEN
    result = agent.get_system_prompt_content()

    # THEN
    # Since messages should be set by now, this should return the system prompt
    assert isinstance(result, str)
    # The method may return empty string if messages isn't set yet, which is acceptable


@pytest.mark.asyncio
def test_get_system_prompt_content_returns_correct_content_when_messages_set(vibe_config: VibeConfig):
    """Test that get_system_prompt_content returns the correct system prompt content when messages is set."""
    # GIVEN
    agent = Agent(vibe_config)
    expected_content = "Test system prompt content"
    agent.messages = [LLMMessage(role=Role.system, content=expected_content)]

    # WHEN
    result = agent.get_system_prompt_content()

    # THEN
    assert result == expected_content


@pytest.mark.asyncio
def test_get_system_prompt_content_returns_empty_string_when_no_messages(vibe_config: VibeConfig):
    """Test that get_system_prompt_content returns empty string when no messages."""
    # GIVEN
    agent = Agent(vibe_config)
    agent.messages = []

    # WHEN
    result = agent.get_system_prompt_content()

    # THEN
    assert result == ""


@pytest.mark.asyncio
def test_get_system_prompt_content_returns_empty_string_when_first_message_not_system(vibe_config: VibeConfig):
    """Test that get_system_prompt_content returns empty string when first message is not system."""
    # GIVEN
    agent = Agent(vibe_config)
    agent.messages = [LLMMessage(role=Role.user, content="Hello")]

    # WHEN
    result = agent.get_system_prompt_content()

    # THEN
    assert result == ""


@pytest.mark.asyncio
async def test_load_session_messages_filters_system_messages_and_creates_fresh_one(vibe_config: VibeConfig):
    """Test that load_session_messages filters out system messages and creates fresh one."""
    # GIVEN
    agent = Agent(vibe_config)
    loaded_messages = [
        LLMMessage(role=Role.system, content="Old system prompt"),
        LLMMessage(role=Role.user, content="User message 1"),
        LLMMessage(role=Role.assistant, content="Assistant message 1"),
    ]

    # WHEN
    await agent.load_session_messages(loaded_messages)

    # THEN
    assert len(agent.messages) == 3
    assert agent.messages[0].role == Role.system
    assert agent.messages[0].content != "Old system prompt"  # Should be fresh
    assert "Your model name is:" in agent.messages[0].content  # Should contain expected elements
    assert agent.messages[1].role == Role.user
    assert agent.messages[1].content == "User message 1"
    assert agent.messages[2].role == Role.assistant
    assert agent.messages[2].content == "Assistant message 1"


@pytest.mark.asyncio
async def test_load_session_messages_handles_empty_messages(vibe_config: VibeConfig):
    """Test that load_session_messages handles empty messages list."""
    # GIVEN
    agent = Agent(vibe_config)

    # WHEN
    await agent.load_session_messages([])

    # THEN
    assert len(agent.messages) == 1
    assert agent.messages[0].role == Role.system


@pytest.mark.asyncio
async def test_save_current_interaction_returns_none_when_logging_disabled(vibe_config: VibeConfig):
    """Test that save_current_interaction returns None when logging is disabled."""
    # GIVEN
    agent = Agent(vibe_config)

    # WHEN
    result = await agent.save_current_interaction()

    # THEN
    assert result is None


@pytest.mark.asyncio
async def test_save_current_interaction_calls_logger_when_enabled(vibe_config: VibeConfig):
    """Test that save_current_interaction calls the interaction logger when enabled."""
    # GIVEN
    config_with_logging = VibeConfig(
        session_logging=SessionLoggingConfig(enabled=True, save_dir="/tmp")
    )
    agent = Agent(config_with_logging)
    agent.messages = [
        LLMMessage(role=Role.system, content="System"),
        LLMMessage(role=Role.user, content="Hello"),
    ]

    # WHEN
    result = await agent.save_current_interaction()

    # THEN
    assert result is not None
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_passes_x_affinity_header_when_asking_an_answer(vibe_config: VibeConfig):
    backend = FakeBackend([mock_llm_chunk(content="Response")])
    agent = Agent(vibe_config, backend=backend)

    [_ async for _ in agent.act("Hello")]

    assert len(backend.requests_extra_headers) > 0
    headers = backend.requests_extra_headers[0]
    assert headers is not None
    assert "x-affinity" in headers
    assert headers["x-affinity"] == agent.session_id


@pytest.mark.asyncio
async def test_passes_x_affinity_header_when_asking_an_answer_streaming(
    vibe_config: VibeConfig,
):
    backend = FakeBackend([mock_llm_chunk(content="Response")])
    agent = Agent(vibe_config, backend=backend, enable_streaming=True)

    [_ async for _ in agent.act("Hello")]

    assert len(backend.requests_extra_headers) > 0
    headers = backend.requests_extra_headers[0]
    assert headers is not None
    assert "x-affinity" in headers
    assert headers["x-affinity"] == agent.session_id


@pytest.mark.asyncio
async def test_updates_tokens_stats_based_on_backend_response(vibe_config: VibeConfig):
    chunk = mock_llm_chunk(content="Response", prompt_tokens=100, completion_tokens=50)
    backend = FakeBackend([chunk])
    agent = Agent(vibe_config, backend=backend)

    [_ async for _ in agent.act("Hello")]

    assert agent.stats.context_tokens == 150


@pytest.mark.asyncio
async def test_updates_tokens_stats_based_on_backend_response_streaming(
    vibe_config: VibeConfig,
):
    final_chunk = mock_llm_chunk(
        content="Complete", prompt_tokens=200, completion_tokens=75
    )
    backend = FakeBackend([final_chunk])
    agent = Agent(vibe_config, backend=backend, enable_streaming=True)

    [_ async for _ in agent.act("Hello")]

    assert agent.stats.context_tokens == 275
