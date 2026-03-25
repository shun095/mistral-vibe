from __future__ import annotations

import argparse
from pathlib import Path
import sys

from rich import print as rprint
import tomli_w

from vibe import __version__
from vibe.cli.textual_ui.app import StartupOptions, run_textual_ui
from vibe.core.agent_loop import AgentLoop
from vibe.core.agents.models import BuiltinAgentName
from vibe.core.config import (
    MissingAPIKeyError,
    MissingPromptFileError,
    VibeConfig,
    load_dotenv_values,
)
from vibe.core.config.harness_files import get_harness_files_manager
from vibe.core.logger import logger
from vibe.core.paths import HISTORY_FILE
from vibe.core.programmatic import run_programmatic
from vibe.core.session.session_loader import SessionLoader
from vibe.core.tracing import setup_tracing
from vibe.core.types import EntrypointMetadata, LLMMessage, OutputFormat, Role
from vibe.core.utils import ConversationLimitException
from vibe.setup.onboarding import run_onboarding


def get_initial_agent_name(args: argparse.Namespace) -> str:
    if args.prompt is not None and args.agent == BuiltinAgentName.DEFAULT:
        return BuiltinAgentName.AUTO_APPROVE
    return args.agent


def get_prompt_from_stdin() -> str | None:
    if sys.stdin.isatty():
        return None
    try:
        if content := sys.stdin.read().strip():
            sys.stdin = sys.__stdin__ = open("/dev/tty")
            return content
    except KeyboardInterrupt:
        pass
    except OSError:
        return None

    return None


def load_config_or_exit() -> VibeConfig:
    try:
        return VibeConfig.load()
    except MissingAPIKeyError:
        run_onboarding()
        return VibeConfig.load()
    except MissingPromptFileError as e:
        rprint(f"[yellow]Invalid system prompt id: {e}[/]")
        sys.exit(1)
    except ValueError as e:
        rprint(f"[yellow]{e}[/]")
        sys.exit(1)


def bootstrap_config_files() -> None:
    mgr = get_harness_files_manager()
    config_file = mgr.user_config_file
    if not config_file.exists():
        try:
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with config_file.open("wb") as f:
                tomli_w.dump(VibeConfig.create_default(), f)
        except Exception as e:
            rprint(f"[yellow]Could not create default config file: {e}[/]")

    history_file = HISTORY_FILE.path
    if not history_file.exists():
        try:
            history_file.parent.mkdir(parents=True, exist_ok=True)
            history_file.write_text("Hello Vibe!\n", "utf-8")
        except Exception as e:
            rprint(f"[yellow]Could not create history file: {e}[/]")


def load_session(
    args: argparse.Namespace, config: VibeConfig
) -> tuple[list[LLMMessage], Path] | None:
    if not args.continue_session and not args.resume:
        return None

    if not config.session_logging.enabled:
        rprint(
            "[red]Session logging is disabled. "
            "Enable it in config to use --continue or --resume[/]"
        )
        sys.exit(1)

    session_to_load = None
    if args.continue_session:
        session_to_load = SessionLoader.find_latest_session(config.session_logging)
        if not session_to_load:
            rprint(
                f"[red]No previous sessions found in "
                f"{config.session_logging.save_dir}[/]"
            )
            sys.exit(1)
    elif args.resume is True:
        return None
    else:
        session_to_load = SessionLoader.find_session_by_id(
            args.resume, config.session_logging
        )
        if not session_to_load:
            rprint(
                f"[red]Session '{args.resume}' not found in "
                f"{config.session_logging.save_dir}[/]"
            )
            sys.exit(1)

    try:
        loaded_messages, _ = SessionLoader.load_session(session_to_load)
        return loaded_messages, session_to_load
    except Exception as e:
        rprint(f"[red]Failed to load session: {e}[/]")
        sys.exit(1)


def _resume_previous_session(
    agent_loop: AgentLoop, loaded_messages: list[LLMMessage], session_path: Path
) -> None:
    non_system_messages = [msg for msg in loaded_messages if msg.role != Role.system]
    agent_loop.messages.extend(non_system_messages)

    _, metadata = SessionLoader.load_session(session_path)
    session_id = metadata.get("session_id", agent_loop.session_id)
    agent_loop.session_id = session_id
    agent_loop.session_logger.resume_existing_session(session_id, session_path)

    logger.info(
        "Resumed session %s with %d messages", session_id, len(non_system_messages)
    )


