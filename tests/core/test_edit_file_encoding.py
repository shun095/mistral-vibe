from __future__ import annotations

from pathlib import Path

import pytest

from tests.mock.utils import collect_result
from vibe.core.tools.base import BaseToolState
from vibe.core.tools.builtins.edit_file import EditFile, EditFileArgs, EditFileConfig


@pytest.mark.asyncio
async def test_edit_file_rewrites_with_detected_encoding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "utf16.txt"
    original = "line one café\nline two été\n"
    path.write_bytes(original.encode("utf-16"))

    tool = EditFile(config_getter=lambda: EditFileConfig(), state=BaseToolState())
    await collect_result(
        tool.run(
            EditFileArgs(
                file_path=str(path),
                old_string="line one café",
                new_string="LINE ONE CAFÉ",
            )
        )
    )

    assert path.read_bytes().startswith(b"\xff\xfe")
    assert path.read_text(encoding="utf-16") == "LINE ONE CAFÉ\nline two été\n"
