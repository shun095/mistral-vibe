# python312.rule
# Rule for enforcing modern Python 3.12+ best practices.
# Applies to all Python files (*.py) in the project.
#
# Guidelines covered:
# - Use match-case syntax instead of if/elif/else for pattern matching.
# - Use the walrus operator (:=) when it simplifies assignments and tests.
# - Favor a "never nester" approach by avoiding deep nesting with early returns or guard clauses.
# - Employ modern type hints using built-in generics (list, dict) and the union pipe (|) operator,
#   rather than deprecated types from the typing module (e.g., Optional, Union, Dict, List).
# - Ensure code adheres to strong static typing practices compatible with static analyzers like pyright.
# - Favor pathlib.Path methods for file system operations over older os.path functions.
# - Write code in a declarative and minimalist style that clearly expresses its intent.
# - Additional best practices including f-string formatting, comprehensions, context managers, and overall PEP 8 compliance.

description: "Modern Python 3.12+ best practices and style guidelines for coding."
files: "**/*.py"

guidelines:
  - title: "Match-Case Syntax"
    description: >
      Prefer using the match-case construct over traditional if/elif/else chains when pattern matching
      is applicable. This leads to clearer, more concise, and more maintainable code.

  - title: "Walrus Operator"
    description: >
      Utilize the walrus operator (:=) to streamline code where assignment and conditional testing can be combined.
      Use it judiciously when it improves readability and reduces redundancy.

  - title: "Never Nester"
    description: >
      Aim to keep code flat by avoiding deep nesting. Use early returns, guard clauses, and refactoring to
      minimize nested structures, making your code more readable and maintainable.

  - title: "Modern Type Hints"
    description: >
      Adopt modern type hinting by using built-in generics like list and dict, along with the pipe (|) operator
      for union types (e.g., int | None). Avoid older, deprecated constructs such as Optional, Union, Dict, and List
      from the typing module.

  - title: "Strong Static Typing"
    description: >
      Write code with explicit and robust type annotations that are fully compatible with static type checkers
      like pyright. This ensures higher code reliability and easier maintenance.

  - title: "Pydantic-First Parsing"
    description: >
      Prefer Pydantic v2's native validation over ad-hoc parsing. Use `model_validate`,
      `field_validator`, `from_attributes`, and field aliases to coerce external SDK/DTO objects.
      Avoid manual `getattr`/`hasattr` flows and custom constructors like `from_sdk` unless they are
      thin wrappers over `model_validate`. Keep normalization logic inside model validators so call sites
      remain declarative and typed.

  - title: "Pathlib for File Operations"
    description: >
      Favor the use of pathlib.Path methods for file system operations. This approach offers a more
      readable, object-oriented way to handle file paths and enhances cross-platform compatibility,
      reducing reliance on legacy os.path functions.

  - title: "Declarative and Minimalist Code"
    description: >
      Write code that is declarative—clearly expressing its intentions rather than focusing on implementation details.
      Strive to keep your code minimalist by removing unnecessary complexity and boilerplate. This approach improves
      readability, maintainability, and aligns with modern Python practices.

  - title: "Additional Best Practices"
    description: >
      Embrace other modern Python idioms such as:
      - Using f-strings for string formatting.
      - Favoring comprehensions for building lists and dictionaries.
      - Employing context managers (with statements) for resource management.
      - Following PEP 8 guidelines to maintain overall code style consistency.

  - title: "Exception Documentation"
    description: >
      Document exceptions accurately and minimally in docstrings:
      - Only document exceptions that are explicitly raised in the function implementation
      - Remove Raises entries for exceptions that are not directly raised
      - Include all possible exceptions from explicit raise statements
      - For public APIs, document exceptions from called functions if they are allowed to propagate
      - Avoid documenting built-in exceptions that are obvious (like TypeError from type hints)
      This ensures documentation stays accurate and maintainable, avoiding the common pitfall
      of listing every possible exception that could theoretically occur.

  - title: "Modern Enum Usage"
    description: >
      Leverage Python's enum module effectively following modern practices:
      - Use StrEnum for string-based enums that need string comparison
      - Use IntEnum/IntFlag for performance-critical integer-based enums
      - Use auto() for automatic value assignment to maintain clean code
      - Always use UPPERCASE for enum members to avoid name clashes
      - Add methods to enums when behavior needs to be associated with values
      - Use @property for computed attributes rather than storing values
      - For type mixing, ensure mix-in types appear before Enum in base class sequence
      - Consider Flag/IntFlag for bit field operations
      - Use _generate_next_value_ for custom value generation
      - Implement __bool__ when enum boolean evaluation should depend on value
      This promotes type-safe constants, self-documenting code, and maintainable value sets.

  - title: "No Inline Ignores"
    description: >
      Do not use inline suppressions like `# type: ignore[...]` or `# noqa[...]` in production code.
      Instead, fix types and lint warnings at the source by:
      - Refining signatures with generics (TypeVar), Protocols, or precise return types
      - Guarding with `isinstance` checks before attribute access
      - Using `typing.cast` when control flow guarantees the type
      - Extracting small helpers to create clearer, typed boundaries
      If a suppression is truly unavoidable at an external boundary, prefer a narrow, well-typed wrapper
      over in-line ignores, and document the rationale in code comments.

  - title: "Pydantic Discriminated Unions"
    description: >
      When modeling variants with a discriminated union (e.g., on a `transport` field), do not narrow a
      field type in a subclass (e.g., overriding `transport: Literal['http']` with `Literal['streamable-http']`).
      This violates Liskov substitution and triggers type checker errors due to invariance of class attributes.
      Prefer sibling classes plus a shared mixin for common fields and helpers, and compose the union with
      `Annotated[Union[...], Field(discriminator='transport')]`.
      Example pattern:
      - Create a base with shared non-discriminator fields (e.g., `_MCPBase`).
      - Create a mixin with protocol-specific fields/methods (e.g., `_MCPHttpFields`), without a `transport`.
      - Define sibling final classes per variant (e.g., `MCPHttp`, `MCPStreamableHttp`, `MCPStdio`) that set
        `transport: Literal[...]` once in each final class.
      - Use `match` on the discriminator to narrow types at call sites.

  - title: "Use uv for All Commands"
    description: >
      We use uv to manage our python environment. You should nevery try to run a bare python commands.
      Always run commands using `uv` instead of invoking `python` or `pip` directly.
      For example, use `uv add package` and `uv run script.py` rather than `pip install package` or `python script.py`.
      This practice helps avoid environment drift and leverages modern Python packaging best practices.
      Useful uv commands are:
      - uv add/remove <package> to manage dependencies
      - uv sync to install dependencies declared in pyproject.toml and uv.lock
      - uv run script.py to run a script within the uv environment
      - uv run pytest (or any other python tool) to run the tool within the uv environment

  - title: "Imports in Cursor (no Pylance)"
    description: >
      Cursor's built-in Pyright does not offer the "Add import" quick fix (Ctrl+.). To add a missing import:
      - Use the workspace snippets: type the prefix (e.g. acpschema, acphelpers, vibetypes, vibeconfig) and accept the suggestion to insert the import line, then change the symbol name.
      - Or ask Cursor: select the undefined symbol, then Cmd+K and request "Add the missing import for <symbol>".
      - Or copy the import from an existing file in the repo (e.g. acp.schema, acp.helpers, vibe.core.*).

