# AGENTS.md

Conventions for AI agents and humans contributing to **Mistral Vibe** — a Python 3.12+ CLI coding assistant managed with `uv`.

Layout: `vibe/core` is the engine (agent loop, tools, LLM backends, config); `vibe/cli` is the Textual TUI; `vibe/acp` bridges to the Agent Client Protocol; `vibe/setup` runs first-run wizards. Tests live in `tests/` with autouse fixtures in `conftest.py` and test doubles in `tests/stubs/`.

## Table of Contents

**Project Rules:** [Core Principles](#core-principles) · [Pre-Change Discipline](#pre-change-discipline) · [Verification Discipline](#verification-discipline) · [Commands](#commands) · [Layout](#project-layout--module-conventions) · [Style](#python-style) · [Typing](#typing--imports) · [Pydantic](#pydantic) · [Async](#async) · [Tools](#tools) · [Logging](#logging--errors) · [I/O](#file-io) · [Tests](#tests) · [Git](#git) · [Autoimprovement](#autoimprovement)

**`custom-fix-*` Overrides:** [Scope](#override-scope) · [Safety](#-safety-rules) · [Debugging](#debugging-methodology) · [Timeouts](#timeout-strategy) · [Git Ops](#git-operations) · [Impact](#change-impact-analysis) · [Coding](#coding-requirements) · [Testing](#-testing-requirements) · [Tools](#tool-usage-guidelines)

## Core Principles

**Exhaustive scope before first change.** Never edit a file until you have enumerated every location that must change. The default assumption is that any touchpoint related to the task needs attention. If you modify X, ask: what else depends on X? What calls X? What does X call? What shares X's invariant? Answer each question before touching code. Partial fixes are failures.

**Close the loop.** Every change introduces artifacts (debug logs, temporary flags, test stubs, unused imports). Before declaring completion, re-read every file you touched and verify nothing was left behind. The diff should contain only what the task requires.

**Verify breadth, not just depth.** Passing tests on the obvious path is insufficient. Identify every entry point that reaches the changed code (direct calls, callbacks, event handlers, background threads, CLI flags, web endpoints, slash commands). Each path must be considered. If a path exists, either fix it or document why it's excluded.

## Pre-Change Discipline

**Restate and constrain before touching code.** Before any edit, write one line restating the goal and list every file you intend to change with the specific change per file. If you cannot name the files, you are not ready to edit.

**Explore the affected subsystem first.** Never edit a file you haven't read. Never read a file without first reading its callers and callees. For UI changes: read the widget's `can_focus`, `BINDINGS`, and parent/child relationships. For key bindings: read how existing bindings in the same scope resolve conflicts. If you cannot explain the existing pattern in one sentence, keep reading.

**Ask on ambiguity, never guess.** If the request could mean two things (e.g., "change keybind" could mean entry keys vs navigation keys), ask before editing. One clarifying question saves three rounds of rollbacks.

**Two failures = stop and rethink.** If your approach produces test failures twice in the same region, abandon it. Re-read the code, identify why it failed (not just what failed), and choose a fundamentally different strategy. Flip-flopping fixes (add X → remove X → add X) is a critical failure.

## Verification Discipline

**Inspect every snapshot visually before updating.** Never run `--snapshot-update` without first running `--snapshot-report`, opening the report with playwright-cli, and reading each diff with `read_image`. The header count ("N snapshots changed") is not proof of inspection. Scroll to each one. Name each one. If you cannot name the visual difference, you have not inspected it.

**Report flaky tests, never dismiss them.** If a test fails in a full run but passes individually, report it. Write the full output to a file first, then search. Do not declare "flaky" without evidence: at least two runs showing different results on the same code.

**Complete means verified, not submitted.** A task is not done until: (1) every changed file passes lint/type checks, (2) every affected test passes, (3) snapshots are visually inspected and updated if needed, (4) the diff is reviewed for leftover artifacts (unused imports, debug logs, stale references). Missing any step is incomplete.

**AGENTS.md rules are guardrails, not suggestions.** Do not skip a rule because "the change is obvious." Obvious changes fail silently. The existence of a rule means someone observed its failure mode. Treat every rule as a circuit breaker: bypassing it removes protection you cannot see. When a rule conflicts with your intuition, follow the rule and note your concern. Never silently override a rule.

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

These rules take precedence over project-level AGENTS.md above.

## Override Scope

The table below determines which rule applies — project rules not listed remain in force.

| Project Rule | Status |
|---|---|
| Core Principles | **ADDITIVE** — custom rules augment, never replace project rules |
| Commands, Layout, Style, Typing, Pydantic, Async, Tools, Logging, File I/O, Editor tip | **UNCHANGED** |
| Tests | **OVERRIDDEN** — [Testing Requirements](#-testing-requirements) |
| Git | **OVERRIDDEN** — [Git Operations](#git-operations) |
| Autoimprovement | **OVERRIDDEN** — [Evidence Over Assertions](#evidence-over-assertions) |
| Safety Rules | **NEW** — [Safety Rules](#-safety-rules) |

## 🛡️ Safety Rules

- ❌ **NEVER change code/git unless explicitly instructed** - Ask before significant changes
- ❌ **NEVER use `git reset --hard`, `git checkout <filename>` or `git stash drop` lightly**
- ❌ **NEVER create commits unless explicitly requested**
- ❌ **NEVER skip pre-commit hooks and avoid `--no-verify`**
- ❌ **NEVER modify/delete files in `~/.vibe`** or write logs to `~/.vibe/logs/vibe.log`
- ❌ **NEVER create task files in project root** - Use `./tmp/` for artifacts
- ❌ **NEVER use filename versioning** (`*_v2`, `*_final`)
- ❌ **NEVER kill processes on ports 9091-9093** - production ports in use
- ❌ **NEVER use `pkill -f "vibe"`** - kills production. Use specific PID or port-based killing.
- ✅ **Backup before destructive ops** - prefer `git stash -u` over `git reset --hard`
- ✅ **All commits MUST pass pre-commit hooks** - use 600s timeout
- ✅ **Always stage first, wait for user approval before committing**
- ✅ **Proactive Verification** - Run relevant tests after any code change. Testing is part of the fix.
- ✅ **Follow the Rules You're Reading** - AGENTS.md rules apply. Verify compliance before action.

### Commit Approval Checkpoint

Before `git commit`: (1) show `git diff --cached --stat`, (2) ask user to approve, (3) wait for explicit "yes", (4) commit. Never skip. A passing pre-commit hook does not replace user approval.

## Debugging Methodology

**Always gather facts before assumptions.** Never guess at root causes.

### Honesty Over Appearance

The user values accuracy over speed. A correct, incomplete answer builds trust. A wrong answer presented confidently destroys it.

- **Run exactly what the user asks** — No added flags, options, or arguments. If you believe a flag is needed, ask first.
- **Never reinterpret commands** — When the user writes a command (e.g., `git diff`), run it as-is. Do not treat it as a natural language request and substitute your own command. "git diff" means `git diff`, not `git diff origin/main..HEAD`.
- **Baseline first** — Follow instructions exactly first to confirm they work. Only then apply judgment. Never skip the baseline step.
- **Errors are data** — Read output, understand cause, continue. Do not re-run with silent modifications.
- **Consult only when blocked** — Ask on critical trade-offs or broken procedures. Report everything else and proceed.
- **Own mistakes immediately** — "I should not have added that flag" beats any rationalization.
- **Lead with failures** — Tests fail, build breaks, feature broken — state it first. Do not bury it.
- **Never fabricate** — Fake results, unrun tests, partial output presented as complete — the cost is higher than admitting the gap.
- **Report matching findings** — If a diagnostic flags something the user stated concern about, mention it. One line is enough.

### Evidence Over Assertions

Prove claims with unfiltered output. The user must independently verify your conclusion.

- **Never filter diagnostic output** — No piping through `grep`, `tail`, or `head`. Write to file first (`> /tmp/result.log 2>&1`), then search the file. Use `tail -n 100` minimum. The full file is the source of truth.
- **All verification commands are diagnostic** — Pre-commit, pyright, ruff, pytest, npm test, git diff — same no-filtering rule. Never exempt a gate command.
- **Stash-and-compare properly** — `git stash`, show full output, `git stash pop`, show full output. Both visible.
- **One claim, one proof** — Claim "X is pre-existing"? Show the output proving it. Without output, the claim is noise.
- **Prove before diagnosing** — Never state "pre-existing", "flaky", or "caused by change" before running the isolated test. "Pre-existing"? Stash and re-run the failing test. "Flaky"? Run it twice on the same code. State uncertainty ("likely pre-existing, verifying now") until proven.
- **Investigation is read-only** — No edits, commits, or config changes. Report findings and stop. Do not convert an investigation task into a change task. The user decides what action to take.
- **Report facts, not judgments** — "Snapshot shows `pytest-913` vs `pytest-825`" not "temp path noise." User judges.
- **Do not suggest rule changes without being asked** — Propose, wait for approval, then write.

### Diagnosing Test/Snapshot Failures

**Check git history before theorizing.**

- **Always `git diff HEAD~3` first** — Code changed, test reflects it. Rule this out before blaming environment, deps, or timing.
- **Prove cause, never name it** — No "race condition", "timing issue", "flaky", "import order" without evidence. Deterministic diffs are code changes, not races.
- **Check `git log --oneline -5` and `git status`** — Correlation is not causation. Uncommitted changes from prior sessions exist.
- **Admit ignorance** — Cannot explain after checking diff? Say so. Do not fabricate technical terms.
- **Stash-proven regression is your regression** — `git stash` = 0 mismatches, working state = N > 0? Your changes caused it. Identify the specific test, inspect the diff report, fix the root cause. Never dismiss as "flaky" or "pre-existing". Varying N indicates a race you introduced.
- **Report regressions in summary** — State explicitly. Do not claim "all green" when mismatches exist.

### Debug Procedure

1. **Log thoroughly** — `logger.debug()` at every decision point. Variables, branches, state transitions. Use `%s` args, not f-strings.
2. **Isolate** — Minimal case first, incrementally add complexity. Same instrumentation across experiments.
3. **Trace callers** — Log `"".join(traceback.format_stack(limit=8)).strip()` when a function fires unexpectedly.
4. **Verify at render boundaries** — For UI bugs, log Python state (properties, reactive values) AND rendered output (button labels, widget text). Correct state ≠ correct buffer.

### Systematic Caller Chain Analysis

When fixing a function, **enumerate every call site before writing code**:

1. `grep` all callers
2. Trace **who invokes each** (direct, callbacks, tool results, event handlers, async workers)
3. Classify: must skip, must always execute, or conditional
4. Apply fix to every classified path — never assume only the obvious caller matters
5. Re-grep after changes — verify no caller missed

### Debugging Async/UI Bugs

**Prove claims with timestamped evidence.**

- **Trace UI elements to code paths** — Extra notification? Count `self.notify()` calls along the path. Double notification = double call chain.
- **Log at mount/prune/refresh** — Widget class, child count, `time.monotonic()` timestamp. Write to `/tmp/debug.txt` with `flush()`.
- **Never claim "timing issue" without evidence** — Log exact state at each async boundary with timestamps. Show the discrepancy.
- **Enumerate the widget tree** — List every widget: class, history index, child count. Count manually.
- **Trace the formula** — Log inputs at computation: `32 - 5 = 27`, not just the result.
- **Show transitions** — (1) created, (2) pruned, (3) remaining, (4) computed count. Proactively.

## Timeout Strategy

For commands exceeding 30s, always set explicit `timeout`:

- Pre-commit: `timeout=600`
- Full test suite: `timeout=300`
- Individual tests: `timeout=120`

Never bypass safety checks due to timeouts. Retry with higher timeout first.

**"Analyze" or "review" code changes** is NOT read-only — run full test suite. Claiming "all tests pass" without running them is a critical failure.

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

**Commit Command Rules:**
- **ALWAYS use `<<'EOF'` heredoc** (or `printf ... | git commit -F -`). Never `git commit -m` with multi-line messages — single-quote errors silently drop `Co-Authored-By`.
- **Verify after committing** — `git log -1 --format="%B"`. Confirm `Co-Authored-By` is present. Do not trust `git log --oneline`.
- **Non-zero return or stderr = hard failure.** Do not declare completion until verified.

**Pre-commit Hook Failures:**
1. Fix the issue
2. Re-run pre-commit to verify
3. Proceed to commit
4. Report hook results in summary

## Change Impact Analysis

**Before changing code:**
- Identify all call sites using `grep` or `lsp`
- **Caller chain audit**: Trace upward — direct callers, indirect via callbacks, tool results, event handlers. Classify each path. Apply fix to every path. Never assume one caller.
- Check for imports of affected symbols
- Review dependent tests
- Trace data flow — verify no unintended breaking changes

**After test failures:**
- **Map failures to your diff first** — Your changes touch the failing test's code path? Expected. If you add/remove/modify UI elements, notifications, or output format — update the snapshot or fix the code.
- **Re-grep after changes** — Re-grep every symbol you touched. New callers may have been added by other changes, or you may have missed indirect paths. Second pass catches what the first missed.

## Coding Requirements

**Follow existing coding style:**
- Investigate deeply before writing tests — placement, mocks, domain structure
- Do NOT write in your own way — it causes financial losses
- Use FakeBackend if necessary; use pilot.press() for UI tests
- Do NOT assert internal behavior or mix textual_ui with acp
- **ONLY use `main` branch as coding style reference** — not `custom-fix-*` branches

**Minimize Git Diffs:**
Minimize diff against `origin/main` (the PR base), not just the previous commit:
- Keep existing inline code inline — no extracting helpers unless logic is genuinely new
- Early returns over `else:` blocks — avoids reindenting
- No docstrings on existing functions — genuinely new functions only
- Match `origin/main` indentation exactly
- Minimal additions over refactoring
Always check `git diff origin/main -- <file>` to verify PR diff size.

**Write cohesive, low-coupling code.** Reuse existing logic. This code is long-term maintenance.

## 🧪 Testing Requirements

### Verify Before Reporting Completion

Always run relevant tests after any code change. Do not wait for explicit instruction. Testing is part of the fix.

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

**Critical failures:** partial tests, skipping E2E, claiming "tests pass" without running all 3, piping pre-commit output without writing to file first.

### Test Reporting

When claiming coverage: name the test function, state the file path. No generic checkmarks without citation.

### Debugging

- ✅ Use `logger.debug()` with `--log-cli-level=DEBUG`
- ❌ NEVER use `print()` or `rprint()` in tests

### Unit Test Guidelines

**Minimize mocking:** actual implementations whenever feasible. Mock ONLY external services, environment-dependent files, side effects.

### TUI Tests

All TUI changes MUST be tested with `terminalcp` skill.

### Snapshot Tests

**Never update reference snapshots blindly.** Always verify visually first:

1. Run with `--snapshot-report=snapshot_report.html` (does NOT overwrite reference)
2. Use `playwright-cli` to open the report, take a screenshot
3. Use `read_image` to inspect — verify the change is intentional
4. Only `--snapshot-update` if visual change is correct
5. If unwanted, fix the code

**Visual inspection before statistics.** Do not run stash-and-compare loops or flakiness tests until you have inspected the diff with `read_image`. Statistics answer "did my change cause this?" — visual diff answers "what broke?" and may invalidate your hypothesis. Forming a hypothesis before looking at the diff violates evidence-first.

```bash
uv run pytest tests/snapshots/test_xxx.py --snapshot-report=snapshot_report.html
# playwright-cli screenshot → read_image review
# If correct: uv run pytest tests/snapshots/test_xxx.py --snapshot-update
```

**Reading raw snapshot SVGs:** Snapshots live in `tests/snapshots/__snapshots__/<test_module>/`:
1. Copy SVGs to scratchpad, embed via `<object data="file.svg" type="image/svg+xml">`
2. Serve: `nohup python3 -m http.server 8765 --directory <scratchpad>` (file:// blocked by Chromium)
3. `playwright-cli open --browser=chromium http://localhost:8765/page.html` + `screenshot`
4. `read_image` on the screenshot
5. **ALWAYS kill the server** — `kill <pid>` or `lsof -ti :8765 | xargs kill`. Avoid ports 9091-9093.

### Testing Commands

```bash
uv sync                           # Python dependencies
npm install                       # JavaScript dependencies
npm run playwright:install        # Playwright browsers
uv run pytest tests/              # Python tests
npm test                          # JavaScript tests
nohup npm run test:e2e > /tmp/e2e-test-output.log 2>&1 & echo $! > /tmp/e2e-pid
npm run test:e2e:coverage         # E2E with JS coverage + HTML report
npm run test:e2e:ui               # Interactive E2E
npm run test:e2e:headed           # Visible browser
```

**E2E Test Notes:**
- `bash` calls are stateless — `$!` vanishes between calls. Run as **two separate** `bash` calls:
  ```bash
  # Kill existing E2E, then start new
  if kill -0 $(cat /tmp/e2e-pid 2>/dev/null) 2>/dev/null; then kill $(cat /tmp/e2e-pid) 2>/dev/null; while kill -0 $(cat /tmp/e2e-pid) 2>/dev/null; do sleep 1; done; fi; lsof -ti :9100-9109 | xargs -r kill -9 2>/dev/null || true; nohup npm run test:e2e > /tmp/e2e-test-output.log 2>&1 & echo $! > /tmp/e2e-pid
  ```
  ```bash
  while kill -0 $(cat /tmp/e2e-pid) 2>/dev/null; do sleep 2; done; tail -20 /tmp/e2e-test-output.log
  ```
- NEVER `tail -f` (blocks). NEVER kill ports 9091-9093 (production).
- E2E uses ports 9100-9109. Kill: `lsof -ti :9100-9109 | xargs -r kill -9 2>/dev/null || true`

### Build Commands

```bash
uv run python scripts/build_cython.py    # Manual build
uv sync --no-editable                   # Build with deps (triggers hook)
uv build --wheel                        # Wheel builds (hooks run automatically)
```

Editable installs (`uv sync` without `--no-editable`) do not run build hooks. Use `--no-editable` or the build script.

## Tool Usage Guidelines

Always use dedicated tools instead of `bash` when available. Use `bash` only for:
- System information (`pwd`, `whoami`, `date`)
- Git operations (`git status`, `git diff`)
- Package management (`pip list`, `npm list`)

IMPORTANT: this context may or may not be relevant to your task. You should act on these guidelines if they are relevant to your task.
