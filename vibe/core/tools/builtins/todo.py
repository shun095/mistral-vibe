from __future__ import annotations

from enum import StrEnum, auto
from pathlib import Path
from typing import ClassVar
import json

from pydantic import BaseModel, Field

from vibe.core.tools.base import (
    BaseTool,
    BaseToolConfig,
    BaseToolState,
    ToolError,
    ToolPermission,
)
from vibe.core.tools.ui import ToolCallDisplay, ToolResultDisplay, ToolUIData
from vibe.core.types import ToolCallEvent, ToolResultEvent


class TodoStatus(StrEnum):
    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    CANCELLED = auto()


class TodoPriority(StrEnum):
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()


class TodoItem(BaseModel):
    id: str
    content: str
    status: TodoStatus = TodoStatus.PENDING
    priority: TodoPriority = TodoPriority.MEDIUM


class TodoArgs(BaseModel):
    action: str = Field(description="Either 'read', 'write', 'save', or 'restore'")
    todos: list[TodoItem] | None = Field(
        default=None, description="Complete list of todos when writing."
    )
    session_file: str | None = Field(
        default=None, description="Session file path for save/restore operations."
    )


class TodoResult(BaseModel):
    message: str
    todos: list[TodoItem]
    total_count: int


class TodoConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ALWAYS
    max_todos: int = 100


class TodoState(BaseToolState):
    todos: list[TodoItem] = Field(default_factory=list)


class Todo(
    BaseTool[TodoArgs, TodoResult, TodoConfig, TodoState],
    ToolUIData[TodoArgs, TodoResult],
):
    description: ClassVar[str] = (
        "Manage todos. Use action='read' to view, action='write' with complete list to update. "
        "Use action='save' to save todos to a session file, action='restore' to load todos from a session file."
    )

    @classmethod
    def get_call_display(cls, event: ToolCallEvent) -> ToolCallDisplay:
        if not isinstance(event.args, TodoArgs):
            return ToolCallDisplay(summary="Invalid arguments")

        args = event.args

        match args.action:
            case "read":
                return ToolCallDisplay(summary="Reading todos")
            case "write":
                count = len(args.todos) if args.todos else 0
                return ToolCallDisplay(summary=f"Writing {count} todos")
            case "save":
                return ToolCallDisplay(summary=f"Saving todos to {args.session_file}")
            case "restore":
                return ToolCallDisplay(summary=f"Restoring todos from {args.session_file}")
            case _:
                return ToolCallDisplay(summary=f"Unknown action: {args.action}")

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if not isinstance(event.result, TodoResult):
            return ToolResultDisplay(success=True, message="Success")

        result = event.result

        return ToolResultDisplay(success=True, message=result.message)

    @classmethod
    def get_status_text(cls) -> str:
        return "Managing todos"

    async def run(self, args: TodoArgs) -> TodoResult:
        match args.action:
            case "read":
                return self._read_todos()
            case "write":
                return self._write_todos(args.todos or [])
            case "save":
                return self._save_todos(args.session_file)
            case "restore":
                return self._restore_todos(args.session_file)
            case _:
                raise ToolError(
                    f"Invalid action '{args.action}'. Use 'read', 'write', 'save', or 'restore'."
                )

    def _read_todos(self) -> TodoResult:
        return TodoResult(
            message=f"Retrieved {len(self.state.todos)} todos",
            todos=[todo.model_dump() for todo in self.state.todos],
            total_count=len(self.state.todos),
        )

    def _write_todos(self, todos: list[TodoItem]) -> TodoResult:
        if len(todos) > self.config.max_todos:
            raise ToolError(f"Cannot store more than {self.config.max_todos} todos")

        ids = [todo.id for todo in todos]
        if len(ids) != len(set(ids)):
            raise ToolError("Todo IDs must be unique")

        self.state.todos = todos

        return TodoResult(
            message=f"Updated {len(todos)} todos",
            todos=[todo.model_dump() for todo in self.state.todos],
            total_count=len(self.state.todos),
        )

    def _save_todos(self, session_file: str | None) -> TodoResult:
        if not session_file:
            raise ToolError("session_file parameter is required for save action")

        try:
            filepath = Path(session_file).expanduser().resolve()
            filepath.parent.mkdir(parents=True, exist_ok=True)

            todos_data = [todo.model_dump() for todo in self.state.todos]
            json_content = json.dumps(todos_data, indent=2, ensure_ascii=False)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(json_content)

            return TodoResult(
                message=f"Saved {len(self.state.todos)} todos to {filepath}",
                todos=[todo.model_dump() for todo in self.state.todos],
                total_count=len(self.state.todos),
            )
        except Exception as e:
            raise ToolError(f"Failed to save todos: {e}")

    def _restore_todos(self, session_file: str | None) -> TodoResult:
        if not session_file:
            raise ToolError("session_file parameter is required for restore action")

        try:
            filepath = Path(session_file).expanduser().resolve()

            if not filepath.exists():
                raise ToolError(f"Session file not found: {filepath}")

            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            data = json.loads(content)
            todos = [TodoItem.model_validate(todo_data) for todo_data in data]

            # Validate the restored todos
            if len(todos) > self.config.max_todos:
                raise ToolError(f"Cannot restore more than {self.config.max_todos} todos")

            ids = [todo.id for todo in todos]
            if len(ids) != len(set(ids)):
                raise ToolError("Restored todo IDs must be unique")

            self.state.todos = todos

            return TodoResult(
                message=f"Restored {len(todos)} todos from {filepath}",
                todos=[todo.model_dump() for todo in self.state.todos],
                total_count=len(self.state.todos),
            )
        except Exception as e:
            raise ToolError(f"Failed to restore todos: {e}")
