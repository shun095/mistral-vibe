"""Tests for agent loop denylist enforcement when calling act() method."""

from __future__ import annotations

import pytest

from vibe.core.agents.models import BuiltinAgentName
from vibe.core.config import VibeConfig
from vibe.core.types import FunctionCall, ToolCall
from tests.mock.utils import mock_llm_chunk
from tests.stubs.fake_backend import FakeBackend
from vibe.core.agent_loop import AgentLoop


class TestAgentLoopActDenylist:
    """Test that denylist is enforced when calling act() method."""

    @pytest.fixture
    def config(self) -> VibeConfig:
        """Create a test config with auto_approve enabled."""
        return VibeConfig(auto_approve=True)

    @pytest.fixture
    def agent_loop(self, config: VibeConfig) -> AgentLoop:
        """Create an AgentLoop instance with auto-approve enabled."""
        return AgentLoop(config=config, agent_name=BuiltinAgentName.AUTO_APPROVE)

    @pytest.mark.asyncio
    async def test_act_blocks_git_checkout_denylist(
        self, agent_loop: AgentLoop
    ) -> None:
        """Test that act() blocks git checkout command from denylist."""
        # Create a mock response that includes a tool call for git checkout
        tool_call = ToolCall(
            id="call_1",
            index=0,
            function=FunctionCall(name="bash", arguments='{"command": "git checkout --help","timeout":10}'),
        )
        
        backend = FakeBackend([
            mock_llm_chunk(content="Let me check git checkout", tool_calls=[tool_call]),
        ])
        
        agent_loop.backend = backend
        
        events = []
        async for event in agent_loop.act("Try to run git checkout --help"):
            events.append(event)
        
        # Find the tool result event
        tool_result_events = [
            e for e in events if hasattr(e, 'tool_name') and e.tool_name == 'bash'
        ]
        
        assert len(tool_result_events) > 0, "No bash tool result event found"
        
        tool_result = tool_result_events[-1]
        assert tool_result.skipped, "Bash command should be skipped"
        assert tool_result.skip_reason is not None
        feedback = str(tool_result.skip_reason)
        assert "blocked by denylist" in feedback
        assert "git checkout" in feedback

    @pytest.mark.asyncio
    async def test_act_blocks_git_reset_hard_denylist(
        self, agent_loop: AgentLoop
    ) -> None:
        """Test that act() blocks git reset --hard command from denylist."""
        # Create a mock response that includes a tool call for git reset --hard
        tool_call = ToolCall(
            id="call_1",
            index=0,
            function=FunctionCall(name="bash", arguments='{"command": "git reset --hard","timeout":10}'),
        )
        
        backend = FakeBackend([
            mock_llm_chunk(content="Let me reset the repository", tool_calls=[tool_call]),
        ])
        
        agent_loop.backend = backend
        
        events = []
        async for event in agent_loop.act("Try to run git reset --hard"):
            events.append(event)
        
        # Find the tool result event
        tool_result_events = [
            e for e in events if hasattr(e, 'tool_name') and e.tool_name == 'bash'
        ]
        
        assert len(tool_result_events) > 0, "No bash tool result event found"
        
        tool_result = tool_result_events[-1]
        assert tool_result.skipped, "Bash command should be skipped"
        assert tool_result.skip_reason is not None
        feedback = str(tool_result.skip_reason)
        assert "blocked by denylist" in feedback
        assert "git reset --hard" in feedback

    @pytest.mark.asyncio
    async def test_act_blocks_vim_editor_denylist(
        self, agent_loop: AgentLoop
    ) -> None:
        """Test that act() blocks vim editor command from denylist."""
        # Create a mock response that includes a tool call for vim
        tool_call = ToolCall(
            id="call_1",
            index=0,
            function=FunctionCall(name="bash", arguments='{"command": "vim file.txt","timeout":10}'),
        )
        
        backend = FakeBackend([
            mock_llm_chunk(content="Let me edit the file with vim", tool_calls=[tool_call]),
        ])
        
        agent_loop.backend = backend
        
        events = []
        async for event in agent_loop.act("Try to run vim file.txt"):
            events.append(event)
        
        # Find the tool result event
        tool_result_events = [
            e for e in events if hasattr(e, 'tool_name') and e.tool_name == 'bash'
        ]
        
        assert len(tool_result_events) > 0, "No bash tool result event found"
        
        tool_result = tool_result_events[-1]
        assert tool_result.skipped, "Bash command should be skipped"
        assert tool_result.skip_reason is not None
        feedback = str(tool_result.skip_reason)
        assert "blocked by denylist" in feedback
        assert "vim" in feedback

    @pytest.mark.asyncio
    async def test_act_blocks_bash_i_shell_denylist(
        self, agent_loop: AgentLoop
    ) -> None:
        """Test that act() blocks bash -i interactive shell from denylist."""
        # Create a mock response that includes a tool call for bash -i
        tool_call = ToolCall(
            id="call_1",
            index=0,
            function=FunctionCall(name="bash", arguments='{"command": "bash -i","timeout":10}'),
        )
        
        backend = FakeBackend([
            mock_llm_chunk(content="Let me start an interactive shell", tool_calls=[tool_call]),
        ])
        
        agent_loop.backend = backend
        
        events = []
        async for event in agent_loop.act("Try to run bash -i"):
            events.append(event)
        
        # Find the tool result event
        tool_result_events = [
            e for e in events if hasattr(e, 'tool_name') and e.tool_name == 'bash'
        ]
        
        assert len(tool_result_events) > 0, "No bash tool result event found"
        
        tool_result = tool_result_events[-1]
        assert tool_result.skipped, "Bash command should be skipped"
        assert tool_result.skip_reason is not None
        feedback = str(tool_result.skip_reason)
        assert "blocked by denylist" in feedback
        assert "bash -i" in feedback

    @pytest.mark.asyncio
    async def test_act_allows_safe_commands_not_in_denylist(
        self, agent_loop: AgentLoop
    ) -> None:
        """Test that act() allows commands that are not in denylist."""
        # Create a mock response that includes a tool call for echo
        tool_call = ToolCall(
            id="call_1",
            index=0,
            function=FunctionCall(name="bash", arguments='{"command": "echo hello","timeout":10}'),
        )
        
        backend = FakeBackend([
            mock_llm_chunk(content="Let me echo a message", tool_calls=[tool_call]),
        ])
        
        agent_loop.backend = backend
        
        events = []
        async for event in agent_loop.act("Try to run echo hello"):
            events.append(event)
        
        # Find the tool result event
        tool_result_events = [
            e for e in events if hasattr(e, 'tool_name') and e.tool_name == 'bash'
        ]
        
        assert len(tool_result_events) > 0, "No bash tool result event found"
        
        tool_result = tool_result_events[-1]
        # echo is in allowlist, so it should execute
        assert not tool_result.skipped, "Bash command should not be skipped"
        assert tool_result.result is not None

    @pytest.mark.asyncio
    async def test_act_blocks_git_checkout_with_args(
        self, agent_loop: AgentLoop
    ) -> None:
        """Test that act() blocks git checkout with various arguments."""
        # Create a mock response that includes a tool call for git checkout with args
        tool_call = ToolCall(
            id="call_1",
            index=0,
            function=FunctionCall(name="bash", arguments='{"command": "git checkout -b new-branch","timeout":10}'),
        )
        
        backend = FakeBackend([
            mock_llm_chunk(content="Let me create a new branch", tool_calls=[tool_call]),
        ])
        
        agent_loop.backend = backend
        
        events = []
        async for event in agent_loop.act("Try to run git checkout -b new-branch"):
            events.append(event)
        
        # Find the tool result event
        tool_result_events = [
            e for e in events if hasattr(e, 'tool_name') and e.tool_name == 'bash'
        ]
        
        assert len(tool_result_events) > 0, "No bash tool result event found"
        
        tool_result = tool_result_events[-1]
        assert tool_result.skipped, "Bash command should be skipped"
        assert tool_result.skip_reason is not None
        feedback = str(tool_result.skip_reason)
        assert "blocked by denylist" in feedback
        assert "git checkout" in feedback

    @pytest.mark.asyncio
    async def test_act_blocks_git_reset_hard_with_flags(
        self, agent_loop: AgentLoop
    ) -> None:
        """Test that act() blocks git reset --hard with additional flags."""
        # Create a mock response that includes a tool call for git reset --hard with flags
        tool_call = ToolCall(
            id="call_1",
            index=0,
            function=FunctionCall(name="bash", arguments='{"command": "git reset --hard -q","timeout":10}'),
        )
        
        backend = FakeBackend([
            mock_llm_chunk(content="Let me reset the repository", tool_calls=[tool_call]),
        ])
        
        agent_loop.backend = backend
        
        events = []
        async for event in agent_loop.act("Try to run git reset --hard -q"):
            events.append(event)
        
        # Find the tool result event
        tool_result_events = [
            e for e in events if hasattr(e, 'tool_name') and e.tool_name == 'bash'
        ]
        
        assert len(tool_result_events) > 0, "No bash tool result event found"
        
        tool_result = tool_result_events[-1]
        assert tool_result.skipped, "Bash command should be skipped"
        assert tool_result.skip_reason is not None
        feedback = str(tool_result.skip_reason)
        assert "blocked by denylist" in feedback
        assert "git reset --hard" in feedback

    @pytest.mark.asyncio
    async def test_act_blocks_editor_with_args(
        self, agent_loop: AgentLoop
    ) -> None:
        """Test that act() blocks editors with arguments."""
        # Create a mock response that includes a tool call for nano with args
        tool_call = ToolCall(
            id="call_1",
            index=0,
            function=FunctionCall(name="bash", arguments='{"command": "nano README.md","timeout":10}'),
        )
        
        backend = FakeBackend([
            mock_llm_chunk(content="Let me edit the README", tool_calls=[tool_call]),
        ])
        
        agent_loop.backend = backend
        
        events = []
        async for event in agent_loop.act("Try to run nano README.md"):
            events.append(event)
        
        # Find the tool result event
        tool_result_events = [
            e for e in events if hasattr(e, 'tool_name') and e.tool_name == 'bash'
        ]
        
        assert len(tool_result_events) > 0, "No bash tool result event found"
        
        tool_result = tool_result_events[-1]
        assert tool_result.skipped, "Bash command should be skipped"
        assert tool_result.skip_reason is not None
        feedback = str(tool_result.skip_reason)
        assert "blocked by denylist" in feedback
        assert "nano" in feedback
