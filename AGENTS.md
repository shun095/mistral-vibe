# AGENTS.md

Conventions for AI agents and humans contributing to **Mistral Vibe** — a Python 3.12+ CLI coding assistant managed with `uv`.

Layout: `vibe/core` is the engine (agent loop, tools, LLM backends, config); `vibe/cli` is the Textual TUI; `vibe/acp` bridges to the Agent Client Protocol; `vibe/setup` runs first-run wizards. Tests live in `tests/` with autouse fixtures in `conftest.py` and test doubles in `tests/stubs/`.

## Core Principles

**Exhaustive scope before first change.** Never edit a file until you have enumerated every location that must change. The default assumption is that any touchpoint related to the task needs attention. If you modify X, ask: what else depends on X? What calls X? What does X call? What shares X's invariant? Answer each question before touching code. Partial fixes are failures.

**Close the loop.** Every change introduces artifacts (debug logs, temporary flags, test stubs, unused imports). Before declaring completion, re-read every file you touched and verify nothing was left behind. The diff should contain only what the task requires.

**Verify breadth, not just depth.** Passing tests on the obvious path is insufficient. Identify every entry point that reaches the changed code (direct calls, callbacks, event handlers, background threads, CLI flags, web endpoints, slash commands). Each path must be considered. If a path exists, either fix it or document why it's excluded.

## Commands

Always go through `uv` — never invoke bare `python` or `pip`.

- `uv run vibe` / `uv run vibe-acp` — the two entry points.
- `uv run pytest` — full suite (parallel via `pytest-xdist`).
- `uv run pyright` — strict type check.
- `uv run ruff check --fix .` and `uv run ruff format .` — run both after every code change and report the files modified.
- `uv run pre-commit run --files <files>` — lint only changed files (default). Use `--all-files` only for full audit. Install once with `uv tool install pre-commit && uv run pre-commit install`.
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
- Avoid comments and docstrings, except for when there's a hard to spot corner case

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
- Configure via env: `LOG_LEVEL` (default `WARNING`), `LOG_MAX_BYTES`. Logs land in `~/.vibe/logs/vibe.log`.
- Pass variables as `%s` positional args, not f-string interpolation: prefer `logger.error("Failed to fetch url=%s", url)` over `logger.error(f"Failed to fetch {url}")`. This defers formatting to the logging framework (only formats if the message is emitted) and keeps messages grep-friendly.
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


# AGENTS.md - User's Instructions for `custom-fix-*` branch

You behave adhering this guidelines strictly to work on `custom-fix-*` branch. These user customization instructions should take precedence over the AGENTS.md file mentioned above.

## 🛡️ Safety Rules

- ❌ **NEVER change code/git unless explicitly instructed** - Ask before significant changes
- ❌ **NEVER use `git reset --hard`, `git checkout <filename>` or `git stash drop` lightly**
- ❌ **NEVER create commits unless explicitly requested**
- ❌ **NEVER skip pre-commit hooks and avoid `--no-verify`**
- ❌ **NEVER modify/delete files in `~/.vibe`** or write logs to `~/.vibe/logs/vibe.log`
- ❌ **NEVER create task files in project root** - Use `./tmp/` for artifacts
- ❌ **NEVER use filename versioning** (`*_v2`, `*_final`)
- ❌ **NEVER kill processes on ports 9091-9093** - these are production ports in use
- ❌ **NEVER use `pkill -f "vibe"`** - this kills production processes. Use specific PID or port-based killing instead.
- ✅ **Backup before destructive operations** - prefer `git stash -u` instead of `git reset --hard`
- ✅ **All commits MUST pass pre-commit hooks** - use 600s timeout for pre-commit commands
- ✅ **Always stage changes first and wait for user approval before committing**
- ✅ **Proactive Verification** - After any code change, automatically run relevant tests before responding. Testing is part of the fix, not a separate task.
- ✅ **Follow the Rules You're Reading** - The guidelines in AGENTS.md apply to you. You MUST follow all rules. Before any action, verify compliance with existing rules.
- ✅ **Commit Approval Checkpoint** - Before running `git commit`, you MUST:
  1. Run `git diff --cached --stat` and show the output to the user
  2. Explicitly ask the user to approve the staged changes
  3. Wait for the user's explicit "yes" or "go ahead" before proceeding
  4. Only then run `git commit`
  Never skip steps 1-3. A passing pre-commit hook does not replace user approval.

## Debugging Methodology

**Always gather facts before assumptions.** Never guess at root causes.

### Evidence Over Assertions

When making a claim about code behavior (e.g., "this error is pre-existing", "all tests pass"), **prove it with unfiltered output**. The user must be able to independently verify your conclusion.

