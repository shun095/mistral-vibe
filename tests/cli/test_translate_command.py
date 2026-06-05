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
from vibe.core.types import PromptProgress, PromptProgressEvent


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
        if app._translation_task:
            await app._translation_task

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
        if app._translation_task:
            await app._translation_task

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
        if app._translation_task:
            await app._translation_task

        assert input_widget.value == "Original text"


@pytest.mark.asyncio
async def test_translate_handles_no_system_prompt() -> None:
    backend = FakeBackend()
    cfg = build_test_vibe_config(models=make_test_models(999))
    agent_loop = build_test_agent_loop(config=cfg, backend=backend)  # type: ignore
    agent_loop.messages.reset([])
    app = build_test_vibe_app(agent_loop=agent_loop)

    async with app.run_test() as pilot:
        await pilot.pause(0.1)

        input_widget = app.query_one(ChatInputContainer)
        input_widget.value = "Original text"

        await app._translate_prompt(cmd_args="Original text")
        if app._translation_task:
            await app._translation_task

        assert input_widget.value == "Original text"


@pytest.mark.asyncio
async def test_translate_emits_prompt_progress_events() -> None:
    backend = FakeBackend(
        chunks=[
            [
                mock_llm_chunk(
                    content="",
                    prompt_progress=PromptProgress(
                        total=100, cache=0, processed=50, time_ms=100
                    ),
                ),
                mock_llm_chunk(
                    content="",
                    prompt_progress=PromptProgress(
                        total=100, cache=0, processed=100, time_ms=200
                    ),
                ),
                mock_llm_chunk(content="Translated"),
            ]
        ]
    )
    cfg = build_test_vibe_config(models=make_test_models(999))
    agent_loop = build_test_agent_loop(config=cfg, backend=backend)  # type: ignore
    app = build_test_vibe_app(agent_loop=agent_loop)

    progress_values = []

    async with app.run_test() as pilot:
        await pilot.pause(0.1)

        original_notify = agent_loop._notify_event_listeners

        def capture_notify(event):
            if isinstance(event, PromptProgressEvent):
                progress_values.append(event.progress_percentage)

        agent_loop._notify_event_listeners = capture_notify  # type: ignore

        # Patch event_handler to capture handle_event calls
        if app.event_handler:
            original_handle = app.event_handler.handle_event

            def capture_handle(event, *args, **kwargs):
                original_handle(event, *args, **kwargs)

            app.event_handler.handle_event = capture_handle  # type: ignore

        await app._translate_prompt(cmd_args="Original text")
        if app._translation_task:
            await app._translation_task

        agent_loop._notify_event_listeners = original_notify  # type: ignore

        assert len(progress_values) == 2
        assert progress_values[0] == 50.0
        assert progress_values[1] == 100.0


@pytest.mark.asyncio
async def test_translate_runs_as_async_task_non_blocking() -> None:
    backend = FakeBackend(chunks=[[mock_llm_chunk(content="Translated")]])
    cfg = build_test_vibe_config(models=make_test_models(999))
    agent_loop = build_test_agent_loop(config=cfg, backend=backend)  # type: ignore
    app = build_test_vibe_app(agent_loop=agent_loop)

    async with app.run_test() as pilot:
        await pilot.pause(0.1)

        await app._translate_prompt(cmd_args="Original text")

        task = app._translation_task
        assert task is not None
        assert not task.done()

        await task
        assert task.done()
        assert app._translation_running is False
        assert app._translation_task is None

        input_widget = app.query_one(ChatInputContainer)
        assert input_widget.value == "Translated"


@pytest.mark.asyncio
async def test_translate_loading_widget_shows_progress() -> None:
    backend = FakeBackend(
        chunks=[
            [
                mock_llm_chunk(
                    content="",
                    prompt_progress=PromptProgress(
                        total=100, cache=0, processed=75, time_ms=150
                    ),
                ),
                mock_llm_chunk(content="Translated"),
            ]
        ]
    )
    cfg = build_test_vibe_config(models=make_test_models(999))
    agent_loop = build_test_agent_loop(config=cfg, backend=backend)  # type: ignore
    app = build_test_vibe_app(agent_loop=agent_loop)

    progress_captured = []

    async with app.run_test() as pilot:
        await pilot.pause(0.1)

        if app.event_handler:
            original_handler = app.event_handler._handle_prompt_progress

            async def capture_progress(event, *args, **kwargs):
                if isinstance(event, PromptProgressEvent):
                    progress_captured.append(event.progress_percentage)
                await original_handler(event, *args, **kwargs)

            app.event_handler._handle_prompt_progress = capture_progress  # type: ignore

        await app._translate_prompt(cmd_args="Original text")
        if app._translation_task:
            await app._translation_task
            await pilot.pause(0.1)

        assert len(progress_captured) == 1
        assert progress_captured[0] == 75.0


@pytest.mark.asyncio
async def test_translate_prevents_concurrent_execution() -> None:
    backend = FakeBackend(chunks=[[mock_llm_chunk(content="Translated")]])
    cfg = build_test_vibe_config(models=make_test_models(999))
    agent_loop = build_test_agent_loop(config=cfg, backend=backend)  # type: ignore
    app = build_test_vibe_app(agent_loop=agent_loop)

    async with app.run_test() as pilot:
        await pilot.pause(0.1)

        app._translation_running = True
        await app._translate_prompt(cmd_args="Should be ignored")
        await pilot.pause(0.1)

        assert app._translation_task is None
        assert backend.requests_messages == []
