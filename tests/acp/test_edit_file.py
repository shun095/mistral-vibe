from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from acp import ReadTextFileResponse
import pytest

from tests.mock.utils import collect_result
from vibe.acp.tools.builtins.edit_file import AcpEditFileState, EditFile
from vibe.core.tools.base import ToolError
from vibe.core.tools.builtins.edit_file import (
    EditFileArgs,
    EditFileConfig,
    EditFileResult,
)
from vibe.core.types import ToolCallEvent, ToolResultEvent


class MockClient:
    def __init__(
        self,
        file_content: str = "original line 1\noriginal line 2\noriginal line 3",
        read_error: Exception | None = None,
        write_error: Exception | None = None,
    ) -> None:
        self._file_content = file_content
        self._read_error = read_error
        self._write_error = write_error
        self._read_text_file_called = False
        self._write_text_file_called = False
        self._session_update_called = False
        self._last_read_params: dict[str, str | int | None] = {}
        self._last_write_params: dict[str, str] = {}
        self._write_calls: list[dict[str, str]] = []

    async def read_text_file(
        self,
        path: str,
        session_id: str,
        limit: int | None = None,
        line: int | None = None,
        **kwargs,
    ) -> ReadTextFileResponse:
        self._read_text_file_called = True
        self._last_read_params = {
            "path": path,
            "session_id": session_id,
            "limit": limit,
            "line": line,
        }

        if self._read_error:
            raise self._read_error

        return ReadTextFileResponse(content=self._file_content)

    async def write_text_file(
        self, content: str, path: str, session_id: str, **kwargs
    ) -> None:
        self._write_text_file_called = True
        params = {"content": content, "path": path, "session_id": session_id}
        self._last_write_params = params
        self._write_calls.append(params)

        if self._write_error:
            raise self._write_error

    async def session_update(self, session_id: str, update, **kwargs) -> None:
        self._session_update_called = True


@pytest.fixture
def mock_client() -> MockClient:
    return MockClient()