- **Never filter diagnostic output** — Do not pipe linter, test, or diff output through `grep`, `tail`, or `head`. Show the full output. Filtering hides context the user needs to trust your conclusion.
- **Stash-and-compare properly** — When comparing two states (e.g., pre-existing vs introduced), run `git stash`, show the full diagnostic output, then `git stash pop`, show the full output again. Both outputs must be visible.
- **One claim, one proof** — If you claim "X is pre-existing", show the tool output that demonstrates X existed before your changes. Without the output, the claim is noise.
- **Investigation is read-only** — When asked to investigate, diagnose, or review, do not edit files, commit changes, or modify configuration. Report findings and stop. The user decides what action to take. Do not convert an investigation task into a change task.
- **Report facts, not judgments** — When presenting findings, describe what you observe without classifying whether it matters. Say "snapshot shows `pytest-913` vs `pytest-825`" rather than "temp path noise, not a real change." The user makes the judgment call.
- **Do not suggest rule changes without being asked** — The Autoimprovement section permits suggesting rules; it does not authorize editing AGENTS.md. Propose the change and wait for approval before writing.

### Diagnosing Test/Snapshot Failures

When test output changes (failures, new warnings, snapshot mismatches), **check git history before theorizing about the cause**.

- **Always run `git diff HEAD~3` first** — the simplest explanation is that code changed and the test reflects that. Rule out code changes before blaming environment, dependencies, or timing.
- **Never name a bug cause without evidence** — do not label a failure as "race condition", "timing issue", "flaky", or "import order" without proving it. Deterministic structural differences are code changes, not races. A race produces random, inconsistent output across runs.
- **Correlation is not causation** — adding a dependency and seeing a test change does not mean the dependency caused it. The branch may have uncommitted changes from a prior session. Check `git log --oneline -5` and `git status` before drawing conclusions.
- **Admit ignorance over inventing explanations** — if you cannot explain why a test changed after checking the diff, say so. Do not fabricate a plausible-sounding technical term to cover the gap.
- **Snapshot regression is a regression** — if `git stash` produces 0 mismatches and your working state produces N > 0, your changes caused it. Identify the specific test, inspect the diff report, and fix the root cause. A varying N across runs does not invalidate the finding — it indicates a race condition introduced by your change. Never dismiss a stash-proven regression as "flaky" or "pre-existing".
- **Report regressions in final summary** — if any test suite shows a regression attributable to your changes (even if individual tests pass), state it explicitly in the final report. Do not claim "all green" when mismatches exist.

1. **Add debug logging thoroughly** — Insert `logger.debug()` at every decision point in the suspected code path. Log variable values, branch taken, and state transitions. Use `%s` positional args, not f-strings.
2. **Plan controlled experiments** — Isolate variables by testing minimal cases first (e.g., single tool type), then incrementally add complexity. Compare behavior between known-good and broken scenarios. Use the same debug instrumentation across all experiments.
3. **Capture stack traces** — When a function is called unexpectedly, log `"".join(traceback.format_stack(limit=8)).strip()` to identify the caller chain. This reveals execution paths that differ between scenarios.
4. **Verify at render boundaries** — For UI bugs, log both Python state (properties, reactive values) AND rendered output (button labels, widget text). Python state being correct does NOT guarantee the render buffer reflects it.

### Systematic Caller Chain Analysis

When a fix targets a function (e.g., "prevent X from being called"), **enumerate every call site before writing code**:

1. `grep` all callers of the target function
2. For each caller, trace **who invokes it** (direct calls, callbacks, tool results, event handlers, async workers)
3. Classify each path: must skip, must always execute, or conditional
4. Apply the fix to every classified path — never assume only the obvious caller matters
5. Verify no caller was missed by re-grep after changes

### Debugging Async/UI Bugs: Trace State Transitions

When debugging async code or UI widget state, **prove claims with timestamped evidence**:

- **Trace UI elements to code paths** — When a visual diff shows unexpected UI elements (extra notifications, missing widgets, duplicate toasts), trace the code path that produces them. Count how many times the producing function (e.g., `self.notify()`, `mount()`) is called along that path. A double notification almost always means the same function is called twice through different call chains.
- **Log at mount/prune/refresh boundaries** — For widget-related bugs, log the widget class name and child count at every `mount`, `prune`, and `refresh` call. Use `time.monotonic()` for timestamps to establish call order. Write to a temp file (`/tmp/debug.txt`) with `flush()` to avoid buffer loss.
- **Never claim "timing issue" without evidence** — If you suspect race conditions or stale state, prove it by logging the exact state at each async boundary. Show the timestamps and values that demonstrate the discrepancy.
- **Enumerate the widget tree** — When explaining widget count discrepancies, list every widget in the container with its class name, history index (if mapped), and child count. Count manually to verify formulas rather than assuming counts match.
- **Trace the formula** — When a computed value (e.g., `remaining = total - visible`) seems wrong, log every input variable at the point of computation. Show the arithmetic: `32 - 5 = 27`, not just the result.
- **Include widget transitions proactively** — When investigating UI bugs, always show: (1) widgets created, (2) widgets pruned, (3) widgets remaining, (4) the computed count. Don't wait for the user to ask for this detail.

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

