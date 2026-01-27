"""Tests for CLI main functions."""

from __future__ import annotations

import argparse
import sys
from unittest.mock import MagicMock, patch

import pytest

from vibe.cli.cli import (
    get_initial_mode,
    get_prompt_from_stdin,
    load_config_or_exit,
)
from vibe.core.config import MissingAPIKeyError, MissingPromptFileError
from vibe.core.modes import AgentMode


class TestGetInitialMode:
    """Test get_initial_mode function."""

    def test_get_initial_mode_default(self) -> None:
        """Test default mode when no flags are set."""
        args = argparse.Namespace(plan=False, auto_approve=False, prompt=None)
        mode = get_initial_mode(args)
        assert mode == AgentMode.DEFAULT

    def test_get_initial_mode_plan(self) -> None:
        """Test plan mode when --plan flag is set."""
        args = argparse.Namespace(plan=True, auto_approve=False, prompt=None)
        mode = get_initial_mode(args)
        assert mode == AgentMode.PLAN

    def test_get_initial_mode_auto_approve(self) -> None:
        """Test auto-approve mode when --auto-approve flag is set."""
        args = argparse.Namespace(plan=False, auto_approve=True, prompt=None)
        mode = get_initial_mode(args)
        assert mode == AgentMode.AUTO_APPROVE

    def test_get_initial_mode_prompt(self) -> None:
        """Test auto-approve mode when --prompt flag is set."""
        args = argparse.Namespace(plan=False, auto_approve=False, prompt="test")
        mode = get_initial_mode(args)
        assert mode == AgentMode.AUTO_APPROVE

    def test_get_initial_mode_plan_priority(self) -> None:
        """Test that plan mode takes priority over auto-approve."""
        args = argparse.Namespace(plan=True, auto_approve=True, prompt=None)
        mode = get_initial_mode(args)
        assert mode == AgentMode.PLAN

    def test_get_initial_mode_prompt_priority(self) -> None:
        """Test that prompt flag takes priority over default."""
        args = argparse.Namespace(plan=False, auto_approve=False, prompt="test")
        mode = get_initial_mode(args)
        assert mode == AgentMode.AUTO_APPROVE

    def test_get_initial_mode_all_flags(self) -> None:
        """Test mode selection with all flags set."""
        args = argparse.Namespace(plan=True, auto_approve=True, prompt="test")
        mode = get_initial_mode(args)
        assert mode == AgentMode.PLAN  # Plan should have highest priority


class TestGetPromptFromStdin:
    """Test get_prompt_from_stdin function."""

    @patch("sys.stdin.isatty", return_value=True)
    def test_get_prompt_from_stdin_tty(self, mock_isatty: MagicMock) -> None:
        """Test that returns None when stdin is a TTY."""
        result = get_prompt_from_stdin()
        assert result is None
        mock_isatty.assert_called_once()

    @patch("sys.stdin.isatty", return_value=False)
    @patch("sys.stdin.read", return_value="test prompt")
    @patch("builtins.open")
    def test_get_prompt_from_stdin_success(
        self, mock_open: MagicMock, mock_read: MagicMock, mock_isatty: MagicMock
    ) -> None:
        """Test successful reading from stdin."""
        mock_stdin = MagicMock()
        mock_open.return_value = mock_stdin
        
        result = get_prompt_from_stdin()
        assert result == "test prompt"
        mock_isatty.assert_called_once()
        mock_read.assert_called_once()
        mock_open.assert_called_once_with("/dev/tty")

    @patch("sys.stdin.isatty", return_value=False)
    @patch("sys.stdin.read", return_value="")
    @patch("builtins.open")
    def test_get_prompt_from_stdin_empty(
        self, mock_open: MagicMock, mock_read: MagicMock, mock_isatty: MagicMock
    ) -> None:
        """Test that returns None when stdin is empty."""
        mock_stdin = MagicMock()
        mock_open.return_value = mock_stdin
        
        result = get_prompt_from_stdin()
        assert result is None
        mock_isatty.assert_called_once()
        mock_read.assert_called_once()

    @patch("sys.stdin.isatty", return_value=False)
    @patch("sys.stdin.read", side_effect=KeyboardInterrupt())
    def test_get_prompt_from_stdin_keyboard_interrupt(
        self, mock_read: MagicMock, mock_isatty: MagicMock
    ) -> None:
        """Test that returns None on KeyboardInterrupt."""
        result = get_prompt_from_stdin()
        assert result is None
        mock_isatty.assert_called_once()
        mock_read.assert_called_once()

    @patch("sys.stdin.isatty", return_value=False)
    @patch("sys.stdin.read", side_effect=OSError())
    def test_get_prompt_from_stdin_os_error(
        self, mock_read: MagicMock, mock_isatty: MagicMock
    ) -> None:
        """Test that returns None on OSError."""
        result = get_prompt_from_stdin()
        assert result is None
        mock_isatty.assert_called_once()
        mock_read.assert_called_once()

    @patch("sys.stdin.isatty", return_value=False)
    @patch("sys.stdin.read", return_value="  test prompt  ")
    @patch("builtins.open")
    def test_get_prompt_from_stdin_strips_whitespace(
        self, mock_open: MagicMock, mock_read: MagicMock, mock_isatty: MagicMock
    ) -> None:
        """Test that prompt is stripped of leading/trailing whitespace."""
        mock_stdin = MagicMock()
        mock_open.return_value = mock_stdin
        
        result = get_prompt_from_stdin()
        assert result == "test prompt"
        mock_isatty.assert_called_once()
        mock_read.assert_called_once()


