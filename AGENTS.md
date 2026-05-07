# AGENTS.md

Conventions for AI agents and humans contributing to **Mistral Vibe** — a Python 3.12+ CLI coding assistant managed with `uv`.

Layout: `vibe/core` is the engine (agent loop, tools, LLM backends, config); `vibe/cli` is the Textual TUI; `vibe/acp` bridges to the Agent Client Protocol; `vibe/setup` runs first-run wizards. Tests live in `tests/` with autouse fixtures in `conftest.py` and test doubles in `tests/stubs/`.

## Commands

Always go through `uv` — never invoke bare `python` or `pip`.

- `uv run vibe` / `uv run vibe-acp` — the two entry points.
- `uv run pytest` — full suite (parallel via `pytest-xdist`).
- `uv run pyright` — strict type check.
- `uv run ruff check --fix .` and `uv run ruff format .` — run both after every code change and report the files modified.
- `uv run pre-commit run --all-files` — full lint pass. Install once with `uv tool install pre-commit && uv run pre-commit install`.
- Useful uv basics: `uv sync --all-extras`, `uv add <pkg>`, `uv remove <pkg>`.

## Project layout & module conventions

- `__init__.py` exposes the public API via an explicit `__all__`.
- Private modules are prefixed with `_` (e.g. `_settings.py`, `_config.py`).
- Pydantic models live in `models.py`; configuration in `_settings.py` / `_config.py`.
- Abstract interfaces use the `_port.py` suffix (hexagonal-style ports).
- Tests mirror the source layout; test doubles in `tests/stubs/` are named `Fake*`.

## Python style

- Prefer `match` / `case` over long `if` / `elif` chains.
- Use the walrus operator `:=` only when it shortens code and improves clarity.
- Be a never-nester: early returns and guard clauses over nested blocks.
- Modern type hints only: built-in generics (`list`, `dict`) and `|` unions. Never import `Optional`, `Union`, `Dict`, `List` from `typing`.
- Use `pathlib.Path` (and `anyio.Path` in async paths) instead of `os.path`.
- Use f-strings, comprehensions, and context managers; follow PEP 8.
- Enums: `StrEnum` / `IntEnum` with `auto()` and UPPERCASE members. For type-mixing, the mix-in type comes before `Enum` in the bases. Add methods or `@property` rather than parallel lookup tables.
- Write declarative, minimalist code: express intent, drop boilerplate.
- Never call a private method from outside of it's class

## Typing & imports

- Pyright is strict and gates CI; fix types at the source.
- No relative imports — `ban-relative-imports = "all"`. Always `from vibe.core.x import …`.
- No inline `# type: ignore` or `# noqa`. Fix with refined signatures (TypeVar, Protocol), `isinstance` guards, `typing.cast` when control flow guarantees the type, or a small typed wrapper at the boundary.

## Pydantic

- Parse external data via `model_validate`, `field_validator`, or `model_validator(mode="before")` — never ad-hoc `getattr` / `hasattr` walks or custom `from_sdk` constructors.
- Set `ConfigDict(extra=…) `explicitly. Use `validation_alias` (or field aliases) for kebab-case TOML keys.
- Discriminated unions (e.g. MCP `transport`): use sibling final classes plus a shared base/mixin, and compose with `Annotated[Union[...], Field(discriminator=...)]`. Never narrow the discriminator field in a subclass — it violates LSP and pyright will reject it.
- Document `Raises:` only for exceptions the function actually raises (or that propagate from public API calls). Don't list speculative built-ins.

## Async

- `asyncio` is the orchestration runtime in the agent loop and tool execution. Use `asyncio.create_task` + queues for concurrent work, not blanket `gather`.
- Use `anyio.Path` for file I/O on async paths.
- Streaming surfaces return `AsyncGenerator[Event, None]`, not coroutines.
- HTTP via `httpx.AsyncClient`; mock with `respx` in tests.

## Tools

- Subclass `BaseTool` from `vibe/core/tools/base.py` with a Pydantic args model and a `BaseToolConfig` generic parameter.
- Implement `async def run(args, ctx: InvokeContext)` and yield events progressively.
- Raise `ToolError` for user-facing failures; raise `ToolPermissionError` for authorization failures.
- Declare permission with `ToolPermission` (`ALWAYS` / `ASK` / `NEVER`); honor it consistently.

## Logging & errors

