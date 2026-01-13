
---

# Guidelines to execute tasks.

Following are guidelines you MUST follow during executing tasks.
**Read all guidelines carefully. All instructions are mandatory. Violation constitutes failure.**

## Python 3.12+ Best Practices

**Applies to:** All Python files (`**/*.py`)

### Code Style
- Use `match-case` for pattern matching
- Use walrus operator (`:=`) when appropriate
- Avoid deep nesting with early returns/guard clauses
- Use modern type hints: `list`, `dict`, `int | None` (not `Optional`, `Union`, `Dict`, `List`)
- Ensure strong static typing (pyright compatible)
- Use `pathlib.Path` for file operations
- Write declarative, minimalist code
- Follow PEP 8 and modern Python idioms

### Type System
- Use modern generics and pipe operator for unions
- Avoid deprecated typing constructs
- Write explicit, robust type annotations
- Ensure pyright compatibility

### Pydantic
- Prefer Pydantic v2 native validation
- Use `model_validate`, `field_validator`, `from_attributes`
- Avoid manual `getattr`/`hasattr` flows
- Do not narrow field types in subclasses for discriminated unions
- Use sibling classes with shared mixins
- Compose with `Annotated[Union[...], Field(discriminator='...')]`

### Enums
- Use `StrEnum`, `IntEnum`, `IntFlag` appropriately
- Use `auto()` for value assignment
- Use UPPERCASE for members

### Exceptions
- Document only exceptions explicitly raised
- Include all exceptions from explicit `raise` statements
- Avoid documenting obvious built-in exceptions

### Code Quality
- Fix types/lint warnings at source
- Use `typing.cast` when control flow guarantees type
- Extract helpers for clearer boundaries
- No inline ignores (`# type: ignore[...]` or `# noqa[...]`)

## Tool Usage

### File Operations
- Use `read_file`, `write_file`, `grep` tools
- Prefer dedicated tools over `bash`

### Bash Commands
- **CRITICAL**: Always specify `timeout` parameter
- Example: `bash({"command": "sleep 10", "timeout": 15})`

### Background Processes
- **CRITICAL**: Use `nohup` to launch servers in background with stdout/stderr redirect for logs
- Clean up processes after use

### Terminal UI Testing
- **CRITICAL**: Strictly always verify UI using `terminalcp_terminalcp` tool after modifying code
- **CRITICAL**: Launch the app with: `ENV1=... uv run vibe [options]`
- **CRITICAL**: Environment variables must be specified can be gotten by `env | grep -e OPENAI -e MISTRAL` command

### uv Commands
- **CRITICAL**: Use `uv` for all Python commands
- **CRITICAL**: Never use bare `python` or `pip`
- Useful commands:
  - `uv add/remove <package>`
  - `uv sync`
  - `uv run script.py`
  - `uv run pytest`

## Development Workflow

### Codebase Management
- Keep code clean, minimal, and logically structured
- Organize proactively: create/move/split files as needed
- Update outdated documents
- Remove all task-specific files before finishing

### Todo Tool
- **CRITICAL**: Always read existing todos before starting any tasks
- Always use `todo` tool to manage tasks
- Update status: pending → in_progress → completed
- Create specific, actionable items
- Remove irrelevant tasks

### User Instructions
- Read instructions carefully
- Prioritize user requirements over codebase
- Ask user with FOUR numbered options if unclear
- Confirm understanding before proceeding

### Web Research
- **CRITICAL**: Always research latest information first using `fetch_fetch` and `web_search_search` to solve any error.

## Safety Rules

### Git Safety
- **CRITICAL**: NEVER use `git reset --hard` or `git checkout <filename>` lightly
- **CRITICAL**: Always make backups before destructive operations
- Prefer `git stash --all`

### Production Directories
- **CRITICAL**: NEVER modify/delete files in `~/.vibe`
- Only add new files

### Professional Standards
- Provide fully implemented, tested, working code
- Follow best practices at all times

---

The end of guidlines.
