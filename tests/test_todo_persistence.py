"""Test todo list persistence across sessions."""

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
async def test_todo_persistence_across_sessions(
    backend: FakeBackend, config_with_session_logging: VibeConfig, tmp_path: Path
) -> None:
    """Test that todo list is preserved when saving and restoring a session."""
    # Create first agent and add todos
    agent1 = Agent(config=config_with_session_logging, backend=backend)
    
    # Add some todos using the todo tool
    todo_tool = agent1.tool_manager.get("todo")
    
    # Write todos
    todos = [
        TodoItem(id="1", content="Test task 1", status=TodoStatus.PENDING, priority=TodoPriority.HIGH),
        TodoItem(id="2", content="Test task 2", status=TodoStatus.IN_PROGRESS, priority=TodoPriority.MEDIUM),
        TodoItem(id="3", content="Test task 3", status=TodoStatus.COMPLETED, priority=TodoPriority.LOW),
    ]
    
    # Directly set the state to avoid validation issues
    todo_tool.state.todos = todos
    
    # Verify the state was set by checking the state directly
    assert len(todo_tool.state.todos) == 3
    assert todo_tool.state.todos[0].content == "Test task 1"
    assert todo_tool.state.todos[1].content == "Test task 2"
    assert todo_tool.state.todos[2].content == "Test task 3"
    
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
    
    # Load the session file and verify tool states are saved
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
    
    # Create a new agent and restore the session
    messages, loaded_metadata = agent1.interaction_logger.load_session(session_file)
    
    agent2 = Agent(config=config_with_session_logging, backend=backend)
    
    # Restore tool states (simulating what the UI does)
    from vibe.cli.textual_ui.app import VibeApp
    
    # Manually restore the todo state
    if loaded_metadata and "tool_states" in loaded_metadata:
        tool_states = loaded_metadata["tool_states"]
        if "todo" in tool_states:
            todo_tool2 = agent2.tool_manager.get("todo")
            from vibe.core.tools.builtins.todo import TodoState
            restored_state = TodoState.model_validate(tool_states["todo"])
            todo_tool2.state = restored_state
    
    # Verify todos are restored by checking the state directly
    todo_tool2 = agent2.tool_manager.get("todo")
    assert len(todo_tool2.state.todos) == 3
    assert todo_tool2.state.todos[0].content == "Test task 1"
    assert todo_tool2.state.todos[0].status == TodoStatus.PENDING
    assert todo_tool2.state.todos[0].priority == TodoPriority.HIGH
    assert todo_tool2.state.todos[1].content == "Test task 2"
    assert todo_tool2.state.todos[1].status == TodoStatus.IN_PROGRESS
    assert todo_tool2.state.todos[1].priority == TodoPriority.MEDIUM
    assert todo_tool2.state.todos[2].content == "Test task 3"
    assert todo_tool2.state.todos[2].status == TodoStatus.COMPLETED
    assert todo_tool2.state.todos[2].priority == TodoPriority.LOW


@pytest.mark.asyncio
async def test_backward_compatibility_without_tool_states(
    backend: FakeBackend, config_with_session_logging: VibeConfig, tmp_path: Path
) -> None:
    """Test that sessions without tool_states still load correctly."""
    # Create a session file manually without tool_states
    session_dir = Path(config_with_session_logging.session_logging.save_dir)
    session_file = session_dir / "test_session_legacy.json"
    
    legacy_data = {
        "metadata": {
            "session_id": "test-session-id",
            "start_time": "2024-01-01T00:00:00",
            "end_time": "2024-01-01T01:00:00",
            "git_commit": None,
            "git_branch": None,
            "environment": {"working_directory": str(Path.cwd())},
            "auto_approve": False,
            "username": "testuser",
            "stats": {"steps": 0, "session_prompt_tokens": 0, "session_completion_tokens": 0},
            "total_messages": 0,
            "tools_available": [],
            "agent_config": config_with_session_logging.model_dump(mode="json"),
            # Note: no tool_states key
        },
        "messages": [],
    }
    
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(legacy_data, f, indent=2)
    
    # Create an agent to use its interaction_logger
    agent1 = Agent(config=config_with_session_logging, backend=backend)
    
    # Load the legacy session
    messages, metadata = agent1.interaction_logger.load_session(session_file)
    
    # Verify it loads without errors
    assert messages == []
    assert metadata is not None
    assert "tool_states" not in metadata  # Should not have tool_states
    
    # Create a new agent with the loaded metadata
    agent2 = Agent(config=config_with_session_logging, backend=backend)
    
    # This should not crash even though there are no tool_states
    from vibe.cli.textual_ui.app import VibeApp
    
    # Simulate the restoration logic from the UI
    if metadata and "tool_states" in metadata:
        # This block should not execute
        pass
    else:
        # This is the expected path for legacy sessions
        pass
    
    # Verify the agent works normally
    todo_tool = agent2.tool_manager.get("todo")
    read_result = await todo_tool.run(TodoArgs(action="read"))
    
    # Should start with empty todo list
    assert len(read_result.todos) == 0
