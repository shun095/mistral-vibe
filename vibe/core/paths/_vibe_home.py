from __future__ import annotations

from collections.abc import Callable
import os
from pathlib import Path

from vibe import VIBE_ROOT


class GlobalPath:
    def __init__(self, resolver: Callable[[], Path]) -> None:
        self._resolver = resolver

    @property
    def path(self) -> Path:
        return self._resolver()


_DEFAULT_VIBE_HOME = Path.home() / ".vibe"


def _get_vibe_home() -> Path:
    if vibe_home := os.getenv("VIBE_HOME"):
        return Path(vibe_home).expanduser().resolve()
    return _DEFAULT_VIBE_HOME


def _is_e2e_test_mode() -> bool:
    """Check if running in E2E test mode."""
    return os.getenv("VIBE_E2E_TEST") == "true"


def _get_e2e_test_dir() -> Path | None:
    """Get the E2E test directory if in test mode."""
    if not _is_e2e_test_mode():
        return None
    if e2e_dir := os.getenv("VIBE_E2E_TEST_DIR"):
        return Path(e2e_dir).expanduser().resolve()
    return None


VIBE_HOME = GlobalPath(_get_vibe_home)
GLOBAL_ENV_FILE = GlobalPath(lambda: VIBE_HOME.path / ".env")


def _resolve_session_log_dir() -> Path:
    """Resolve session log directory, using E2E test dir if in test mode."""
    e2e_dir = _get_e2e_test_dir()
    if e2e_dir:
        return e2e_dir / "logs" / "session"
    return VIBE_HOME.path / "logs" / "session"


def _resolve_history_file() -> Path:
    """Resolve history file path, using E2E test dir if in test mode."""
    e2e_dir = _get_e2e_test_dir()
    if e2e_dir:
        return e2e_dir / "vibehistory"
    return VIBE_HOME.path / "vibehistory"


SESSION_LOG_DIR = GlobalPath(_resolve_session_log_dir)
TRUSTED_FOLDERS_FILE = GlobalPath(lambda: VIBE_HOME.path / "trusted_folders.toml")
LOG_DIR = GlobalPath(lambda: VIBE_HOME.path / "logs")
LOG_FILE = GlobalPath(lambda: VIBE_HOME.path / "logs" / "vibe.log")
HISTORY_FILE = GlobalPath(_resolve_history_file)
PLANS_DIR = GlobalPath(lambda: VIBE_HOME.path / "plans")

DEFAULT_TOOL_DIR = GlobalPath(lambda: VIBE_ROOT / "core" / "tools" / "builtins")
