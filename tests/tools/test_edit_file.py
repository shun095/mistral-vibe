from __future__ import annotations

import pytest

from tests.mock.utils import collect_result
from vibe.core.tools.base import ToolError, ToolPermission
from vibe.core.tools.builtins.edit_file import (
    EditFile,
    EditFileArgs,
    EditFileConfig,
    EditFileState,
)


@pytest.fixture
def edit_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = EditFileConfig()
    return EditFile(config=config, state=EditFileState())


@pytest.mark.asyncio
async def test_replaces_single_occurrence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = EditFileConfig()
    edit_file_tool = EditFile(config=config, state=EditFileState())

    # Create a test file
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """def old_function():
    return "old"

def another_function():
    return "another"
"""
    )

    result = await collect_result(
        edit_file_tool.run(
            EditFileArgs(
                file_path=str(test_file),
                old_string='def old_function():\n    return "old"',
                new_string='def new_function():\n    return "new"',
                replace_all=False,
            )
        )
    )

    assert result.blocks_applied == 1
    assert result.file == str(test_file)
    # content field contains the unified diff between old and new content
    assert "old_function" in result.content
    assert "new_function" in result.content

    # Verify file was actually updated
    updated_content = test_file.read_text()
    assert "new_function" in updated_content
    assert "old_function" not in updated_content


@pytest.mark.asyncio
async def test_replaces_all_occurrences(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = EditFileConfig()
    edit_file_tool = EditFile(config=config, state=EditFileState())

    # Create a test file with multiple occurrences
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """old_value = 1
another = 2
old_value = 3
"""
    )

    result = await collect_result(
        edit_file_tool.run(
            EditFileArgs(
                file_path=str(test_file),
                old_string="old_value = 3",
                new_string="new_value = 30",
                replace_all=True,
            )
        )
    )

    # With replace_all=True, all occurrences should be replaced
    assert result.blocks_applied == 1  # Only one occurrence of "old_value = 3"

    # Verify file was updated
    updated_content = test_file.read_text()
    assert "new_value = 30" in updated_content
    assert "old_value = 3" not in updated_content
    # Also verify that the other occurrence (old_value = 1) was NOT replaced
    assert "old_value = 1" in updated_content


@pytest.mark.asyncio
async def test_fails_when_old_string_not_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = EditFileConfig()
    edit_file_tool = EditFile(config=config, state=EditFileState())

    # Create a test file
    test_file = tmp_path / "test.py"
    test_file.write_text('def hello():\n    return "world"')

    # Try to replace a string that doesn't exist
    with pytest.raises(ToolError) as err:
        await collect_result(
            edit_file_tool.run(
                EditFileArgs(
                    file_path=str(test_file),
                    old_string="nonexistent_string",
                    new_string="new_string",
                )
            )
        )

    assert "old_string not found in file" in str(err.value)


@pytest.mark.asyncio
async def test_requires_absolute_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = EditFileConfig()
    edit_file_tool = EditFile(config=config, state=EditFileState())

    with pytest.raises(ToolError) as err:
        await collect_result(
            edit_file_tool.run(
                EditFileArgs(
                    file_path="relative/path.py",
                    old_string="old",
                    new_string="new",
                )
            )
        )

    assert "file_path must be an absolute path" in str(err.value)


@pytest.mark.asyncio
async def test_fails_for_nonexistent_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = EditFileConfig()
    edit_file_tool = EditFile(config=config, state=EditFileState())

    with pytest.raises(ToolError) as err:
        await collect_result(
            edit_file_tool.run(
                EditFileArgs(
                    file_path=str(tmp_path / "nonexistent.py"),
                    old_string="old",
                    new_string="new",
                )
            )
        )

    assert "File does not exist" in str(err.value)


@pytest.mark.asyncio
async def test_fails_for_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = EditFileConfig()
    edit_file_tool = EditFile(config=config, state=EditFileState())

    # Use tmp_path itself as a directory
    with pytest.raises(ToolError) as err:
        await collect_result(
            edit_file_tool.run(
                EditFileArgs(
                    file_path=str(tmp_path),
                    old_string="old",
                    new_string="new",
                )
            )
        )

    assert "Path is not a file" in str(err.value)


