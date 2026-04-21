from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vibe.core.config import VibeConfig
from vibe.core.config._settings import SessionLoggingConfig
from vibe.core.config.harness_files import (
    HarnessFilesManager,
    init_harness_files_manager,
    reset_harness_files_manager,
)


def unlock_config_paths() -> None:
    """Helper to enable config persistence for tests."""
    reset_harness_files_manager()
    init_harness_files_manager("user")


def setup_config_file_for_test(
    tmp_path: Path, config_file_name: str = "config.toml"
) -> Path:
    """Helper to create a config file path for tests."""
    return tmp_path / config_file_name


def mock_harness_manager_for_config_file(config_file: Path) -> HarnessFilesManager:
    """Create a mock HarnessFilesManager that returns the specified config file."""
    mock_manager = MagicMock(spec=HarnessFilesManager)
    mock_manager.config_file = config_file
    mock_manager.user_config_file = config_file
    mock_manager.persist_allowed = True
    mock_manager.sources = ("user",)
    return mock_manager


class TestExcludeDefaults:
    """Tests for VibeConfig._exclude_defaults method."""

    def test_excludes_top_level_default_values(self) -> None:
        """Test that top-level fields with default values are excluded."""
        config_dict = {
            "active_model": "devstral-2",  # default value
            "vim_keybindings": False,  # default value
            "auto_approve": True,  # non-default value
        }

        result = VibeConfig._exclude_defaults(config_dict)

        assert "active_model" not in result
        assert "vim_keybindings" not in result
        assert "auto_approve" in result
        assert result["auto_approve"] is True

    def test_excludes_none_values(self) -> None:
        """Test that None values are excluded (not TOML serializable)."""
        config_dict = {"active_model": "custom-model", "vim_keybindings": None}

        result = VibeConfig._exclude_defaults(config_dict)

        assert "active_model" in result
        assert "vim_keybindings" not in result

    def test_excludes_default_factory_lists(self) -> None:
        """Test that empty lists (default_factory) are excluded."""
        config_dict = {
            "mcp_servers": [],  # default is empty list
            "lsp_servers": [],  # default is empty list
        }

        result = VibeConfig._exclude_defaults(config_dict)

        assert "mcp_servers" not in result
        assert "lsp_servers" not in result

    def test_keeps_non_empty_lists(self) -> None:
        """Test that non-empty lists are kept."""
        config_dict = {
            "mcp_servers": [
                {"name": "test_server", "transport": "stdio", "command": "test"}
            ]
        }

        result = VibeConfig._exclude_defaults(config_dict)

        assert "mcp_servers" in result
        assert len(result["mcp_servers"]) == 1

    def test_excludes_nested_default_values(self) -> None:
        """Test that nested dict default values are excluded."""
        config_dict = {
            "project_context": {
                "default_commit_count": 5,  # default value
                "timeout_seconds": 5.0,  # non-default value (default is 2.0)
            }
        }

        result = VibeConfig._exclude_defaults(config_dict)

        assert "project_context" in result
        assert "default_commit_count" not in result["project_context"]
        assert "timeout_seconds" in result["project_context"]
        assert result["project_context"]["timeout_seconds"] == 5.0

    def test_excludes_empty_nested_dicts(self) -> None:
        """Test that nested dicts that become empty after exclusion are removed."""
        config_dict = {
            "project_context": {
                "default_commit_count": 5,  # default value
                "timeout_seconds": 2.0,  # default value
            }
        }

        result = VibeConfig._exclude_defaults(config_dict)

        # All values are defaults, so project_context should be excluded
        assert "project_context" not in result

    def test_excludes_none_from_nested_lists(self) -> None:
        """Test that None values in nested lists are filtered out."""
        config_dict = {"tool_paths": [None, "/path/to/tools"]}

        result = VibeConfig._exclude_defaults(config_dict)

        assert "tool_paths" in result
        assert None not in result["tool_paths"]
        assert "/path/to/tools" in result["tool_paths"]

    def test_excludes_empty_string_default(self) -> None:
        """Test that empty string default values are excluded."""
        config_dict = {
            "displayed_workdir": "",  # default is empty string
            "active_model": "custom-model",  # non-default value
        }

        result = VibeConfig._exclude_defaults(config_dict)

        assert "displayed_workdir" not in result
        assert "active_model" in result
        assert result["active_model"] == "custom-model"

    def test_keeps_non_empty_string(self) -> None:
        """Test that non-empty strings are kept."""
        config_dict = {"displayed_workdir": "/custom/path"}

        result = VibeConfig._exclude_defaults(config_dict)

        assert "displayed_workdir" in result
        assert result["displayed_workdir"] == "/custom/path"

    def test_excludes_empty_string_in_nested_section(self) -> None:
        """Test that empty string defaults in nested sections are excluded."""
        # The resolved default for save_dir is the path from the validator
        resolved_default = SessionLoggingConfig().save_dir
        config_dict = {
            "session_logging": {
                "save_dir": resolved_default,  # matches resolved default
                "enabled": False,  # non-default value (default is True)
            }
        }

        result = VibeConfig._exclude_defaults(config_dict)

        assert "session_logging" in result
        assert "save_dir" not in result["session_logging"]
        assert "enabled" in result["session_logging"]
        assert result["session_logging"]["enabled"] is False

    def test_excludes_validator_resolved_default(self) -> None:
        """Test that values matching validator-resolved defaults are excluded.

        The save_dir field has a validator that transforms '' into a resolved path.
        When the config contains that resolved path, it should be excluded as default.
        """
        resolved_default = SessionLoggingConfig().save_dir
        config_dict = {"session_logging": {"save_dir": resolved_default}}

        result = VibeConfig._exclude_defaults(config_dict)

        # session_logging section should be empty after exclusion
        assert "session_logging" not in result

    def test_get_resolved_default_returns_none_for_required_fields(self) -> None:
        """Test that _get_resolved_default returns None when model has required fields."""
        from pydantic import BaseModel, Field

        class ModelWithRequired(BaseModel):
            required_field: str = Field()
            optional_field: str = "default"

        resolved = VibeConfig._get_resolved_default(ModelWithRequired, "optional_field")
        assert resolved is None

    def test_get_resolved_default_returns_none_on_factory_exception(self) -> None:
        """Test that _get_resolved_default returns None when default_factory raises."""
        import unittest.mock as mock

        from pydantic import BaseModel
        from pydantic_core import PydanticUndefined

        class ModelWithFailingFactory(BaseModel):
            good_field: str = "ok"
            bad_field: dict = {}

        # Create a mock finfo that has is_required=False and a default value
        good_finfo = mock.MagicMock()
        good_finfo.is_required.return_value = False
        good_finfo.default = "ok"
        good_finfo.default_factory = None

        # Create a mock finfo with a failing default_factory
        failing_finfo = mock.MagicMock()
        failing_finfo.is_required.return_value = False
        failing_finfo.default = PydanticUndefined
        failing_finfo.default_factory = mock.MagicMock(side_effect=RuntimeError("fail"))

        with mock.patch.object(
            ModelWithFailingFactory,
            "model_fields",
            {"good_field": good_finfo, "bad_field": failing_finfo},
        ):
            resolved = VibeConfig._get_resolved_default(
                ModelWithFailingFactory, "good_field"
            )
            assert resolved is None

    def test_get_resolved_default_returns_none_on_instantiation_failure(self) -> None:
        """Test that _get_resolved_default returns None when model instantiation fails."""
        from pydantic import BaseModel

        class ModelFailingInit(BaseModel):
            field: str = "default"

            def __init__(self, **data):
                raise ValueError("instantiation failed")

        resolved = VibeConfig._get_resolved_default(ModelFailingInit, "field")
        assert resolved is None


