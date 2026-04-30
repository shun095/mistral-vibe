# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in this repository.

## Project Overview

Mistral Vibe is an open-source CLI coding assistant powered by Mistral models. It runs as a Python application with a Textual-based TUI and an optional WebUI. The codebase implements the Agent Client Protocol (ACP) for IDE integration.

**Python 3.12+ only.** All commands must be run through `uv` -- never invoke `python` or `pip` directly.

## Module Architecture

The `vibe/` package has three top-level modules with strict import contracts:

- **`vibe.core`** -- Shared business logic: agent_loop, tools, config, LLM backends, session management, skills, MCP, prompts, system_prompt. Must NOT import `vibe.cli` or `vibe.acp` (exception: `vibe.core.agent_loop` may import `vibe.cli.terminal_detect`).
- **`vibe.cli`** -- Interactive CLI entry point, Textual TUI, commands, voice, web_ui server. Entry: `vibe.cli.entrypoint:main`.
- **`vibe.acp`** -- ACP server for IDE integration. Entry: `vibe.acp.entrypoint:main`. Must NOT import `vibe.cli`.

Import-linter enforces these contracts. Run `uv run import-linter lint` to verify.

## Commands

### Dependencies

```bash
uv sync                           # Python deps (editable, no Cython build)
uv sync --no-editable             # Python deps + Cython build hook
npm install                       # JS deps
npm run playwright:install        # Playwright browsers for E2E
```

### Test Suite (all three must pass)

```bash
uv run pytest tests/              # Python tests (pytest-xdist, -n auto)
npm test                          # JS unit tests (Jest, tests/js/*.test.js)
npm run test:e2e                  # WebUI E2E (Playwright, Chromium-only default)
```

**Single Python test:** `uv run pytest tests/path/to/test_file.py::test_function -vv --no-header`
**Single JS test:** `npm test -- tests/js/app.test.js`
**E2E in background:** `nohup npm run test:e2e > /tmp/e2e-test-output.log 2>&1 &`

### Lint and Type Check

```bash
uv run ruff check .               # Ruff lint (--fix to auto-fix)
uv run ruff format .              # Ruff format
uv run ruff format --check .      # Format check (CI)
uv run pyright                    # Type checking
uv run pre-commit run --all-files # Full pre-commit suite
```

### Run the Application

```bash
uv run vibe                       # Interactive CLI
uv run vibe --prompt "..."        # Programmatic (non-interactive) mode
uv run vibe-acp                   # ACP server mode for IDE integration
```

### Build

```bash
uv build --wheel                  # Build wheel (triggers Cython build hook)
```

## Key Patterns

### Agent Loop
`vibe.core.agent_loop.py` is the central run loop. It processes messages through a `MiddlewarePipeline` (AutoCompact, ContextWarning, PriceLimit, TurnLimit) and dispatches tool calls. Both CLI and ACP modes use the same core loop, differing only in I/O transport.

### Tools
Built-in tools are in `vibe.core.tools.builtins/`. Tool discovery and execution is coordinated by `vibe.core.tools.manager.ToolManager`. MCP tools are handled by `vibe.core.tools.mcp/`.

### Config
`vibe.core.config._settings.VibeConfig` (Pydantic model) is read from `~/.vibe/config.toml` or `./.vibe/config.toml`. Provider and model configs are nested models.

### Skills
Skills are discovered from `~/.vibe/skills/`, `.vibe/skills/`, `.agents/skills/`, and custom `skill_paths`. The builtin self-awareness skill at `vibe/core/skills/builtins/vibe.py` must be updated when CLI features change.

### Session
Sessions are persisted as JSON in `~/.vibe/sessions/`. Session continuation uses `--continue` / `--resume`.

## Port Safety

- **Ports 9091-9093** are production ports -- never kill processes on these.
- E2E tests use ports 9100-9109 -- safe to clean up after tests.

## Testing Notes

- TUI tests use `pytest-textual-snapshot` with the `terminalcp` skill.
- MCP snapshot tests use direct injection (not mocked servers).
- Minimize mocking in unit tests -- use real implementations when feasible.
- No docstrings in test functions.
- E2E test config: `playwright.config.ts` (8 parallel workers, 120s timeout, 3 browser projects).

## Python Style

See `AGENTS.md` for detailed Python 3.12+ coding guidelines (modern type hints, Pydantic-first parsing, pathlib, walrus operator, match-case, no inline type ignores).