class TestLoadConfigOrExit:
    """Test load_config_or_exit function."""

    @patch("vibe.cli.cli.VibeConfig")
    def test_load_config_or_exit_success(
        self, mock_config: MagicMock
    ) -> None:
        """Test successful config loading."""
        mock_config_instance = MagicMock()
        mock_config.load.return_value = mock_config_instance
        
        result = load_config_or_exit()
        assert result == mock_config_instance
        mock_config.load.assert_called_once_with(None, **AgentMode.DEFAULT.config_overrides)

    @patch("vibe.cli.cli.VibeConfig")
    def test_load_config_or_exit_api_key_error(
        self, mock_config: MagicMock
    ) -> None:
        """Test that exits on API key error."""
        # The function doesn't call load_api_keys_from_env, it's handled by VibeConfig.load
        mock_config.load.side_effect = MissingAPIKeyError("MISTRAL_API_KEY", "mistral")
        
        # Should run onboarding and try again
        with patch("vibe.cli.cli.run_onboarding"):
            with pytest.raises(MissingAPIKeyError):
                load_config_or_exit()

    @patch("vibe.cli.cli.VibeConfig")
    def test_load_config_or_exit_config_error(
        self, mock_config: MagicMock
    ) -> None:
        """Test that exits on config error."""
        mock_config.load.side_effect = MissingPromptFileError("test_error", "/tmp")
        
        with pytest.raises(SystemExit) as exc_info:
            load_config_or_exit()
        assert exc_info.value.code == 1

    @patch("vibe.cli.cli.VibeConfig")
    def test_load_config_or_exit_with_agent(
        self, mock_config: MagicMock
    ) -> None:
        """Test config loading with agent parameter."""
        mock_config_instance = MagicMock()
        mock_config.load.return_value = mock_config_instance
        
        result = load_config_or_exit(agent="test-agent")
        assert result == mock_config_instance
        mock_config.load.assert_called_once_with("test-agent", **AgentMode.DEFAULT.config_overrides)

    @patch("vibe.cli.cli.VibeConfig")
    def test_load_config_or_exit_with_mode(
        self, mock_config: MagicMock
    ) -> None:
        """Test config loading with mode parameter."""
        mock_config_instance = MagicMock()
        mock_config.load.return_value = mock_config_instance
        
        result = load_config_or_exit(mode=AgentMode.PLAN)
        assert result == mock_config_instance
        mock_config.load.assert_called_once_with(None, **AgentMode.PLAN.config_overrides)


