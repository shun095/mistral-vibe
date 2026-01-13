from __future__ import annotations

import asyncio
from typing import Any

from vibe.core.agent_loop import AgentLoop
from vibe.core.agents.models import BuiltinAgentName
from vibe.core.config import VibeConfig
from vibe.core.output_formatters import create_formatter
from vibe.core.tools.builtins.todo import TodoItem, TodoState
from vibe.core.types import AssistantEvent, LLMMessage, OutputFormat, Role
from vibe.core.utils import ConversationLimitException, logger


def run_programmatic(
    config: VibeConfig,
    prompt: str,
    max_turns: int | None = None,
    max_price: float | None = None,
    output_format: OutputFormat = OutputFormat.TEXT,
    previous_messages: list[LLMMessage] | None = None,
    agent_name: str = BuiltinAgentName.AUTO_APPROVE,
) -> str | None:
    formatter = create_formatter(output_format)

    agent_loop = AgentLoop(
        config,
        agent_name=agent_name,
        message_observer=formatter.on_message_added,
        max_turns=max_turns,
        max_price=max_price,
        enable_streaming=False,
    )
    logger.info("USER: %s", prompt)

    async def _async_run() -> str | None:
        if previous_messages:
            non_system_messages = [
                msg for msg in previous_messages if not (msg.role == Role.system)
            ]
            agent_loop.messages.extend(non_system_messages)
            logger.info(
                "Loaded %d messages from previous session", len(non_system_messages)
            )

        async for event in agent_loop.act(prompt):
            formatter.on_event(event)
            if isinstance(event, AssistantEvent) and event.stopped_by_middleware:
                raise ConversationLimitException(event.content)

        return formatter.finalize()

    return asyncio.run(_async_run())


async def _restore_tool_states(agent: Agent, tool_states: dict[str, Any]) -> None:
    """Restore tool states from session metadata."""
    for tool_name, state_data in tool_states.items():
        try:
            tool_instance = agent.tool_manager.get(tool_name)
            if hasattr(tool_instance, 'state'):
                # Handle todo tool state specifically
                if tool_name == "todo" and isinstance(state_data, dict):
                    todos_data = state_data.get("todos", [])
                    todos = [TodoItem.model_validate(todo_data) for todo_data in todos_data]
                    tool_instance.state = TodoState(todos=todos)
                    logger.info(f"Restored {len(todos)} todos for tool: {tool_name}")
                else:
                    # For other tools, try to restore state using model_validate
                    state_class = type(tool_instance.state)
                    restored_state = state_class.model_validate(state_data)
                    tool_instance.state = restored_state
                    logger.info(f"Restored state for tool: {tool_name}")
        except Exception as e:
            logger.warning(f"Failed to restore state for tool {tool_name}: {e}")
