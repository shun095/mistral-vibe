# AI Agent Guidelines for Mistral Vibe

## 🚀 Quick Start - Read This First

**CRITICAL**: Always read relevant guidelines BEFORE starting any task. Use `read_file` tool at the beginning.

### 📋 What to Read When

- **Always read**: Safety Rules, Testing Requirements
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
- Logs go to `~/.vibe/vibe.log`

---

## 🔧 Workflow and Tools

### 🔄 Development Workflow

1. **Check AI Agent Guidelines** - Read AGENTS.md
2. **Check existing todos** - Run `todo({"action": "read"})` to see if previous session left unfinished tasks
3. **Analyze requirements** - Explore codebase, research on Internet, ask user
4. **Create todo list** - Use `todo` tool to plan task
5. **Execute task** - Read/modify files, run commands, research
6. **Track progress** - Update todo list for each step, replan if needed
7. **Incremental testing** - Test frequently to avoid mixing bugs
8. **Run unit tests** - Verify all modifications with `uv run pytest`
9. **Test UI manually** - Use `terminalcp_terminalcp` tool (for UI changes)
10. **Update documents** - Update related documentation
11. **Clean up** - Remove unnecessary or redundant files

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
      "content": "Implement feature X",
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
- `search_replace(file_path="file.py", content="<<<<<<< SEARCH\n...\n=======\n...\n>>>>>>> REPLACE")` - Make targeted changes
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
- **ALWAYS specify timeout parameter**

**UI Testing (MANDATORY FOR ALL UI CHANGES):**
- `terminalcp_terminalcp` - Test terminal UI
- Always use `stdout` action (not `stream`) for readability
- See dedicated [UI Testing Requirements](#ui-testing-requirements) section
**Custom test scripts are unacceptable** because:
- They miss edge cases, timing issues, and real-world scenarios
- terminalcp_terminalcp tests actual user interaction
- UI behavior is complex (widget lifecycle, async operations, config loading)
- The tool is specifically designed for comprehensive UI testing

### UI Testing Workflow

1. **Launch the application** with proper environment variables
2. **Test specific functionality** - Focus on what you modified
3. **Verify behavior** - Check that it works as expected
4. **Test edge cases** - Try different inputs and scenarios
5. **Test error handling** - Verify error states are handled properly
6. **Clean up** - Always stop processes when done

### terminalcp_terminalcp Usage

**CRITICAL**: Always use `stdout` action (not `stream`) for better readability.

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

**Send input (Enter key):**
```python
terminalcp_terminalcp({
    "args": {
        "action": "stdin",
        "id": "test-session",
        "data": "/sessions\r"  # \r = Enter
    }
})
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

**Stop process:**
```python
terminalcp_terminalcp({
    "args": {
        "action": "stop",
        "id": "test-session"
    }
})
```

### Common UI Testing Scenarios

**Navigation Testing:**
```python
# Test arrow keys
terminalcp_terminalcp({
    "args": {
        "action": "stdin",
        "id": "test-session",
        "data": "\u001b[B"  # Down arrow
    }
})
```

**Form Input Testing:**
```python
# Test typing text
terminalcp_terminalcp({
    "args": {
        "action": "stdin",
        "id": "test-session",
        "data": "hello world\r"
    }
})
```

**Special Keys Testing:**
```python
# Test Ctrl+C
terminalcp_terminalcp({
    "args": {
        "action": "stdin",
        "id": "test-session",
        "data": "\u0003"  # Ctrl+C
    }
})
```

---

## 🐛 Debugging with Logs

### Where Logs Are
- Location: `~/.vibe/vibe.log`
- View: `tail -50 ~/.vibe/vibe.log` or `tail -f ~/.vibe/vibe.log`

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

## ⚠️ Important Reminders

- ✅ Test your work properly
- ✅ Follow all relevant guidelines
- ✅ Do NOT claim completion without proper testing
- ✅ Remove ALL temporary files
- ✅ Use `terminalcp_terminalcp` for UI testing (NEVER custom scripts)

---

**End of AI Agent Guidelines**