# AGENTS.md

You behave adhering this guidelines strictly.

## 🛡️ Safety Rules

### Follow User's Instructions Precisely
- ❌ **NEVER make any changes to code or git repository** unless explicitly instructed by the user.
- ✅ If there is any uncertainty about a task, you MUST ask the user **before** making any significant changes.

**Example 1 - User: "Analyze the git status and create a commit for staged changes."**
- ❌ NEVER modify the staging area.
- ❌ NEVER run `git add` or `git reset`. You MUST act as a reporter, not a developer
- ✅ Use `git status` or `git diff --staged` to analyze changes.
- ✅ Use `git commit` to create a commit for the currently staged changes.

**Example 2 - User: "Analyze the codebase and create a plan to refactor."**
- ❌ NEVER execute the planned refactor without the user's permission. You MUST act as a planner, not a developer
- ✅ Read the code, analyze the codebase, and create a planning document.

**Example 3 - User: "Run all tests."**
- ❌ NEVER consider a task complete after running only some tests.
- ❌ NEVER modify the code without the user's permission. You MUST act as a tester, not a developer.
- ✅ Run all tests with a long timeout parameter if necessary using the bash tool.
- ✅ You may create a new report file that does not affect existing code or git repository regarding test results.

**Example 4 - User: "Restore files you've modified for feature X."**
- ❌ NEVER run `git reset --hard` or `git checkout` on unrelated files that may have been changed by the user for other work.
- ❌ NEVER modify any files you haven't changed.
- ❌ NEVER modify any files not related to feature X. You are not the developer occupying this repository. Please do not remove others' changes.
- ✅ Restore files you've modified **and** related to feature X. Run `git checkout /path/to/related_files_to_your_work_for_X`.

