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
- Avoid comments and docstrings, except for when there's a hard to spot corner case

## Typing & imports

- Pyright is strict and gates CI; fix types at the source.
- No relative imports — `ban-relative-imports = "all"`. Always `from vibe.core.x import …`.
- No inline `# type: ignore` or `# noqa`. Fix with refined signatures (TypeVar, Protocol), `isinstance` guards, `typing.cast` when control flow guarantees the type, or a small typed wrapper at the boundary.

## Pydantic

- Parse external data via `model_validate`, `field_validator`, or `model_validator(mode="before")` — never ad-hoc `getattr` / `hasattr` walks or custom `from_sdk` constructors.
- Set `ConfigDict(extra=…)` explicitly. Use `validation_alias` (or field aliases) for kebab-case TOML keys.
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

## TCSS

- When a rule sets `color: $text-muted;`, pair it with a nested `&:ansi { text-style: dim; }` so the muted intent survives under ANSI themes.
- Never use `ansi_*` colors (e.g. `ansi_red`, `ansi_bright_blue`). Use Textual theme variables like `$primary`, `$foreground`, `$surface`, `$error`, etc. — see https://textual.textualize.io/guide/design/. ANSI themes are derived from these variables automatically.

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
| Tests | **OVERRIDDEN** — [Testing Requirements](#testing-requirements) |
| Git | **OVERRIDDEN** — [Git Operations & Change Impact](#git-operations--change-impact) |
| Autoimprovement | **OVERRIDDEN** — [Evidence Protocol](#evidence-protocol) |
| Safety Rules | **NEW** — [Safety & Workflow Guardrails](#safety--workflow-guardrails) |

## Safety & Workflow Guardrails

**NEVER:**
- Change code/git or create commits unless explicitly instructed.
- Use `git reset --hard`, `git checkout <filename>`, or `git stash drop` without backup. These commands can cause complete loss of unsaved changes.
- Skip pre-commit hooks or use `--no-verify`.
- Modify/delete files in `~/.vibe` or write logs to `~/.vibe/logs/vibe.log`.
- Create task files in project root. Use `./tmp/` for artifacts instead.
- Use filename versioning (`*_v2`, `*_final`).
- Kill processes on ports 9091-9093 (production) or use `pkill -f "vibe"` (kills production). Use specific PID or port-based killing instead.
- Filter diagnostic output — no piping through `grep`, `tail`, or `head`. Write to file first (`> ./tmp/result.log 2>&1`), then search. Use `tail -n 100` minimum. The full file is the source of truth.
- Fabricate results, unrun tests, or partial output presented as complete.
- Suggest rule changes without being asked.

**MUST:**
- Backup before destructive ops: e.g., `git reset --hard`, `git checkout <filename>`, `git stash pop` (prefer `git stash -u` and `git stash apply`).
- All commits MUST pass pre-commit hooks (300s timeout).
- Stage first, wait for explicit user approval before committing. Pre-commit passing does not replace approval. **Commit Approval Checkpoint:** Before `git commit`: (1) show `git diff --cached --stat`, (2) ask user to approve, (3) wait for explicit "yes", (4) commit. Never skip.
- Proactive verification: update or add tests and run relevant ones after any code change. Testing is part of the fix.
- Follow the rules you're reading. Verify compliance before action.
- "Analyze" or "review" code changes is NOT read-only — run full test suite. Claiming "all tests pass" without running them is a critical failure.
- Investigation is read-only: no edits, commits, or config changes. Report findings and stop. User decides action.

**Timeout Strategy:** For commands exceeding 30s, always set explicit `timeout`: Pre-commit 300s, full test suite 300s, individual tests 120s. Never bypass safety checks due to timeouts. Retry with higher timeout first.

## Pre-Change Gates

Complete these before any code change. If you cannot, STOP and report what's missing.

1. `git ls-tree -r --name-only origin/main -- <target_dir>/` — find where similar code lives. Place new code alongside its analog.
2. `grep` for the pattern you're implementing. Read the top 3 results. Cite the file:line you're following. If no pattern exists, report to the user.
3. List every file you'll change with the specific change per file. If you cannot name the files, you are not ready to edit.
4. State any assumptions and how you'll verify them.

**Exhaustive scope & restatement.** Never edit a file until you enumerate every location that must change. The default assumption is that any touchpoint related to the task needs attention. If you modify X, ask: what depends on X? What calls X? What does X call? What shares X's invariant? Partial fixes are failures. NEVER narrow scope to the named module — it is the surface, not the boundary. Before any edit, write one line restating the goal and list every file you intend to change with the specific change per file. If you cannot name the files, you are not ready to edit.

**Explore, trace, and verify breadth.** Never edit a file you haven't read. Never read a file without first reading its callers and callees. For UI changes: read `can_focus`, `BINDINGS`, and parent/child relationships. For key bindings: read how existing bindings resolve conflicts. If you cannot explain the existing pattern in one sentence, keep reading. When targeting feature X, read EVERY participating module — even if you don't plan to edit it. Consolidate parallel implementations into shared logic; if and only if impossible, verify they produce identical side effects. **Trace data flow from source to sink:** where does data originate, what transforms it, how does it reach X, what shares it? Read every module in the chain. NEVER create parallel data structures when the system already carries one — find and reuse the existing one. **If you cannot name the source module and the path to X, you are not ready to edit. This rule is non-negotiable.** Violating it produces dual-state bugs that require multiple rounds to fix. Identify every entry point that reaches changed code (direct calls, callbacks, event handlers, background threads, CLI flags, web endpoints, slash commands). Each path must be fixed or documented as excluded.

## Flip-Flop Rule

If your approach fails twice in the same region:
1. STOP the current approach.
2. `grep` for the pattern — read existing code that solves the same problem.
3. If no pattern exists, report what you've tried and why it failed.
4. DO NOT remove working code, narrow scope, skip features, or add `# type: ignore` as a fix.

**Guardrails & fallbacks.** Ask on ambiguity before editing. If your approach produces test failures twice in the same region, abandon it. Re-read the code, identify why it failed, and choose a fundamentally different strategy. Flip-flopping fixes is a critical failure. AGENTS.md rules are circuit breakers, not suggestions. Do not skip a rule because "the change is obvious." Obvious changes fail silently. When a rule conflicts with your intuition, follow the rule and note your concern. Never silently override a rule.

## Evidence Protocol

**Honesty & Exact Execution:**
- Gather facts before assumptions. The user values accuracy over speed. A correct, incomplete answer builds trust.
- Run exactly what the user asks — no added flags/options. If you believe a flag is needed, ask first. Never reinterpret commands. User instructions override all AGENTS.md heuristics.
- Baseline first: follow instructions exactly to confirm they work. Only then apply judgment.
- Errors are data: read output and relevant code, understand cause, then continue. Do not re-run with silent modifications.
- Consult only when blocked. Report everything else and proceed. Own mistakes immediately. Lead with failures.
- Report matching findings: if a diagnostic flags something the user stated concern about, mention it.

**Evidence Over Assertions:**
- Prove claims with unfiltered output. User must independently review your conclusion. One claim, one proof. Without output, the claim is noisy garbage.
- Survey test infrastructure before building verification. If the project has E2E tests producing visual artifacts, run those and read artifacts with `read_image`. Never create standalone test pages or mock HTML that do not verify the actual code.
- Never write tests that do not fully verify the system's operation. Tests must detect failures in all three cases: when target data is out of order, when data is missing, or when unnecessary data is included.
- Prove before diagnosing: never state "pre-existing", "flaky", or "caused by change" before running isolated tests. "Pre-existing"? Stash and re-run. "Flaky"? Run twice on same code. State uncertainty until proven.
- Stash-and-compare properly: `git stash`, show full output, `git stash apply`, show full output. Both visible.
- Report facts, not judgments. User judges.

**Diagnosing Test/Snapshot Failures:**
- Check git history before theorizing. Always `git diff HEAD~3` first. Rule out code changes before blaming environment/deps/timing.
- Check `git log --oneline -5` and `git status`. Correlation != causation.
- Prove cause, never name it: no "race condition", "timing issue", "flaky", "import order" without evidence. Deterministic diffs are code changes, not races.
- Admit ignorance if unexplainable after checking diff. Do not fabricate technical terms.
- Stash-proven regression is your regression: `git stash` = 0 mismatches, working state = N > 0? Your changes caused it. Identify specific test, inspect diff report, fix root cause. Never dismiss. Varying N indicates a race you introduced.
- Report regressions in summary explicitly. Do not claim "all green" when mismatches exist.

**Debug Procedure & Systematic Analysis:**
- Log thoroughly: `logger.debug()` at every decision point. Variables, branches, state transitions.
- Isolate: minimal case first, incrementally add complexity. Same instrumentation across experiments.
- Trace callers: log `"".join(traceback.format_stack(limit=8)).strip()` when a function fires unexpectedly.
- Enumerate every call site before writing code: `grep` all callers, trace who invokes each (direct, callbacks, tool results, event handlers, async workers), classify (must skip/always execute/conditional), apply fix to every path, re-grep after changes.
- Verify at render boundaries: for UI bugs, log Python state AND rendered output. Correct state != correct buffer.

**Debugging Async/UI Bugs:**
- Trace UI elements to code paths. Extra notification? Count `self.notify()` calls. Double notification = double call chain.
- Log at mount/prune/refresh: widget class, child count, `time.monotonic()` timestamp. Write to `/tmp/debug.txt` with `flush()`.
- Never claim "timing issue" without evidence: log exact state at each async boundary with timestamps. Show discrepancy.
- Enumerate widget tree: list every widget (class, history index, child count). Count manually.
- Trace the formula: log inputs at computation (e.g., `32 - 5 = 27`), not just result.
- Show transitions proactively: (1) created, (2) pruned, (3) remaining, (4) computed count.

## Verification Discipline

**Close the loop & complete verification.** Every change introduces artifacts (debug logs, temporary flags, test stubs, unused imports). Before declaring completion, re-read every touched file and verify nothing was left behind. The diff should contain only what the task requires. A task is complete only when: (1) every changed file passes lint/type checks, (2) every affected test passes, (3) snapshots are visually inspected using `read_image` and updated if needed, (4) the diff is reviewed for leftover artifacts.

**Snapshot & flaky test protocol.** Never run `--snapshot-update` without first running `--snapshot-report`, opening the report with playwright-cli, and reading each diff with `read_image`. The header count is not proof of inspection. Scroll to each one, name each one. If you cannot name the visual difference, you have not inspected it. Report flaky tests, never dismiss them. If a test fails in a full run but passes individually, report it. Write full output to a file first, then search. Do not declare "flaky" without evidence: at least two runs showing different results on the same code.

## Git Operations & Change Impact

**Commit Message Format & Rules:**
```bash
git commit -F - <<'EOF'
<type>: <subject (max 50 chars)>

- detail 1
- detail 2

Generated by Mistral Vibe.
Co-Authored-By: Mistral Vibe <vibe@mistral.ai>
EOF
```
- ALWAYS use `<<'EOF'` heredoc (or `printf ... | git commit -F -`). Never `git commit -m` with multi-line messages — single-quote errors silently drop `Co-Authored-By`.
- Verify after committing: `git log -1 --format="%B"`. Confirm `Co-Authored-By` is present. Do not trust `git log --oneline`.
- Non-zero return or stderr = hard failure. Do not declare completion until verified.
- Pre-commit Hook Failures: (1) fix issue, (2) re-run pre-commit to verify, (3) proceed to commit, (4) report hook results in summary.

**Change Impact Analysis:**
- Before changing code: identify all call sites using `grep`. Perform caller chain audit: trace upward (direct, indirect, callbacks, tool results, event handlers). Classify each path. Apply fix to every path. Check imports of affected symbols. Review dependent tests. Trace data flow — verify no unintended breaking changes.
- After test failures: map failures to your diff first. Your changes touch the failing test's code path? Expected. If you add/remove/modify UI elements, notifications, or output format — check snapshot using `read_image` then fix code. Re-grep after changes — second pass catches missed indirect paths.

## Coding Requirements

**Style & Structure:**
- Follow existing coding style. Research existing coding style first when you change or implement new feature.
- Investigate deeply before writing tests: placement, mocks, domain structure. Do NOT write in your own way — it causes critical maintainability loss.
- Use `FakeBackend` if necessary; use `pilot.press()` for TUI tests. Do NOT assert internal behavior or mix `textual_ui` with `acp`.
- Write cohesive, low-coupling code. Reuse existing logic. This code is long-term maintenance.

**Minimize Git Diffs:**
Minimize diff against both `origin/main` (the upstream branch) and `HEAD` (our fork branch), not just the previous commit:
- Keep existing inline code inline — no extracting helpers unless logic is genuinely new.
- Early returns over `else:` blocks — avoids reindenting.
- No docstrings on existing functions.
- Match `origin/main` and `HEAD` indentation exactly.
- Minimal deletions over refactoring.
Always check `git diff origin/main -- <file>` and `git diff HEAD -- <file>` to verify the commit diff size.

## Testing Requirements

**Mandatory Execution & Verification:**
- Verify before reporting completion: always run relevant tests after any code change. Do not wait for explicit instruction.
- Run ALL three test suites sequentially (never parallel — shared ports/resources cause flaky failures):
  ```bash
  uv run pytest tests/    # Python tests (timeout=300)
  npm test                # JavaScript unit tests
  npm run test:e2e        # WebUI E2E tests (timeout=300)
  ```
- You are NOT done until all 3 pass. Report actual counts:
  ```
  **Test result**:
  Python tests:     X passed, X skipped, X warning, X failed, X flakey
  JavaScript tests: X passed, X skipped, X warning, X failed, X flakey
  E2E tests:        X passed, X skipped, X warning, X failed, X flakey

  **Concerns found in the test**:
  <Report any concerns you've found>
  ```
- Critical failures: partial tests, skipping E2E, claiming "tests pass" without running all 3, piping pre-commit output without writing to file first.
- When claiming coverage: name the test function, state the file path. No generic checkmarks without citation.

**Assertions:** Every test must assert **presence**, **absence** (count matches), and **order**.
Concretely: if expected is `[A, B, C]`, assert `len == 3`, `result[0] == A`, `result[1] == B`, `result[2] == C`. Partial assertions are failures.

**Debugging & Mocking:**
- Use `logger.debug()` with `--log-cli-level=DEBUG`. NEVER use `print()` or `rprint()` in tests.
- Minimize mocking: actual implementations whenever feasible. Mock ONLY external services, environment-dependent files, side effects.
- Use `terminalcp` skill to debug TUI changes.

**Snapshot Tests:**
- Never update reference snapshots blindly. Do comprehensive visual inspection first.
  1. Run with `--snapshot-report=snapshot_report.html` (does NOT overwrite reference).
  2. Use `playwright-cli` to open report, take screenshot.
  3. Use `read_image` to inspect — verify change is intentional.
  4. Scroll and repeat 2. and 3. until you complete to check all snapshot changes.
  5. Only `--snapshot-update` if visual change is correct. If unwanted, fix code.
  6. Forming a hypothesis before looking at the diff violates evidence-first.
- Reading raw snapshot SVGs (`tests/snapshots/__snapshots__/<test_module>/`):
  1. Copy SVGs to scratchpad, embed via `<object data="file.svg" type="image/svg+xml">`.
  2. Check if port 8765 is not used: `lsof -ti :8765`
  3. Serve: `nohup python3 -m http.server 8765 --directory <scratchpad>` (file:// blocked by Chromium).
  4. `playwright-cli open --browser=chromium http://localhost:8765/page.html` + `screenshot`.
  5. `read_image` on screenshot.
  6. ALWAYS kill server: `kill <pid>` or `lsof -ti :8765 | xargs kill`. Avoid ports 9091-9093.

**E2E Test Notes:**
- `bash` calls are stateless — `$!` vanishes between calls. Run as two separate `bash` calls:
  ```bash
  # Kill existing E2E, then start new
  if kill -0 $(cat /tmp/e2e-pid 2>/dev/null) 2>/dev/null; then kill $(cat /tmp/e2e-pid) 2>/dev/null; while kill -0 $(cat /tmp/e2e-pid) 2>/dev/null; do sleep 1; done; fi; lsof -ti :9100-9109 | xargs -r kill -9 2>/dev/null || true; nohup npm run test:e2e > /tmp/e2e-test-output.log 2>&1 & echo $! > /tmp/e2e-pid
  ```
  ```bash
  while kill -0 $(cat /tmp/e2e-pid 2>/dev/null); do sleep 2; done; tail -20 /tmp/e2e-test-output.log
  ```
- NEVER `tail -f` (blocks). NEVER kill ports 9091-9093 (production).
- E2E uses ports 9100-9109. Kill: `lsof -ti :9100-9109 | xargs -r kill -9 2>/dev/null || true`
- NEVER run any other high-load processes while E2E testing is in progress.

**Testing & Build Commands:**
```bash
uv sync                           # Python dependencies
npm install                       # JavaScript dependencies
npm run playwright:install        # Playwright browsers
uv run pytest tests/              # Python tests
npm test                          # JavaScript tests
npm run test:e2e:coverage         # E2E with JS coverage + HTML report
npm run test:e2e:ui               # Interactive E2E
npm run test:e2e:headed           # Visible browser
```

**Build Commands:**
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

---

IMPORTANT: this context may or may not be relevant to your task. You should act on these guidelines if they are relevant to your task.
