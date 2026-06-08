from __future__ import annotations

import pytest
from textual.pilot import Pilot

from tests.conftest import (
    build_test_agent_loop,
    build_test_vibe_app,
    build_test_vibe_config,
)
from vibe.cli.textual_ui.app import VibeApp
from vibe.cli.textual_ui.widgets.chat_input.body import ChatInputBody
from vibe.cli.textual_ui.widgets.messages import (
    AssistantMessage,
    ErrorMessage,
    UserMessage,
)
from vibe.core.agents.models import BuiltinAgentName
from vibe.core.types import FunctionCall, Role, ToolCall


async def _wait_for_agent(app: VibeApp, pilot: Pilot) -> None:
    """Wait for agent loop to fully complete."""
    for _ in range(750):
        if not app._agent_running:
            break
        await pilot.pause(0.02)


@pytest.fixture
def edit_test_app() -> VibeApp:
    from tests.mock.utils import mock_llm_chunk

    config = build_test_vibe_config()
    from tests.stubs.fake_backend import FakeBackend

    backend = FakeBackend(  # type: ignore
        chunks=[
            [mock_llm_chunk(content="Hello from assistant 1")],
            [mock_llm_chunk(content="Hello from assistant 2")],
            [mock_llm_chunk(content="Hello from edited response")],
        ]
    )
    agent_loop = build_test_agent_loop(config=config, backend=backend)  # type: ignore
    app = build_test_vibe_app(agent_loop=agent_loop)
    return app


@pytest.fixture
def edit_test_app_5chunks() -> VibeApp:
    from tests.mock.utils import mock_llm_chunk

    config = build_test_vibe_config()
    from tests.stubs.fake_backend import FakeBackend

    # New flow: msg1→0, msg2→1, msg3→2, edit→3, msg4→4
    backend = FakeBackend(  # type: ignore
        chunks=[
            [mock_llm_chunk(content="Hello from assistant 1")],
            [mock_llm_chunk(content="Hello from assistant 2")],
            [mock_llm_chunk(content="Hello from assistant 3")],
            [mock_llm_chunk(content="Hello from edited response")],
            [mock_llm_chunk(content="Hello from assistant 5")],
        ]
    )
    agent_loop = build_test_agent_loop(config=config, backend=backend)  # type: ignore
    app = build_test_vibe_app(agent_loop=agent_loop)
    return app


@pytest.fixture
def edit_test_app_with_tools() -> VibeApp:
    from tests.mock.utils import mock_llm_chunk
    from tests.stubs.fake_backend import FakeBackend
    from tests.stubs.fake_tool import FakeTool

    config = build_test_vibe_config(enabled_tools=["stub_tool"])

    def tc(call_id: str, arg: str, index: int = 0) -> ToolCall:
        return ToolCall(
            id=call_id,
            index=index,
            function=FunctionCall(name="stub_tool", arguments=f'{{"q":"{arg}"}}'),
        )

    # New flow: msg1→0-1, msg2→2-3, edit_msg2→4-5, msg3→6-7, edit_msg3→8-9
    backend = FakeBackend(  # type: ignore
        chunks=[
            # Turn 1: first message → stub_tool → final
            [mock_llm_chunk(content="Calling tool.", tool_calls=[tc("call_1", "q1")])],
            [mock_llm_chunk(content="First response done.")],
            # Turn 2: second message → stub_tool → final
            [mock_llm_chunk(content="Calling tool.", tool_calls=[tc("call_2", "q2")])],
            [mock_llm_chunk(content="Second response done.")],
            # Turn 3: edited second → stub_tool → final
            [mock_llm_chunk(content="Calling tool.", tool_calls=[tc("call_3", "q3")])],
            [mock_llm_chunk(content="Edited response done.")],
            # Turn 4: third message → stub_tool → final
            [mock_llm_chunk(content="Calling tool.", tool_calls=[tc("call_4", "q4")])],
            [mock_llm_chunk(content="Third response done.")],
            # Turn 5: edited third → stub_tool → final
            [mock_llm_chunk(content="Calling tool.", tool_calls=[tc("call_5", "q5")])],
            [mock_llm_chunk(content="Final edited response done.")],
        ]
    )
    agent_loop = build_test_agent_loop(  # type: ignore
        config=config, agent_name=BuiltinAgentName.AUTO_APPROVE, backend=backend
    )
    agent_loop.tool_manager._all_tools["stub_tool"] = FakeTool
    app = build_test_vibe_app(agent_loop=agent_loop)
    return app


