# Maintainer Review: `custom-fix-2.9` vs `origin/main`

## Diff Summary

| Metric | Value |
|---|---|
| Files changed | 362 (197 new, 165 modified) |
| Lines added | +52,856 |
| Lines deleted | -1,342 |
| Net | +51,514 |

---

## P0 — Blockers (Must Fix Before Merge)

| # | File | Issue | Evidence |
|---|------|-------|----------|
| 1 | `pyproject.toml:118,125` | Duplicate `pytest-xdist>=3.8.0` | Confirmed: appears twice |
| 2 | `scripts/e2e-coverage.js` | Buggy script — remove it and its `test:e2e:coverage` entry from `package.json` | Script is broken and no longer used |
| 3 | `package.json:23,28` | `@types/node ^25.5.0` and `typescript ^6.0.2` — verify versions exist (as of 2026-05 these may be valid) | Check with `npm view @types/node version` and `npm view typescript version` |
| 4 | `vibe/core/event_bus.py:15` | Uses stdlib `logging` instead of `vibe.core.logger` | AGENTS.md violation |
| 5 | `vibe/core/lsp/client_manager.py:26` | `asyncio.Lock()` created at class-definition time (wrong event loop) | Runtime bug under test isolation |
| 6 | `vibe/cli/textual_ui/handlers/event_handler.py:303` | `_chained()` doesn't catch `CancelledError` from `await previous` | Command chain breaks on cancelled task |

---

## P1 — AGENTS.md Violations

| # | File | Issue |
|---|------|-------|
| 7 | `vibe/core/agent_loop.py:205` | Duplicate `import os` inside `_select_backend()` (already at line 10) |
| 8 | `vibe/core/tools/builtins/bash.py:564` | f-string in logger: `logger.debug(f"Config: {self.config}")` |
| 9 | `vibe/core/tools/builtins/lsp.py:17-18` | Imports after module-level constants |
| 10 | `vibe/core/config/_settings.py:17` | Constant defined before imports |
| 11 | `tests/tools/test_lsp_diagnostics.py` | 31 docstrings on test methods (AGENTS.md forbids them) |
| 12 | `tests/core/test_config_exclude_defaults.py` | 68 docstrings on test methods |
| 13 | `tests/cli/textual_ui/test_history_picker.py` | 46 docstrings on test methods |
| 14 | `tests/snapshots/test_ui_snapshot_load_more_5scenarios.py:434-450` | `print()` calls in tests (must use `logger.debug()`) |

---

## P2 — DRY / Code Quality

| # | File | Issue |
|---|------|-------|
| 15 | `vibe/core/utils/retry.py` | Identical `LLMRetryEvent` creation block duplicated in `async_retry` and `async_generator_retry` |
| 16 | `vibe/core/tools/builtins/` | LSP diagnostics pattern duplicated across 4 tool files (edit_file, search_replace, read_file, write_file) |
| 17 | `vibe/core/llm/backend/generic.py` + `mistral.py` | Duplicated `_apply_retry_decorators()` |
| 18 | `vibe/cli/textual_ui/widgets/tool_widgets.py` | LSP diagnostics rendering duplicated 4x in compose() methods |
| 19 | `vibe/cli/web_ui/static/js/app.js:300-500` | `handleEvent` / `_replayEvent` switch duplication (20+ cases each) |
| 20 | `vibe/cli/web_ui/static/js/app.js:910,2840,2870` | Bash card DOM creation duplicated 3x |
| 21 | `vibe/cli/textual_ui/app.py:1062,1072` | `_queued_message` submit block duplicated |
| 22 | `tests/tools/test_lsp_diagnostics.py` | `mock_process` setup duplicated 21 times — extract to fixture |

---

## P3 — Architecture Concerns

| # | File | Issue |
|---|------|-------|
| 23 | `vibe/core/agent_loop.py` | E2E test backend selection via env var in production code |
| 24 | `vibe/core/tools/manager.py` | ClassVar MCP cache without lifecycle management |
| 25 | `vibe/core/tools/builtins/read_image.py` | ClassVar fetch cache without eviction or thread safety |
| 26 | `vibe/core/loop_detection.py:167` | UPPERCASE parameter name `TOOL_ERROR_TAG` |
| 27 | `vibe/core/types.py` | `ToolCallSignature.__eq__` ignores `call_id` field |
| 28 | `vibe/core/tools/base.py` | `Callable[..., T]` defeats type checking |
| 29 | `vibe/core/lsp/` | 5 FIXME comments left in production code |
| 30 | `vibe/cli/web_ui/static/css/style.css` | Hardcoded `#d5f5e3`/`#f5d5dc` in 7+ rules — breaks dark mode |
| 31 | `.pre-commit-config.yaml` | Full test suites as pre-commit hooks (adds minutes per commit) |

---

## P4 — File Size Concerns

| File | Lines | Assessment |
|------|-------|------------|
| `vibe/cli/web_ui/static/js/app.js` | 2,952 | Split into popup-manager, message-renderer, git-viewer |
| `vibe/cli/web_ui/server.py` | 1,025 | Split into auth, routes, websocket, serialization |
| `tests/js/app.test.js` | 1,287 | Split by feature area |
| `vibe/core/lsp/client.py` | 577 | Consider splitting message reader from protocol client |

---

## Positive Observations

- **LSP integration** follows hexagonal architecture cleanly — ports/adapters separation is correct
- **Fuzzy search** has excellent Cython integration with pure-Python fallback
- **New tools** follow a consistent `BaseTool` subclass pattern with proper permissions
- **Event bus** is a proper async pub/sub with fault isolation
- **E2E test fixtures** show good patterns (port pre-allocation, per-test lifecycle)
- **WebUI module** is properly separated from TUI — zero reverse imports from core
- **Config comment preservation** via `tomlkit` is a quality-of-life improvement
- **`json_repair`** for defensive JSON parsing in LLM responses is good

---

## Overall Assessment

The branch introduces substantial new features (WebUI, LSP, fuzzy search, new tools) with generally sound architecture. The main concerns are:

1. **5 P0 blockers** must be fixed before merge (#3 demoted to verification only)
2. **14 AGENTS.md violations** need cleanup (test docstrings, logging format, import order)
3. **12 DRY violations** suggest extractable helpers
4. **Monolithic files** (app.js at 2,952 lines, server.py at 1,025 lines) need splitting
5. **AGENTS.md** has branch-specific user rules appended that shouldn't merge to `main`

The diff is large (+51.5k net lines) but mostly justified by the scope of new features. The code quality is solid overall, with the issues above being polish rather than fundamental problems.


---


## Maintainer feedback about this report

P0:
- #1: Correct
- #2: Correct — remove `scripts/e2e-coverage.js` and its `test:e2e:coverage` script entry from `package.json`
- #3: Not a blocker — versions may exist as of 2026-05, verify with `npm view`
- #4: Correct
- #5: Correct
- #6: Correct

P1: All corrrect.
P2: All correct, but be very careful not to break features if you refactor.
P3:
- #23: E2E test backend selection is necessary for testing — keep it, but ensure the env var guard is tight
- The others are correct. Be careful not to break features if you fix.
P4: All correct. But be very careful not to break if you fix.
