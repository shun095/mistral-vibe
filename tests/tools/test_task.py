from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import build_test_vibe_config
from tests.mock.utils import collect_result
from vibe.core.agents.manager import AgentManager
from vibe.core.agents.models import BUILTIN_AGENTS, AgentType
from vibe.core.tools.base import BaseToolState, InvokeContext, ToolError
from vibe.core.tools.builtins.task import Task, TaskArgs, TaskResult, TaskToolConfig
from vibe.core.types import AssistantEvent, LLMMessage, Role, ToolStreamEvent


@pytest.fixture
def task_tool() -> Task:
    return Task(config=TaskToolConfig(), state=BaseToolState())


class TestTaskArgs:
    def test_default_agent_is_explore(self) -> None:
        args = TaskArgs(task="do something")
        assert args.agent == "explore"

    def test_custom_values(self) -> None:
        args = TaskArgs(task="do something", agent="explore")
        assert args.task == "do something"
        assert args.agent == "explore"


class TestTaskToolValidation:
    @pytest.fixture
    def ctx(self) -> InvokeContext:
        config = build_test_vibe_config(
            include_project_context=False, include_prompt_detail=False
        )
        manager = AgentManager(lambda: config)
        return InvokeContext(tool_call_id="test-call-id", agent_manager=manager)

    @pytest.mark.asyncio
    async def test_rejects_primary_agent(
        self, task_tool: Task, ctx: InvokeContext
    ) -> None:
        args = TaskArgs(task="do something", agent="default")

        with pytest.raises(ToolError) as exc_info:
            await collect_result(task_tool.run(args, ctx))

        assert "agent" in str(exc_info.value).lower()
        assert "subagent" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_rejects_nonexistent_agent(
        self, task_tool: Task, ctx: InvokeContext
    ) -> None:
        args = TaskArgs(task="do something", agent="nonexistent")

        with pytest.raises(ToolError) as exc_info:
            await collect_result(task_tool.run(args, ctx))

        assert "Unknown agent" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_requires_agent_manager_in_context(self, task_tool: Task) -> None:
        args = TaskArgs(task="do something", agent="explore")
        ctx = InvokeContext(tool_call_id="test-call-id")  # No agent_manager

        with pytest.raises(ToolError) as exc_info:
            await collect_result(task_tool.run(args, ctx))

        assert "agent_manager" in str(exc_info.value).lower()

    def test_explore_agent_is_valid_subagent(self) -> None:
        agent = BUILTIN_AGENTS["explore"]
        assert agent.agent_type == AgentType.SUBAGENT


