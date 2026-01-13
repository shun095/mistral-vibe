# AI Agent Guidelines for Mistral Vibe

This document provides comprehensive guidelines for AI agents working on the Mistral Vibe project. It covers coding standards, tool usage, development workflows, and debugging techniques.

## Table of Contents

- [Introduction](#introduction)
- [Python 3.12+ Best Practices](#python-312-best-practices)
  - [Code Style](#code-style)
  - [Type System](#type-system)
  - [Pydantic](#pydantic)
  - [Enums](#enums)
  - [Exceptions](#exceptions)
  - [Code Quality](#code-quality)
- [Tool Usage](#tool-usage)
  - [File Operations](#file-operations)
  - [Bash Commands](#bash-commands)
  - [Background Processes](#background-processes)
  - [Terminal UI Testing](#terminal-ui-testing)
  - [uv Commands](#uv-commands)
- [Development Workflow](#development-workflow)
  - [Codebase Management](#codebase-management)
  - [Todo Tool](#todo-tool)
  - [User Instructions](#user-instructions)
  - [Web Research](#web-research)
- [Safety Rules](#safety-rules)
  - [Git Safety](#git-safety)
  - [Production Directories](#production-directories)
  - [Professional Standards](#professional-standards)
- [Debugging Tips](#debugging-tips)
  - [Logging](#logging)
  - [Terminal UI Testing with terminalcp](#terminal-ui-testing-with-terminalcp)
  - [Common Debugging Scenarios](#common-debugging-scenarios)
    - [Debugging Textual Widget Lifecycle](#debugging-textual-widget-lifecycle)
    - [Debugging Async Operations](#debugging-async-operations)
    - [Debugging Configuration Issues](#debugging-configuration-issues)
    - [Debugging Session Loading](#debugging-session-loading)
    - [Debugging ListView Issues](#debugging-listview-issues)
- [Useful Commands](#useful-commands)

## Introduction

These guidelines are **mandatory** for all AI agents working on the Mistral Vibe project. They ensure consistency, maintainability, and high quality across the codebase. Always read these guidelines carefully before starting any task.

## Python 3.12+ Best Practices

**Applies to:** All Python files (`**/*.py`)

### Code Style

Modern Python code should be clean, readable, and leverage Python 3.12+ features:

- **Use `match-case` for pattern matching** instead of long if-elif chains
- **Use walrus operator (`:=`)** for assignments in expressions to reduce nesting
- **Avoid deep nesting** by using early returns and guard clauses
- **Use modern type hints**:
  - `list`, `dict`, `int | None` (not `Optional`, `Union`, `Dict`, `List`)
  - `list[str]` instead of `List[str]`
- **Ensure strong static typing** for pyright compatibility
- **Use `pathlib.Path`** for all file operations instead of `os.path`
- **Write declarative, minimalist code** - prefer clarity over cleverness
- **Follow PEP 8** and modern Python idioms

### Type System

Leverage Python's modern type system:

- Use **modern generics** with pipe operator for unions: `str | int | None`
- Avoid deprecated typing constructs like `Optional`, `Union`, `Dict`, `List`
- Write **explicit, robust type annotations** for all functions and variables
- Ensure **pyright compatibility** by testing with the type checker

### Pydantic

When using Pydantic v2:

- **Prefer Pydantic v2 native validation** methods
- Use `model_validate()` for validation
- Use `field_validator()` for field validation
- Use `from_attributes()` for model conversion
- **Avoid manual `getattr`/`hasattr` flows** - use Pydantic's built-in features
- **Do not narrow field types** in subclasses for discriminated unions
- **Use sibling classes with shared mixins** for code reuse
- **Compose with discriminated unions**:
  ```python
  Annotated[Union[...], Field(discriminator='...')]
  ```

### Enums

Use Python's enum types effectively:

- **Use `StrEnum`, `IntEnum`, `IntFlag`** appropriately based on use case
- **Use `auto()`** for automatic value assignment
- **Use UPPERCASE** for enum members (e.g., `MODE_A`, `MODE_B`)

### Exceptions

Document exceptions properly:

- **Document only exceptions explicitly raised** in function docstrings
- **Include all exceptions** from explicit `raise` statements
- **Avoid documenting obvious built-in exceptions** (e.g., `ValueError`, `TypeError`)

### Code Quality

Maintain high code quality:

- **Fix types/lint warnings at source** - don't suppress them
- Use `typing.cast` when control flow guarantees type
- **Extract helpers** for complex logic to improve boundaries
- **No inline ignores** - avoid `# type: ignore[...]` or `# noqa[...]`

## Tool Usage

### File Operations

Use the dedicated tools for file operations:

- **`read_file`** - Read file contents with optional line offsets and limits
- **`write_file`** - Create or overwrite files (use `overwrite=True` for existing files)
- **`grep`** - Recursively search for patterns in files
- **Prefer dedicated tools** over `bash` for file operations

### Bash Commands

**CRITICAL**: Always specify `timeout` parameter for bash commands:

```python
bash({"command": "sleep 10", "timeout": 15})
```

### Background Processes

**CRITICAL**: Use `nohup` to launch servers in background:

```bash
nohup command > output.log 2> error.log &
```

Always clean up processes after use.

### Terminal UI Testing

**CRITICAL**: Always verify UI using `terminalcp_terminalcp` tool:

- Launch the app with environment variables
- Test interactive behavior
- Clean up processes when done

### uv Commands

**CRITICAL**: Use `uv` for all Python commands:

- **Never use bare `python` or `pip`**
- Useful commands:
  - `uv add/remove <package>` - Add or remove dependencies
  - `uv sync` - Synchronize dependencies
  - `uv run script.py` - Run a Python script
  - `uv run pytest` - Run tests

## Development Workflow

### Codebase Management

Maintain a clean and organized codebase:

- Keep code clean, minimal, and logically structured
- Organize proactively: create/move/split files as needed
- Update outdated documents
- Remove all task-specific files before finishing

### Todo Tool

**CRITICAL**: Always use the `todo` tool to manage tasks:

- **Read existing todos** before starting any tasks
- **Update status**: pending → in_progress → completed
- **Create specific, actionable items**
- **Remove irrelevant tasks**

Example usage:

```python
todo({
  "action": "write",
  "todos": [
    {
      "id": "1",
      "content": "Implement new feature",
      "status": "in_progress",
      "priority": "high"
    }
  ]
})
```

### User Instructions

Handle user instructions effectively:

- **Read instructions carefully** and understand requirements
- **Prioritize user requirements** over codebase conventions
- **Ask user with FOUR numbered options** if unclear about requirements
- **Confirm understanding** before proceeding with implementation

### Web Research

**CRITICAL**: Always research latest information first:

- Use `fetch_fetch` to fetch URLs
- Use `web_search_search` to search for solutions
- Research before asking for human assistance

## Safety Rules

### Git Safety

**CRITICAL**: Handle git operations carefully:

- **NEVER use `git reset --hard`** or `git checkout <filename>` lightly
- **Always make backups** before destructive operations
- **Prefer `git stash --all`** for saving changes temporarily

### Production Directories

**CRITICAL**: Protect production directories:

- **NEVER modify/delete files** in `~/.vibe`
- Only add new files to production directories

### Professional Standards

Maintain professional standards:

- Provide **fully implemented, tested, working code**
- Follow best practices at all times
- Ensure code is production-ready

## Debugging Tips

### Logging

**CRITICAL**: Use proper logging for debugging:

- Import logger: `from vibe.core.utils import logger`
- Use appropriate log levels:
  - `logger.info()` - Informational messages
  - `logger.debug()` - Detailed debugging information
  - `logger.warning()` - Warning messages
  - `logger.error()` - Error messages
- Logs are written to `~/.vibe/vibe.log` (not stdout/stderr)
- Monitor logs in real-time: `tail -f ~/.vibe/vibe.log`

**CRITICAL**: Always log widget lifecycle events:

- `on_mount`, `on_mount_async`, etc.
- Log widget attributes before and after operations

Example:

```python
from vibe.core.utils import logger

logger.info(f"SessionSelector: Loading {len(sessions)} sessions")
logger.error(f"Failed to load session: {e}")
logger.info(f"Widget state: _list_view={self._list_view}, _sessions={len(self._sessions)}")
```

### Terminal UI Testing with terminalcp

**CRITICAL**: Use `terminalcp_terminalcp` for UI testing:

**Launch app**:

```python
terminalcp_terminalcp({
    "args": {
        "action": "start",
        "command": "cd /path/to/project && OPENAI_BASE_URL=... OPENAI_API_KEY=... MISTRAL_API_KEY=... uv run vibe",
        "cwd": "/path/to/project",
        "name": "test-session"
    }
})
```

**Get environment variables**:

```bash
env | grep -e OPENAI -e MISTRAL
```

**Send input**:

```python
terminalcp_terminalcp({
    "args": {
        "action": "stdin",
        "id": "test-session",
        "data": "/sessions\r"  # \r for Enter key
    }
})
```

**View UI output**:

```python
terminalcp_terminalcp({
    "args": {
        "action": "stdout",
        "id": "test-session",
        "lines": 50  # Number of lines to retrieve
    }
})
```

**View raw process output**:

```python
terminalcp_terminalcp({
    "args": {
        "action": "stream",
        "id": "test-session",
        "since_last": true  # Only new output since last call
    }
})
```

**Stop process**:

```python
terminalcp_terminalcp({
    "args": {
        "action": "stop",
        "id": "test-session"
    }
})
```

### Common Debugging Scenarios

#### Debugging Textual Widget Lifecycle

**CRITICAL**: Common issues with Textual widgets:

- Add logging to `on_mount()` to verify initialization
- Check if child widgets are `None` before using them
- Use `query_one()` or `query()` instead of widget attributes
- Verify `compose()` has completed before accessing widgets
- Log widget ID and parent to understand hierarchy

Example:

```python
def on_mount(self) -> None:
    logger.info(f"Widget mounted: _list_view={self._list_view}")
    logger.info(f"Widget ID = {self.id}")
    logger.info(f"Parent = {self.parent}")
    
    if self._list_view is None:
        logger.error("ListView is None!")
        list_view = self.query_one("#session-list", ListView)
        logger.info(f"Found ListView via query: {list_view}")
    else:
        logger.info(f"ListView has {len(self._list_view.children)} children")
```

#### Debugging Async Operations

Debug async code:

- Use `logger.info()` before and after async operations
- Check if coroutines are being awaited properly
- Verify event handlers are registered

Example:

```python
def on_mount(self) -> None:
    logger.info("Widget mounted, registering event handlers")
    self.set_interval(1, self._check_state)  # Polling for state changes
```

#### Debugging Configuration Issues

**CRITICAL**: Configuration issues are common:

- Check the `config` property vs `_config` attribute
- The `config` property returns `self.agent.config` if agent exists, otherwise `self._config`
- Verify agent initialization state before accessing agent config
- Log both to understand which one is being used

Example:

```python
logger.info(f"Agent exists: {self.agent is not None}")
logger.info(f"Using config: {self.config}")
logger.info(f"Direct _config: {self._config}")

if self.agent is None:
    logger.warning("Agent is None, using _config directly")
else:
    logger.info("Agent exists, using agent.config")
```

#### Debugging Session Loading

Debug session loading issues:

- Check session directory exists: `~/.vibe/logs/session/`
- Verify session files are valid JSON
- Check file permissions

Example:

```python
logger.info(f"Session config: {self.session_config}")
logger.info(f"Save dir: {save_dir}, exists: {save_dir.exists()}")
logger.info(f"Found {len(session_files)} files matching pattern: {pattern}")
```

#### Debugging ListView Issues

Debug ListView problems:

- Verify items are being added to the list
- Check if the list is being cleared before population
- Ensure the list view has focus when needed

Example:

```python
def _update_session_list(self) -> None:
    logger.info(f"Updating list: {len(self._sessions)} sessions")
    self._list_view.clear()
    for session in self._sessions:
        logger.debug(f"Adding session: {session.display_name}")
        self._list_view.append(ListItem(Static(session.display_name)))
    logger.info(f"List now has {len(self._list_view.children)} items")
```

## Useful Commands

### Check session files

```bash
ls -la ~/.vibe/logs/session/ | wc -l  # Count session files
ls -lh ~/.vibe/logs/session/ | head -20  # List recent sessions
```

### Check logs

```bash
tail -50 ~/.vibe/vibe.log  # View last 50 log lines
tail -f ~/.vibe/vibe.log  # Follow logs in real-time
grep "SessionSelector" ~/.vibe/vibe.log  # Filter logs by component
```

### Check environment

```bash
env | grep -e OPENAI -e MISTRAL  # Show API keys
which uv  # Verify uv is available
uv --version  # Check uv version
```

### Run tests

```bash
uv run pytest tests/ -v  # Run all tests
uv run pytest tests/test_specific.py -v  # Run specific test file
uv run pytest tests/test_specific.py::test_function -v  # Run specific test
```
