from __future__ import annotations

import json
from pathlib import Path

from vibe.cli.queue_manager import QueueManager


def test_read_entries_from_empty_file(tmp_path: Path) -> None:
    queue_file = tmp_path / ".vibe" / "queue.jsonl"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text("", encoding="utf-8")

    manager = QueueManager(base_dir=tmp_path)
    result = manager.read_entries()

    assert result == []


def test_read_entries_from_missing_file(tmp_path: Path) -> None:
    manager = QueueManager(base_dir=tmp_path)
    result = manager.read_entries()

    assert result == []


def test_read_entries_returns_json_strings(tmp_path: Path) -> None:
    queue_file = tmp_path / ".vibe" / "queue.jsonl"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(
        json.dumps("Hello World")
        + "\n"
        + json.dumps("/clear")
        + "\n"
        + json.dumps("!ls -la")
        + "\n",
        encoding="utf-8",
    )

    manager = QueueManager(base_dir=tmp_path)
    result = manager.read_entries()

    assert result == ["Hello World", "/clear", "!ls -la"]


def test_read_entries_handles_raw_text_lines(tmp_path: Path) -> None:
    queue_file = tmp_path / ".vibe" / "queue.jsonl"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text("plain text line\nanother line\n", encoding="utf-8")

    manager = QueueManager(base_dir=tmp_path)
    result = manager.read_entries()

    assert result == ["plain text line", "another line"]


def test_read_entries_skips_blank_lines(tmp_path: Path) -> None:
    queue_file = tmp_path / ".vibe" / "queue.jsonl"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(
        json.dumps("first") + "\n\n" + json.dumps("second") + "\n", encoding="utf-8"
    )

    manager = QueueManager(base_dir=tmp_path)
    result = manager.read_entries()

    assert result == ["first", "second"]


def test_remove_entry_removes_by_index(tmp_path: Path) -> None:
    queue_file = tmp_path / ".vibe" / "queue.jsonl"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(
        json.dumps("first")
        + "\n"
        + json.dumps("second")
        + "\n"
        + json.dumps("third")
        + "\n",
        encoding="utf-8",
    )

    manager = QueueManager(base_dir=tmp_path)

    assert manager.remove_entry(1) is True
    result = manager.read_entries()

    assert result == ["first", "third"]


def test_remove_first_entry(tmp_path: Path) -> None:
    queue_file = tmp_path / ".vibe" / "queue.jsonl"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(
        json.dumps("first") + "\n" + json.dumps("second") + "\n", encoding="utf-8"
    )

    manager = QueueManager(base_dir=tmp_path)

    assert manager.remove_entry(0) is True
    result = manager.read_entries()

    assert result == ["second"]


def test_remove_last_entry(tmp_path: Path) -> None:
    queue_file = tmp_path / ".vibe" / "queue.jsonl"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(json.dumps("only") + "\n", encoding="utf-8")

    manager = QueueManager(base_dir=tmp_path)

    assert manager.remove_entry(0) is True
    result = manager.read_entries()

    assert result == []
    assert not queue_file.exists()


def test_remove_entry_out_of_range(tmp_path: Path) -> None:
    queue_file = tmp_path / ".vibe" / "queue.jsonl"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(json.dumps("only") + "\n", encoding="utf-8")

    manager = QueueManager(base_dir=tmp_path)

    assert manager.remove_entry(5) is False
    assert manager.remove_entry(-1) is False


def test_remove_entry_from_empty_file(tmp_path: Path) -> None:
    queue_file = tmp_path / ".vibe" / "queue.jsonl"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text("", encoding="utf-8")

    manager = QueueManager(base_dir=tmp_path)

    assert manager.remove_entry(0) is False


def test_remove_last_entry_cleans_up_directory(tmp_path: Path) -> None:
    queue_file = tmp_path / ".vibe" / "queue.jsonl"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(json.dumps("only") + "\n", encoding="utf-8")

    manager = QueueManager(base_dir=tmp_path)

    assert manager.remove_entry(0) is True
    assert not queue_file.exists()
    assert not queue_file.parent.exists()


def test_remove_entry_preserves_non_ascii(tmp_path: Path) -> None:
    queue_file = tmp_path / ".vibe" / "queue.jsonl"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(
        json.dumps("Hello 世界") + "\n" + json.dumps("Привет") + "\n", encoding="utf-8"
    )

    manager = QueueManager(base_dir=tmp_path)

    assert manager.remove_entry(0) is True
    result = manager.read_entries()

    assert result == ["Привет"]


def test_append_creates_file_and_directory(tmp_path: Path) -> None:
    manager = QueueManager(base_dir=tmp_path)

    assert manager.append("hello") == 1
    result = manager.read_entries()

    assert result == ["hello"]


def test_append_adds_to_existing_entries(tmp_path: Path) -> None:
    queue_file = tmp_path / ".vibe" / "queue.jsonl"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(json.dumps("first") + "\n", encoding="utf-8")

    manager = QueueManager(base_dir=tmp_path)

    assert manager.append("second") == 2
    result = manager.read_entries()

    assert result == ["first", "second"]


def test_append_preserves_non_ascii(tmp_path: Path) -> None:
    manager = QueueManager(base_dir=tmp_path)

    manager.append("Hello 世界")
    manager.append("Привет")

    result = manager.read_entries()
    assert result == ["Hello 世界", "Привет"]


def test_clear_removes_file(tmp_path: Path) -> None:
    queue_file = tmp_path / ".vibe" / "queue.jsonl"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(json.dumps("entry") + "\n", encoding="utf-8")

    manager = QueueManager(base_dir=tmp_path)

    assert manager.clear() is True
    assert not queue_file.exists()
    assert not queue_file.parent.exists()


def test_clear_on_missing_file(tmp_path: Path) -> None:
    manager = QueueManager(base_dir=tmp_path)

    assert manager.clear() is True
