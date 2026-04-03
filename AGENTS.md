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

  - title: "Minimize Git Diffs"
    description: >
      When adding features, minimize the diff against `origin/main` (the PR base), not just the previous commit:
      - Keep existing inline code inline; do not extract to helper functions unless the logic is genuinely new
      - Use early returns instead of `else:` blocks to avoid reindenting existing code
      - Do not add docstrings to existing functions; only add to genuinely new functions
      - Match original indentation from `origin/main` exactly when modifying code
      - Add new feature code as minimal additions rather than refactoring for "cleaner" structure
      Always check `git diff origin/main -- <file>` to verify the actual PR diff size.

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
- ❌ **NEVER change code/git unless explicitly instructed**
- ✅ Ask user before any significant changes or when uncertain
- Act as reporter/planner/tester, not developer, unless instructed

### Git Safety
- ❌ **NEVER use `git reset --hard` or `git checkout <filename>` lightly**
- ❌ **NEVER create commits unless explicitly requested**
- ❌ **NEVER skip pre-commit hooks with `--no-verify`** - hooks enforce critical quality gates
- ✅ Backup before destructive operations; prefer `git stash --all` for temporary saves
- ✅ Only stage/commit files related to the requested feature
- ✅ **All commits MUST pass pre-commit hooks** - run `uv run pre-commit run --files <staged_files>` before committing
- ✅ **Specify 600s timeout when running `git commit`** - pre-commit hooks may need extended time for type checking and linting

### Production Directories
- ❌ **NEVER modify/delete files in `~/.vibe`**
- ❌ **NEVER write logs to `~/.vibe/vibe.log` during testing**
- ✅ Use project directory log files for testing; only add new files to production

### Task Files
- ❌ **NEVER put any new documents/debug scripts in root**.
- ✅ Place temp files in `./tmp/` only when necessary. You MUST create the `./tmp/` directory if not exist.

### File Versioning
- ❌ **NEVER use filename versioning (`*_v2`, `*_final`, etc.)**
- ✅ Backup old files as `./tmp/*_v1.bak` before recreating

## Common Requirements
- Keep codebase and documents simple, clean and logically structured.

## Change Impact Analysis

**Before planning any changes, analyze potential side effects:**
- Identify all call sites of modified functions/classes using `grep`
- Check for imports of affected symbols across the codebase
- Review dependent tests that may fail
- Trace data flow: how changes propagate through the system
- Verify no unintended breaking changes to public APIs

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
- ❌ **NEVER use `print()` or `rprint()` statements for debugging** - they clutter output and don't integrate with logging

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

### 🧪 Testing Commands

```bash
# Install dependencies
uv sync              # Python dependencies
npm install          # JavaScript dependencies (Jest)
npm run playwright:install  # Playwright browsers

# Run all tests
uv run pytest tests/ # Python tests
npm test             # JavaScript unit tests (Jest)
npm run test:e2e     # WebUI E2E tests (Playwright)

# Run with debug logging
uv run pytest tests/ --log-cli-level=DEBUG

# Run specific test file
uv run pytest tests/cli/textual_ui/test_interrupt_question_popup.py
npm test -- vibe-client.test.js

# JavaScript coverage
npm run test:coverage

# E2E test variants
npm run test:e2e:ui       # Run with interactive UI
npm run test:e2e:debug    # Run with debugger
npm run test:e2e:headed   # Run with visible browser
npm run test:e2e:chromium # Run on Chromium only
```

**Custom test scripts are unacceptable** - they cannot reproduce real user interaction.

### `npm run test:e2e` - WebUI E2E Tests

**What it does:** Runs Playwright end-to-end tests against the Mistral Vibe WebUI.

**Location:** `tests/js/e2e/webui/tests/`

**Tested scenarios:**
- `auth.spec.ts` - Authentication flows
- `basic-chat.spec.ts` - Chat interface and message exchange
- `bash-command.spec.ts` - Bash command execution
- `tool-approval.spec.ts` - Tool approval workflows

**Configuration:** `playwright.config.ts`
- Runs on Chromium, Firefox, and WebKit (Safari)
- 120s timeout per test, 30s for assertions
- Auto-retries 2x in CI
- Generates HTML report in `playwright-report/`
- Captures traces, screenshots, and videos on failure

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