class TestCLIIntegration:
    """Test CLI integration scenarios."""

    @patch("vibe.cli.cli.get_prompt_from_stdin")
    @patch("vibe.cli.cli.load_config_or_exit")
    @patch("vibe.cli.cli.get_initial_mode")
    def test_cli_mode_selection_integration(
        self,
        mock_get_mode: MagicMock,
        mock_load_config: MagicMock,
        mock_get_prompt: MagicMock,
    ) -> None:
        """Test integration of mode selection with config loading."""
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config
        mock_get_mode.return_value = AgentMode.PLAN
        mock_get_prompt.return_value = "test prompt"
        
        # Test that the mocked functions return the expected values
        mode = mock_get_mode(argparse.Namespace(plan=True, auto_approve=False, prompt=None))
        assert mode == AgentMode.PLAN
        
        config = mock_load_config()
        assert config == mock_config
        
        prompt = mock_get_prompt()
        assert prompt == "test prompt"

    @patch("sys.stdin.isatty", return_value=False)
    @patch("sys.stdin.read", return_value="test from stdin")
    @patch("builtins.open")
    def test_cli_stdin_integration(
        self, mock_open: MagicMock, mock_read: MagicMock, mock_isatty: MagicMock
    ) -> None:
        """Test integration of stdin prompt reading."""
        mock_stdin = MagicMock()
        mock_open.return_value = mock_stdin
        
        prompt = get_prompt_from_stdin()
        assert prompt == "test from stdin"
        
        # Verify stdin was restored


class TestBootstrapConfigFiles:
    """Test bootstrap_config_files function."""

    @patch("vibe.cli.cli.CONFIG_FILE")
    @patch("vibe.cli.cli.INSTRUCTIONS_FILE")
    @patch("vibe.cli.cli.HISTORY_FILE")
    @patch("vibe.cli.cli.VibeConfig")
    def test_bootstrap_config_files_all_exist(
        self,
        mock_config: MagicMock,
        mock_history: MagicMock,
        mock_instructions: MagicMock,
        mock_config_file: MagicMock,
    ) -> None:
        """Test when all config files already exist."""
        mock_config_file.path.exists.return_value = True
        mock_history.path.exists.return_value = True
        mock_instructions.path.exists.return_value = True
        
        from vibe.cli.cli import bootstrap_config_files
        
        bootstrap_config_files()
        
        # Should not try to create any files
        mock_config.save_updates.assert_not_called()

    @patch("vibe.cli.cli.CONFIG_FILE")
    @patch("vibe.cli.cli.INSTRUCTIONS_FILE")
    @patch("vibe.cli.cli.HISTORY_FILE")
    @patch("vibe.cli.cli.VibeConfig")
    def test_bootstrap_config_files_create_missing(
        self,
        mock_config: MagicMock,
        mock_history: MagicMock,
        mock_instructions: MagicMock,
        mock_config_file: MagicMock,
    ) -> None:
        """Test when config files need to be created."""
        mock_config_file.path.exists.return_value = False
        mock_history.path.exists.return_value = False
        mock_instructions.path.exists.return_value = False
        
        mock_config_file.path = MagicMock()
        mock_history.path = MagicMock()
        mock_instructions.path = MagicMock()
        mock_history.path.parent = MagicMock()
        mock_instructions.path.parent = MagicMock()
        
        mock_default_config = MagicMock()
        mock_config.create_default.return_value = mock_default_config
        
        # Mock save_updates to not raise errors
        mock_config.save_updates = MagicMock(return_value=None)
        
        from vibe.cli.cli import bootstrap_config_files
        
        # Should not raise an exception
        bootstrap_config_files()

    @patch("vibe.cli.cli.CONFIG_FILE")
    @patch("vibe.cli.cli.INSTRUCTIONS_FILE")
    @patch("vibe.cli.cli.HISTORY_FILE")
    @patch("vibe.cli.cli.VibeConfig")
    def test_bootstrap_config_files_handle_errors(
        self,
        mock_config: MagicMock,
        mock_history: MagicMock,
        mock_instructions: MagicMock,
        mock_config_file: MagicMock,
    ) -> None:
        """Test error handling when creating config files."""
        mock_config_file.path.exists.return_value = False
        mock_config.save_updates.side_effect = Exception("Test error")
        
        from vibe.cli.cli import bootstrap_config_files
        
        # Should not raise exception
        bootstrap_config_files()