class TestTaskToolExecution:
    @pytest.fixture
    def ctx(self) -> InvokeContext:
        config = build_test_vibe_config(
            include_project_context=False, include_prompt_detail=False
        )
        manager = AgentManager(lambda: config)
        return InvokeContext(tool_call_id="test-call-id", agent_manager=manager)

    @pytest.mark.asyncio
    async def test_happy_path_returns_subagent_response(
        self, task_tool: Task, ctx: InvokeContext
    ) -> None:
        """Test that task tool successfully runs a subagent and returns its response."""
        mock_messages = [
            LLMMessage(role=Role.system, content="system"),
            LLMMessage(role=Role.user, content="task"),
            LLMMessage(role=Role.assistant, content="response 1"),
            LLMMessage(role=Role.assistant, content="response 2"),
        ]

        async def mock_act(task: str):
            yield AssistantEvent(content="Hello from subagent!\n\nThis is a comprehensive response with multiple lines.")
            yield AssistantEvent(content="\nAdditional details and findings.")

        with patch("vibe.core.tools.builtins.task.AgentLoop") as mock_agent_loop_class:
            mock_agent_loop = MagicMock()
            mock_agent_loop.act = mock_act
            mock_agent_loop.messages = mock_messages
            mock_agent_loop.set_approval_callback = MagicMock()
            mock_agent_loop_class.return_value = mock_agent_loop

            args = TaskArgs(task="explore the codebase", agent="explore")
            result = await collect_result(task_tool.run(args, ctx))

            assert isinstance(result, TaskResult)
            assert result.response == "Hello from subagent!\n\nThis is a comprehensive response with multiple lines.\nAdditional details and findings."
            assert result.turns_used == 2  # 2 assistant messages in mock_messages
            assert result.completed is True

    @pytest.mark.asyncio
    async def test_handles_stopped_by_middleware(
        self, task_tool: Task, ctx: InvokeContext
    ) -> None:
        """Test that task tool reports incomplete when stopped by middleware."""
        mock_messages = [
            LLMMessage(role=Role.system, content="system"),
            LLMMessage(role=Role.assistant, content="partial"),
        ]

        async def mock_act(task: str):
            yield AssistantEvent(content="Partial response", stopped_by_middleware=True)

        with patch("vibe.core.tools.builtins.task.AgentLoop") as mock_agent_loop_class:
            mock_agent_loop = MagicMock()
            mock_agent_loop.act = mock_act
            mock_agent_loop.messages = mock_messages
            mock_agent_loop.set_approval_callback = MagicMock()
            mock_agent_loop_class.return_value = mock_agent_loop

            args = TaskArgs(task="do something", agent="explore")
            result = await collect_result(task_tool.run(args, ctx))

            assert isinstance(result, TaskResult)
            assert result.completed is False

    @pytest.mark.asyncio
    async def test_handles_subagent_exception(
        self, task_tool: Task, ctx: InvokeContext
    ) -> None:
        """Test that task tool gracefully handles exceptions from subagent."""
        mock_messages = [LLMMessage(role=Role.system, content="system")]

        async def mock_act(task: str):
            yield AssistantEvent(content="Starting...")
            raise RuntimeError("Simulated error")

        with patch("vibe.core.tools.builtins.task.AgentLoop") as mock_agent_loop_class:
            mock_agent_loop = MagicMock()
            mock_agent_loop.act = mock_act
            mock_agent_loop.messages = mock_messages
            mock_agent_loop.set_approval_callback = MagicMock()
            mock_agent_loop_class.return_value = mock_agent_loop

            args = TaskArgs(task="do something", agent="explore")
            result = await collect_result(task_tool.run(args, ctx))

            assert isinstance(result, TaskResult)
            assert result.completed is False
            assert "Simulated error" in result.response

    @pytest.mark.asyncio
    async def test_retry_on_insufficient_response(
        self, task_tool: Task, ctx: InvokeContext
    ) -> None:
        """Test that task tool retries when response is insufficient (single line)."""
        mock_messages = [
            LLMMessage(role=Role.system, content="system"),
            LLMMessage(role=Role.assistant, content="Single line response"),
        ]

        attempt_count = 0

        async def mock_act(task: str):
            nonlocal attempt_count
            attempt_count += 1
            
            # First attempt: single line (insufficient)
            if attempt_count == 1:
                yield AssistantEvent(content="Single line response")
            # Second attempt: multi-line (sufficient)
            elif attempt_count == 2:
                yield AssistantEvent(content="Comprehensive response\n\nWith multiple lines")
            # Third attempt: still insufficient
            else:
                yield AssistantEvent(content="Another single line")

        with patch("vibe.core.tools.builtins.task.AgentLoop") as mock_agent_loop_class:
            mock_agent_loop = MagicMock()
            mock_agent_loop.act = mock_act
            mock_agent_loop.messages = mock_messages
            mock_agent_loop.set_approval_callback = MagicMock()
            mock_agent_loop_class.return_value = mock_agent_loop

            args = TaskArgs(task="analyze code", agent="explore")
            
            # Collect all events (not just the result)
            events = []
            async for event in task_tool.run(args, ctx):
                events.append(event)
                # Stop after getting ToolStreamEvent feedback
                if len(events) == 1 and isinstance(event, ToolStreamEvent):
                    break
            
            # Should have received feedback about insufficient response
            assert len(events) == 1
            assert isinstance(events[0], ToolStreamEvent)
            assert "insufficient" in events[0].message.lower()
            assert "brief" in events[0].message.lower()