- Use `from vibe.core.logger import logger` — stdlib `logging` with `StructuredLogFormatter`, not `structlog`.
- Configure via env: `LOG_LEVEL` (default `WARNING`), `DEBUG_MODE`, `LOG_MAX_BYTES`. Logs land in `~/.vibe/logs/vibe.log`.
- Pass variables as keyword args, not interpolated into the message: prefer `logger.error("Failed to fetch", url=url)` over `logger.error(f"Failed to fetch {url}")`.
- Define module-local exception hierarchies. Always chain with `raise NewError(...) from e`. Rich exceptions expose a `_fmt()` helper for human-readable output.

## File I/O

- Prefer `vibe.core.utils.io.read_safe` / `read_safe_async` / `decode_safe` over raw `Path.read_text()`, `Path.read_bytes().decode()`, or `open()`.
- They return `ReadSafeResult(text, encoding)` and try UTF-8, then BOM detection, then locale, then `charset_normalizer` lazily.
- Pass `raise_on_error=True` only when callers must distinguish corrupt files from valid ones; the default replaces undecodable bytes with U+FFFD.

## Tests

- Stack: `pytest` + `pytest-asyncio` + `pytest-textual-snapshot` + `respx`.
- Mark async tests with `@pytest.mark.asyncio`. Mock outbound HTTP with `respx`.
- Rely on the autouse fixtures in `tests/conftest.py` (`config_dir`, `tmp_working_directory`) for filesystem and home-dir isolation.
- No docstrings on test functions, methods, or classes — descriptive names like `test_create_user_returns_403_when_unauthorized` carry the intent. Pytest displays docstrings instead of node IDs when present, which hurts.
- Tests are exempt from the `ANN` and `PLR` ruff rules (see `per-file-ignores`).

## Git

- Never use `git commit --amend`, `git push --force`, or `git push --force-with-lease`.
- Always create new commits and push with a plain `git push`.
- If a push is rejected due to upstream changes, rebase onto the updated remote branch — never merge and never force-push.

## Editor tip

In Cursor / Pyright, the "Add import" quick fix is missing — use the workspace snippets `acpschema`, `acphelpers`, `vibetypes`, `vibeconfig` to insert the import line, then rename the symbol.


## Autoimprovement

- Suggest to add new rules to AGENTS.md based on user input or PR comments, when a change request could be generalized as a rule.
- Suggest updates to the README.md file according to feature changes or additions
- Keep the builtin Vibe Skill (`vibe/core/skills/builtins/vibe.py`) up-to-date. It documents the CLI's features, such as args, flags, config options and persistence, commands, built-in agents, file discovery logic.

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
      - Refining signatures with generics (TypeVar, Protocols), or precise return types
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
      We use uv to manage our python environment. You should never try to run bare python commands.
      Always run commands using `uv` instead of invoking `python` or `pip` directly.
      For example, use `uv add package` and `uv run script.py` rather than `pip install package` or `python script.py`.
      This practice helps avoid environment drift and leverages modern Python packaging best practices.
      Useful uv commands are:
      - uv add/remove <package> to manage dependencies
      - uv sync to install dependencies declared in pyproject.toml and uv.lock
      - uv run script.py to run a script within the uv environment
      - uv run pytest (or any other python tool) to run the tool within the uv environment

  - title: "Safe File Reading"
    description: >
      When reading files from disk, prefer the helpers in `vibe.core.utils.io` over raw
      `Path.read_text()`, `Path.read_bytes().decode()`, or `open()` calls:
      - `read_safe(path)` — synchronous read with automatic encoding detection.
      - `read_safe_async(path)` — async equivalent (anyio-based).
      - `decode_safe(raw)` — decode an already-read `bytes` object.
      These functions try UTF-8 first, then BOM detection, the locale encoding, and
      `charset_normalizer` (lazily, only when cheaper candidates fail). They return a
      `ReadSafeResult(text, encoding)` so callers always get valid `str` output without
      having to handle encoding errors manually.
      Use `raise_on_error=True` only when the caller must distinguish corrupt files from
      valid ones; the default (`False`) replaces undecodable bytes with U+FFFD.

  - title: "Imports in Cursor (no Pylance)"
    description: >
      Cursor's built-in Pyright does not offer the "Add import" quick fix (Ctrl+.). To add a missing import:
      - Use the workspace snippets: type the prefix (e.g. acpschema, acphelpers, vibetypes, vibeconfig) and accept the suggestion to insert the import line, then change the symbol name.
      - Or ask Cursor: select the undefined symbol, then Cmd+K and request "Add the missing import for <symbol>".
      - Or copy the import from an existing file in the repo (e.g. acp.schema, acp.helpers, vibe.core.*).

  - title: "Keep Builtin Vibe Skill Up-to-Date"
    description: >
      The file `vibe/core/skills/builtins/vibe.py` is the builtin self-awareness skill.
      It documents the CLI's features for the model: config.toml fields, CLI parameters, slash
      commands, agents, skills, tools, VIBE_HOME structure, and environment variables.
      When you change any of the following, update `vibe/core/skills/builtins/vibe.py`
      to reflect the new behavior:
      - CLI arguments or flags (vibe/cli/entrypoint.py)
      - config.toml fields or defaults (vibe/core/config/_settings.py)
      - Slash commands (vibe/cli/commands.py)
      - Built-in agents (vibe/core/agents/)
      - VIBE_HOME directory layout or paths (vibe/core/paths/)
      - Skill, tool, or agent discovery logic
      - Environment variables
      If in doubt, read the skill file and check whether your change makes any section stale.

  - title: "No Docstrings in Tests"
    description: >
      Do not add docstrings to test functions, test methods, or test classes.
      Test names should be descriptive enough to convey intent (e.g.,
      `test_create_user_returns_403_when_unauthorized`). Docstrings in tests add
      noise, duplicate the function name, and can suppress pytest's default output
      (pytest displays the docstring instead of the node id when one is present).
      Use inline comments sparingly for non-obvious setup or assertions instead.

