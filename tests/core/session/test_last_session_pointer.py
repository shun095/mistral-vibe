from __future__ import annotations

from pathlib import Path

import pytest

from vibe.core.config import SessionLoggingConfig
from vibe.core.session import last_session_pointer


@pytest.fixture
def session_logging(tmp_path: Path) -> SessionLoggingConfig:
    return SessionLoggingConfig(save_dir=str(tmp_path))


def _set_tty(monkeypatch: pytest.MonkeyPatch, key: str | None) -> None:
    monkeypatch.setattr(last_session_pointer, "current_tty_key", lambda: key)


def test_load_returns_none_when_no_tty(
    session_logging: SessionLoggingConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_tty(monkeypatch, None)
    assert last_session_pointer.load(session_logging) is None


def test_load_returns_none_when_no_pointer_written(
    session_logging: SessionLoggingConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_tty(monkeypatch, "ttys001")
    assert last_session_pointer.load(session_logging) is None


def test_record_then_load_round_trip(
    session_logging: SessionLoggingConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_tty(monkeypatch, "ttys001")
    last_session_pointer.record(session_logging, "abc-123")
    assert last_session_pointer.load(session_logging) == "abc-123"


def test_record_skips_when_no_tty(
    session_logging: SessionLoggingConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_tty(monkeypatch, None)
    last_session_pointer.record(session_logging, "abc-123")
    pointer_dir = Path(session_logging.save_dir) / last_session_pointer.POINTER_DIR_NAME
    assert not pointer_dir.exists()


def test_record_skips_when_logging_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    disabled = SessionLoggingConfig(save_dir=str(tmp_path), enabled=False)
    _set_tty(monkeypatch, "ttys001")
    last_session_pointer.record(disabled, "abc-123")
    assert not (tmp_path / last_session_pointer.POINTER_DIR_NAME).exists()


def test_pointers_are_per_tty(
    session_logging: SessionLoggingConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_tty(monkeypatch, "ttys001")
    last_session_pointer.record(session_logging, "session-a")

    _set_tty(monkeypatch, "ttys002")
    last_session_pointer.record(session_logging, "session-b")
    assert last_session_pointer.load(session_logging) == "session-b"

    _set_tty(monkeypatch, "ttys001")
    assert last_session_pointer.load(session_logging) == "session-a"


def test_record_ignores_empty_session_id(
    session_logging: SessionLoggingConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_tty(monkeypatch, "ttys001")
    last_session_pointer.record(session_logging, None)
    last_session_pointer.record(session_logging, "")
    assert last_session_pointer.load(session_logging) is None


def test_clear_matching_removes_matching_pointers_only(
    session_logging: SessionLoggingConfig,
) -> None:
    pointer_dir = Path(session_logging.save_dir) / last_session_pointer.POINTER_DIR_NAME
    pointer_dir.mkdir()
    (pointer_dir / "ttys001").write_text("deleted-session\n", encoding="utf-8")
    (pointer_dir / "ttys002").write_text("other-session\n", encoding="utf-8")
    (pointer_dir / "ttys003").write_text("deleted-session\n", encoding="utf-8")
    (pointer_dir / "nested").mkdir()

    last_session_pointer.clear_matching(session_logging, "deleted-session")

    assert not (pointer_dir / "ttys001").exists()
    assert (pointer_dir / "ttys002").read_text(encoding="utf-8") == "other-session\n"
    assert not (pointer_dir / "ttys003").exists()
    assert (pointer_dir / "nested").is_dir()


def test_clear_matching_skips_when_logging_disabled(tmp_path: Path) -> None:
    disabled = SessionLoggingConfig(save_dir=str(tmp_path), enabled=False)
    pointer_dir = tmp_path / last_session_pointer.POINTER_DIR_NAME
    pointer_dir.mkdir()
    pointer_path = pointer_dir / "ttys001"
    pointer_path.write_text("deleted-session\n", encoding="utf-8")

    last_session_pointer.clear_matching(disabled, "deleted-session")

    assert pointer_path.exists()


def test_current_tty_key_returns_none_when_ttyname_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr(last_session_pointer.os, "ttyname", raising=False)

    assert last_session_pointer.current_tty_key() is None


def _patch_windows(monkeypatch: pytest.MonkeyPatch, hwnd: int) -> None:
    import ctypes
    from types import SimpleNamespace

    fake_windll = SimpleNamespace(
        kernel32=SimpleNamespace(GetConsoleWindow=lambda: hwnd)
    )
    monkeypatch.setattr(last_session_pointer.sys, "platform", "win32")
    monkeypatch.setattr(ctypes, "windll", fake_windll, raising=False)


def test_current_tty_key_uses_console_hwnd_on_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_windows(monkeypatch, hwnd=12345)
    assert last_session_pointer.current_tty_key() == "conhost-12345"


def test_current_tty_key_falls_back_to_wt_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_windows(monkeypatch, hwnd=0)
    monkeypatch.setenv("WT_SESSION", "abcd-1234")
    assert last_session_pointer.current_tty_key() == "wt-abcd-1234"


def test_current_tty_key_falls_back_to_ppid_on_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_windows(monkeypatch, hwnd=0)
    monkeypatch.delenv("WT_SESSION", raising=False)
    monkeypatch.setattr(last_session_pointer.os, "getppid", lambda: 4242)
    assert last_session_pointer.current_tty_key() == "ppid-4242"


def test_pointer_roundtrip_with_find_session_by_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simulate the full -c round-trip:

    1. Session exits → _get_session_resume_info() returns short_session_id(full_id)
    2. last_session_pointer.record() stores the short ID (8 chars)
    3. User runs `vibe -c` → last_session_pointer.load() reads the short ID
    4. SessionLoader.find_session_by_id() calls shorten_session_id() (idempotent for 8 chars)
       and finds the directory via glob prefix_*_8chars.
    """
    from datetime import datetime
    import json

    from vibe.core.session.session_id import shorten_session_id
    from vibe.core.session.session_loader import SessionLoader

    full_id = "a1b2c3d4-e5f6-789a-bcde-xyz123abc456"
    short_id = shorten_session_id(full_id)  # "a1b2c3d4"

    save_dir = tmp_path / "sessions"
    save_dir.mkdir()
    config = SessionLoggingConfig(
        save_dir=str(save_dir), session_prefix="session", enabled=True
    )

    # Create session directory with the real naming convention
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_folder = save_dir / f"session_{timestamp}_{short_id}"
    session_folder.mkdir()

    (session_folder / "messages.jsonl").write_text(
        '{"role": "user", "content": "hello"}\n', encoding="utf-8"
    )
    (session_folder / "meta.json").write_text(
        json.dumps({
            "session_id": full_id,
            "environment": {"working_directory": "/test"},
        }),
        encoding="utf-8",
    )

    _set_tty(monkeypatch, "ttys001")

    # _get_session_resume_info() returns short_session_id(full_id)
    last_session_pointer.record(config, short_id)

    # Simulate what -c does: load pointer → find_session_by_id
    loaded = last_session_pointer.load(config)
    assert loaded is not None
    assert loaded == short_id

    result = SessionLoader.find_session_by_id(loaded, config)
    assert result is not None, (
        f"Pointer round-trip failed: stored {short_id!r}, "
        f"loaded {loaded!r}, glob uses shorten_session_id({loaded!r}) = {shorten_session_id(loaded)!r}"
    )
    assert result == session_folder


def test_pointer_fallback_when_current_session_not_saved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reproduce the bug: /clear → quit without message → -c restores wrong session.

    Scenario:
    1. Session A exists on disk (saved from a previous run)
    2. User runs /clear → new session B (not saved, no messages sent)
    3. User quits → _get_session_resume_info() can't find B on disk
    4. WITHOUT FIX: returns None → pointer not updated → stale pointer
    5. WITH FIX: falls back to find_latest_session → returns A's ID → pointer updated

    This test verifies that find_latest_session correctly returns session A
    when the current session B doesn't exist on disk.
    """
    from datetime import datetime
    import json

    from vibe.core.session.session_id import shorten_session_id
    from vibe.core.session.session_loader import SessionLoader

    full_id_a = "a1b2c3d4-e5f6-789a-bcde-xyz123abc456"
    short_id_a = shorten_session_id(full_id_a)  # "a1b2c3d4"

    save_dir = tmp_path / "sessions"
    save_dir.mkdir()
    config = SessionLoggingConfig(
        save_dir=str(save_dir), session_prefix="session", enabled=True
    )

    # Create session A on disk (the only saved session)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_a_folder = save_dir / f"session_{timestamp}_{short_id_a}"
    session_a_folder.mkdir()
    (session_a_folder / "messages.jsonl").write_text(
        '{"role": "user", "content": "hello"}\n', encoding="utf-8"
    )
    (session_a_folder / "meta.json").write_text(
        json.dumps({
            "session_id": full_id_a,
            "parent_session_id": None,
            "start_time": "2024-01-01T00:00:00",
            "end_time": None,
            "git_commit": None,
            "git_branch": None,
            "environment": {"working_directory": str(tmp_path)},
            "username": "test",
        }),
        encoding="utf-8",
    )

    # Session B does NOT exist on disk (user did /clear but sent no messages)
    full_id_b = "b2c3d4e5-f6a7-890b-cdef-abc123def456"

    # Verify: does_session_exist(B) → None (B not saved)
    assert SessionLoader.does_session_exist(full_id_b, config) is None

    # Verify: find_latest_session → returns A (the only saved session)
    import pathlib

    latest = SessionLoader.find_latest_session(
        config, working_directory=pathlib.Path(str(tmp_path)).resolve()
    )
    assert latest is not None, "find_latest_session should return session A"
    assert latest == session_a_folder

    metadata = SessionLoader.load_metadata(latest)
    assert metadata.session_id == full_id_a

    # Simulate the pointer recording short_session_id of the fallback session
    _set_tty(monkeypatch, "ttys001")
    fallback_short_id = shorten_session_id(metadata.session_id)
    last_session_pointer.record(config, fallback_short_id)

    # Simulate -c: load pointer → find_session_by_id
    loaded = last_session_pointer.load(config)
    assert loaded is not None
    assert loaded == fallback_short_id

    result = SessionLoader.find_session_by_id(loaded, config)
    assert result is not None, (
        f"Pointer round-trip failed after fallback: "
        f"stored {loaded!r}, glob uses {shorten_session_id(loaded)!r}"
    )
    assert result == session_a_folder