**Before changing codes:**
- Identify all call sites using `grep` or `lsp`
- **Caller chain audit**: For each call site found, trace upward to discover who calls it (direct callers, indirect callers via callbacks, tool results, event handlers). Classify each path: does it need the change or must it behave differently? Apply the fix to every path that needs it. Never assume only one caller matters.
- Check for imports of affected symbols
- Review dependent tests that may fail
- Trace data flow and verify no unintended breaking changes

**After test failures:**
- **Map failures to your diff first** — Before assuming a test failure is pre-existing or flaky, check whether your changed files touch the code path exercised by the failing test. If your changes add/remove/modify UI elements, notifications, or output format, the test diff is expected — update the snapshot or fix the code.
- **Re-grep after changes** — After modifying code, re-run the same `grep` search to verify no new call sites were introduced that could trigger the same bug through a different path. After every change, re-grep every symbol you touched — new callers may have been added by other changes, or you may have missed indirect paths. The second pass catches what the first missed.

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

Run **sequentially** — never in parallel. Suites share ports and resources; concurrent runs cause flaky failures.

```bash
uv run pytest tests/    # Python tests (timeout=300)
npm test                # JavaScript unit tests
npm run test:e2e        # WebUI E2E tests (timeout=300)
```

**You are NOT done until all 3 pass.** Report actual counts:
```
Python tests:     X passed, Y skipped, Z failed
JavaScript tests: X passed, Y skipped, Z failed
E2E tests:        X passed, Y skipped, Z failed
```

**Critical failures:**
- Running partial tests (`pytest tests/specific/path/`)
- Skipping E2E tests
- Claiming "tests pass" without running all 3
- Filtering pre-commit output with `tail` or `grep` — always show full output so failures are visible

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

### Snapshot Tests

When a snapshot test fails, **never update the reference snapshot blindly**. Always verify the visual change first:

1. Run the failing test with `--snapshot-report=snapshot_report.html` to generate a diff report (this does NOT overwrite the reference)
2. Use the `playwright-cli` skill to open `snapshot_report.html` and take a screenshot
3. Use `read_image` to inspect the screenshot and verify the change is intentional
4. Only update the snapshot with `--snapshot-update` if the visual change is correct and expected
5. If the change is unwanted, fix the code instead of updating the snapshot

**Mandatory visual inspection before any statistical analysis.** Do not run stash-and-compare loops, bisect experiments, or flakiness tests until you have opened the diff report and inspected it with `read_image`. Statistics answer "did my change cause this?" but only the visual diff answers "what broke?" — and the visual answer may invalidate your hypothesis entirely. Forming a hypothesis ("it's flaky", "it's pre-existing") before looking at the diff is a violation of the evidence-first principle.

Example:
```bash
uv run pytest tests/snapshots/test_xxx.py --snapshot-report=snapshot_report.html
# Then use playwright-cli to screenshot snapshot_report.html
# Then use read_image to review
# If correct: uv run pytest tests/snapshots/test_xxx.py --snapshot-update
```

**Reading raw snapshot SVGs:** Snapshot SVGs live in `tests/snapshots/__snapshots__/<test_module>/`. To visually inspect them:
1. Copy SVGs to scratchpad, create an HTML file embedding them via `<object data="file.svg" type="image/svg+xml">`
2. Serve via `nohup python3 -m http.server 8765 --directory <scratchpad>` (file:// protocol is blocked by Chromium)
3. Use `playwright-cli open --browser=chromium http://localhost:8765/page.html` + `screenshot`
4. Use `read_image` on the screenshot
5. **ALWAYS kill the HTTP server after use** — `kill <pid>` or `lsof -ti :8765 | xargs kill`. Never leave ports open. Avoid ports 9091-9093 (production).

### Testing Commands

```bash
uv sync                           # Python dependencies
npm install                       # JavaScript dependencies
npm run playwright:install        # Playwright browsers
uv run pytest tests/              # Python tests
npm test                          # JavaScript tests
nohup npm run test:e2e > /tmp/e2e-test-output.log 2>&1 & echo $! > /tmp/e2e-pid  # E2E tests (background)
npm run test:e2e:coverage         # E2E tests with JS coverage + HTML report
npm run test:e2e:ui               # Interactive E2E
npm run test:e2e:headed           # Visible browser
```

**E2E Test Notes:**
- `bash` calls are stateless — `$!` vanishes between calls. Run these as **two separate** `bash` calls:
  ```bash
  nohup npm run test:e2e > /tmp/e2e-test-output.log 2>&1 & echo $! > /tmp/e2e-pid
  ```
  ```bash
  while kill -0 $(cat /tmp/e2e-pid) 2>/dev/null; do sleep 2; done; tail -20 /tmp/e2e-test-output.log
  ```
- NEVER use `tail -f` (blocks forever). NEVER kill ports 9091-9093 (production).
- E2E uses ports 9100-9109. Kill safely: `lsof -ti :9100-9109 | xargs -r kill -9 2>/dev/null || true`

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