# AGENTS.md

You behave adhering this guidelines strictly.

## 🛡️ Safety Rules

- ❌ **NEVER change code/git unless explicitly instructed** - Ask before significant changes
- ❌ **NEVER use `git reset --hard` or `git checkout <filename>` lightly**
- ❌ **NEVER create commits unless explicitly requested**
- ❌ **NEVER skip pre-commit hooks with `--no-verify`**
- ❌ **NEVER modify/delete files in `~/.vibe`** or write logs to `~/.vibe/vibe.log`
- ❌ **NEVER create task files in root** - Use `./tmp/` for artifacts
- ❌ **NEVER use filename versioning** (`*_v2`, `*_final`)
- ❌ **NEVER kill processes on ports 9091-9093** - these are production ports in use
- ❌ **NEVER use `pkill -f "vibe"`** - this kills production processes. Use specific PID or port-based killing instead.
- ✅ Backup before destructive operations; prefer `git stash --all`
- ✅ **All commits MUST pass pre-commit hooks** - use `timeout=600` for pre-commit commands
- ✅ **Always stage changes first and wait for user approval before committing**
- ✅ **Proactive Verification** - After any code change, automatically run relevant tests before responding. Testing is part of the fix, not a separate task.
- ✅ **Follow the Rules You're Reading** - The guidelines in AGENTS.md apply to you. Don't write rules you won't follow. Before any action, verify compliance with existing rules.
- ✅ **Commit Approval Checkpoint** - Before running `git commit`, you MUST:
  1. Run `git diff --cached --stat` and show the output to the user
  2. Explicitly ask the user to approve the staged changes
  3. Wait for the user's explicit "yes" or "go ahead" before proceeding
  4. Only then run `git commit`
  Never skip steps 1-3. A passing pre-commit hook does not replace user approval.

## Timeout Strategy

For commands exceeding 30s, always set explicit `timeout`:
- Pre-commit: `timeout=600`
- Full test suite: `timeout=300`
- Individual tests: `timeout=120`

**Never bypass safety checks** due to timeouts. Retry with higher timeout before escalating.

**When asked to "analyze" or "review" code changes:**
- This is NOT a read-only task - run full test suite and report results
- Claiming "all tests pass" without running them is a critical failure

## Git Operations

**Commit Message Format:**
```bash
git commit -F - <<'EOF'
<type>: <subject (max 50 chars)>

- detail 1
- detail 2

Generated by Mistral Vibe.
Co-Authored-By: Mistral Vibe <vibe@mistral.ai>
EOF
```

**Pre-commit Hook Failures:**
1. Fix the issue (formatting, lint, etc.)
2. Re-run pre-commit to verify fix
3. Only then proceed to commit
4. Report hook results in final summary

## Change Impact Analysis

**Before planning changes:**
- Identify all call sites using `grep` or `lsp`
- Check for imports of affected symbols
- Review dependent tests that may fail
- Trace data flow and verify no unintended breaking changes

## Coding Requirements