@pytest.mark.asyncio
async def test_edit_last_message(edit_test_app_5chunks: VibeApp) -> None:
    """Comprehensive edit test: history, DOM, task lifecycle, input, history."""
    async with edit_test_app_5chunks.run_test() as pilot:
        app = edit_test_app_5chunks
        chat_input = app.query_one(ChatInputBody)

        await pilot.press(*"message 1")
        await pilot.press("enter")
        await pilot.pause()

        await pilot.press(*"message 2")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        await pilot.press(*"message 3")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        await pilot.press(*"/edit edited message 3")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()

        assert app._agent_running is False
        assert chat_input.value == ""

        history = chat_input.history
        assert history is not None
        assert history._entries[-1] == "edited message 3"
        assert not any(e.startswith("/edit") for e in history._entries)

        msgs = app.agent_loop.messages
        assert len(msgs) == 7
        assert msgs[0].role == Role.system
        assert msgs[1].role == Role.user and msgs[1].content == "message 1"
        assert (
            msgs[2].role == Role.assistant
            and msgs[2].content == "Hello from assistant 1"
        )
        assert msgs[3].role == Role.user and msgs[3].content == "message 2"
        assert (
            msgs[4].role == Role.assistant
            and msgs[4].content == "Hello from assistant 2"
        )
        assert msgs[5].role == Role.user and msgs[5].content == "edited message 3"
        assert (
            msgs[6].role == Role.assistant
            and msgs[6].content == "Hello from edited response"
        )

        dom = [
            w
            for w in app.query("#messages > *")
            if isinstance(w, (UserMessage, AssistantMessage))
        ]
        assert len(dom) == 6
        assert isinstance(dom[0], UserMessage)
        assert dom[0].get_content() == "message 1"
        assert isinstance(dom[1], AssistantMessage)
        assert dom[1]._content == "Hello from assistant 1"
        assert isinstance(dom[2], UserMessage)
        assert dom[2].get_content() == "message 2"
        assert isinstance(dom[3], AssistantMessage)
        assert dom[3]._content == "Hello from assistant 2"
        assert isinstance(dom[4], UserMessage)
        assert dom[4].get_content() == "edited message 3"
        assert isinstance(dom[5], AssistantMessage)
        assert dom[5]._content == "Hello from edited response"

        app.exit()


@pytest.mark.asyncio
async def test_edit_last_message_twice() -> None:
    """Test edit → new message → edit again (verifies truncation chain)."""
    from tests.mock.utils import mock_llm_chunk

    config = build_test_vibe_config()
    from tests.stubs.fake_backend import FakeBackend

    # Consumption order: msg1→0, msg2→1, edit→2, msg3→3, edit→4
    backend = FakeBackend(  # type: ignore
        chunks=[
            [mock_llm_chunk(content="Hello from assistant 1")],
            [mock_llm_chunk(content="Hello from assistant 2")],
            [mock_llm_chunk(content="Hello from edited response")],
            [mock_llm_chunk(content="Hello from assistant 3")],
            [mock_llm_chunk(content="Hello from assistant 5")],
        ]
    )
    agent_loop = build_test_agent_loop(config=config, backend=backend)  # type: ignore
    app = build_test_vibe_app(agent_loop=agent_loop)

    async with app.run_test() as pilot:
        app = app

        await pilot.press(*"first message")
        await pilot.press("enter")
        await pilot.pause()

        await pilot.press(*"second message")
        await pilot.press("enter")
        await pilot.pause()

        await pilot.press("/")
        await pilot.press(*"edit second message new content")
        await pilot.press("enter")
        await pilot.pause()

        await pilot.press(*"third message")
        await pilot.press("enter")
        await pilot.pause()

        await pilot.press("/")
        await pilot.press(*"edit third message new content")
        await pilot.press("enter")
        await pilot.pause()

        msgs = app.agent_loop.messages
        assert len(msgs) == 7
        assert msgs[0].role == Role.system
        assert msgs[1].role == Role.user and msgs[1].content == "first message"
        assert (
            msgs[2].role == Role.assistant
            and msgs[2].content == "Hello from assistant 1"
        )
        assert (
            msgs[3].role == Role.user
            and msgs[3].content == "second message new content"
        )
        assert (
            msgs[4].role == Role.assistant
            and msgs[4].content == "Hello from edited response"
        )
        assert (
            msgs[5].role == Role.user and msgs[5].content == "third message new content"
        )
        assert (
            msgs[6].role == Role.assistant
            and msgs[6].content == "Hello from assistant 5"
        )

        app.exit()


