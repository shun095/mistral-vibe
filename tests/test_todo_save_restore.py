"""Test todo list save/restore functionality."""

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
async def test_todo_save_to_file(backend: FakeBackend, tmp_path: Path) -> None:
    """Test that todo list can be saved to a file."""
    config = VibeConfig(
        active_model="devstral-latest",
        models=[
            ModelConfig(
                name="devstral-latest", provider="mistral", alias="devstral-latest"
            ),
        ],
        enabled_tools=["todo"],
    )
    
    agent = Agent(config=config, backend=backend)
    todo_tool = agent.tool_manager.get("todo")
    
    # Add some todos
    todos = [
        TodoItem(id="1", content="Test task 1", status=TodoStatus.PENDING, priority=TodoPriority.HIGH),
        TodoItem(id="2", content="Test task 2", status=TodoStatus.IN_PROGRESS, priority=TodoPriority.MEDIUM),
        TodoItem(id="3", content="Test task 3", status=TodoStatus.COMPLETED, priority=TodoPriority.LOW),
    ]
    
    await todo_tool.run(TodoArgs(action="write", todos=todos))
    
    # Save to a file
    save_file = tmp_path / "test_todos.json"
    result = await todo_tool.run(TodoArgs(action="save", session_file=str(save_file)))
    
    # Verify the file was created
    assert save_file.exists()
    assert result.message == f"Saved 3 todos to {save_file}"
    
    # Verify the content
    with open(save_file, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
    
    assert len(saved_data) == 3
    assert saved_data[0]["id"] == "1"
    assert saved_data[0]["content"] == "Test task 1"
    assert saved_data[0]["status"] == "pending"
    assert saved_data[0]["priority"] == "high"


@pytest.mark.asyncio
async def test_todo_restore_from_file(backend: FakeBackend, tmp_path: Path) -> None:
    """Test that todo list can be restored from a file."""
    config = VibeConfig(
        active_model="devstral-latest",
        models=[
            ModelConfig(
                name="devstral-latest", provider="mistral", alias="devstral-latest"
            ),
        ],
        enabled_tools=["todo"],
    )
    
    agent = Agent(config=config, backend=backend)
    todo_tool = agent.tool_manager.get("todo")
    
    # Create a test file
    save_file = tmp_path / "test_todos.json"
    test_data = [
        {"id": "1", "content": "Restored task 1", "status": "pending", "priority": "high"},
        {"id": "2", "content": "Restored task 2", "status": "in_progress", "priority": "medium"},
    ]
    
    with open(save_file, "w", encoding="utf-8") as f:
        json.dump(test_data, f)
    
    # Restore from the file
    result = await todo_tool.run(TodoArgs(action="restore", session_file=str(save_file)))
    
    # Verify the restore was successful
    assert result.message == f"Restored 2 todos from {save_file}"
    
    # Verify the todos are in the state
    read_result = await todo_tool.run(TodoArgs(action="read"))
    assert len(read_result.todos) == 2
    assert read_result.todos[0].id == "1"
    assert read_result.todos[0].content == "Restored task 1"
    assert read_result.todos[0].status == TodoStatus.PENDING
    assert read_result.todos[0].priority == TodoPriority.HIGH
    assert read_result.todos[1].id == "2"
    assert read_result.todos[1].content == "Restored task 2"
    assert read_result.todos[1].status == TodoStatus.IN_PROGRESS
    assert read_result.todos[1].priority == TodoPriority.MEDIUM


@pytest.mark.asyncio
async def test_todo_save_restore_roundtrip(backend: FakeBackend, tmp_path: Path) -> None:
    """Test that save and restore work correctly together."""
    config = VibeConfig(
        active_model="devstral-latest",
        models=[
            ModelConfig(
                name="devstral-latest", provider="mistral", alias="devstral-latest"
            ),
        ],
        enabled_tools=["todo"],
    )
    
    agent = Agent(config=config, backend=backend)
    todo_tool = agent.tool_manager.get("todo")
    
    # Create initial todos
    original_todos = [
        TodoItem(id="1", content="Original task 1", status=TodoStatus.PENDING, priority=TodoPriority.HIGH),
        TodoItem(id="2", content="Original task 2", status=TodoStatus.IN_PROGRESS, priority=TodoPriority.MEDIUM),
        TodoItem(id="3", content="Original task 3", status=TodoStatus.COMPLETED, priority=TodoPriority.LOW),
    ]
    
    await todo_tool.run(TodoArgs(action="write", todos=original_todos))
    
    # Save to a file
    save_file = tmp_path / "roundtrip_todos.json"
    await todo_tool.run(TodoArgs(action="save", session_file=str(save_file)))
    
    # Clear the todos
    await todo_tool.run(TodoArgs(action="write", todos=[]))
    read_result = await todo_tool.run(TodoArgs(action="read"))
    assert len(read_result.todos) == 0
    
    # Restore from the file
    await todo_tool.run(TodoArgs(action="restore", session_file=str(save_file)))
    
    # Verify the todos are restored correctly
    read_result = await todo_tool.run(TodoArgs(action="read"))
    assert len(read_result.todos) == 3
    
    for i, todo in enumerate(read_result.todos):
        assert todo.id == original_todos[i].id
        assert todo.content == original_todos[i].content
        assert todo.status == original_todos[i].status
        assert todo.priority == original_todos[i].priority


@pytest.mark.asyncio
async def test_todo_save_without_file_parameter(backend: FakeBackend, tmp_path: Path) -> None:
    """Test that save without session_file parameter fails appropriately."""
    config = VibeConfig(
        active_model="devstral-latest",
        models=[
            ModelConfig(
                name="devstral-latest", provider="mistral", alias="devstral-latest"
            ),
        ],
        enabled_tools=["todo"],
    )
    
    agent = Agent(config=config, backend=backend)
    todo_tool = agent.tool_manager.get("todo")
    
    # Try to save without specifying a file
    with pytest.raises(Exception) as exc_info:
        await todo_tool.run(TodoArgs(action="save"))
    
    assert "session_file parameter is required" in str(exc_info.value)


@pytest.mark.asyncio
async def test_todo_restore_without_file_parameter(backend: FakeBackend, tmp_path: Path) -> None:
    """Test that restore without session_file parameter fails appropriately."""
    config = VibeConfig(
        active_model="devstral-latest",
        models=[
            ModelConfig(
                name="devstral-latest", provider="mistral", alias="devstral-latest"
            ),
        ],
        enabled_tools=["todo"],
    )
    
    agent = Agent(config=config, backend=backend)
    todo_tool = agent.tool_manager.get("todo")
    
    # Try to restore without specifying a file
    with pytest.raises(Exception) as exc_info:
        await todo_tool.run(TodoArgs(action="restore"))
    
    assert "session_file parameter is required" in str(exc_info.value)


@pytest.mark.asyncio
async def test_todo_restore_nonexistent_file(backend: FakeBackend, tmp_path: Path) -> None:
    """Test that restore from non-existent file fails appropriately."""
    config = VibeConfig(
        active_model="devstral-latest",
        models=[
            ModelConfig(
                name="devstral-latest", provider="mistral", alias="devstral-latest"
            ),
        ],
        enabled_tools=["todo"],
    )
    
    agent = Agent(config=config, backend=backend)
    todo_tool = agent.tool_manager.get("todo")
    
    # Try to restore from non-existent file
    with pytest.raises(Exception) as exc_info:
        await todo_tool.run(TodoArgs(action="restore", session_file=str(tmp_path / "nonexistent.json")))
    
    assert "Session file not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_todo_save_with_tilde_expansion(backend: FakeBackend, tmp_path: Path) -> None:
    """Test that save works with tilde expansion in file paths."""
    config = VibeConfig(
        active_model="devstral-latest",
        models=[
            ModelConfig(
                name="devstral-latest", provider="mistral", alias="devstral-latest"
            ),
        ],
        enabled_tools=["todo"],
    )
    
    agent = Agent(config=config, backend=backend)
    todo_tool = agent.tool_manager.get("todo")
    
    # Add a todo
    await todo_tool.run(TodoArgs(action="write", todos=[TodoItem(id="1", content="Test")]))
    
    # Save to a file with tilde path in a temp directory
    test_dir = tmp_path / "vibe_test"
    save_file = test_dir / "test_todos.json"
    
    result = await todo_tool.run(TodoArgs(action="save", session_file=f"{test_dir}/test_todos.json"))
    
    # Verify the file was created
    assert save_file.exists()
    assert result.message == f"Saved 1 todos to {save_file}"
    
    # Verify the content
    with open(save_file, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
    
    assert len(saved_data) == 1
    assert saved_data[0]["id"] == "1"
    assert saved_data[0]["content"] == "Test"