**Follow existing coding style:**
- Investigate deeply before writing tests - understand placement, mocks, domain structure
- Do NOT write in your own way - it causes financial losses
- Use FakeBackend if necessary; use pilot.press() for UI tests
- Do NOT assert internal behavior or mix textual_ui with acp
- **ONLY use `main` branch as coding style reference** - not `custom-fix-*` branches

**Minimize Git Diffs:**
When adding features, minimize the diff against `origin/main` (the PR base), not just the previous commit:
- Keep existing inline code inline; do not extract to helper functions unless the logic is genuinely new
- Use early returns instead of `else:` blocks to avoid reindenting existing code
- Do not add docstrings to existing functions; only add to genuinely new functions
- Match original indentation from `origin/main` exactly when modifying code
- Add new feature code as minimal additions rather than refactoring for "cleaner" structure
Always check `git diff origin/main -- <file>` to verify the actual PR diff size.

**Write cohesive, low-coupling code:**
- Reuse existing logic when possible
- This code will be maintained long-term

## 🧪 Testing Requirements

### Verify Before Reporting Completion

After any code modification, always run relevant tests before claiming the fix is complete. Do not wait for explicit instruction to test. Testing is part of the fix, not a separate task.

### MANDATORY: Run ALL Three Test Suites

```bash
uv run pytest tests/    # Python tests (timeout=300)
npm test                # JavaScript unit tests
npm run test:e2e        # WebUI E2E tests (timeout=300)
```

**You are NOT done until all 3 pass.** Report actual counts:
```
Python tests:     X passed, Y skipped
JavaScript tests: X passed
E2E tests:        X passed, Y skipped
```

**Critical failures:**
- Running partial tests (`pytest tests/specific/path/`)
- Skipping E2E tests
- Claiming "tests pass" without running all 3

### Test Reporting

**When claiming coverage:**
- Name specific test function (e.g., `test_lsp_find_references`)
- State test file path (e.g., `tests/tools/test_lsp_goto.py`)
- Do not use generic checkmarks without citation

### Debugging

- ✅ Use `logger.debug()` with `--log-cli-level=DEBUG`
- ❌ NEVER use `print()` or `rprint()` in tests

### Unit Test Guidelines

**Minimize mocking:**
- Use actual implementations whenever feasible
- Mock ONLY for: external services, environment-dependent files, side effects

### TUI Tests

All TUI changes MUST be tested with `terminalcp` skill.

### Testing Commands

```bash
uv sync                           # Python dependencies
npm install                       # JavaScript dependencies
npm run playwright:install        # Playwright browsers
uv run pytest tests/              # Python tests
npm test                          # JavaScript tests
nohup npm run test:e2e > /tmp/e2e-test-output.log 2>&1 &  # E2E tests (background with logging)
npm run test:e2e:coverage         # E2E tests with JS coverage + HTML report
npm run test:e2e:ui               # Interactive E2E
npm run test:e2e:headed           # Visible browser
```

**E2E Test Notes:**
- Step 1 — launch in background:
  ```bash
  nohup npm run test:e2e > /tmp/e2e-test-output.log 2>&1 & E2E_PID=$!
  ```
- Step 2 — wait for completion, then check results:
  ```bash
  while kill -0 $E2E_PID 2>/dev/null; do sleep 2; done; grep -E "(passed|failed|skipped)" /tmp/e2e-test-output.log
  ```
- NEVER use `tail -f /tmp/e2e-test-output.log` which blocks forever
- **NEVER kill processes on ports 9091-9093** - these are production ports in use
- E2E tests use ports 9100-9109 by default (safe to kill after tests complete)
- **To kill E2E test processes safely:**
  ```bash
  lsof -ti :9100-9109 | xargs -r kill -9 2>/dev/null || true
  ```

### Build Commands

```bash
# Build Cython extensions (required for performance-critical modules)
uv run python scripts/build_cython.py    # Manual build
uv sync --no-editable                   # Build with dependencies (triggers build hook)

# For wheel builds (build hooks run automatically)
uv build --wheel
```

**Note:** Editable installs (`uv sync` without `--no-editable`) do not run build hooks. Use `--no-editable` or manually run the build script to compile Cython extensions.


## Tool Usage Guidelines

Always use dedicated tools instead of `bash` when available. Use `bash` only for:
- System information (`pwd`, `whoami`, `date`)
- Git operations (`git status`, `git diff`)
- Package management (`pip list`, `npm list`)

IMPORTANT: this context may or may not be relevant to your task. You should act on these guidelines if they are relevant to your task.
