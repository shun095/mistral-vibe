"""Tests for agent loop denylist enforcement, especially in auto-approve mode."""

from __future__ import annotations

import pytest

from vibe.core.agent_loop import AgentLoop, ToolExecutionResponse
from vibe.core.agents.models import BuiltinAgentName
from vibe.core.config import VibeConfig
from vibe.core.tools.builtins.bash import BashArgs


class TestAgentLoopDenylist:
    """Test that denylist is enforced even in auto-approve mode."""

    @pytest.fixture
    def config(self) -> VibeConfig:
        """Create a test config with auto_approve enabled."""
        return VibeConfig(auto_approve=True)

    @pytest.fixture
    def agent_loop(self, config: VibeConfig) -> AgentLoop:
        """Create an AgentLoop instance with auto-approve enabled."""
        return AgentLoop(config=config, agent_name=BuiltinAgentName.AUTO_APPROVE)

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_denylist_blocked_in_auto_approve_mode(
        self, agent_loop: AgentLoop
    ) -> None:
        """Test that denylisted commands are blocked even in auto-approve mode."""
        bash_tool = agent_loop.tool_manager.get("bash")
        
        # Test git checkout (denylisted command)
        args = BashArgs(command="git checkout main")
        decision = await agent_loop._should_execute_tool(
            bash_tool, args, "test-call-id"
        )
        
        assert decision.verdict == ToolExecutionResponse.SKIP
        assert decision.feedback is not None
        feedback = str(decision.feedback)
        assert "blocked by denylist" in feedback
        assert "git checkout" in feedback

    @pytest.mark.asyncio
    async def test_denylist_blocked_git_reset_hard(
        self, agent_loop: AgentLoop
    ) -> None:
        """Test that git reset --hard is blocked in auto-approve mode."""
        bash_tool = agent_loop.tool_manager.get("bash")
        
        args = BashArgs(command="git reset --hard")
        decision = await agent_loop._should_execute_tool(
            bash_tool, args, "test-call-id"
        )
        
        assert decision.verdict == ToolExecutionResponse.SKIP
        assert decision.feedback is not None
        feedback = str(decision.feedback)
        assert "blocked by denylist" in feedback
        assert "git reset --hard" in feedback

    @pytest.mark.asyncio
    async def test_denylist_blocked_editors(
        self, agent_loop: AgentLoop
    ) -> None:
        """Test that text editors are blocked in auto-approve mode."""
        bash_tool = agent_loop.tool_manager.get("bash")
        
        for editor_cmd in ["vim file.txt", "nano file.txt", "emacs file.txt"]:
            args = BashArgs(command=editor_cmd)
            decision = await agent_loop._should_execute_tool(
                bash_tool, args, "test-call-id"
            )
            
            assert decision.verdict == ToolExecutionResponse.SKIP
            assert decision.feedback is not None
            feedback = str(decision.feedback)
            assert "blocked by denylist" in feedback

    @pytest.mark.asyncio
    async def test_denylist_blocked_shells(
        self, agent_loop: AgentLoop
    ) -> None:
        """Test that interactive shells are blocked in auto-approve mode."""
        bash_tool = agent_loop.tool_manager.get("bash")
        
        for shell_cmd in ["bash -i", "sh -i", "zsh -i"]:
            args = BashArgs(command=shell_cmd)
            decision = await agent_loop._should_execute_tool(
                bash_tool, args, "test-call-id"
            )
            
            assert decision.verdict == ToolExecutionResponse.SKIP
            assert decision.feedback is not None
            feedback = str(decision.feedback)
            assert "blocked by denylist" in feedback

    @pytest.mark.asyncio
    async def test_allowlist_bypasses_denylist_in_auto_approve(
        self, agent_loop: AgentLoop
    ) -> None:
        """Test that allowlisted commands are executed even in auto-approve mode."""
        bash_tool = agent_loop.tool_manager.get("bash")
        
        # Test allowlisted commands (safe commands)
        for safe_cmd in ["echo hello", "pwd", "ls", "git status"]:
            args = BashArgs(command=safe_cmd)
            decision = await agent_loop._should_execute_tool(
                bash_tool, args, "test-call-id"
            )
            
            assert decision.verdict == ToolExecutionResponse.EXECUTE

    @pytest.mark.asyncio
    async def test_auto_approve_still_works_for_allowed_commands(
        self, agent_loop: AgentLoop
    ) -> None:
        """Test that auto-approve mode still auto-approves non-denylisted commands."""
        bash_tool = agent_loop.tool_manager.get("bash")
        
        # Commands that are not in allowlist or denylist should be auto-approved
        # (since auto_approve is True)
        args = BashArgs(command="cat README.md")
        decision = await agent_loop._should_execute_tool(
            bash_tool, args, "test-call-id"
        )
        
        # Should be executed (auto-approved) since it's not denylisted
        assert decision.verdict == ToolExecutionResponse.EXECUTE

    @pytest.mark.asyncio
    async def test_denylist_pattern_matching_in_auto_approve(
        self, agent_loop: AgentLoop
    ) -> None:
        """Test that denylist pattern matching works correctly in auto-approve mode."""
        bash_tool = agent_loop.tool_manager.get("bash")
        
        # Test that variations of denylisted commands are blocked
        denylisted_commands = [
            "git checkout main",
            "git checkout -b feature",
            "git checkout file.txt",
            "git reset --hard HEAD",
        ]
        
        for cmd in denylisted_commands:
            args = BashArgs(command=cmd)
            decision = await agent_loop._should_execute_tool(
                bash_tool, args, "test-call-id"
            )
            
            assert decision.verdict == ToolExecutionResponse.SKIP
            assert decision.feedback is not None
            feedback = str(decision.feedback)
            assert "blocked by denylist" in feedback