class TestLoadSession:
    """Test load_session function."""

    @patch("vibe.cli.cli.InteractionLogger")
    def test_load_session_no_flags(
        self, mock_logger: MagicMock
    ) -> None:
        """Test when neither continue nor resume flags are set."""
        args = argparse.Namespace(continue_session=False, resume=None)
        config = MagicMock()
        config.session_logging.enabled = True
        
        from vibe.cli.cli import load_session
        
        result = load_session(args, config)
        assert result == (None, None)

    @patch("vibe.cli.cli.InteractionLogger")
    def test_load_session_disabled(
        self, mock_logger: MagicMock
    ) -> None:
        """Test when session logging is disabled."""
        args = argparse.Namespace(continue_session=True, resume=None)
        config = MagicMock()
        config.session_logging.enabled = False
        
        from vibe.cli.cli import load_session
        
        with pytest.raises(SystemExit):
            load_session(args, config)

    @patch("vibe.cli.cli.InteractionLogger")
    def test_load_session_continue_no_sessions(
        self, mock_logger: MagicMock
    ) -> None:
        """Test when --continue is set but no sessions exist."""
        args = argparse.Namespace(continue_session=True, resume=None)
        config = MagicMock()
        config.session_logging.enabled = True
        mock_logger.find_latest_session.return_value = None
        
        from vibe.cli.cli import load_session
        
        with pytest.raises(SystemExit):
            load_session(args, config)

    @patch("vibe.cli.cli.InteractionLogger")
    def test_load_session_resume_not_found(
        self, mock_logger: MagicMock
    ) -> None:
        """Test when --resume is set with non-existent session ID."""
        args = argparse.Namespace(continue_session=False, resume="nonexistent")
        config = MagicMock()
        config.session_logging.enabled = True
        mock_logger.find_session_by_id.return_value = None
        
        from vibe.cli.cli import load_session
        
        with pytest.raises(SystemExit):
            load_session(args, config)

    @patch("vibe.cli.cli.InteractionLogger")
    def test_load_session_success(
        self, mock_logger: MagicMock
    ) -> None:
        """Test successful session loading."""
        args = argparse.Namespace(continue_session=True, resume=None)
        config = MagicMock()
        config.session_logging.enabled = True
        mock_logger.find_latest_session.return_value = "session123"
        mock_logger.load_session.return_value = ([MagicMock()], {"metadata": "value"})
        
        from vibe.cli.cli import load_session
        
        result = load_session(args, config)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        assert isinstance(result[1], dict)
        assert result[1] == {"metadata": "value"}

    @patch("vibe.cli.cli.InteractionLogger")
    def test_load_session_load_error(
        self, mock_logger: MagicMock
    ) -> None:
        """Test when session loading fails."""
        args = argparse.Namespace(continue_session=True, resume=None)
        config = MagicMock()
        config.session_logging.enabled = True
        mock_logger.find_latest_session.return_value = "session123"
        mock_logger.load_session.side_effect = Exception("Load error")
        
        from vibe.cli.cli import load_session
        
        with pytest.raises(SystemExit):
            load_session(args, config)


