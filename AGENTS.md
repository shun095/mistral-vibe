# AGENT.md - AI Agent Guidelines for Mistral Vibe

## 🚀 Quick Start - Read This First

**CRITICAL**: Always read relevant guidelines BEFORE starting any task. Use `read_file` tool with `./AGENTS.md` at the beginning.

### 📋 What to Read When

- **Always read**: Safety Rules, Testing Requirements, Truthfulness and Avoiding Hallucinations
- **Python code**: Python Development Guidelines
- **Development tasks**: Workflow and Tools
- **UI components**: UI Testing Requirements
- **Debugging**: Debugging with Logs

---

## 🛡️ Safety Rules

### Git Safety
- ❌ NEVER use `git reset --hard` or `git checkout <filename>` lightly
- ✅ Always make backups before destructive operations
- ✅ Prefer `git stash --all` for saving changes temporarily
- ✅ Only stage/commit files related to the requested feature

### Production Directories
- ❌ NEVER modify/delete files in `~/.vibe`
- ❌ NEVER write logs to `~/.vibe/vibe.log` during development/testing
- ✅ Always use a dedicated log file in the project directory for testing
- ✅ Only add new files to production directories

---

## 🧪 Testing Requirements

### Mandatory Standards

**1. Unit Tests (MANDATORY FOR ALL CODE)**
- All Python code changes MUST pass all existing pytest tests
- Run `uv run pytest` before claiming completion
- Fix any failing tests