def _run_programmatic_mode(
    args: argparse.Namespace,
    config: VibeConfig,
    loaded_session: tuple[list[LLMMessage], Path] | None,
    initial_agent_name: str,
) -> None:
    """Run CLI in programmatic mode with prompt from args or stdin."""
    stdin_prompt = get_prompt_from_stdin()
    config.disabled_tools = [*config.disabled_tools, "ask_user_question"]
    programmatic_prompt = args.prompt or stdin_prompt
    if not programmatic_prompt:
        print("Error: No prompt provided for programmatic mode", file=sys.stderr)
        sys.exit(1)

    output_format = OutputFormat(args.output if hasattr(args, "output") else "text")

    try:
        final_response = run_programmatic(
            config=config,
            prompt=programmatic_prompt,
            max_turns=args.max_turns,
            max_price=args.max_price,
            output_format=output_format,
            previous_messages=loaded_session[0] if loaded_session else None,
            agent_name=initial_agent_name,
        )
        if final_response:
            print(final_response)
        sys.exit(0)
    except ConversationLimitException as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _run_interactive_mode_with_web(
    args: argparse.Namespace, agent_loop: AgentLoop, stdin_prompt: str | None
) -> None:
    """Run interactive mode with web UI server."""
    import os

    from vibe.cli.plan_offer.adapters.http_whoami_gateway import HttpWhoAmIGateway
    from vibe.cli.textual_ui.app import VibeApp
    from vibe.cli.textual_ui.session_exit import print_session_resume_message
    from vibe.cli.update_notifier import (
        FileSystemUpdateCacheRepository,
        PyPIUpdateGateway,
    )
    from vibe.cli.web_ui.run_server import run_web_server_in_background

    token = os.environ.get("VIBE_WEB_TOKEN", "")

    update_notifier = PyPIUpdateGateway(project_name="mistral-vibe")
    update_cache_repository = FileSystemUpdateCacheRepository()
    plan_offer_gateway = HttpWhoAmIGateway()
    tui_app = VibeApp(
        agent_loop=agent_loop,
        initial_prompt=args.initial_prompt or stdin_prompt,
        teleport_on_start=args.teleport,
        update_notifier=update_notifier,
        update_cache_repository=update_cache_repository,
        plan_offer_gateway=plan_offer_gateway,
    )

    rprint(f"\n[green]Starting Web UI on port {args.web_port}...[/]\n")
    web_server_thread = run_web_server_in_background(
        port=args.web_port, token=token, agent_loop=agent_loop, tui_app=tui_app
    )
    rprint(
        f"[green]Web UI started at http://localhost:{args.web_port}/?token={token}[/]\n"
    )

    session_id = tui_app.run()
    print_session_resume_message(session_id, agent_loop.stats)
    web_server_thread.join(timeout=2)


def _run_interactive_mode(
    args: argparse.Namespace,
    config: VibeConfig,
    loaded_session: tuple[list[LLMMessage], Path] | None,
    initial_agent_name: str,
) -> None:
    """Run CLI in interactive mode, optionally with web UI."""
    stdin_prompt = get_prompt_from_stdin()
    agent_loop = AgentLoop(
        config,
        agent_name=initial_agent_name,
        enable_streaming=True,
        entrypoint_metadata=EntrypointMetadata(
            agent_entrypoint="cli",
            agent_version=__version__,
            client_name="vibe_cli",
            client_version=__version__,
        ),
    )

    if loaded_session:
        _resume_previous_session(agent_loop, *loaded_session)

    if args.web:
        _run_interactive_mode_with_web(args, agent_loop, stdin_prompt)
    else:
        run_textual_ui(
            agent_loop=agent_loop,
            startup=StartupOptions(
                initial_prompt=args.initial_prompt or stdin_prompt,
                teleport_on_start=args.teleport,
                show_resume_picker=args.resume is True,
            ),
        )


def run_cli(args: argparse.Namespace) -> None:
    """Run the CLI with the given arguments."""
    load_dotenv_values()
    bootstrap_config_files()

    if args.setup:
        run_onboarding()
        sys.exit(0)

    try:
        initial_agent_name = get_initial_agent_name(args)
        config = load_config_or_exit()
        setup_tracing(config)

        if args.enabled_tools:
            config.enabled_tools = args.enabled_tools

        loaded_session = load_session(args, config)

        if args.prompt is not None:
            _run_programmatic_mode(args, config, loaded_session, initial_agent_name)
        else:
            _run_interactive_mode(args, config, loaded_session, initial_agent_name)

    except (KeyboardInterrupt, EOFError):
        rprint("\n[dim]Bye![/]")
        sys.exit(0)
