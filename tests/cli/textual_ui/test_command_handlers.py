"""Tests for command handler signature compatibility.

Ensures all command handlers accept the cmd_args parameter passed by _handle_command.
"""

from __future__ import annotations

import inspect


class TestCommandHandlerSignatures:
    """Test that command handlers have compatible signatures."""

    def test_all_command_handlers_accept_kwargs(self):
        """All command handlers must accept **kwargs to handle cmd_args parameter.

        This test prevents regressions where a command handler is defined without
        accepting the cmd_args parameter that _handle_command passes to all handlers.

        Regression test for: TypeError: VibeApp._restart_app() got an unexpected
        keyword argument 'cmd_args'
        """
        from vibe.cli.commands import CommandRegistry
        from vibe.cli.textual_ui.app import VibeApp

        # Get all command handlers from the CommandRegistry
        registry = CommandRegistry()
        handlers_to_check = [cmd.handler for cmd in registry.commands.values()]

        failures = []
        for handler_name in handlers_to_check:
            if not hasattr(VibeApp, handler_name):
                failures.append(f"{handler_name}: not found in VibeApp")
                continue

            handler = getattr(VibeApp, handler_name)
            sig = inspect.signature(handler)
            params = sig.parameters

            # Check if handler accepts **kwargs
            has_kwargs = any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
            )

            # Check if handler explicitly accepts cmd_args
            has_cmd_args = "cmd_args" in params

            if not has_kwargs and not has_cmd_args:
                failures.append(
                    f"{handler_name}: {sig} - does not accept **kwargs or cmd_args"
                )

        assert not failures, (
            "The following command handlers do not accept cmd_args parameter:\n"
            + "\n".join(failures)
        )

    def test_handle_command_passes_cmd_args(self):
        """Verify _handle_command passes cmd_args to all handlers."""
        from vibe.cli.textual_ui.app import VibeApp

        # Check the source code of _handle_command
        source = inspect.getsource(VibeApp._handle_command)

        # Verify it passes cmd_args to handlers
        assert "cmd_args=cmd_args" in source, (
            "_handle_command should pass cmd_args to handlers"
        )