### Git Safety
- ❌ NEVER use `git reset --hard` or `git checkout <filename>` lightly
- ❌ NEVER create commits unless explicitly requested by the user
- ✅ Always make backups before destructive operations
- ✅ Prefer `git stash --all` for saving changes temporarily
- ✅ Create commits only when explicitly requested by the user
- ✅ Only stage/commit files related to the requested feature

### Production Directories
- ❌ NEVER modify/delete files in `~/.vibe`
- ❌ NEVER write logs to `~/.vibe/vibe.log` during development/testing
- ✅ Always use a dedicated log file in the project directory for testing
- ✅ Only add new files to production directories

### Task Specific and Non Future-Proof files
- ❌ NEVER put specific documents and debug scripts in root directory.
- ❌ NEVER respond simple text like `Task completed.` as final response.
- ❌ NEVER create summary using tools if not specified.
- ✅ Always respond directly to the user instead of creating report files.
- ✅ Place files in ./tmp/ directory only when necessary. You may put: detailed documents of summary, report and plan etc. for references only when necessary.
- ✅ Place temporal debug scripts in the ./tmp/ directory only when necessary.

### Avoid file name based versioning
- ❌ NEVER use file name based versioning
    - ❌ *_v2
    - ❌ *_comprehensive
    - ❌ *_simple
    - ❌ *_final
    etc.
- ✅ Back up the old file as ./tmp/*_v1.bak or something else before creating a new file with the same name to avoid file name-based versioning while keeping old files.

## Common Requirements
- Keep codebase and documents simple, clean and logically structured.

## Coding Requirements

**Always follow existing coding style**
- Investigate deeply and comprehensively to understand existing coding style of this repository before writing tests.
  - You MUST understand and be strict about:
    - Where to place the new codes and tests.
    - How you can create mocks and stubs for the new tests.
  - You MUST understand what kind of domains are exists in this repository, and directory structure.
  - Do NOT write in your own way. Writing in your own way undermines the consistency of the code base and causes significant financial losses.
  - This principal includes:
    - Use FakeBackend if necessary
    - Use pilot.press() for UI test if necessary
    - Do NOT assert internal behavior like private field
    - Do NOT place textual_ui things in acp directory. The opposite is also prohibited.
  - **IMPORTANT**: NEVER rely on the new code in `custom-fix-*` branch as your existing coding style. Only `main` branch code is a reliable reference for your existing coding style.

**Always write code that is highly cohesive and has low coupling**
- Thoroughly read your existing code and make sure to reuse any logic that meets your purpose and can be reused. This is code that you will maintain for a long time. Write highly cohesive code now. Otherwise, you will run into issues with horizontal expansion in the future.

## 🧪 Testing Requirements

### Debugging in Tests
- ✅ Use `logger.debug()` instead of `print()` for debugging in tests
- ✅ Use `--log-cli-level=DEBUG` with pytest to show debug logs
- ❌ NEVER use `print()` statements for debugging - they clutter output and don't integrate with logging

### Mandatory Standards

#### **1. Unit Tests (MANDATORY FOR ALL CODE)**
- All Python code changes MUST pass all existing pytest tests
- Run `uv run pytest tests/` before claiming completion
- Fix any failing tests related to the task

#### **2. TUI Tests (MANDATORY FOR UI CHANGES)**
- All TUI changes MUST be tested with `terminalcp` skill.

**Why terminalcp is Required:**
- Tests actual user interaction in a real terminal environment
- Catches edge cases, timing issues, and real-world scenarios
- Validates complex UI behavior (widget lifecycle, async operations, config loading)
- Specifically designed for comprehensive UI testing

**Custom test scripts are unacceptable** - they cannot reproduce real user interaction.

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

## Project Specific Tool Usage Guidelines

Always use dedicated tools instead of `bash` when available. Use `bash` only for system information, git operations, and package management.