@pytest.mark.asyncio
async def test_fails_with_empty_old_string(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = EditFileConfig()
    edit_file_tool = EditFile(config=config, state=EditFileState())

    with pytest.raises(ToolError) as err:
        await collect_result(
            edit_file_tool.run(
                EditFileArgs(
                    file_path=str(tmp_path / "test.py"),
                    old_string="",
                    new_string="new",
                )
            )
        )

    assert "old_string cannot be empty" in str(err.value)


@pytest.mark.asyncio
async def test_fails_with_empty_new_string(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = EditFileConfig()
    edit_file_tool = EditFile(config=EditFileConfig(), state=EditFileState())

    # Create test file first
    test_file = tmp_path / "test.py"
    test_file.write_text("old")

    with pytest.raises(ToolError) as err:
        await collect_result(
            edit_file_tool.run(
                EditFileArgs(
                    file_path=str(test_file),
                    old_string="old",
                    new_string="",
                )
            )
        )

    assert "new_string cannot be empty" in str(err.value)


def test_check_allowlist_denylist(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = EditFileConfig(
        allowlist=["/tmp/*"], denylist=["/etc/*"]
    )
    edit_file_tool = EditFile(config=config, state=EditFileState())

    # Allowlisted
    allowlisted = edit_file_tool.check_allowlist_denylist(
        EditFileArgs(file_path="/tmp/test.py", old_string="old", new_string="new")
    )
    assert allowlisted is ToolPermission.ALWAYS

    # Denylisted
    denylisted = edit_file_tool.check_allowlist_denylist(
        EditFileArgs(file_path="/etc/passwd", old_string="old", new_string="new")
    )
    assert denylisted is ToolPermission.NEVER

    # Neither
    neither = edit_file_tool.check_allowlist_denylist(
        EditFileArgs(file_path="/home/user/test.py", old_string="old", new_string="new")
    )
    assert neither is None


@pytest.mark.asyncio
async def test_multiline_replacement_with_context(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = EditFileConfig()
    edit_file_tool = EditFile(config=config, state=EditFileState())

    # Create a test file with multiline content
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """def function_one():
    # Some comment
    old_value = 1
    return old_value

def function_two():
    y = 2
    return y
"""
    )

    result = await collect_result(
        edit_file_tool.run(
            EditFileArgs(
                file_path=str(test_file),
                old_string='def function_one():\n    # Some comment\n    old_value = 1\n    return old_value',
                new_string='def function_one():\n    # Updated comment\n    new_value = 10\n    return new_value',
            )
        )
    )

    assert result.blocks_applied == 1

    # Verify file was updated
    updated_content = test_file.read_text()
    assert "# Updated comment" in updated_content
    assert "new_value = 10" in updated_content
    assert "new_value" in updated_content
    # Verify old values are gone
    assert "old_value = 1" not in updated_content
    assert "return old_value" not in updated_content


@pytest.mark.asyncio
async def test_backup_file_creation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = EditFileConfig(create_backup=True)
    edit_file_tool = EditFile(config=config, state=EditFileState())

    # Create a test file
    test_file = tmp_path / "test.py"
    original_content = 'def old_function():\n    return "old"\n'
    test_file.write_text(original_content)

    result = await collect_result(
        edit_file_tool.run(
            EditFileArgs(
                file_path=str(test_file),
                old_string='def old_function():\n    return "old"',
                new_string='def new_function():\n    return "new"',
                replace_all=False,
            )
        )
    )

    assert result.blocks_applied == 1
    # Verify backup file was created
    backup_file = tmp_path / "test.py.bak"
    assert backup_file.exists()
    # Verify backup content matches original
    assert backup_file.read_text() == original_content
    # Verify main file was updated
    assert "new_function" in test_file.read_text()


@pytest.mark.asyncio
async def test_context_display_in_errors(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = EditFileConfig()
    edit_file_tool = EditFile(config=config, state=EditFileState())

    # Create a test file with similar content
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """def function_a():
    value = 1
    return value

def function_b():
    value = 2
    return value

def function_c():
    value = 3
    return value
"""
    )

    # Try to replace a string that doesn't exist
    # Using a string that's similar but not present to trigger context analysis
    with pytest.raises(ToolError) as err:
        await collect_result(
            edit_file_tool.run(
                EditFileArgs(
                    file_path=str(test_file),
                    old_string="value = 99",  # This doesn't exist in the file
                    new_string="value = 999",
                )
            )
        )

    error_message = str(err.value)
    # Check that context is included in error message
    assert "Context analysis:" in error_message
    # Check that the context shows which line was not found
    assert "First target line" in error_message
    assert "not found anywhere" in error_message


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_multiple_occurrence_warning(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = EditFileConfig()
    edit_file_tool = EditFile(config=config, state=EditFileState())

    # Create a test file with multiple identical occurrences
    test_file = tmp_path / "test.py"
    original_content = """value = 1
another = 2
value = 1
yet another = 3
value = 1
"""
    test_file.write_text(original_content)

    result = await collect_result(
        edit_file_tool.run(
            EditFileArgs(
                file_path=str(test_file),
                old_string="value = 1",
                new_string="new_value = 10",
                replace_all=False,  # Only replace first occurrence
            )
        )
    )

    assert result.blocks_applied == 1
    # Check that warnings are included in the result
    assert len(result.warnings) > 0
    # Check that warning mentions multiple occurrences
    assert "appears" in result.warnings[0]
    assert "3 times" in result.warnings[0]
    # Verify only first occurrence was replaced
    content = test_file.read_text()
    assert "new_value = 10" in content  # First occurrence replaced
    assert content.count("value = 1\n") == 2  # Two occurrences remain (original 3 - 1 replaced = 2)


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_create_backup_config_option(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Test with create_backup=False (default)
    config_no_backup = EditFileConfig(create_backup=False)
    edit_file_tool_no_backup = EditFile(config=config_no_backup, state=EditFileState())

    test_file = tmp_path / "test_no_backup.py"
    original = "old content\n"
    test_file.write_text(original)

    result1 = await collect_result(
        edit_file_tool_no_backup.run(
            EditFileArgs(
                file_path=str(test_file),
                old_string="old content",
                new_string="new content",
            )
        )
    )

    backup_file = tmp_path / "test_no_backup.py.bak"
    assert not backup_file.exists()  # No backup should be created
    assert result1.blocks_applied == 1

    # Test with create_backup=True
    config_with_backup = EditFileConfig(create_backup=True)
    edit_file_tool_with_backup = EditFile(config=config_with_backup, state=EditFileState())

    test_file2 = tmp_path / "test_with_backup.py"
    original2 = "old content 2\n"
    test_file2.write_text(original2)

    result2 = await collect_result(
        edit_file_tool_with_backup.run(
            EditFileArgs(
                file_path=str(test_file2),
                old_string="old content 2",
                new_string="new content 2",
            )
        )
    )

    backup_file2 = tmp_path / "test_with_backup.py.bak"
    assert backup_file2.exists()
    assert backup_file2.read_text() == original2
    assert result2.blocks_applied == 1


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_fuzzy_match_with_enabled_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = EditFileConfig(fuzzy_threshold=0.9)
    edit_file_tool = EditFile(config=config, state=EditFileState())

    # Create a test file with slight whitespace differences
    test_file = tmp_path / "test.py"
    original = """def function():
    # Old comment
    value = 1
    return value"""
    test_file.write_text(original)

    # Try with a string that has slight whitespace differences (will need fuzzy matching)
    result = await collect_result(
        edit_file_tool.run(
            EditFileArgs(
                file_path=str(test_file),
                old_string='def function():\n    # Old comment\n    value = 1\n    return value',
                new_string='def function():\n    # New comment\n    value = 10\n    return value',
            )
        )
    )

    assert result.blocks_applied == 1
    assert len(result.warnings) == 0
    
    # Verify file was updated
    updated_content = test_file.read_text()
    assert "# New comment" in updated_content
    assert "value = 10" in updated_content


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_fuzzy_match_provides_similar_matches_in_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = EditFileConfig(fuzzy_threshold=0.8)
    edit_file_tool = EditFile(config=config, state=EditFileState())

    # Create a test file
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """def function_a():
    value = 1
    return value

def function_b():
    value = 2
    return value
"""
    )

    # Try to replace with a string that doesn't exist exactly
    with pytest.raises(ToolError) as err:
        await collect_result(
            edit_file_tool.run(
                EditFileArgs(
                    file_path=str(test_file),
                    old_string="def function_a():\n    value = 99\n    return value",
                    new_string="def function_a():\n    value = 999\n    return value",
                )
            )
        )

    error_message = str(err.value)
    # Check that fuzzy match context is included in error message
    assert "Closest fuzzy match" in error_message or "similarity" in error_message
    # Check that context analysis is included
    assert "Context analysis:" in error_message