@pytest.fixture
def acp_edit_file_tool(
    mock_client: MockClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> EditFile:
    monkeypatch.chdir(tmp_path)
    config = EditFileConfig()
    state = AcpEditFileState.model_construct(
        client=mock_client,
        session_id="test_session_123",
        tool_call_id="test_tool_call_456",
    )
    return EditFile(config_getter=lambda: config, state=state)


class TestAcpEditFileBasic:
    def test_get_name(self) -> None:
        assert EditFile.get_name() == "edit_file"


class TestAcpEditFileExecution:
    @pytest.mark.asyncio
    async def test_run_success(
        self, acp_edit_file_tool: EditFile, mock_client: MockClient, tmp_path: Path
    ) -> None:
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("original line 1\noriginal line 2\noriginal line 3")
        args = EditFileArgs(
            file_path=str(test_file),
            old_string="original line 2",
            new_string="modified line 2",
        )
        result = await collect_result(acp_edit_file_tool.run(args))

        assert isinstance(result, EditFileResult)
        assert result.file == str(test_file)
        assert result.blocks_applied == 1
        assert mock_client._read_text_file_called
        assert mock_client._write_text_file_called

        read_params = mock_client._last_read_params
        assert read_params["session_id"] == "test_session_123"
        assert read_params["path"] == str(test_file)

        write_params = mock_client._last_write_params
        assert write_params["session_id"] == "test_session_123"
        assert write_params["path"] == str(test_file)
        assert (
            write_params["content"]
            == "original line 1\nmodified line 2\noriginal line 3"
        )

    @pytest.mark.asyncio
    async def test_run_replace_all(
        self, acp_edit_file_tool: EditFile, mock_client: MockClient, tmp_path: Path
    ) -> None:
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("foo bar\nfoo baz\nfoo qux")
        mock_client._file_content = "foo bar\nfoo baz\nfoo qux"
        args = EditFileArgs(
            file_path=str(test_file),
            old_string="foo",
            new_string="baz",
            replace_all=True,
        )
        result = await collect_result(acp_edit_file_tool.run(args))

        assert result.blocks_applied == 3
        write_params = mock_client._last_write_params
        assert write_params["content"] == "baz bar\nbaz baz\nbaz qux"

    @pytest.mark.asyncio
    async def test_run_with_backup(
        self, mock_client: MockClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        config = EditFileConfig(create_backup=True)
        tool = EditFile(
            config_getter=lambda: config,
            state=AcpEditFileState.model_construct(
                client=mock_client, session_id="test_session", tool_call_id="test_call"
            ),
        )

        test_file = tmp_path / "test_file.txt"
        test_file.write_text("original line 1\noriginal line 2")
        args = EditFileArgs(
            file_path=str(test_file),
            old_string="original line 1",
            new_string="modified line 1",
        )
        result = await collect_result(tool.run(args))

        assert result.blocks_applied == 1
        assert len(mock_client._write_calls) >= 1
        assert sum(w["path"].endswith(".bak") for w in mock_client._write_calls) == 1

    @pytest.mark.asyncio
    async def test_run_read_error(
        self, mock_client: MockClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        mock_client._read_error = RuntimeError("File not found")

        tool = EditFile(
            config_getter=lambda: EditFileConfig(),
            state=AcpEditFileState.model_construct(
                client=mock_client, session_id="test_session", tool_call_id="test_call"
            ),
        )

        test_file = tmp_path / "test.txt"
        test_file.touch()
        args = EditFileArgs(
            file_path=str(test_file), old_string="old", new_string="new"
        )
        with pytest.raises(ToolError) as exc_info:
            await collect_result(tool.run(args))

        assert (
            str(exc_info.value)
            == f"Unexpected error reading {test_file}: File not found"
        )

    @pytest.mark.asyncio
    async def test_run_write_error(
        self, mock_client: MockClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        mock_client._write_error = RuntimeError("Permission denied")
        test_file = tmp_path / "test.txt"
        test_file.touch()
        mock_client._file_content = "old"

        tool = EditFile(
            config_getter=lambda: EditFileConfig(),
            state=AcpEditFileState.model_construct(
                client=mock_client, session_id="test_session", tool_call_id="test_call"
            ),
        )

        args = EditFileArgs(
            file_path=str(test_file), old_string="old", new_string="new"
        )
        with pytest.raises(ToolError) as exc_info:
            await collect_result(tool.run(args))

        assert str(exc_info.value) == f"Error writing {test_file}: Permission denied"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "client,session_id,expected_error",
        [
            (
                None,
                "test_session",
                "Client not available in tool state. This tool can only be used within an ACP session.",
            ),
            (
                MockClient(),
                None,
                "Session ID not available in tool state. This tool can only be used within an ACP session.",
            ),
        ],
    )
    async def test_run_without_required_state(
        self,
        tmp_path: Path,
        client: MockClient | None,
        session_id: str | None,
        expected_error: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        test_file = tmp_path / "test.txt"
        test_file.touch()
        tool = EditFile(
            config_getter=lambda: EditFileConfig(),
            state=AcpEditFileState.model_construct(
                client=client, session_id=session_id, tool_call_id="test_call"
            ),
        )

        args = EditFileArgs(
            file_path=str(test_file), old_string="old", new_string="new"
        )
        with pytest.raises(ToolError) as exc_info:
            await collect_result(tool.run(args))

        assert str(exc_info.value) == expected_error


class TestAcpEditFileSessionUpdates:
    def test_tool_call_session_update(self) -> None:
        event = ToolCallEvent(
            tool_name="edit_file",
            tool_call_id="test_call_123",
            args=EditFileArgs(
                file_path="/tmp/test.txt", old_string="old text", new_string="new text"
            ),
            tool_class=EditFile,
        )

        update = EditFile.tool_call_session_update(event)
        assert update is not None
        assert update.session_update == "tool_call"
        assert update.tool_call_id == "test_call_123"
        assert update.kind == "edit"
        assert update.title is not None
        assert update.content is not None
        assert isinstance(update.content, list)
        assert len(update.content) == 1
        assert update.content[0].type == "diff"
        assert update.content[0].path == "/tmp/test.txt"
        assert update.content[0].old_text == "old text"
        assert update.content[0].new_text == "new text"
        assert update.locations is not None
        assert len(update.locations) == 1
        assert update.locations[0].path == str(Path("/tmp/test.txt").resolve())

    def test_tool_call_session_update_invalid_args(self) -> None:
        event = ToolCallEvent.model_construct(
            tool_name="edit_file",
            tool_call_id="test_call_123",
            args=cast(Any, object()),
            tool_class=EditFile,
        )

        update = EditFile.tool_call_session_update(event)
        assert update is not None
        assert update.title == "edit_file"

    def test_tool_result_session_update(self) -> None:
        result = EditFileResult(
            file="/tmp/test.txt",
            blocks_applied=1,
            lines_changed=1,
            warnings=[],
            content="--- ORIGINAL\n+++ MODIFIED\n@@ -1 +1 @@\n-old\n+new\n",
        )

        event = ToolResultEvent(
            tool_name="edit_file",
            tool_call_id="test_call_123",
            result=result,
            tool_class=EditFile,
        )

        update = EditFile.tool_result_session_update(event)
        assert update is not None
        assert update.session_update == "tool_call_update"
        assert update.tool_call_id == "test_call_123"
        assert update.status == "completed"
        assert update.content is not None
        assert isinstance(update.content, list)
        assert len(update.content) == 1
        assert update.content[0].type == "diff"
        assert update.content[0].path == "/tmp/test.txt"
        assert update.locations is not None
        assert len(update.locations) == 1
        assert update.locations[0].path == str(Path("/tmp/test.txt").resolve())

    def test_tool_result_session_update_invalid_result(self) -> None:
        event = ToolResultEvent.model_construct(
            tool_name="edit_file",
            tool_call_id="test_call_123",
            result=cast(Any, object()),
            tool_class=EditFile,
        )

        update = EditFile.tool_result_session_update(event)
        assert update is not None
        assert update.status == "failed"
