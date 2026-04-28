"""Queue manager for auto-submitting queued messages after task completion.

Manages `(cwd)/.vibe/queue.jsonl` — each line is a JSON-encoded string
representing a queued message (plain text, slash commands, or bash commands).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from vibe.core.utils.io import read_safe

logger = logging.getLogger(__name__)

_QUEUE_DIR = ".vibe"
_QUEUE_FILE = "queue.jsonl"


class QueueManager:
    """Manages a JSONL queue file for auto-submitting messages.

    Args:
        base_dir: Base directory for the queue file (default: cwd).
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        self._queue_path = (base_dir or Path.cwd()) / _QUEUE_DIR / _QUEUE_FILE

    def _try_remove_parent_dir(self) -> None:
        """Attempt to remove the parent .vibe directory if empty."""
        try:
            self._queue_path.parent.rmdir()
        except OSError:
            pass  # Directory not empty or other non-critical error

    def read_entries(self) -> list[str]:
        """Read all entries from the queue file.

        Returns:
            List of message strings, empty if file missing or empty.
        """
        if not self._queue_path.exists():
            return []

        text = read_safe(self._queue_path).text.strip()

        if not text:
            return []

        entries: list[str] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                entry = line
            entries.append(entry if isinstance(entry, str) else str(entry))
        return entries

    def remove_entry(self, index: int) -> bool:
        """Remove the entry at the given index from the queue file.

        Args:
            index: Zero-based index of the entry to remove.

        Returns:
            True if the entry was removed, False on error.
        """
        entries = self.read_entries()
        if not entries or index < 0 or index >= len(entries):
            return False

        entries.pop(index)

        try:
            if entries:
                self._queue_path.write_text(
                    "\n".join(json.dumps(e, ensure_ascii=False) for e in entries)
                    + "\n",
                    encoding="utf-8",
                )
            else:
                self._queue_path.unlink(missing_ok=True)
                self._try_remove_parent_dir()
        except OSError as e:
            logger.warning("Failed to write queue file: %s", e)
            return False
        return True

    def clear(self) -> bool:
        """Remove the queue file entirely.

        Returns:
            True if cleared, False on error.
        """
        try:
            self._queue_path.unlink(missing_ok=True)
            self._try_remove_parent_dir()
        except OSError as e:
            logger.warning("Failed to clear queue file: %s", e)
            return False
        return True

    def append(self, message: str) -> int | None:
        """Append a message to the queue file.

        Args:
            message: The message string to append.

        Returns:
            Total number of entries after append, or None on error.
        """
        try:
            self._queue_path.parent.mkdir(parents=True, exist_ok=True)
            with self._queue_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(message, ensure_ascii=False) + "\n")
        except OSError as e:
            logger.warning("Failed to append to queue file: %s", e)
            return None
        return len(self.read_entries())
