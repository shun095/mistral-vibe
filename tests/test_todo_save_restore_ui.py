#!/usr/bin/env python3
"""
Test script to verify the new save/restore functionality works with UI and backend.
This script tests the new save and restore actions for todo lists.
"""

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from tests.stubs.fake_backend import FakeBackend
from vibe.core.agent import Agent
from vibe.core.config import ModelConfig, VibeConfig
from vibe.core.tools.builtins.todo import TodoArgs, TodoItem, TodoPriority, TodoStatus
from vibe.core.types import LLMChunk, LLMMessage, LLMUsage, Role


@pytest.mark.asyncio
async def test_todo_save_to_custom_file() -> None:
    """Test saving todos to a custom file location."""
    config = VibeConfig(
        active_model="devstral-latest",
        models=[
            ModelConfig(
                name="devstral-latest", provider="mistral", alias="devstral-latest"
            ),
        ],
        enabled_tools=["todo"],
    )
    
    backend = FakeBackend(
        LLMChunk(
            message=LLMMessage(role=Role.assistant, content="Done"),
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1),
        )
    )
    
    agent = Agent(config=config, backend=backend)
    todo_tool = agent.tool_manager.get("todo")
    
    # Create todos
    todos = [
        TodoItem(id="1", content="Save Test Task 1", status=TodoStatus.PENDING, priority=TodoPriority.HIGH),
        TodoItem(id="2", content="Save Test Task 2", status=TodoStatus.IN_PROGRESS, priority=TodoPriority.MEDIUM),
    ]
    
    await todo_tool.run(TodoArgs(action="write", todos=todos))
    
    # Save to a custom file
    with tempfile.TemporaryDirectory() as tmp_dir:
        save_file = Path(tmp_dir) / "custom_todos.json"
        result = await todo_tool.run(TodoArgs(action="save", session_file=str(save_file)))
        
        # Verify save was successful
        assert save_file.exists()
        assert result.message == f"Saved 2 todos to {save_file}"
        
        # Verify content
        with open(save_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        
        assert len(saved_data) == 2
        assert saved_data[0]["id"] == "1"
        assert saved_data[0]["content"] == "Save Test Task 1"
        assert saved_data[1]["id"] == "2"
        assert saved_data[1]["content"] == "Save Test Task 2"
    
    print("✓ Save to custom file test passed")


@pytest.mark.asyncio
async def test_todo_restore_from_custom_file() -> None:
    """Test restoring todos from a custom file location."""
    config = VibeConfig(
        active_model="devstral-latest",
        models=[
            ModelConfig(
                name="devstral-latest", provider="mistral", alias="devstral-latest"
            ),
        ],
        enabled_tools=["todo"],
    )
    
    backend = FakeBackend(
        LLMChunk(
            message=LLMMessage(role=Role.assistant, content="Done"),
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1),
        )
    )
    
    agent = Agent(config=config, backend=backend)
    todo_tool = agent.tool_manager.get("todo")
    
    # Create a test file
    with tempfile.TemporaryDirectory() as tmp_dir:
        save_file = Path(tmp_dir) / "restore_todos.json"
        test_data = [
            {"id": "1", "content": "Restore Test Task 1", "status": "pending", "priority": "high"},
            {"id": "2", "content": "Restore Test Task 2", "status": "in_progress", "priority": "medium"},
            {"id": "3", "content": "Restore Test Task 3", "status": "completed", "priority": "low"},
        ]
        
        with open(save_file, "w", encoding="utf-8") as f:
            json.dump(test_data, f)
        
        # Restore from the file
        result = await todo_tool.run(TodoArgs(action="restore", session_file=str(save_file)))
        
        # Verify restore was successful
        assert result.message == f"Restored 3 todos from {save_file}"
        
        # Verify todos are in the state
        read_result = await todo_tool.run(TodoArgs(action="read"))
        assert len(read_result.todos) == 3
        assert read_result.todos[0].content == "Restore Test Task 1"
        assert read_result.todos[1].content == "Restore Test Task 2"
        assert read_result.todos[2].content == "Restore Test Task 3"
    
    print("✓ Restore from custom file test passed")


