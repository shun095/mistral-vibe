from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import ClassVar

from pydantic import BaseModel, Field

from vibe.core.agent_loop import AgentLoop
from vibe.core.agents.models import AgentType
from vibe.core.config import SessionLoggingConfig, VibeConfig
from vibe.core.tools.base import (
    BaseTool,
    BaseToolConfig,
    BaseToolState,
    InvokeContext,
    ToolError,
    ToolPermission,
)
from vibe.core.tools.ui import (
    ToolCallDisplay,
    ToolResultDisplay,
    ToolUIData,
    ToolUIDataAdapter,
)
from vibe.core.types import (
    AssistantEvent,
    Role,
    ToolCallEvent,
    ToolResultEvent,
    ToolStreamEvent,
)


class TaskArgs(BaseModel):
    task: str = Field(description="The task to delegate to the subagent")
    agent: str = Field(
        default="explore",
        description="Name of the agent profile to use (must be a subagent)",
    )


class TaskResult(BaseModel):
    response: str = Field(description="The accumulated response from the subagent")
    turns_used: int = Field(description="Number of turns the subagent used")
    completed: bool = Field(description="Whether the task completed normally")


class TaskToolConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ASK
    max_retries: int = 3  # Maximum retry attempts for insufficient responses


class Task(
    BaseTool[TaskArgs, TaskResult, TaskToolConfig, BaseToolState],
    ToolUIData[TaskArgs, TaskResult],
):
    description: ClassVar[str] = (
        "Delegate a task to a subagent for independent execution. "
        "Useful for exploration, research, or parallel work that doesn't "
        "require user interaction. The subagent runs in-memory without "
        "saving interaction logs."
    )

    @classmethod
    def get_call_display(cls, event: ToolCallEvent) -> ToolCallDisplay:
        args = event.args
        if isinstance(args, TaskArgs):
            return ToolCallDisplay(summary=f"Running {args.agent} agent: {args.task}")
        return ToolCallDisplay(summary="Running subagent")

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        result = event.result
        if isinstance(result, TaskResult):
            turn_word = "turn" if result.turns_used == 1 else "turns"
            if not result.completed:
                return ToolResultDisplay(
                    success=False,
                    message=f"Agent interrupted after {result.turns_used} {turn_word}",
                )
            return ToolResultDisplay(
                success=True,
                message=f"Agent completed in {result.turns_used} {turn_word}",
            )
        return ToolResultDisplay(success=True, message="Agent completed")

    @classmethod
    def get_status_text(cls) -> str:
        return "Running subagent"

    def _is_response_complete(self, response: str) -> tuple[bool, str]:
        """Check if response is complete (not a single line)."""
        if not response or not response.strip():
            return False, "Response is empty. Please provide a comprehensive summary."
        
        # Check if response is a single line
        lines = response.strip().split('\n')
        if len(lines) == 1:
            return (
                False,
                "Response is too brief. Please provide a comprehensive summary "
                "with multiple paragraphs or bullet points."
            )
        
        return True, ""

    def _get_task_instruction(
        self, original_task: str, attempt: int, max_attempts: int
    ) -> str:
        """Get the task instruction for the subagent, with enhanced instructions for retries."""
        if attempt == 0:
            # First attempt - use original task
            return original_task
        
        # Subsequent attempts - add guidance
        return f"""
{original_task}

IMPORTANT: Your previous response was insufficient. Please provide a comprehensive summary with multiple paragraphs or bullet points. Include:
- What you accomplished
- Key findings or information discovered
- Any relevant code snippets, file contents, or details
- Recommendations or next steps if applicable
- Clear, actionable information for the main agent

This is attempt {attempt + 1} of {max_attempts}. Provide a complete multi-paragraph response.
"""

    async def run(
        self, args: TaskArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | TaskResult, None]:
        if not ctx or not ctx.agent_manager:
            raise ToolError("Task tool requires agent_manager in context")

        agent_manager = ctx.agent_manager

        try:
            agent_profile = agent_manager.get_agent(args.agent)
        except ValueError as e:
            raise ToolError(f"Unknown agent: {args.agent}") from e

        if agent_profile.agent_type != AgentType.SUBAGENT:
            raise ToolError(
                f"Agent '{args.agent}' is a {agent_profile.agent_type.value} agent. "
                f"Only subagents can be used with the task tool. "
                f"This is a security constraint to prevent recursive spawning."
            )

        # Create a single AgentLoop for the entire task
        base_config = VibeConfig.load(
            session_logging=SessionLoggingConfig(enabled=False)
        )
        subagent_loop = AgentLoop(config=base_config, agent_name=args.agent)

        if ctx and ctx.approval_callback:
            subagent_loop.set_approval_callback(ctx.approval_callback)

        attempt = 0
        
        # Main loop: continue until response is complete or max retries reached
        while attempt < self.config.max_retries:
            accumulated_response: list[str] = []
            completed = True
            
            # Determine task instruction based on attempt
            task_instruction = self._get_task_instruction(
                args.task, attempt, self.config.max_retries
            )
            
            try:
                # Run the agent loop for this attempt
                async for event in subagent_loop.act(task_instruction):
                    if isinstance(event, AssistantEvent) and event.content:
                        accumulated_response.append(event.content)
                        if event.stopped_by_middleware:
                            completed = False
                    elif isinstance(event, ToolResultEvent):
                        if event.skipped:
                            completed = False
                        elif event.result and event.tool_class:
                            adapter = ToolUIDataAdapter(event.tool_class)
                            display = adapter.get_result_display(event)
                            message = f"{event.tool_name}: {display.message}"
                            yield ToolStreamEvent(
                                tool_name=self.get_name(),
                                message=message,
                                tool_call_id=ctx.tool_call_id,
                            )
                
                turns_used = sum(
                    msg.role == Role.assistant for msg in subagent_loop.messages
                )

            except Exception as e:
                completed = False
                accumulated_response.append(f"\n[Subagent error: {e}]")
                turns_used = sum(
                    msg.role == Role.assistant for msg in subagent_loop.messages
                )
            
            # Get the concatenated response for validation
            concatenated_response = "".join(accumulated_response) if accumulated_response else ""
            
            # Validate response quality using the concatenated response
            is_complete, feedback = self._is_response_complete(concatenated_response)
            
            if is_complete:
                # Success! Return the result
                yield TaskResult(
                    response="".join(accumulated_response),
                    turns_used=turns_used,
                    completed=completed,
                )
                return
            
            # Response was insufficient, prepare for retry
            if attempt < self.config.max_retries - 1:
                # Yield feedback to user (but NOT TaskResult!)
                yield ToolStreamEvent(
                    tool_name=self.get_name(),
                    message=f"Subagent response was insufficient: {feedback}",
                    tool_call_id=ctx.tool_call_id,
                )
                # Continue to next iteration of retry loop
                attempt += 1
                continue
            
            # Last attempt failed - return incomplete result
            yield TaskResult(
                response="".join(accumulated_response),
                turns_used=turns_used,
                completed=False,
            )
            return
