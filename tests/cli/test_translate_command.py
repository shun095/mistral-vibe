from __future__ import annotations

import pytest

from tests.conftest import (
    build_test_agent_loop,
    build_test_vibe_app,
    build_test_vibe_config,
    make_test_models,
)
from tests.mock.utils import mock_llm_chunk
from tests.stubs.fake_backend import FakeBackend
from vibe.cli.textual_ui.widgets.chat_input import ChatInputContainer
from vibe.cli.textual_ui.widgets.messages import UserCommandMessage


@pytest.mark.asyncio
async def test_translate_replaces_input_with_translated_text() -> None:
    backend = FakeBackend(
        chunks=[[mock_llm_chunk(content="Hello, how can I help you?")]]
    )
    cfg = build_test_vibe_config(models=make_test_models(999))
    agent_loop = build_test_agent_loop(config=cfg, backend=backend)  # type: ignore
    app = build_test_vibe_app(agent_loop=agent_loop)

    async with app.run_test() as pilot:
        await pilot.pause(0.1)

        await app._translate_prompt(cmd_args="Hola, como estas?")
        await pilot.pause(0.2)

        input_widget = app.query_one(ChatInputContainer)
        assert input_widget.value == "Hello, how can I help you?"


@pytest.mark.asyncio
async def test_translate_shows_usage_on_empty_args() -> None:
    backend = FakeBackend()
    cfg = build_test_vibe_config(models=make_test_models(999))
    agent_loop = build_test_agent_loop(config=cfg, backend=backend)  # type: ignore
    app = build_test_vibe_app(agent_loop=agent_loop)

    async with app.run_test() as pilot:
        await pilot.pause(0.1)

        await app._translate_prompt(cmd_args="")
        await pilot.pause(0.2)

        messages = list(app.query(UserCommandMessage))
        assert any("Usage" in m._content for m in messages)


@pytest.mark.asyncio
async def test_translate_uses_system_prompt() -> None:
    backend = FakeBackend(chunks=[[mock_llm_chunk(content="Translated text")]])
    cfg = build_test_vibe_config(models=make_test_models(999))
    agent_loop = build_test_agent_loop(config=cfg, backend=backend)  # type: ignore
    app = build_test_vibe_app(agent_loop=agent_loop)

    async with app.run_test() as pilot:
        await pilot.pause(0.1)

        await app._translate_prompt(cmd_args="Original text")
        await pilot.pause(0.2)

        assert len(backend.requests_messages) == 1
        requests = backend.requests_messages[0]
        assert len(requests) == 2
        assert requests[0].role.value == "system"
        assert requests[1].role.value == "user"
        assert (
            requests[1].content is not None and "Original text" in requests[1].content
        )


@pytest.mark.asyncio
async def test_translate_handles_empty_llm_response() -> None:
    backend = FakeBackend(chunks=[[mock_llm_chunk(content="")]])
    cfg = build_test_vibe_config(models=make_test_models(999))
    agent_loop = build_test_agent_loop(config=cfg, backend=backend)  # type: ignore
    app = build_test_vibe_app(agent_loop=agent_loop)

    async with app.run_test() as pilot:
        await pilot.pause(0.1)

        input_widget = app.query_one(ChatInputContainer)
        input_widget.value = "Original text"

        await app._translate_prompt(cmd_args="Original text")
        await pilot.pause(0.2)

        # Input should not be modified when LLM returns empty
        assert input_widget.value == "Original text"


@pytest.mark.asyncio
async def test_translate_handles_no_system_prompt() -> None:
    backend = FakeBackend()
    cfg = build_test_vibe_config(models=make_test_models(999))
    agent_loop = build_test_agent_loop(config=cfg, backend=backend)  # type: ignore
    # Remove system message to trigger the guard
    agent_loop.messages.reset([])
    app = build_test_vibe_app(agent_loop=agent_loop)

    async with app.run_test() as pilot:
        await pilot.pause(0.1)

        input_widget = app.query_one(ChatInputContainer)
        input_widget.value = "Original text"

        await app._translate_prompt(cmd_args="Original text")
        await pilot.pause(0.2)

        # Input should not be modified when no system prompt
        assert input_widget.value == "Original text"