**2. UI Tests (MANDATORY FOR UI CHANGES)**
- See dedicated [UI Testing Requirements](#ui-testing-requirements) section
- All UI changes MUST be tested with `terminalcp_terminalcp`

### Writing Unit Tests

**Minimize Mocking and Simulation**
- Avoid unnecessary mocking or simulation in test code as much as possible
- Use actual implementations rather than mocks whenever feasible
- Mock or simulate ONLY for:
  - External services (e.g., LLM backend servers, API endpoints)
  - Production files that vary by environment (e.g., configuration files, history files, session files in `~/.vibe` directory)
  - Components that have side effects or depend on external state

**Rationale**
- Actual implementations provide more realistic testing
- Mocks can hide bugs and create false confidence
- External services have environment-dependent behaviors that should be isolated
- Production files contain environment-specific data that shouldn't be hardcoded in tests

### Testing Checklist

**Before Starting:**
- [ ] Read these guidelines
- [ ] Read UI Testing Guide if working on UI components

**During Development:**
- [ ] Write clean, testable code
- [ ] Follow incremental testing approach

**Before Marking Complete:**
- [ ] Run `uv run pytest` and verify all tests pass
- [ ] Test with real inputs
- [ ] Verify output matches expectations
- [ ] Test edge cases and error handling
- [ ] Clean up background processes

---

## 🐍 Python Development Guidelines

### Code Style
- Use modern Python 3.12+ features
- Use `match-case` instead of long if-elif chains
- Use walrus operator (`:=`) to reduce nesting
- Use modern type hints: `str | int | None` (not `Optional`, `Union`)
- Use `pathlib.Path` for file operations
- Write declarative, minimalist code
- Follow PEP 8

### Type System
- Use modern generics: `list[str]`, `dict[str, int]`
- Write explicit, robust type annotations
- Ensure pyright compatibility

### Pydantic
- Use Pydantic v2 native validation
- Use `model_validate()` for validation
- Use `field_validator()` for field validation
- Avoid manual `getattr`/`hasattr` flows
- Use discriminated unions with `Field(discriminator='...')`

### Logging
- Import: `from vibe.core.utils import logger`
- Use appropriate levels: `info`, `debug`, `warning`, `error`
- Log widget lifecycle events
- **Production logs go to `~/.vibe/vibe.log`**
- **Development/testing logs MUST use a dedicated file** (e.g., `./logs/vibe.log`)

---

## 🔧 Workflow and Tools

### 🔄 Development Workflow

**Follow Kent Beck's Test-Driven Development (TDD) Style**

AI Agents must follow a strict iterative workflow:
1. **Write a simple test** (RED phase) - Create a minimal test that fails
2. **Implement minimal code** (GREEN phase) - Write only enough code to pass the test
3. **Refactor** (REFACTOR phase) - Improve code quality without changing behavior
4. **Repeat** - Continue with the next smallest test/implementation cycle

**Key Principles:**
- **One test at a time** - Focus on a single behavior
- **One implementation at a time** - Write minimal code to pass the current test
- **Frequent testing** - Run tests after each small change
- **Small, debuggable pieces** - Break problems into tiny, verifiable components
- **Avoid big design upfront** - Let tests drive the design

**Workflow Steps:**
1. **Check AI Agent Guidelines** - Read AGENTS.md
2. **Check existing todos** - Run `todo({"action": "read"})` to see if previous session left unfinished tasks
3. **Analyze requirements** - Explore codebase, research on Internet, ask user
4. **Create todo list** - Use `todo` tool to plan task. The list must reflect TDD style workflow.
5. **Write test first** - Create a failing test for the smallest behavior
6. **Implement minimal code** - Write only enough to pass the test
7. **Run tests** - Verify the test passes
8. **Refactor** - Improve code quality while keeping tests green
9. **Repeat cycle** - Move to next smallest test/implementation
10. **Run all unit tests** - Verify all modifications with `uv run pytest`
11. **Test UI manually** - Use `terminalcp_terminalcp` tool (for UI changes)
12. **Update documents** - Update related documentation
13. **Clean up** - Remove unnecessary or redundant files

### Task Management with Todo Tool

**CRITICAL**: Always check existing todos at the start of each session:

```python
# Read current todos (DO THIS FIRST!)
todo({"action": "read"})

# Create/update todos
todo({
  "action": "write",
  "todos": [
    {
      "id": "1",
      "content": "Implement a test case to verify X as Red",
      "status": "in_progress",
      "priority": "high"
    }
  ]
})
```

**Best Practices:**
- **ALWAYS check existing todos** before creating new ones
- Create specific, actionable items
- Update status: pending → in_progress → completed
- Remove irrelevant tasks from previous sessions
- Replan when encountering problems

### Essential Tools

**CRITICAL**: Always use dedicated tools instead of `bash` when available. Use `bash` only for system information, git operations, and package management.

**File Operations (PREFERRED OVER bash cat/head/tail):**
- `read_file(path="file.py", offset=0, limit=100)` - Read files with line offsets
- `write_file(path="file.py", content="...", overwrite=True)` - Create/overwrite files
- `search_replace(file_path="file.py", content="<<<<<<< SEARCH\n...\n=======\n...\n
- `grep(pattern="TODO", path="src/")` - Search for patterns (PREFERRED OVER bash grep)

**Task Management:**
- `todo({"action": "read"})` - Read current todo list
- `todo({"action": "write", "todos": [...]})` - Create/update todo items

**Web Research:**
- `fetch_fetch({"url": "https://example.com", "max_length": 5000})` - Fetch web pages
- `web_search_search({"query": "Python best practices", "max_results": 10})` - Search the web

**System Operations (USE bash ONLY WHEN NECESSARY):**
- `bash({"command": "pwd", "timeout": 5})` - System information (pwd, whoami, date)
- `bash({"command": "git status", "timeout": 10})` - Git operations
- `bash({"command": "ls -la", "timeout": 10})` - Directory listings
- `bash({"command": "uv run pytest", "timeout": 60})` - Run tests (PREFER uv directly when possible)
- **CRITICAL: ALWAYS specify timeout parameter** - Omitting the timeout parameter is strictly prohibited

  **Timeout Requirements:**
  - **REQUIRED**: All bash commands MUST include a timeout parameter
  - **REASON**: Prevents hanging processes and ensures task completion
  - **FORMAT**: `"timeout": <seconds>` where <seconds> is appropriate for the command
  - **EXAMPLES**:
    - Quick commands: `"timeout": 5` (pwd, whoami, date)
    - Medium commands: `"timeout": 10` (git status, ls, grep)
    - Long commands: `"timeout": 60` (pytest, build processes)
    - Very long commands: `"timeout": 300` (installations, compilations)

**MANDATORY RULE**: Never use `bash` without the `timeout` parameter. This is a strict requirement to prevent hanging processes.

### UI Testing (MANDATORY FOR ALL UI CHANGES)

**Why terminalcp_terminalcp is Required:**
- Tests actual user interaction in a real terminal environment
- Catches edge cases, timing issues, and real-world scenarios
- Validates complex UI behavior (widget lifecycle, async operations, config loading)
- Specifically designed for comprehensive UI testing

**Custom test scripts are unacceptable** - they cannot replicate real user interaction.

**Log File Requirement:**
- **MANDATORY**: Always specify `VIBE_LOG_FILE=./logs/vibe.log` when launching tests
- This prevents accidental modification of production logs in `~/.vibe/vibe.log`
- Example: `OPENAI_BASE_URL=... OPENAI_API_KEY=... MISTRAL_API_KEY=... VIBE_LOG_FILE=./logs/vibe.log uv run vibe`

### terminalcp_terminalcp - Comprehensive Guide

#### Overview
`terminalcp_terminalcp` is the mandatory tool for testing terminal UI. It provides a virtual terminal environment to interact with your application.

#### Basic Usage

**Launch app:**
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

**IMPORTANT**: Always specify OPENAI_* and MISTRAL_* environment variables. Get them with:
```bash
env | grep -e OPENAI -e MISTRAL
```

**View UI output:**
```python
terminalcp_terminalcp({
    "args": {
        "action": "stdout",
        "id": "test-session",
        "lines": 50  # Number of lines to retrieve
    }
})
```

**Send input:**
```python
terminalcp_terminalcp({
    "args": {
        "action": "stdin",
        "id": "test-session",
        "data": "/sessions\r"  # \r = Enter
    }
})
```

**Stop process:**
```python
terminalcp_terminalcp({
    "args": {
        "action": "stop",
        "id": "test-session"
    }
})
```

#### Advanced Usage

**Logging Configuration:**
Use VIBE_* environment variables for better debugging:
- `VIBE_LOG_LEVEL`: Set log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `VIBE_LOG_FILE`: Set custom log file path (e.g., `./logs/vibe.log`)

Example with logging:
```bash
OPENAI_BASE_URL=... OPENAI_API_KEY=... MISTRAL_API_KEY=... VIBE_LOG_FILE=./logs/vibe.log uv run vibe
```

**Keyboard Input Examples:**
- Enter: `"\r"` or `"\u000d"`
- Tab: `"\t"` or `"\u0009"`
- Escape: `"\u001b"`
- Backspace: `"\u007f"`
- Ctrl+C: `"\u0003"`
- Arrow keys: Up=`"\u001b[A"`, Down=`"\u001b[B"`, Right=`"\u001b[C"`, Left=`"\u001b[D"`

#### UI Testing Workflow

1. **Launch the application** with proper environment variables
2. **Test specific functionality** - Focus on what you modified
3. **Verify behavior** - Check that it works as expected
4. **Test edge cases** - Try different inputs and scenarios
5. **Test error handling** - Verify error states are handled properly
6. **Clean up** - Always stop processes when done



---

## 🐛 Debugging with Logs

### Production vs Development Logs

**CRITICAL**: The `~/.vibe/vibe.log` file is used by production instances and must never be modified during development or testing.

### Where Logs Are
- **Production Location**: `~/.vibe/vibe.log`
- **Development Location**: `./logs/vibe.log` (or your specified path)

### Using terminalcp for Debugging

**MANDATORY**: When debugging with `terminalcp_terminalcp`, you MUST specify a dedicated log file to avoid interfering with production logs.

```python
terminalcp_terminalcp({
    "args": {
        "action": "start",
        "command": "cd /path/to/project && OPENAI_BASE_URL=... OPENAI_API_KEY=... MISTRAL_API_KEY=... VIBE_LOG_FILE=./logs/vibe.log uv run vibe",
        "cwd": "/path/to/project",
        "name": "debug-session"
    }
})
```

This ensures logs are written to the project directory (`./logs/`) instead of `~/.vibe/`, preventing interference with production logs.

**Why this is critical:**
- Production instances may be actively using `~/.vibe/vibe.log`
- Writing to the same log file can cause data corruption or log loss
- Separate log files allow parallel development and production
- Development logs are easier to access and manage in the project directory

### How to Log
```python
from vibe.core.utils import logger

logger.info(f"Info message: {value}")
logger.debug(f"Debug details: {details}")
logger.warning(f"Warning: {issue}")
logger.error(f"Error: {error}", exc_info=True)
```

### Common Log Points
- Function entry/exit
- State changes
- Widget lifecycle (`on_mount`, `compose`)
- Async operations
- Configuration loading

---

## 📝 Professional Standards

### Definition of "Working Code"
- Code that has been executed and verified
- Code tested with actual inputs producing expected outputs
- Code that doesn't crash or behave unexpectedly
- Code validated through runtime testing

### Acceptable Evidence
- Screenshots from `terminalcp_terminalcp`
- Log output demonstrating success
- Test results showing correct functionality
- Manual verification

### Unacceptable
- "It should work" without testing
- "The code looks correct" without runtime verification
- Custom test scripts for UI testing (use `terminalcp_terminalcp`)

---

## 🎯 Truthfulness and Avoiding Hallucinations

### Zero-Tolerance Policy for Hallucinations

**AI Agents MUST respond only based on facts. Hallucinations are strictly prohibited.**

### What Constitutes Hallucination

Typical hallucinations include:

1. **Date/Time Errors**
   - ❌ Saying "today is 2024-01-01" without verifying the actual date
   - ✅ Checking the current date using `bash({"command": "date", "timeout": 5})` before making date-related statements

2. **False Completion Claims**
   - ❌ Saying "All tests pass" without running `uv run pytest`
   - ❌ Saying "Production ready" without end-to-end testing via `terminalcp_terminalcp`
   - ❌ Saying "All existing functionality remains" without regression tests
   - ✅ Only claim completion after verified testing

3. **Ignoring Instructions**
   - ❌ Ignoring guidelines in AGENTS.md
   - ❌ Ignoring workflow, tool usage, or testing requirements
   - ✅ Always follow documented procedures

4. **Checking Todo Lists Without Action**
   - ❌ Reading todos but not completing the actual tasks
   - ✅ Complete tasks before marking them as done

### Required Behavior

**When you cannot complete a task:**
- Explain what was attempted
- Explain what specific obstacles were encountered
- Explain why the task could not be finished cleanly
- Suggest next steps or alternative approaches

**When you make mistakes:**
- Acknowledge the error immediately
- Explain what went wrong
- Provide corrected information
- Continue with the correct approach

### Fact-Based Responses

Instead of guessing or making assumptions, AI Agents must:

1. **Verify facts** before stating them
2. **Run tests** before claiming they pass
3. **Test functionality** before claiming it works
4. **Check actual behavior** before describing it
5. **Admit when uncertain** and suggest verification methods

**Examples of acceptable responses:**
- "I cannot verify this without running the tests. Would you like me to run `uv run pytest`?"
- "I attempted to implement X, but encountered error Y. The task is incomplete."
- "I checked the date, and today is 2024-01-01. However, I need to verify Z before proceeding."
- "I cannot claim completion because I haven't tested with `terminalcp_terminalcp` yet."

**Examples of unacceptable responses:**
- "All tests pass" (without running them)
- "The feature works perfectly" (without testing it)
- "Today is 2024-01-01" (without verifying the actual date)
- "I completed all tasks" (when todos still show pending items)

---

## ⚠️ Important Reminders

- ✅ Test your work properly
- ✅ Follow all relevant guidelines
- ✅ Do NOT claim completion without proper testing
- ✅ Remove ALL temporary files
- ✅ Use `terminalcp_terminalcp` for UI testing (NEVER custom scripts)
- ✅ **ALWAYS use dedicated log files** (`./logs/vibe.log`) for testing
- ✅ **NEVER write to `~/.vibe/vibe.log`** during development

### Zero-Tolerance Policy for Hallucinations

**AI Agents MUST respond only based on facts. Hallucinations are strictly prohibited.**

### What Constitutes Hallucination

Typical hallucinations include:

1. **Date/Time Errors**
   - ❌ Saying "today is 2024-01-01" without verifying the actual date
   - ✅ Checking the current date using `bash({"command": "date", "timeout": 5})` before making date-related statements

2. **False Completion Claims**
   - ❌ Saying "All tests pass" without running `uv run pytest`
   - ❌ Saying "Production ready" without end-to-end testing via `terminalcp_terminalcp`
   - ❌ Saying "All existing functionality remains" without regression tests
   - ✅ Only claim completion after verified testing

3. **Ignoring Instructions**
   - ❌ Ignoring guidelines in AGENTS.md
   - ❌ Ignoring workflow, tool usage, or testing requirements
   - ✅ Always follow documented procedures

4. **Checking Todo Lists Without Action**
   - ❌ Reading todos but not completing the actual tasks
   - ✅ Complete tasks before marking them as done

### Required Behavior

**When you cannot complete a task:**
- Explain what was attempted
- Explain what specific obstacles were encountered
- Explain why the task could not be finished cleanly
- Suggest next steps or alternative approaches

**When you make mistakes:**
- Acknowledge the error immediately
- Explain what went wrong
- Provide corrected information
- Continue with the correct approach

### Fact-Based Responses

Instead of guessing or making assumptions, AI Agents must:

1. **Verify facts** before stating them
2. **Run tests** before claiming they pass
3. **Test functionality** before claiming it works
4. **Check actual behavior** before describing it
5. **Admit when uncertain** and suggest verification methods

**Examples of acceptable responses:**
- "I cannot verify this without running the tests. Would you like me to run `uv run pytest`?"
- "I attempted to implement X, but encountered error Y. The task is incomplete."
- "I checked the date, and today is 2024-01-01. However, I need to verify Z before proceeding."
- "I cannot claim completion because I haven't tested with `terminalcp_terminalcp` yet."

**Examples of unacceptable responses:**
- "All tests pass" (without running them)
- "The feature works perfectly" (without testing it)
- "Today is 2024-01-01" (without verifying the actual date)
- "I completed all tasks" (when todos still show pending items)

---

## 📋 Quick Reference Summary

### Key Principles
1. **Always verify facts** - Never assume or guess
2. **Test everything** - Unit tests for code, `terminalcp_terminalcp` for UI
3. **Follow the workflow** - TDD approach: Write test → Implement → Refactor
4. **Use the right tools** - Prefer dedicated tools over `bash`
5. **Be truthful** - Zero tolerance for hallucinations
6. **Use dedicated log files** - Always use `./logs/vibe.log` for testing

### Essential Commands
- `todo({"action": "read"})` - Check existing tasks
- `read_file(path="file.py", offset=0, limit=100)` - Read files
- `search_replace(file_path="file.py", content="<<<<<<< SEARCH\n...\n=======\n...\n


### Log File Configuration
- **Production**: `VIBE_LOG_FILE=~/.vibe/vibe.log` (default, read-only)
- **Development**: `VIBE_LOG_FILE=./logs/vibe.log` (MANDATORY for testing)
---

