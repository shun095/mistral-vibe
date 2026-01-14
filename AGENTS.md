# AI Agent Guidelines for Mistral Vibe (IMPORTANT: YOU MUST ALWAYS STRICTLY ADHERE TO THIS GUIDELINES)

**Last Updated**: 2024-06-10
**Version**: 2.0

This document provides comprehensive guidelines for AI agents working on the Mistral Vibe project. It covers coding standards, tool usage, development workflows, and debugging techniques.

## Table of Contents

- [Quick Start Guide](#quick-start-guide)
- [Introduction](#introduction)
  - [Primary Purpose](#primary-purpose)
  - [Rationale](#rationale)
- [Python 3.12+ Best Practices](#python-312-best-practices)
  - [Code Style](#code-style)
  - [Type System](#type-system)
  - [Pydantic](#pydantic)
  - [Enums](#enums)
  - [Exceptions](#exceptions)
  - [Code Quality](#code-quality)
- [Tool Usage](#tool-usage)
  - [Tool Decision Guide](#tool-decision-guide)
  - [File Operations](#file-operations)
  - [Bash Commands](#bash-commands)
  - [Background Processes](#background-processes)
  - [Terminal UI Testing](#terminal-ui-testing)
  - [uv Commands](#uv-commands)
- [Development Workflow](#development-workflow)
  - [Getting Started](#getting-started)
  - [Codebase Management](#codebase-management)
  - [Todo Tool](#todo-tool)
  - [User Instructions](#user-instructions)
  - [Web Research](#web-research)
  - [Testing Strategy](#testing-strategy)
  - [Code Review Checklist](#code-review-checklist)
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
  - [Troubleshooting](#troubleshooting)
- [Glossary](#glossary)
- [Terminal UI Testing Best Practices](#terminal-ui-testing-best-practices)
  - [Why terminalcp_terminalcp is Mandatory](#why-terminalcp_terminalcp-is-mandatory)
  - [Common Mistakes to Avoid](#common-mistakes-to-avoid)
  - [How to Use terminalcp_terminalcp Effectively](#how-to-use-terminalcp_terminalcp-effectively)
- [Useful Commands](#useful-commands)
  - [Verification Checklist](#verification-checklist)
  - [Session Management](#session-management)
  - [Log Management](#log-management)
  - [Environment Checks](#environment-checks)
  - [Testing](#testing)
- [Changelog](#changelog)

## Introduction

These guidelines are **mandatory** for all AI agents working on the Mistral Vibe project. They ensure consistency, maintainability, and high quality across the codebase. Always read these guidelines carefully before starting any task.

### Primary Purpose

This document serves **three critical purposes**:

1. **Code Quality & Organization**
   - Maintain a clean, minimal, non-redundant codebase
   - Ensure good code smells and logical organization
   - Follow Python 3.12+ best practices
   - Write production-ready code

2. **Runtime Verification**
   - **CRITICAL**: Prevent AI agents from:
     - Writing code that appears correct but doesn't actually work
     - Reporting tasks as "completed" when only superficial testing has been done
     - Submitting code without verifying it runs correctly in real-world scenarios

3. **AI Agent Effectiveness**
   - **Provide practical tips and reminders** that agents can apply immediately
   - **Prevent common mistakes** that waste time and effort
   - **Guide efficient workflows** with proven development patterns
   - **Ensure consistency** across all AI-generated contributions
   - **Help agents remember best practices** through clear, actionable guidelines

**You must verify your work actually functions** - not just theoretically, but in practice. This means:
- Running the actual application with `terminalcp_terminalcp` for UI changes
- Testing interactive behavior with real user inputs
- Confirming that changes work as expected before marking tasks complete

**CRITICAL REMINDER**: AI agents frequently try to write custom test scripts instead of using `terminalcp_terminalcp`. This is unacceptable. You MUST use the provided tool for all UI testing.

**Use this document as your reference guide** - Bookmark it, refer to it frequently, and follow the patterns established here to work effectively and efficiently.

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

- **Fix types/lint warnings at source** - don't suppress them with inline ignores
- Use `typing.cast` when control flow guarantees type
- **Extract helpers** for complex logic to improve boundaries and reduce complexity
- **No inline ignores** - avoid `# type: ignore[...]` or `# noqa[...]` - fix the underlying issue
- **Keep functions focused** - Single responsibility principle
- **Minimize dependencies** - Only import what you need
- **Avoid premature optimization** - Write clean code first, optimize only when needed

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

**WHY THIS IS CRITICAL**: Many UI changes appear correct in code but fail in practice due to:
- Widget lifecycle issues (e.g., accessing widgets before they're mounted)
- Async timing problems (e.g., operations completing in wrong order)
- Configuration loading failures (e.g., agent not initialized)
- Environment variable requirements (e.g., missing API keys)

**DO NOT** claim a UI task is complete without running it through `terminalcp_terminalcp` and verifying it works correctly. This is not optional - it's a requirement for all UI-related changes.

**IMPORTANT**: Do NOT write test scripts to verify UI behavior. The `terminalcp_terminalcp` tool provides comprehensive testing capabilities that are far superior to custom scripts. Using this tool ensures consistent, thorough testing across all UI changes.

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

- **Keep code clean, minimal, and logically structured** - Remove unnecessary complexity
- **Organize proactively**: create/move/split files as needed to maintain logical organization
- **Update outdated documents** - Ensure documentation reflects current code
- **Remove all task-specific files** before finishing - Don't leave temporary files
- **Eliminate redundancy** - Avoid duplicating code or functionality
- **Follow DRY principle** - Don't Repeat Yourself
- **Maintain good code smells** - Write code that's easy to read, test, and maintain

### Todo Tool

**CRITICAL**: Always use the `todo` tool to manage tasks:

- **Read existing todos** before starting any tasks - Don't miss existing work
- **Update status**: pending → in_progress → completed - Keep track of progress
- **Create specific, actionable items** - Avoid vague tasks
- **Remove irrelevant tasks** - Keep the list focused

**WHY THIS MATTERS**: The todo tool helps you:
- Stay organized and focused
- Track progress effectively
- Avoid forgetting important steps
- Maintain clarity on what needs to be done

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

- **Read instructions carefully** and understand requirements - Don't make assumptions
- **Prioritize user requirements** over codebase conventions - User needs come first
- **Ask user with FOUR numbered options** if unclear about requirements - Provide clear choices
- **Confirm understanding** before proceeding with implementation - Avoid misunderstandings

**WHY THIS MATTERS**: Clear communication prevents:
- Wasted effort on the wrong solution
- Misunderstood requirements
- Rework and revisions
- Frustration for both you and the user

### Web Research

**CRITICAL**: Always research latest information first:

- Use `fetch_fetch` to fetch URLs - Get the most up-to-date information
- Use `web_search_search` to search for solutions - Find proven approaches
- Research before asking for human assistance - Save time for everyone

**WHY THIS MATTERS**: Research helps you:
- Find solutions faster
- Avoid asking obvious questions
- Work more independently
- Provide better answers when helping others
- Stay current with best practices

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

**DEFINITION OF "WORKING CODE"**:
- Code that has been executed and verified to function correctly
- Code that has been tested with actual inputs and produces expected outputs
- Code that doesn't crash or behave unexpectedly when used
- Code that has been validated through runtime testing, not just static analysis

**ACCEPTABLE EVIDENCE**:
- Screenshots from `terminalcp_terminalcp` showing the UI working correctly
- Log output demonstrating successful execution
- Test results showing functionality works as intended
- Manual verification that the feature behaves correctly

**UNACCEPTABLE**:
- "It should work" without actual testing
- "The code looks correct" without runtime verification
- "I tested it in my mind" without actual execution
- **Custom test scripts instead of using `terminalcp_terminalcp`**

**CRITICAL**: Writing custom test scripts is NOT acceptable. You MUST use `terminalcp_terminalcp` for all UI testing. This is not optional - it's a mandatory requirement.

## Debugging Tips

### Logging

**CRITICAL**: Use proper logging for debugging:

- Import logger: `from vibe.core.utils import logger` - Essential for debugging
- Use appropriate log levels:
  - `logger.info()` - Informational messages - Use for normal operation tracking
  - `logger.debug()` - Detailed debugging information - Use for troubleshooting
  - `logger.warning()` - Warning messages - Use for potential issues
  - `logger.error()` - Error messages - Use for failures
- Logs are written to `~/.vibe/vibe.log` (not stdout/stderr) - Check this file for issues
- Monitor logs in real-time: `tail -f ~/.vibe/vibe.log` - Watch logs as they happen

**CRITICAL**: Always log widget lifecycle events:

- `on_mount`, `on_mount_async`, etc. - Track when widgets initialize
- Log widget attributes before and after operations - Understand state changes

**WHY THIS MATTERS**: Logging helps you:
- Debug issues faster
- Understand application flow
- Track down bugs efficiently
- Document what's happening
- Avoid "black box" problems

Example:

```python
from vibe.core.utils import logger

logger.info(f"SessionSelector: Loading {len(sessions)} sessions")
logger.error(f"Failed to load session: {e}")
logger.info(f"Widget state: _list_view={self._list_view}, _sessions={len(self._sessions)}")
```

### Terminal UI Testing with terminalcp

**CRITICAL**: Use `terminalcp_terminalcp` for UI testing:

**PURPOSE**: This tool exists to prevent the submission of non-working code. Many changes that look correct in code reviews fail when actually executed due to subtle issues that only appear at runtime.

**REQUIREMENT**: For any UI-related task, you MUST:
1. Launch the application using `terminalcp_terminalcp`
2. Test the specific functionality you modified
3. Verify it works as expected
4. Only then can you mark the task as complete

This is not optional advice - it's a mandatory requirement for all UI work.

**IMPORTANT**: Do NOT write custom test scripts. The `terminalcp_terminalcp` tool is specifically designed for comprehensive UI testing and provides all the functionality you need. Custom scripts are invariably incomplete and miss critical edge cases.

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

## Terminal UI Testing Best Practices

### Why terminalcp_terminalcp is Mandatory

**CRITICAL**: AI agents frequently attempt to write custom test scripts instead of using `terminalcp_terminalcp`. This is unacceptable and leads to incomplete testing. Here's why:

1. **Custom scripts are always incomplete**: They miss edge cases, timing issues, and real-world scenarios
2. **terminalcp_terminalcp provides comprehensive testing**: It tests actual user interaction, not just code execution
3. **UI behavior is complex**: Widget lifecycle, async operations, and configuration loading require real testing
4. **The tool is designed for this purpose**: It has been specifically created to handle all UI testing scenarios

### Common Mistakes to Avoid

**DO NOT**:
- Write custom test scripts for UI verification
- Assume code works without actual testing
- Use only static analysis or code review
- Test only happy paths without edge cases

**DO**:
- Use `terminalcp_terminalcp` for ALL UI-related work
- Test interactive behavior thoroughly
- Verify error handling and edge cases
- Clean up processes after testing

### How to Use terminalcp_terminalcp Effectively

1. **Launch the application**: Start with proper environment variables
2. **Test specific functionality**: Focus on what you modified
3. **Verify behavior**: Check that it works as expected
4. **Test edge cases**: Try different inputs and scenarios
5. **Clean up**: Always stop processes when done

## Useful Commands

### Verification Checklist

Before marking any task as complete, ask yourself:

#### Runtime Verification
1. **Have I actually run the code?** (Not just read it, not just thought about it)
2. **Have I tested it with real inputs?** (Not just imaginary test cases)
3. **Have I verified the output matches expectations?** (Not just assumed it would)
4. **Have I used `terminalcp_terminalcp` for UI changes?** (For any visual or interactive modifications)
5. **Can I provide evidence it works?** (Screenshots, logs, test output)

#### Code Quality
6. **Is the code clean and minimal?** (No unnecessary complexity)
7. **Is there any redundancy?** (No duplicated code or functionality)
8. **Are functions focused?** (Single responsibility principle)
9. **Are dependencies minimized?** (Only importing what's needed)
10. **Are there any inline ignores?** (All type/lint warnings fixed at source)

#### UI-Specific Requirements
11. **Did I use `terminalcp_terminalcp` instead of writing custom test scripts?** (Mandatory for all UI work)
12. **Did I test the actual interactive behavior?** (Not just static rendering)
13. **Did I verify the UI responds correctly to user input?** (Test navigation, commands, etc.)

If you cannot answer "YES" to all of these questions, **the task is NOT complete**.

**REMINDER**: Writing custom test scripts is NOT a substitute for using `terminalcp_terminalcp`. The tool provides comprehensive testing capabilities that custom scripts cannot match.

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
