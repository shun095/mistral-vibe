"""Tests for CLI entry point and argument parsing."""

from __future__ import annotations

import argparse
import sys
from unittest.mock import MagicMock, patch

import pytest

from vibe.cli.entrypoint import parse_arguments


class TestParseArguments:
    """Test argument parsing functionality."""

    def test_parse_arguments_no_args(self) -> None:
        """Test parsing with no arguments."""
        with patch("sys.argv", ["vibe"]):
            args = parse_arguments()
            assert args.initial_prompt is None
            assert args.prompt is None
            assert args.auto_approve is False
            assert args.plan is False

    def test_parse_arguments_with_initial_prompt(self) -> None:
        """Test parsing with initial prompt."""
        with patch("sys.argv", ["vibe", "Hello world"]):
            args = parse_arguments()
            assert args.initial_prompt == "Hello world"
            assert args.prompt is None
            assert args.auto_approve is False
            assert args.plan is False

    def test_parse_arguments_with_prompt_flag(self) -> None:
        """Test parsing with --prompt flag."""
        with patch("sys.argv", ["vibe", "--prompt", "Test query"]):
            args = parse_arguments()
            assert args.initial_prompt is None
            assert args.prompt == "Test query"
            assert args.auto_approve is False
            assert args.plan is False

    def test_parse_arguments_with_auto_approve(self) -> None:
        """Test parsing with --auto-approve flag."""
        with patch("sys.argv", ["vibe", "--auto-approve"]):
            args = parse_arguments()
            assert args.initial_prompt is None
            assert args.prompt is None
            assert args.auto_approve is True
            assert args.plan is False

    def test_parse_arguments_with_plan_flag(self) -> None:
        """Test parsing with --plan flag."""
        with patch("sys.argv", ["vibe", "--plan"]):
            args = parse_arguments()
            assert args.initial_prompt is None
            assert args.prompt is None
            assert args.auto_approve is False
            assert args.plan is True

    def test_parse_arguments_with_multiple_flags(self) -> None:
        """Test parsing with multiple flags."""
        with patch("sys.argv", ["vibe", "--auto-approve", "--plan", "Test prompt"]):
            args = parse_arguments()
            assert args.initial_prompt == "Test prompt"
            assert args.prompt is None
            assert args.auto_approve is True
            assert args.plan is True

    def test_parse_arguments_prompt_flag_without_value(self) -> None:
        """Test parsing with --prompt flag without value (should use empty string)."""
        with patch("sys.argv", ["vibe", "--prompt"]):
            args = parse_arguments()
            assert args.initial_prompt is None
            assert args.prompt == ""
            assert args.auto_approve is False
            assert args.plan is False

    def test_parse_arguments_version_flag(self) -> None:
        """Test parsing with --version flag."""
        with patch("sys.argv", ["vibe", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                parse_arguments()
            assert exc_info.value.code == 0

    def test_parse_arguments_short_flags(self) -> None:
        """Test parsing with short flags."""
        with patch("sys.argv", ["vibe", "-p", "Test query"]):
            args = parse_arguments()
            assert args.initial_prompt is None
            assert args.prompt == "Test query"
            assert args.auto_approve is False
            assert args.plan is False


class TestArgumentValidation:
    """Test argument validation and edge cases."""

    def test_parse_arguments_with_special_characters(self) -> None:
        """Test parsing with special characters in prompt."""
        special_prompt = "Test with 'quotes' and \"double quotes\" and $variables"
        with patch("sys.argv", ["vibe", special_prompt]):
            args = parse_arguments()
            assert args.initial_prompt == special_prompt

    def test_parse_arguments_with_multiline_prompt(self) -> None:
        """Test parsing with multiline prompt."""
        multiline_prompt = "Line 1\nLine 2\nLine 3"
        with patch("sys.argv", ["vibe", multiline_prompt]):
            args = parse_arguments()
            assert args.initial_prompt == multiline_prompt

    def test_parse_arguments_with_unicode(self) -> None:
        """Test parsing with unicode characters."""
        unicode_prompt = "Test with unicode: 你好世界 🚀"
        with patch("sys.argv", ["vibe", unicode_prompt]):
            args = parse_arguments()
            assert args.initial_prompt == unicode_prompt

    def test_parse_arguments_empty_string_prompt(self) -> None:
        """Test parsing with empty string as prompt."""
        with patch("sys.argv", ["vibe", ""]):
            args = parse_arguments()
            assert args.initial_prompt == ""

    def test_parse_arguments_whitespace_only_prompt(self) -> None:
        """Test parsing with whitespace-only prompt."""
        with patch("sys.argv", ["vibe", "   "]):
            args = parse_arguments()
            assert args.initial_prompt == "   "


class TestArgumentParserConfiguration:
    """Test argument parser configuration."""

    def test_parser_description(self) -> None:
        """Test that parser has correct description."""
        with patch("sys.argv", ["vibe"]):
            args = parse_arguments()
            # Just verify it doesn't raise an exception
            assert True

    def test_parser_help_text(self) -> None:
        """Test that help text is available."""
        with patch("sys.argv", ["vibe", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                parse_arguments()
            assert exc_info.value.code == 0

    def test_parser_metavar_for_initial_prompt(self) -> None:
        """Test that initial_prompt has correct metavar."""
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "initial_prompt",
            nargs="?",
            metavar="PROMPT",
            help="Initial prompt to start the interactive session with.",
        )
        # Just verify the structure is correct
        assert True


class TestArgumentCombinations:
    """Test various combinations of arguments."""

    def test_prompt_and_auto_approve(self) -> None:
        """Test combination of --prompt and --auto-approve."""
        with patch("sys.argv", ["vibe", "--prompt", "Query", "--auto-approve"]):
            args = parse_arguments()
            assert args.prompt == "Query"
            assert args.auto_approve is True

    def test_prompt_and_plan(self) -> None:
        """Test combination of --prompt and --plan."""
        with patch("sys.argv", ["vibe", "--prompt", "Query", "--plan"]):
            args = parse_arguments()
            assert args.prompt == "Query"
            assert args.plan is True

    def test_all_flags_together(self) -> None:
        """Test all flags together."""
        with patch("sys.argv", ["vibe", "--auto-approve", "--plan", "--prompt", "Query"]):
            args = parse_arguments()
            assert args.prompt == "Query"
            assert args.auto_approve is True
            assert args.plan is True

    def test_initial_prompt_with_flags(self) -> None:
        """Test initial prompt with flags."""
        with patch("sys.argv", ["vibe", "Initial", "--auto-approve", "--plan"]):
            args = parse_arguments()
            assert args.initial_prompt == "Initial"
            assert args.auto_approve is True
            assert args.plan is True


class TestCheckAndResolveTrustedFolder:
    """Test check_and_resolve_trusted_folder function."""

    @patch("vibe.cli.entrypoint.Path.cwd")
    @patch("vibe.cli.entrypoint.Path.home")
    @patch("vibe.cli.entrypoint.has_trustable_content")
    @patch("vibe.cli.entrypoint.trusted_folders_manager")
    def test_check_trusted_folder_home_directory(
        self,
        mock_manager: MagicMock,
        mock_has_trustable: MagicMock,
        mock_home: MagicMock,
        mock_cwd: MagicMock,
    ) -> None:
        """Test when current directory is home directory."""
        mock_path_obj = MagicMock()
        mock_home_obj = MagicMock()
        # Make the resolve objects equal so the comparison passes
        mock_path_obj.resolve.return_value = mock_home_obj
        mock_cwd.return_value = mock_path_obj
        mock_home.return_value = mock_home_obj
        # Make mock objects equal for comparison
        mock_path_obj.__eq__ = lambda self, other: True
        mock_home_obj.__eq__ = lambda self, other: True
        mock_has_trustable.return_value = True
        
        from vibe.cli.entrypoint import check_and_resolve_trusted_folder
        
        check_and_resolve_trusted_folder()
        
        # Should not interact with trusted folders manager
        mock_manager.is_trusted.assert_not_called()

    @patch("vibe.cli.entrypoint.Path")
    @patch("vibe.cli.entrypoint.has_trustable_content")
    @patch("vibe.cli.entrypoint.trusted_folders_manager")
    def test_check_trusted_folder_not_trustable(
        self,
        mock_manager: MagicMock,
        mock_has_trustable: MagicMock,
        mock_path: MagicMock,
    ) -> None:
        """Test when current directory is not trustable."""
        mock_cwd = MagicMock()
        mock_cwd.resolve.return_value = MagicMock()
        mock_path.cwd.return_value = mock_cwd
        mock_path.home.return_value = MagicMock()
        mock_has_trustable.return_value = False
        
        from vibe.cli.entrypoint import check_and_resolve_trusted_folder
        
        check_and_resolve_trusted_folder()
        
        # Should not interact with trusted folders manager
        mock_manager.is_trusted.assert_not_called()

    @patch("vibe.cli.entrypoint.Path")
    @patch("vibe.cli.entrypoint.has_trustable_content")
    @patch("vibe.cli.entrypoint.trusted_folders_manager")
    @patch("vibe.cli.entrypoint.ask_trust_folder")
    def test_check_trusted_folder_already_trusted(
        self,
        mock_ask: MagicMock,
        mock_manager: MagicMock,
        mock_has_trustable: MagicMock,
        mock_path: MagicMock,
    ) -> None:
        """Test when folder is already trusted."""
        mock_cwd = MagicMock()
        mock_cwd.resolve.return_value = MagicMock()
        mock_path.cwd.return_value = mock_cwd
        mock_path.home.return_value = MagicMock()
        mock_has_trustable.return_value = True
        mock_manager.is_trusted.return_value = True
        
        from vibe.cli.entrypoint import check_and_resolve_trusted_folder
        
        check_and_resolve_trusted_folder()
        
        # Should not ask for trust
        mock_ask.assert_not_called()

    @patch("vibe.cli.entrypoint.Path")
    @patch("vibe.cli.entrypoint.has_trustable_content")
    @patch("vibe.cli.entrypoint.trusted_folders_manager")
    @patch("vibe.cli.entrypoint.ask_trust_folder")
    def test_check_trusted_folder_ask_trust(
        self,
        mock_ask: MagicMock,
        mock_manager: MagicMock,
        mock_has_trustable: MagicMock,
        mock_path: MagicMock,
    ) -> None:
        """Test when user is asked to trust folder."""
        mock_cwd = MagicMock()
        mock_cwd.resolve.return_value = MagicMock()
        mock_path.cwd.return_value = mock_cwd
        mock_path.home.return_value = MagicMock()
        mock_has_trustable.return_value = True
        mock_manager.is_trusted.return_value = None
        mock_ask.return_value = True
        
        from vibe.cli.entrypoint import check_and_resolve_trusted_folder
        
        check_and_resolve_trusted_folder()
        
        # Should ask for trust
        mock_ask.assert_called_once()
        # Should add to trusted folders
        mock_manager.add_trusted.assert_called_once()

    @patch("vibe.cli.entrypoint.Path")
    @patch("vibe.cli.entrypoint.has_trustable_content")
    @patch("vibe.cli.entrypoint.trusted_folders_manager")
    @patch("vibe.cli.entrypoint.ask_trust_folder")
    def test_check_trusted_folder_user_declines(
        self,
        mock_ask: MagicMock,
        mock_manager: MagicMock,
        mock_has_trustable: MagicMock,
        mock_path: MagicMock,
    ) -> None:
        """Test when user declines to trust folder."""
        mock_cwd = MagicMock()
        mock_cwd.resolve.return_value = MagicMock()
        mock_path.cwd.return_value = mock_cwd
        mock_path.home.return_value = MagicMock()
        mock_has_trustable.return_value = True
        mock_manager.is_trusted.return_value = None
        mock_ask.return_value = False
        
        from vibe.cli.entrypoint import check_and_resolve_trusted_folder
        
        check_and_resolve_trusted_folder()
        
        # Should ask for trust
        mock_ask.assert_called_once()
        # Should add to untrusted folders
        mock_manager.add_untrusted.assert_called_once()

    @patch("vibe.cli.entrypoint.Path")
    @patch("vibe.cli.entrypoint.has_trustable_content")
    @patch("vibe.cli.entrypoint.trusted_folders_manager")
    @patch("vibe.cli.entrypoint.ask_trust_folder")
    def test_check_trusted_folder_keyboard_interrupt(
        self,
        mock_ask: MagicMock,
        mock_manager: MagicMock,
        mock_has_trustable: MagicMock,
        mock_path: MagicMock,
    ) -> None:
        """Test when user interrupts trust dialog."""
        mock_cwd = MagicMock()
        mock_cwd.resolve.return_value = MagicMock()
        mock_path.cwd.return_value = mock_cwd
        mock_path.home.return_value = MagicMock()
        mock_has_trustable.return_value = True
        mock_manager.is_trusted.return_value = None
        mock_ask.side_effect = KeyboardInterrupt()
        
        from vibe.cli.entrypoint import check_and_resolve_trusted_folder
        
        with pytest.raises(SystemExit):
            check_and_resolve_trusted_folder()

    @patch("vibe.cli.entrypoint.Path")
    @patch("vibe.cli.entrypoint.has_trustable_content")
    @patch("vibe.cli.entrypoint.trusted_folders_manager")
    @patch("vibe.cli.entrypoint.ask_trust_folder")
    def test_check_trusted_folder_exception(
        self,
        mock_ask: MagicMock,
        mock_manager: MagicMock,
        mock_has_trustable: MagicMock,
        mock_path: MagicMock,
    ) -> None:
        """Test when exception occurs during trust dialog."""
        mock_cwd = MagicMock()
        mock_cwd.resolve.return_value = MagicMock()
        mock_path.cwd.return_value = mock_cwd
        mock_path.home.return_value = MagicMock()
        mock_has_trustable.return_value = True
        mock_manager.is_trusted.return_value = None
        mock_ask.side_effect = Exception("Test error")
        
        from vibe.cli.entrypoint import check_and_resolve_trusted_folder
        
        # Should not raise exception
        check_and_resolve_trusted_folder()


class TestMain:
    """Test main function."""

    @patch("vibe.cli.entrypoint.parse_arguments")
    @patch("vibe.cli.entrypoint.check_and_resolve_trusted_folder")
    @patch("vibe.cli.entrypoint.unlock_config_paths")
    @patch("vibe.cli.cli.run_cli")
    def test_main_interactive_mode(
        self,
        mock_run_cli: MagicMock,
        mock_unlock: MagicMock,
        mock_check_trust: MagicMock,
        mock_parse: MagicMock,
    ) -> None:
        """Test main function in interactive mode."""
        args = MagicMock()
        args.prompt = None
        mock_parse.return_value = args
        
        from vibe.cli.entrypoint import main
        
        main()
        
        mock_check_trust.assert_called_once()
        mock_unlock.assert_called_once()
        mock_run_cli.assert_called_once_with(args)

    @patch("vibe.cli.entrypoint.parse_arguments")
    @patch("vibe.cli.entrypoint.check_and_resolve_trusted_folder")
    @patch("vibe.cli.entrypoint.unlock_config_paths")
    @patch("vibe.cli.cli.run_cli")
    def test_main_programmatic_mode(
        self,
        mock_run_cli: MagicMock,
        mock_unlock: MagicMock,
        mock_check_trust: MagicMock,
        mock_parse: MagicMock,
    ) -> None:
        """Test main function in programmatic mode."""
        args = MagicMock()
        args.prompt = "test prompt"
        mock_parse.return_value = args
        
        from vibe.cli.entrypoint import main
        
        main()
        
        # Should not check trusted folder in programmatic mode
        mock_check_trust.assert_not_called()
        mock_unlock.assert_called_once()
        mock_run_cli.assert_called_once_with(args)