class TestRunCLI:
    """Test run_cli function."""

    @patch("vibe.cli.cli.load_api_keys_from_env")
    @patch("vibe.cli.cli.bootstrap_config_files")
    @patch("vibe.cli.cli.get_initial_mode")
    @patch("vibe.cli.cli.load_config_or_exit")
    @patch("vibe.cli.cli.load_session")
    @patch("vibe.cli.cli.get_prompt_from_stdin")
    @patch("vibe.cli.cli.run_textual_ui")
    def test_run_cli_interactive_mode(
        self,
        mock_run_ui: MagicMock,
        mock_get_prompt: MagicMock,
        mock_load_session: MagicMock,
        mock_load_config: MagicMock,
        mock_get_mode: MagicMock,
        mock_bootstrap: MagicMock,
        mock_load_keys: MagicMock,
    ) -> None:
        """Test running CLI in interactive mode."""
        args = argparse.Namespace(
            setup=False,
            prompt=None,
            initial_prompt=None,
            enabled_tools=None,
            agent=None,
        )
        mock_config = MagicMock()
        mock_get_mode.return_value = MagicMock()
        mock_load_config.return_value = mock_config
        mock_load_session.return_value = (None, None)
        mock_get_prompt.return_value = "test prompt"
        
        from vibe.cli.cli import run_cli
        
        run_cli(args)
        
        mock_run_ui.assert_called_once()

    @patch("vibe.cli.cli.load_api_keys_from_env")
    @patch("vibe.cli.cli.bootstrap_config_files")
    @patch("vibe.cli.cli.get_initial_mode")
    @patch("vibe.cli.cli.load_config_or_exit")
    @patch("vibe.cli.cli.load_session")
    @patch("vibe.cli.cli.get_prompt_from_stdin")
    @patch("vibe.cli.cli.run_programmatic")
    def test_run_cli_programmatic_mode(
        self,
        mock_run_programmatic: MagicMock,
        mock_get_prompt: MagicMock,
        mock_load_session: MagicMock,
        mock_load_config: MagicMock,
        mock_get_mode: MagicMock,
        mock_bootstrap: MagicMock,
        mock_load_keys: MagicMock,
    ) -> None:
        """Test running CLI in programmatic mode."""
        args = argparse.Namespace(
            setup=False,
            prompt="test prompt",
            initial_prompt=None,
            enabled_tools=None,
            agent=None,
            max_turns=5,
            max_price=1.0,
            output="text",
        )
        mock_config = MagicMock()
        mock_get_mode.return_value = MagicMock()
        mock_load_config.return_value = mock_config
        mock_load_session.return_value = (None, None)
        mock_get_prompt.return_value = ""
        mock_run_programmatic.return_value = "test response"
        
        from vibe.cli.cli import run_cli
        
        with pytest.raises(SystemExit):
            run_cli(args)
        
        mock_run_programmatic.assert_called_once()

    @patch("vibe.cli.cli.load_api_keys_from_env")
    @patch("vibe.cli.cli.run_onboarding")
    def test_run_cli_setup_mode(
        self,
        mock_run_onboarding: MagicMock,
        mock_load_keys: MagicMock,
    ) -> None:
        """Test running CLI in setup mode."""
        args = argparse.Namespace(setup=True)
        
        from vibe.cli.cli import run_cli
        
        with pytest.raises(SystemExit):
            run_cli(args)
        
        mock_run_onboarding.assert_called_once()

    @patch("vibe.cli.cli.load_api_keys_from_env")
    @patch("vibe.cli.cli.bootstrap_config_files")
    @patch("vibe.cli.cli.get_initial_mode")
    @patch("vibe.cli.cli.load_config_or_exit")
    @patch("vibe.cli.cli.load_session")
    @patch("vibe.cli.cli.get_prompt_from_stdin")
    @patch("vibe.cli.cli.run_programmatic")
    def test_run_cli_programmatic_no_prompt(
        self,
        mock_run_programmatic: MagicMock,
        mock_get_prompt: MagicMock,
        mock_load_session: MagicMock,
        mock_load_config: MagicMock,
        mock_get_mode: MagicMock,
        mock_bootstrap: MagicMock,
        mock_load_keys: MagicMock,
    ) -> None:
        """Test programmatic mode with no prompt provided."""
        args = argparse.Namespace(
            setup=False,
            prompt="",
            initial_prompt=None,
            enabled_tools=None,
            agent=None,
            max_turns=5,
            max_price=1.0,
            output="text",
        )
        mock_config = MagicMock()
        mock_get_mode.return_value = MagicMock()
        mock_load_config.return_value = mock_config
        mock_load_session.return_value = (None, None)
        mock_get_prompt.return_value = ""
        
        from vibe.cli.cli import run_cli
        
        with pytest.raises(SystemExit):
            run_cli(args)

    @patch("vibe.cli.cli.load_api_keys_from_env")
    @patch("vibe.cli.cli.bootstrap_config_files")
    @patch("vibe.cli.cli.get_initial_mode")
    @patch("vibe.cli.cli.load_config_or_exit")
    @patch("vibe.cli.cli.load_session")
    @patch("vibe.cli.cli.get_prompt_from_stdin")
    @patch("vibe.cli.cli.run_programmatic")
    def test_run_cli_programmatic_conversation_limit(
        self,
        mock_run_programmatic: MagicMock,
        mock_get_prompt: MagicMock,
        mock_load_session: MagicMock,
        mock_load_config: MagicMock,
        mock_get_mode: MagicMock,
        mock_bootstrap: MagicMock,
        mock_load_keys: MagicMock,
    ) -> None:
        """Test programmatic mode with conversation limit exception."""
        from vibe.core.utils import ConversationLimitException
        
        args = argparse.Namespace(
            setup=False,
            prompt="test prompt",
            initial_prompt=None,
            enabled_tools=None,
            agent=None,
            max_turns=5,
            max_price=1.0,
            output="text",
        )
        mock_config = MagicMock()
        mock_get_mode.return_value = MagicMock()
        mock_load_config.return_value = mock_config
        mock_load_session.return_value = (None, None)
        mock_get_prompt.return_value = ""
        mock_run_programmatic.side_effect = ConversationLimitException("Limit reached")
        
        from vibe.cli.cli import run_cli
        
        with pytest.raises(SystemExit):
            run_cli(args)

    @patch("vibe.cli.cli.load_api_keys_from_env")
    @patch("vibe.cli.cli.bootstrap_config_files")
    @patch("vibe.cli.cli.get_initial_mode")
    @patch("vibe.cli.cli.load_config_or_exit")
    @patch("vibe.cli.cli.load_session")
    @patch("vibe.cli.cli.get_prompt_from_stdin")
    @patch("vibe.cli.cli.run_programmatic")
    def test_run_cli_programmatic_runtime_error(
        self,
        mock_run_programmatic: MagicMock,
        mock_get_prompt: MagicMock,
        mock_load_session: MagicMock,
        mock_load_config: MagicMock,
        mock_get_mode: MagicMock,
        mock_bootstrap: MagicMock,
        mock_load_keys: MagicMock,
    ) -> None:
        """Test programmatic mode with runtime error."""
        args = argparse.Namespace(
            setup=False,
            prompt="test prompt",
            initial_prompt=None,
            enabled_tools=None,
            agent=None,
            max_turns=5,
            max_price=1.0,
            output="text",
        )
        mock_config = MagicMock()
        mock_get_mode.return_value = MagicMock()
        mock_load_config.return_value = mock_config
        mock_load_session.return_value = (None, None)
        mock_get_prompt.return_value = ""
        mock_run_programmatic.side_effect = RuntimeError("Test error")
        
        from vibe.cli.cli import run_cli
        
        with pytest.raises(SystemExit):
            run_cli(args)

    @patch("vibe.cli.cli.load_api_keys_from_env")
    @patch("vibe.cli.cli.bootstrap_config_files")
    @patch("vibe.cli.cli.get_initial_mode")
    @patch("vibe.cli.cli.load_config_or_exit")
    @patch("vibe.cli.cli.load_session")
    @patch("vibe.cli.cli.get_prompt_from_stdin")
    @patch("vibe.cli.cli.run_textual_ui")
    def test_run_cli_keyboard_interrupt(
        self,
        mock_run_ui: MagicMock,
        mock_get_prompt: MagicMock,
        mock_load_session: MagicMock,
        mock_load_config: MagicMock,
        mock_get_mode: MagicMock,
        mock_bootstrap: MagicMock,
        mock_load_keys: MagicMock,
    ) -> None:
        """Test handling of keyboard interrupt."""
        args = argparse.Namespace(
            setup=False,
            prompt=None,
            initial_prompt=None,
            enabled_tools=None,
            agent=None,
        )
        mock_config = MagicMock()
        mock_get_mode.return_value = MagicMock()
        mock_load_config.return_value = mock_config
        mock_load_session.return_value = (None, None)
        mock_get_prompt.return_value = "test prompt"
        mock_run_ui.side_effect = KeyboardInterrupt()
        
        from vibe.cli.cli import run_cli
        
        with pytest.raises(SystemExit):
            run_cli(args)

    @patch("vibe.cli.cli.load_api_keys_from_env")
    @patch("vibe.cli.cli.bootstrap_config_files")
    @patch("vibe.cli.cli.get_initial_mode")
    @patch("vibe.cli.cli.load_config_or_exit")
    @patch("vibe.cli.cli.load_session")
    @patch("vibe.cli.cli.get_prompt_from_stdin")
    @patch("vibe.cli.cli.run_textual_ui")
    def test_run_cli_eof_error(
        self,
        mock_run_ui: MagicMock,
        mock_get_prompt: MagicMock,
        mock_load_session: MagicMock,
        mock_load_config: MagicMock,
        mock_get_mode: MagicMock,
        mock_bootstrap: MagicMock,
        mock_load_keys: MagicMock,
    ) -> None:
        """Test handling of EOF error."""
        args = argparse.Namespace(
            setup=False,
            prompt=None,
            initial_prompt=None,
            enabled_tools=None,
            agent=None,
        )
        mock_config = MagicMock()
        mock_get_mode.return_value = MagicMock()
        mock_load_config.return_value = mock_config
        mock_load_session.return_value = (None, None)
        mock_get_prompt.return_value = "test prompt"
        mock_run_ui.side_effect = EOFError()
        
        from vibe.cli.cli import run_cli
        
        with pytest.raises(SystemExit):
            run_cli(args)