class TestAgentLoopNormalMode:
    """Test that denylist works correctly in normal (non-auto-approve) mode."""

    @pytest.fixture
    def config(self) -> VibeConfig:
        """Create a test config with auto_approve disabled."""
        return VibeConfig(auto_approve=False)

    @pytest.fixture
    def agent_loop(self, config: VibeConfig) -> AgentLoop:
        """Create an AgentLoop instance with auto-approve disabled."""
        return AgentLoop(config=config, agent_name=BuiltinAgentName.DEFAULT)

    @pytest.mark.asyncio
    async def test_denylist_blocked_in_normal_mode(
        self, agent_loop: AgentLoop
    ) -> None:
        """Test that denylisted commands are blocked in normal mode."""
        bash_tool = agent_loop.tool_manager.get("bash")
        
        args = BashArgs(command="git checkout main")
        decision = await agent_loop._should_execute_tool(
            bash_tool, args, "test-call-id"
        )
        
        assert decision.verdict == ToolExecutionResponse.SKIP
        assert decision.feedback is not None
        feedback = str(decision.feedback)
        assert "blocked by denylist" in feedback

    @pytest.mark.asyncio
    async def test_normal_mode_requires_approval_for_non_denylisted(
        self, agent_loop: AgentLoop
    ) -> None:
        """Test that normal mode requires approval for non-denylisted commands."""
        bash_tool = agent_loop.tool_manager.get("bash")
        
        # Test with a command that's not in allowlist or denylist
        # Without setting up an approval callback, this should skip
        args = BashArgs(command="date +%Y-%m-%d")
        decision = await agent_loop._should_execute_tool(
            bash_tool, args, "test-call-id"
        )
        
        # Should skip because no approval callback is set
        assert decision.verdict == ToolExecutionResponse.SKIP


class TestDenylistPrecedence:
    """Test that denylist takes precedence over all other checks."""

    @pytest.fixture
    def config(self) -> VibeConfig:
        """Create a test config with auto_approve enabled and bash permission set to ALWAYS."""
        from vibe.core.tools.builtins.bash import BashToolConfig
        from vibe.core.tools.base import ToolPermission
        
        bash_config = BashToolConfig(permission=ToolPermission.ALWAYS)
        return VibeConfig(
            auto_approve=True,
            tools={"bash": bash_config}
        )

    @pytest.fixture
    def agent_loop(self, config: VibeConfig) -> AgentLoop:
        """Create an AgentLoop instance with auto-approve and always permission."""
        return AgentLoop(config=config, agent_name=BuiltinAgentName.AUTO_APPROVE)

    @pytest.mark.asyncio
    async def test_denylist_takes_precedence_over_auto_approve(
        self, agent_loop: AgentLoop
    ) -> None:
        """Test that denylist blocks commands even with auto_approve=True."""
        bash_tool = agent_loop.tool_manager.get("bash")
        
        # Even though auto_approve is True and bash permission is ALWAYS,
        # denylisted commands should still be blocked
        args = BashArgs(command="git checkout main")
        decision = await agent_loop._should_execute_tool(
            bash_tool, args, "test-call-id"
        )
        
        assert decision.verdict == ToolExecutionResponse.SKIP
        assert decision.feedback is not None
        feedback = str(decision.feedback)
        assert "blocked by denylist" in feedback

    @pytest.mark.asyncio
    async def test_denylist_takes_precedence_over_always_permission(
        self, agent_loop: AgentLoop
    ) -> None:
        """Test that denylist blocks commands even with permission=ALWAYS."""
        bash_tool = agent_loop.tool_manager.get("bash")
        
        # The tool config has permission=ALWAYS, but denylist should still block
        args = BashArgs(command="git reset --hard")
        decision = await agent_loop._should_execute_tool(
            bash_tool, args, "test-call-id"
        )
        
        assert decision.verdict == ToolExecutionResponse.SKIP
        assert decision.feedback is not None
        feedback = str(decision.feedback)
        assert "blocked by denylist" in feedback

    @pytest.mark.asyncio
    async def test_allowlist_bypasses_all_checks(
        self, agent_loop: AgentLoop
    ) -> None:
        """Test that allowlisted commands bypass all checks including permission."""
        bash_tool = agent_loop.tool_manager.get("bash")
        
        # Allowlisted commands should execute even with denylist checks
        args = BashArgs(command="echo hello")
        decision = await agent_loop._should_execute_tool(
            bash_tool, args, "test-call-id"
        )
        
        assert decision.verdict == ToolExecutionResponse.EXECUTE