@pytest.mark.asyncio
async def test_edit_last_message_with_tool_calls(
    edit_test_app_with_tools: VibeApp,
) -> None:
    """Test edit → new message → edit with tool calls in every assistant response."""
    async with edit_test_app_with_tools.run_test() as pilot:
        app = edit_test_app_with_tools

        await pilot.press(*"first message")
        await pilot.press("enter")
        await _wait_for_agent(app, pilot)

        await pilot.press(*"second message")
        await pilot.press("enter")
        await _wait_for_agent(app, pilot)

        await pilot.press("/")
        await pilot.press(*"edit second message new content")
        await pilot.press("enter")
        await _wait_for_agent(app, pilot)

        await pilot.press(*"third message")
        await pilot.press("enter")
        await _wait_for_agent(app, pilot)

        await pilot.press("/")
        await pilot.press(*"edit third message new content")
        await pilot.press("enter")
        await _wait_for_agent(app, pilot)

        msgs = app.agent_loop.messages
        # 13 messages: system + 3*(user + asst_tool + tool + asst_final) - 2 truncations
        # 0:system 1:user1 2:asst(tool) 3:tool 4:asst(final)
        # 5:user2_edited 6:asst(tool) 7:tool 8:asst(edited)
        # 9:user3_edited 10:asst(tool) 11:tool 12:asst(final_edited)
        assert len(msgs) == 13
        assert msgs[0].role == Role.system
        assert msgs[1].role == Role.user and msgs[1].content == "first message"
        assert msgs[2].role == Role.assistant and msgs[2].tool_calls is not None
        assert msgs[3].role == Role.tool
        assert (
            msgs[4].role == Role.assistant and msgs[4].content == "First response done."
        )
        assert (
            msgs[5].role == Role.user
            and msgs[5].content == "second message new content"
        )
        assert msgs[6].role == Role.assistant and msgs[6].tool_calls is not None
        assert msgs[7].role == Role.tool
        assert (
            msgs[8].role == Role.assistant
            and msgs[8].content == "Edited response done."
        )
        assert (
            msgs[9].role == Role.user and msgs[9].content == "third message new content"
        )
        assert msgs[10].role == Role.assistant and msgs[10].tool_calls is not None
        assert msgs[11].role == Role.tool
        assert (
            msgs[12].role == Role.assistant
            and msgs[12].content == "Final edited response done."
        )

        app.exit()


@pytest.mark.asyncio
async def test_edit_last_message_no_messages(edit_test_app: VibeApp) -> None:
    """Test that editing without any messages shows error."""
    async with edit_test_app.run_test() as pilot:
        app = edit_test_app

        await pilot.press("/")
        await pilot.press(*"edit test")
        await pilot.press("enter")
        await pilot.pause()

        assert app._agent_running is False
        assert len(app.agent_loop.messages) == 1
        assert app.agent_loop.messages[0].role == Role.system
        assert app.query_one(ErrorMessage) is not None

        app.exit()


@pytest.mark.asyncio
async def test_edit_last_message_empty_content(edit_test_app: VibeApp) -> None:
    """Test that editing with empty content shows error."""
    async with edit_test_app.run_test() as pilot:
        app = edit_test_app

        await pilot.press(*"first message")
        await pilot.press("enter")
        await pilot.pause()

        await pilot.press("/")
        await pilot.press(*"edit")
        await pilot.press("enter")
        await pilot.pause()

        assert app._agent_running is False
        assert len(app.agent_loop.messages) == 3
        assert app.agent_loop.messages[0].role == Role.system
        assert (
            app.agent_loop.messages[1].role == Role.user
            and app.agent_loop.messages[1].content == "first message"
        )
        assert (
            app.agent_loop.messages[2].role == Role.assistant
            and app.agent_loop.messages[2].content == "Hello from assistant 1"
        )
        assert app.query_one(ErrorMessage) is not None

        app.exit()


@pytest.mark.asyncio
async def test_edit_last_message_multiple_edits() -> None:
    """Test multiple consecutive edits."""
    from tests.mock.utils import mock_llm_chunk

    config = build_test_vibe_config()
    from tests.stubs.fake_backend import FakeBackend

    # Consumption: msg→0, edit1→1, edit2→2, edit3→3
    backend = FakeBackend(  # type: ignore
        chunks=[
            [mock_llm_chunk(content="Response 1")],
            [mock_llm_chunk(content="Response 2")],
            [mock_llm_chunk(content="Response 3")],
            [mock_llm_chunk(content="Hello from assistant 5")],
        ]
    )
    agent_loop = build_test_agent_loop(config=config, backend=backend)  # type: ignore
    app = build_test_vibe_app(agent_loop=agent_loop)

    async with app.run_test() as pilot:
        app = app

        await pilot.press(*"original message")
        await pilot.press("enter")
        await pilot.pause()

        await pilot.press("/")
        await pilot.press(*"edit first edit")
        await pilot.press("enter")
        await pilot.pause()

        await pilot.press("/")
        await pilot.press(*"edit second edit")
        await pilot.press("enter")
        await pilot.pause()

        await pilot.press("/")
        await pilot.press(*"edit final edit")
        await pilot.press("enter")
        await pilot.pause()

        msgs = app.agent_loop.messages
        assert len(msgs) == 3
        assert msgs[0].role == Role.system
        assert msgs[1].role == Role.user and msgs[1].content == "final edit"
        assert (
            msgs[2].role == Role.assistant
            and msgs[2].content == "Hello from assistant 5"
        )

        app.exit()
