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
      We use uv to manage our python environment. You should never try to run bare python commands.
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

- ❌ **NEVER change code/git unless explicitly instructed** - Ask before significant changes
- ❌ **NEVER use `git reset --hard` or `git checkout <filename>` lightly**
- ❌ **NEVER create commits unless explicitly requested**
- ❌ **NEVER skip pre-commit hooks with `--no-verify`**
- ❌ **NEVER modify/delete files in `~/.vibe`** or write logs to `~/.vibe/vibe.log`
- ❌ **NEVER create task files in root** - Use `./tmp/` for artifacts
- ❌ **NEVER use filename versioning** (`*_v2`, `*_final`)
- ✅ Backup before destructive operations; prefer `git stash --all`
- ✅ **All commits MUST pass pre-commit hooks** with 600s timeout
- ✅ **Always stage changes first and wait for user approval before committing**
- ✅ **Proactive Verification** - After any code change, automatically run relevant tests before responding. Testing is part of the fix, not a separate task.
- ✅ **Follow the Rules You're Reading** - The guidelines in AGENTS.md apply to you. Don't write rules you won't follow. Before any action, verify compliance with existing rules.
- ✅ **Commit Approval Checkpoint** - Before running `git commit`:
  1. Confirm user explicitly requested the commit
  2. Verify changes are staged
  3. Never commit documentation changes without review

**When asked to "analyze" or "review" code changes:**
- This is NOT a read-only task - run full test suite and report results
- Claiming "all tests pass" without running them is a critical failure

## Git Operations

**Commit Message Format:**
```bash
git commit -m "subject line (max 50 chars)" -m "- bullet point for change" -m "- bullet point for change"
```
Use multiple `-m` flags for multi-line messages. Do not use heredoc or embedded newlines in a single `-m` argument.

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

**Write cohesive, low-coupling code:**
- Reuse existing logic when possible
- This code will be maintained long-term

## 🧪 Testing Requirements

### Verify Before Reporting Completion

After any code modification, always run relevant tests before claiming the fix is complete. Do not wait for explicit instruction to test. Testing is part of the fix, not a separate task.

### MANDATORY: Run ALL Three Test Suites

```bash
uv run pytest tests/    # Python tests
npm test                # JavaScript unit tests
npm run test:e2e        # WebUI E2E tests
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
npm run test:e2e                  # E2E tests
npm run test:e2e:ui               # Interactive E2E
npm run test:e2e:headed           # Visible browser
```

## Tool Usage Guidelines

Always use dedicated tools instead of `bash` when available. Use `bash` only for:
- System information (`pwd`, `whoami`, `date`)
- Git operations (`git status`, `git diff`)
- Package management (`pip list`, `npm list`)