class TestConfigCommentPreservation:
    """Tests for preserving comment-out lines in config.toml."""

    def test_preserves_comment_out_lines(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that comment-out lines in config.toml are preserved after save."""
        # Create a temporary config file with comment-out lines
        config_content = """# This is a comment
active_model = "some-other-model"

# This is a comment-out line that should be preserved
# active_model = "some-other-model"

# Another comment
auto_approve = true
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        # Patch CONFIG_FILE to use the temporary file
        unlock_config_paths()
        monkeypatch.setattr(
            "vibe.core.config._settings.get_harness_files_manager",
            lambda: mock_harness_manager_for_config_file(config_file),
        )

        # Save updates
        VibeConfig.save_updates({"active_model": "custom-model"})

        # Read back the config file
        result = config_file.read_text()

        # Verify comment-out lines are preserved
        assert "# This is a comment" in result
        assert "# This is a comment-out line that should be preserved" in result
        assert '# active_model = "some-other-model"' in result
        assert "# Another comment" in result
        assert 'active_model = "custom-model"' in result
        assert "auto_approve = true" in result

    def test_preserves_comment_out_nested_values(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that comment-out lines in nested sections are preserved."""
        config_content = """[project_context]
# default_commit_count = 5

# This is a comment-out nested value
# timeout_seconds = 2.0

default_commit_count = 10
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        unlock_config_paths()
        monkeypatch.setattr(
            "vibe.core.config._settings.get_harness_files_manager",
            lambda: mock_harness_manager_for_config_file(config_file),
        )

        # Save some updates
        VibeConfig.save_updates({"project_context": {"default_commit_count": 10}})

        result = config_file.read_text()

        # Verify comment-out nested values are preserved
        assert "# This is a comment-out nested value" in result
        assert "# timeout_seconds = 2.0" in result
        assert "default_commit_count = 10" in result

    def test_preserves_comments_on_new_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that new config files work correctly."""
        config_file = tmp_path / "config.toml"
        # Don't create the file - test new file creation

        unlock_config_paths()
        monkeypatch.setattr(
            "vibe.core.config._settings.get_harness_files_manager",
            lambda: mock_harness_manager_for_config_file(config_file),
        )

        # Save config for a new file
        VibeConfig.save_updates({"active_model": "custom-model"})

        result = config_file.read_text()

        # Verify the config was written
        assert 'active_model = "custom-model"' in result

    def test_removes_default_values_from_existing_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that default values are removed while preserving comments."""
        config_content = """# My config file
active_model = "some-other-model"
vim_keybindings = true

# Comment-out line
# some_setting = "value"

auto_approve = true
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        unlock_config_paths()
        monkeypatch.setattr(
            "vibe.core.config._settings.get_harness_files_manager",
            lambda: mock_harness_manager_for_config_file(config_file),
        )

        # Set vim_keybindings back to default (False)
        VibeConfig.save_updates({"vim_keybindings": False})

        result = config_file.read_text()

        # Default value should be removed
        assert "vim_keybindings" not in result
        # Non-default values should remain
        assert 'active_model = "some-other-model"' in result
        assert "auto_approve = true" in result
        # Comment-out lines should be preserved
        assert "# My config file" in result
        assert "# Comment-out line" in result
        assert '# some_setting = "value"' in result

    def test_removes_nested_default_values_preserves_comments(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that nested section default values are removed while preserving comments."""
        config_content = """# Project context settings
[project_context]
# Default commit count is 5
default_commit_count = 10

# This is a custom timeout setting
timeout_seconds = 5.0

# Comment for default_commit_count
# default_commit_count = 5
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        unlock_config_paths()
        monkeypatch.setattr(
            "vibe.core.config._settings.get_harness_files_manager",
            lambda: mock_harness_manager_for_config_file(config_file),
        )

        # Set default_commit_count back to default (5)
        VibeConfig.save_updates({"project_context": {"default_commit_count": 5}})

        result = config_file.read_text()

        # Default value should be removed (check for active config line, not comments)
        import re

        assert not re.search(r"^(?!#)\s*default_commit_count\s*=", result, re.MULTILINE)
        # Non-default values should remain
        assert "timeout_seconds = 5.0" in result
        # Comment-out lines should be preserved
        assert "# Project context settings" in result
        assert "# Default commit count is 5" in result
        assert "# This is a custom timeout setting" in result
        assert "# Comment for default_commit_count" in result
        assert "# default_commit_count = 5" in result

    def test_removes_session_logging_default_values_preserves_comments(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that session_logging section default values are removed while preserving comments."""
        config_content = """# Session logging settings
[session_logging]
# Save directory for logs
save_dir = "/custom/logs"

# Session prefix
session_prefix = "session"

# This is a comment-out line
# enabled = false
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        unlock_config_paths()
        monkeypatch.setattr(
            "vibe.core.config._settings.get_harness_files_manager",
            lambda: mock_harness_manager_for_config_file(config_file),
        )

        # Set session_prefix back to default ("session")
        VibeConfig.save_updates({"session_logging": {"session_prefix": "session"}})

        result = config_file.read_text()

        # Default value should be removed
        assert "session_prefix" not in result
        # Non-default values should remain
        assert 'save_dir = "/custom/logs"' in result
        # Comment-out lines should be preserved
        assert "# Session logging settings" in result
        assert "# Save directory for logs" in result
        assert "# Session prefix" in result
        assert "# This is a comment-out line" in result
        assert "# enabled = false" in result

    def test_creates_nested_section_with_non_default_values(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that nested sections are created with only non-default values."""
        config_file = tmp_path / "config.toml"
        # Don't create the file - test new file creation

        unlock_config_paths()
        monkeypatch.setattr(
            "vibe.core.config._settings.get_harness_files_manager",
            lambda: mock_harness_manager_for_config_file(config_file),
        )

        # Save config with nested section
        VibeConfig.save_updates({"project_context": {"timeout_seconds": 5.0}})

        result = config_file.read_text()

        # Non-default value should be in the file
        assert "[project_context]" in result
        assert "timeout_seconds = 5.0" in result
        # Default values should not be in the file
        assert "default_commit_count" not in result

    def test_preserves_all_comments_in_nested_sections(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that all comments in nested sections are preserved after multiple saves."""
        config_content = """# Main config
auto_approve = true

# Project context section
[project_context]
# Commit count comment
default_commit_count = 10

# Timeout comment
timeout_seconds = 5.0

# Default commit count comment
# default_commit_count = 5

# Session logging section
[session_logging]
# Save dir comment
save_dir = "/custom/logs"

# Session prefix comment
# session_prefix = "session"
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        unlock_config_paths()
        monkeypatch.setattr(
            "vibe.core.config._settings.get_harness_files_manager",
            lambda: mock_harness_manager_for_config_file(config_file),
        )

        # Save with default values
        VibeConfig.save_updates({
            "project_context": {"default_commit_count": 5},
            "session_logging": {"session_prefix": "session"},
        })

        result = config_file.read_text()

        # All comments should be preserved
        assert "# Main config" in result
        assert "# Project context section" in result
        assert "# Commit count comment" in result
        assert "# Timeout comment" in result
        assert "# Default commit count comment" in result
        assert "# default_commit_count = 5" in result
        assert "# Session logging section" in result
        assert "# Save dir comment" in result
        assert "# Session prefix comment" in result
        assert '# session_prefix = "session"' in result

        # Default values should be removed (check for actual config lines, not comments)
        # default_commit_count should not appear as an active config line
        import re

        assert not re.search(r"^(?!#)\s*default_commit_count\s*=", result, re.MULTILINE)
        # session_prefix should not appear as an active config line (only in comment)
        assert not re.search(r"^(?!#)\s*session_prefix\s*=", result, re.MULTILINE)

        # Non-default values should remain
        assert "auto_approve = true" in result
        assert "timeout_seconds = 5.0" in result
        assert 'save_dir = "/custom/logs"' in result

    def test_removes_empty_string_from_config_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that empty string values are removed from config file."""
        config_content = """# Config with empty string
displayed_workdir = "/some/path"
auto_approve = true
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        unlock_config_paths()
        monkeypatch.setattr(
            "vibe.core.config._settings.get_harness_files_manager",
            lambda: mock_harness_manager_for_config_file(config_file),
        )

        # Set displayed_workdir back to default (empty string)
        VibeConfig.save_updates({"displayed_workdir": ""})

        result = config_file.read_text()

        # Empty string should be removed
        assert "displayed_workdir" not in result
        # Other values should remain
        assert "auto_approve = true" in result
        assert "# Config with empty string" in result

    def test_removes_session_prefix_default_from_session_logging(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that session_prefix default value is removed from session_logging section."""
        config_content = """[session_logging]
session_prefix = "custom_prefix"
enabled = false
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        unlock_config_paths()
        monkeypatch.setattr(
            "vibe.core.config._settings.get_harness_files_manager",
            lambda: mock_harness_manager_for_config_file(config_file),
        )

        # Set session_prefix back to default ("session")
        VibeConfig.save_updates({"session_logging": {"session_prefix": "session"}})

        result = config_file.read_text()

        # Default session_prefix should be removed
        assert "session_prefix" not in result
        # Other values should remain
        assert "enabled = false" in result

    def test_removes_all_defaults_not_just_updated(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that ALL default values are removed, not just the ones being updated."""
        # Create a config with multiple default values
        config_content = """active_model = "custom-model"
tool_paths = []
lsp_servers = []
enabled_tools = []
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        unlock_config_paths()
        monkeypatch.setattr(
            "vibe.core.config._settings.get_harness_files_manager",
            lambda: mock_harness_manager_for_config_file(config_file),
        )

        # Update only active_model - but ALL defaults should be removed
        VibeConfig.save_updates({"active_model": "another-model"})

        result = config_file.read_text()

        # active_model should be updated
        assert 'active_model = "another-model"' in result
        # ALL default empty lists should be removed, even though we didn't update them
        assert "tool_paths" not in result
        assert "lsp_servers" not in result
        assert "enabled_tools" not in result

    def test_removes_empty_nested_section(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that empty nested sections are removed entirely."""
        config_content = """[[models]]
name = "local_mock"
provider = "local_mock"

[project_context]

[session_logging]
save_dir = "/custom/logs"
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        unlock_config_paths()
        monkeypatch.setattr(
            "vibe.core.config._settings.get_harness_files_manager",
            lambda: mock_harness_manager_for_config_file(config_file),
        )

        # Save with any update to trigger cleanup
        VibeConfig.save_updates({"active_model": "devstral-2"})

        result = config_file.read_text()

        # Empty project_context section should be removed
        assert "[project_context]" not in result
        # Non-empty session_logging should remain
        assert "[session_logging]" in result
        assert 'save_dir = "/custom/logs"' in result

    def test_preserves_comments_in_models_array(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that comments inside [[models]] array are preserved."""
        config_content = """# Comment before models
[[models]]
# This is model 1
name = "local_mock"
provider = "local_mock"
alias = "local_mock"
auto_compact_threshold = 80000

[session_logging]
save_dir = "/custom/logs"
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        unlock_config_paths()
        monkeypatch.setattr(
            "vibe.core.config._settings.get_harness_files_manager",
            lambda: mock_harness_manager_for_config_file(config_file),
        )

        # Save with any update to trigger cleanup
        VibeConfig.save_updates({"active_model": "devstral-2"})

        result = config_file.read_text()

        # Comments should be preserved
        assert "# Comment before models" in result
        assert "# This is model 1" in result
        # Model should remain
        assert 'name = "local_mock"' in result

    def test_removes_default_values_from_models_array(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that default values are removed from [[models]] array items."""
        config_content = """[[models]]
name = "test_model"
provider = "test_provider"
alias = "test"
input_price = 0.0
output_price = 0.0
thinking = "off"
auto_compact_threshold = 200000
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        unlock_config_paths()
        monkeypatch.setattr(
            "vibe.core.config._settings.get_harness_files_manager",
            lambda: mock_harness_manager_for_config_file(config_file),
        )

        # Save with any update to trigger cleanup
        VibeConfig.save_updates({"active_model": "devstral-2"})

        result = config_file.read_text()

        # Required fields should remain
        assert 'name = "test_model"' in result
        assert 'provider = "test_provider"' in result
        assert 'alias = "test"' in result
        # Default values should be removed
        assert "input_price" not in result
        assert "output_price" not in result
        assert "thinking" not in result
        assert "auto_compact_threshold" not in result

    def test_removes_default_values_from_providers_array(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that default values are removed from [[providers]] array items."""
        config_content = """[[providers]]
name = "custom_provider"
api_base = "https://custom.api/v1"
api_key_env_var = "CUSTOM_API_KEY"
api_style = "openai"
backend = "generic"
reasoning_field_name = "reasoning_content"
project_id = ""
region = ""
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        unlock_config_paths()
        monkeypatch.setattr(
            "vibe.core.config._settings.get_harness_files_manager",
            lambda: mock_harness_manager_for_config_file(config_file),
        )

        # Save with any update to trigger cleanup
        VibeConfig.save_updates({"active_model": "devstral-2"})

        result = config_file.read_text()

        # Required fields should remain
        assert 'name = "custom_provider"' in result
        assert 'api_base = "https://custom.api/v1"' in result
        assert 'api_key_env_var = "CUSTOM_API_KEY"' in result
        # Default values should be removed
        assert "api_style" not in result
        assert "backend" not in result
        assert "reasoning_field_name" not in result
        assert "project_id" not in result
        assert "region" not in result


class TestMCPServersEnvRemoval:
    """Tests for removing empty [mcp_servers.env] sections."""

    def test_removes_empty_mcp_servers_env(self, tmp_path):
        """Test that empty [mcp_servers.env] sections are removed."""
        import tomlkit

        config_content = """
active_model = "test"

[[mcp_servers]]
name = "web_search"
transport = "stdio"
command = "uvx"
args = ["duckduckgo-mcp-server"]

[mcp_servers.env]
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        doc = tomlkit.parse(config_content)
        VibeConfig._remove_defaults_from_doc(doc)
        output = tomlkit.dumps(doc)

        assert "[mcp_servers.env]" not in output
        assert "[[mcp_servers]]" in output
        assert 'name = "web_search"' in output

    def test_keeps_non_empty_mcp_servers_env(self, tmp_path):
        """Test that non-empty [mcp_servers.env] sections are preserved."""
        import tomlkit

        config_content = """
active_model = "test"

[[mcp_servers]]
name = "web_search"
transport = "stdio"
command = "uvx"
args = ["duckduckgo-mcp-server"]

[mcp_servers.env]
MY_VAR = "value"
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        doc = tomlkit.parse(config_content)
        VibeConfig._remove_defaults_from_doc(doc)
        output = tomlkit.dumps(doc)

        assert "[mcp_servers.env]" in output
        assert 'MY_VAR = "value"' in output