@pytest.mark.asyncio
async def test_todo_save_restore_workflow() -> None:
    """Test a complete save-restore workflow."""
    config = VibeConfig(
        active_model="devstral-latest",
        models=[
            ModelConfig(
                name="devstral-latest", provider="mistral", alias="devstral-latest"
            ),
        ],
        enabled_tools=["todo"],
    )
    
    backend = FakeBackend(
        LLMChunk(
            message=LLMMessage(role=Role.assistant, content="Done"),
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1),
        )
    )
    
    agent = Agent(config=config, backend=backend)
    todo_tool = agent.tool_manager.get("todo")
    
    # Step 1: Create initial todos
    initial_todos = [
        TodoItem(id="1", content="Workflow Task 1", status=TodoStatus.PENDING, priority=TodoPriority.HIGH),
        TodoItem(id="2", content="Workflow Task 2", status=TodoStatus.IN_PROGRESS, priority=TodoPriority.MEDIUM),
        TodoItem(id="3", content="Workflow Task 3", status=TodoStatus.COMPLETED, priority=TodoPriority.LOW),
    ]
    
    await todo_tool.run(TodoArgs(action="write", todos=initial_todos))
    print("Step 1: Created initial todos")
    
    # Step 2: Save to file
    with tempfile.TemporaryDirectory() as tmp_dir:
        save_file = Path(tmp_dir) / "workflow_todos.json"
        save_result = await todo_tool.run(TodoArgs(action="save", session_file=str(save_file)))
        print(f"Step 2: Saved todos to {save_file}")
        
        # Step 3: Clear todos
        await todo_tool.run(TodoArgs(action="write", todos=[]))
        read_result = await todo_tool.run(TodoArgs(action="read"))
        assert len(read_result.todos) == 0
        print("Step 3: Cleared todos")
        
        # Step 4: Restore from file
        restore_result = await todo_tool.run(TodoArgs(action="restore", session_file=str(save_file)))
        print(f"Step 4: Restored todos from {save_file}")
        
        # Step 5: Verify restoration
        final_result = await todo_tool.run(TodoArgs(action="read"))
        assert len(final_result.todos) == 3
        
        for i, todo in enumerate(final_result.todos):
            assert todo.id == initial_todos[i].id
            assert todo.content == initial_todos[i].content
            assert todo.status == initial_todos[i].status
            assert todo.priority == initial_todos[i].priority
        
        print("Step 5: Verified all todos restored correctly")
    
    print("✓ Complete save-restore workflow test passed")


@pytest.mark.asyncio
async def test_todo_save_restore_with_ui_simulation() -> None:
    """Test save/restore functionality with UI-like simulation."""
    config = VibeConfig(
        active_model="devstral-latest",
        models=[
            ModelConfig(
                name="devstral-latest", provider="mistral", alias="devstral-latest"
            ),
        ],
        enabled_tools=["todo"],
    )
    
    backend = FakeBackend(
        LLMChunk(
            message=LLMMessage(role=Role.assistant, content="Done"),
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1),
        )
    )
    
    # Simulate first session
    print("=== Session 1: Creating and saving todos ===")
    agent1 = Agent(config=config, backend=backend)
    todo_tool1 = agent1.tool_manager.get("todo")
    
    # User creates todos in the UI
    ui_todos = [
        TodoItem(id="1", content="UI Task 1", status=TodoStatus.PENDING, priority=TodoPriority.HIGH),
        TodoItem(id="2", content="UI Task 2", status=TodoStatus.IN_PROGRESS, priority=TodoPriority.MEDIUM),
    ]
    
    await todo_tool1.run(TodoArgs(action="write", todos=ui_todos))
    print(f"Created {len(ui_todos)} todos")
    
    # User saves todos to a file (simulating "Save todos" button)
    with tempfile.TemporaryDirectory() as tmp_dir:
        save_file = Path(tmp_dir) / "ui_todos.json"
        save_result = await todo_tool1.run(TodoArgs(action="save", session_file=str(save_file)))
        print(f"Saved todos to {save_file}")
        
        # Simulate second session (new agent instance)
        print("\n=== Session 2: Restoring todos ===")
        agent2 = Agent(config=config, backend=backend)
        todo_tool2 = agent2.tool_manager.get("todo")
        
        # User restores todos from file (simulating "Load todos" button)
        restore_result = await todo_tool2.run(TodoArgs(action="restore", session_file=str(save_file)))
        print(f"Restored todos from {save_file}")
        
        # Verify todos are visible in the UI
        read_result = await todo_tool2.run(TodoArgs(action="read"))
        print(f"UI displays {len(read_result.todos)} todos:")
        for todo in read_result.todos:
            print(f"  - [{todo.status.value}] [{todo.priority.value}] {todo.content}")
        
        # Verify backend can access the restored todos
        print("\n=== Backend Access Verification ===")
        if hasattr(todo_tool2, 'state') and todo_tool2.state:
            print(f"Backend can access {len(todo_tool2.state.todos)} todos")
            for todo in todo_tool2.state.todos:
                print(f"  - {todo.content} ({todo.status.value})")
        
        # Verify the todos match what was saved
        assert len(read_result.todos) == 2
        assert read_result.todos[0].content == "UI Task 1"
        assert read_result.todos[1].content == "UI Task 2"
    
    print("\n✓ UI simulation test passed")


async def main():
    """Run all tests."""
    print("=" * 70)
    print("Testing Todo Save/Restore Functionality")
    print("=" * 70)
    print()
    
    print("TEST 1: Save to Custom File")
    print("-" * 70)
    await test_todo_save_to_custom_file()
    print()
    
    print("TEST 2: Restore from Custom File")
    print("-" * 70)
    await test_todo_restore_from_custom_file()
    print()
    
    print("TEST 3: Complete Save-Restore Workflow")
    print("-" * 70)
    await test_todo_save_restore_workflow()
    print()
    
    print("TEST 4: UI Simulation")
    print("-" * 70)
    await test_todo_save_restore_with_ui_simulation()
    print()
    
    print("=" * 70)
    print("✓ ALL SAVE/RESTORE TESTS PASSED!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())