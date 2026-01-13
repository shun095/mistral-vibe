"""Comprehensive test for todo list persistence across sessions."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from tests.stubs.fake_backend import FakeBackend
from vibe.core.agent import Agent
from vibe.core.config import ModelConfig, SessionLoggingConfig, VibeConfig
from vibe.core.tools.builtins.todo import TodoArgs, TodoItem, TodoPriority, TodoStatus
from vibe.core.types import LLMChunk, LLMMessage, LLMUsage, Role


@pytest.fixture
def backend() -> FakeBackend:
    """Create a fake backend for testing."""
    backend = FakeBackend(
        LLMChunk(
            message=LLMMessage(role=Role.assistant, content="Done"),
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1),
        )
    )
    return backend


@pytest.fixture
def config_with_session_logging(tmp_path: Path) -> VibeConfig:
    """Create a config with session logging enabled."""
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()
    
    return VibeConfig(
        active_model="devstral-latest",
        models=[
            ModelConfig(
                name="devstral-latest", provider="mistral", alias="devstral-latest"
            ),
        ],
        session_logging=SessionLoggingConfig(
            enabled=True,
            save_dir=str(session_dir),
            session_prefix="test_session",
        ),
        enabled_tools=["todo"],
    )


@pytest.mark.asyncio
async def test_todo_persistence_end_to_end(
    backend: FakeBackend, config_with_session_logging: VibeConfig, tmp_path: Path
) -> None:
    """Test complete end-to-end todo persistence workflow."""
    
    # Step 1: Create first agent and add todos using the todo tool API
    agent1 = Agent(config=config_with_session_logging, backend=backend)
    todo_tool1 = agent1.tool_manager.get("todo")
    
    # Write initial todos
    initial_todos = [
        TodoItem(id="1", content="Test task 1", status=TodoStatus.PENDING, priority=TodoPriority.HIGH),
        TodoItem(id="2", content="Test task 2", status=TodoStatus.IN_PROGRESS, priority=TodoPriority.MEDIUM),
        TodoItem(id="3", content="Test task 3", status=TodoStatus.COMPLETED, priority=TodoPriority.LOW),
    ]
    
    result1 = await todo_tool1.run(TodoArgs(action="write", todos=initial_todos))
    assert len(result1.todos) == 3
    assert result1.todos[0].content == "Test task 1"
    
    # Step 2: Save the session
    await agent1.interaction_logger.save_interaction(
        agent1.messages,
        agent1.stats,
        agent1.config,
        agent1.tool_manager,
    )
    
    # Find the saved session file
    session_files = list(Path(config_with_session_logging.session_logging.save_dir).glob("test_session_*.json"))
    assert len(session_files) == 1
    session_file = session_files[0]
    
    # Step 3: Verify tool states are saved in the session file
    with open(session_file, "r", encoding="utf-8") as f:
        session_data = json.load(f)
    
    metadata = session_data["metadata"]
    assert "tool_states" in metadata
    assert "todo" in metadata["tool_states"]
    
    saved_todo_state = metadata["tool_states"]["todo"]
    assert "todos" in saved_todo_state
    assert len(saved_todo_state["todos"]) == 3
    assert saved_todo_state["todos"][0]["content"] == "Test task 1"
    assert saved_todo_state["todos"][0]["status"] == "pending"
    assert saved_todo_state["todos"][0]["priority"] == "high"
    
    # Step 4: Create a new agent and restore the session using the same method as the UI
    messages, loaded_metadata = agent1.interaction_logger.load_session(session_file)
    
    agent2 = Agent(config=config_with_session_logging, backend=backend)
    
    # Step 5: Restore tool states using the same method as the UI
    if loaded_metadata and "tool_states" in loaded_metadata:
        tool_states = loaded_metadata["tool_states"]
        if "todo" in tool_states:
            todo_tool2 = agent2.tool_manager.get("todo")
            from vibe.core.tools.builtins.todo import TodoState
            restored_state = TodoState.model_validate(tool_states["todo"])
            todo_tool2.state = restored_state
    
    # Step 6: Verify todos are restored by using the todo tool API
    todo_tool2 = agent2.tool_manager.get("todo")
    read_result = await todo_tool2.run(TodoArgs(action="read"))
    
    # Verify all todos are restored correctly
    assert len(read_result.todos) == 3
    assert read_result.todos[0].content == "Test task 1"
    assert read_result.todos[0].status == TodoStatus.PENDING
    assert read_result.todos[0].priority == TodoPriority.HIGH
    assert read_result.todos[1].content == "Test task 2"
    assert read_result.todos[1].status == TodoStatus.IN_PROGRESS
    assert read_result.todos[1].priority == TodoPriority.MEDIUM
    assert read_result.todos[2].content == "Test task 3"
    assert read_result.todos[2].status == TodoStatus.COMPLETED
    assert read_result.todos[2].priority == TodoPriority.LOW
    
    # Step 7: Modify todos in the second agent and save again
    modified_todos = [
        TodoItem(id="1", content="Test task 1", status=TodoStatus.COMPLETED, priority=TodoPriority.HIGH),
        TodoItem(id="2", content="Test task 2", status=TodoStatus.COMPLETED, priority=TodoPriority.MEDIUM),
        TodoItem(id="3", content="Test task 3", status=TodoStatus.COMPLETED, priority=TodoPriority.LOW),
        TodoItem(id="4", content="New task", status=TodoStatus.PENDING, priority=TodoPriority.HIGH),
    ]
    
    result2 = await todo_tool2.run(TodoArgs(action="write", todos=modified_todos))
    assert len(result2.todos) == 4
    
    # Save the modified session
    await agent2.interaction_logger.save_interaction(
        agent2.messages,
        agent2.stats,
        agent2.config,
        agent2.tool_manager,
    )
    
    # Step 8: Create a third agent and restore the modified session
    agent3 = Agent(config=config_with_session_logging, backend=backend)

    # Find the modified session file (agent2 created a new one with a different timestamp)
    session_files = list(Path(config_with_session_logging.session_logging.save_dir).glob("test_session_*.json"))
    assert len(session_files) == 2  # One from agent1, one from agent2
    # Get the most recent file (agent2's save)
    session_file = max(session_files, key=lambda p: p.stat().st_mtime)

    messages3, loaded_metadata3 = agent1.interaction_logger.load_session(session_file)
    
    # Restore tool states
    if loaded_metadata3 and "tool_states" in loaded_metadata3:
        tool_states3 = loaded_metadata3["tool_states"]
        if "todo" in tool_states3:
            todo_tool3 = agent3.tool_manager.get("todo")
            from vibe.core.tools.builtins.todo import TodoState
            restored_state3 = TodoState.model_validate(tool_states3["todo"])
            todo_tool3.state = restored_state3
    
    # Step 9: Verify the modified todos are restored
    todo_tool3 = agent3.tool_manager.get("todo")
    read_result3 = await todo_tool3.run(TodoArgs(action="read"))
    
    assert len(read_result3.todos) == 4
    assert read_result3.todos[3].content == "New task"
    assert read_result3.todos[3].status == TodoStatus.PENDING
    assert read_result3.todos[3].priority == TodoPriority.HIGH


@pytest.mark.asyncio
async def test_todo_persistence_with_programmatic_api(
    backend: FakeBackend, config_with_session_logging: VibeConfig, tmp_path: Path
) -> None:
    """Test todo persistence using the programmatic API."""
    from vibe.core.programmatic import _restore_tool_states
    
    # Create first agent and add todos
    agent1 = Agent(config=config_with_session_logging, backend=backend)
    todo_tool1 = agent1.tool_manager.get("todo")
    
    # Write initial todos
    initial_todos = [
        TodoItem(id="1", content="Programmatic task 1", status=TodoStatus.PENDING, priority=TodoPriority.HIGH),
        TodoItem(id="2", content="Programmatic task 2", status=TodoStatus.IN_PROGRESS, priority=TodoPriority.MEDIUM),
    ]
    
    result1 = await todo_tool1.run(TodoArgs(action="write", todos=initial_todos))
    assert len(result1.todos) == 2
    
    # Save the session
    await agent1.interaction_logger.save_interaction(
        agent1.messages,
        agent1.stats,
        agent1.config,
        agent1.tool_manager,
    )
    
    # Find the saved session file
    session_files = list(Path(config_with_session_logging.session_logging.save_dir).glob("test_session_*.json"))
    assert len(session_files) == 1
    session_file = session_files[0]
    
    # Load the session
    messages, loaded_metadata = agent1.interaction_logger.load_session(session_file)
    
    # Create a new agent
    agent2 = Agent(config=config_with_session_logging, backend=backend)
    
    # Restore tool states using the programmatic API function
    if loaded_metadata and "tool_states" in loaded_metadata:
        await _restore_tool_states(agent2, loaded_metadata["tool_states"])
    
    # Verify todos are restored
    todo_tool2 = agent2.tool_manager.get("todo")
    read_result = await todo_tool2.run(TodoArgs(action="read"))
    
    assert len(read_result.todos) == 2
    assert read_result.todos[0].content == "Programmatic task 1"
    assert read_result.todos[0].status == TodoStatus.PENDING
    assert read_result.todos[0].priority == TodoPriority.HIGH
    assert read_result.todos[1].content == "Programmatic task 2"
    assert read_result.todos[1].status == TodoStatus.IN_PROGRESS
    assert read_result.todos[1].priority == TodoPriority.MEDIUM