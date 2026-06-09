from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys
import threading
from typing import TYPE_CHECKING, Any

from rich import print as rprint

if TYPE_CHECKING:
    from vibe.core.code_server import CodeServerManager
from rich.console import Console
import tomli_w

from vibe import __version__
from vibe.cli.textual_ui.app import StartupOptions, run_textual_ui
from vibe.cli.update_notifier import (
    FileSystemUpdateCacheRepository,
    UpdateCacheRepository,
    get_pending_update_from_cache,
    mark_update_as_dismissed,
)
from vibe.core.agent_loop import AgentLoop, TeleportError
from vibe.core.config import MissingAPIKeyError, VibeConfig, load_dotenv_values
from vibe.core.config.harness_files import get_harness_files_manager
from vibe.core.hooks.config import HookConfigResult, load_hooks_from_fs
from vibe.core.logger import logger
from vibe.core.paths import HISTORY_FILE
from vibe.core.programmatic import run_programmatic
from vibe.core.session import last_session_pointer
from vibe.core.session.session_loader import SessionLoader
from vibe.core.telemetry.build_metadata import build_entrypoint_metadata
from vibe.core.telemetry.types import EntrypointMetadata
from vibe.core.tracing import setup_tracing
from vibe.core.trusted_folders import find_trustable_files, trusted_folders_manager
from vibe.core.types import LLMMessage, OutputFormat
from vibe.core.utils import ConversationLimitException
from vibe.setup.onboarding import run_onboarding
from vibe.setup.update_prompt import UpdatePromptResult, ask_update_prompt


def _build_cli_entrypoint_metadata() -> EntrypointMetadata:
    return build_entrypoint_metadata(
        agent_entrypoint="cli",
        agent_version=__version__,
        client_name="vibe_cli",
        client_version=__version__,
    )


def get_initial_agent_name(args: argparse.Namespace, config: VibeConfig) -> str:
    return args.agent or config.default_agent


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


def load_config_or_exit(*, interactive: bool) -> VibeConfig:
    try:
        return VibeConfig.load()
    except MissingAPIKeyError as e:
        if not interactive:
            print(
                f"Error: {e}. Set the environment variable (e.g. in ~/.vibe/.env "
                "or your shell), or run `vibe --setup` once interactively.",
                file=sys.stderr,
            )
            sys.exit(1)
        run_onboarding(entrypoint_metadata=_build_cli_entrypoint_metadata())
        return VibeConfig.load()
    except ValueError as e:
        rprint(f"[yellow]{e}[/]")
        sys.exit(1)


def warn_if_workdir_trust_is_unset() -> None:
    try:
        cwd = Path.cwd()
    except FileNotFoundError:
        return
    if cwd.resolve() == Path.home().resolve():
        return
    if trusted_folders_manager.is_trusted(cwd) is not None:
        return
    detected = find_trustable_files(cwd)
    if not detected:
        return
    files_str = ", ".join(detected)
    Console(stderr=True).print(
        f"[yellow]Warning:[/] {cwd} is not trusted; "
        f"project configuration ({files_str}) will be ignored. "
        "Re-run with --trust to trust this folder temporarily."
    )


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
        cwd = Path.cwd().resolve()
        pointer_session_id = last_session_pointer.load(config.session_logging)
        if pointer_session_id:
            session_to_load = SessionLoader.find_session_by_id(
                pointer_session_id, config.session_logging, working_directory=cwd
            )
        if not session_to_load:
            session_to_load = SessionLoader.find_latest_session(
                config.session_logging, working_directory=cwd
            )
        if not session_to_load:
            rprint(
                f"[red]No previous sessions found in "
                f"{config.session_logging.save_dir} for {cwd=}[/]"
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
) -> bool:
    """Resume a previous session.

    Returns True if the saved system prompt was not found in metadata
    (i.e., the calculated prompt was used instead).
    """
    _, metadata = SessionLoader.load_session(session_path)

    # Reuse system prompt from saved session metadata (fallback to calculated)
    saved_system_prompt = metadata.get("system_prompt")
    use_saved = saved_system_prompt is not None
    if use_saved:
        try:
            saved_msg = LLMMessage.model_validate(saved_system_prompt)
            content = saved_msg.content
            if not isinstance(content, str) or not content:
                raise ValueError("empty or invalid system prompt content")
            agent_loop.messages[0] = saved_msg
            agent_loop._resume_system_prompt = content
        except (TypeError, ValueError, KeyError):
            use_saved = False
    if not use_saved:
        logger.warning(
            "Session %s has no saved system_prompt in meta.json; "
            "using calculated prompt instead",
            agent_loop.session_id,
        )

    agent_loop.messages.extend(loaded_messages)

    session_id = metadata.get("session_id", agent_loop.session_id)
    agent_loop.session_id = session_id
    agent_loop.parent_session_id = metadata.get("parent_session_id")
    agent_loop.session_logger.resume_existing_session(session_id, session_path)

    logger.info("Resumed session %s with %d messages", session_id, len(loaded_messages))
    return not use_saved


def _spawn_code_server(
    config: Any,
) -> tuple[CodeServerManager | None, int, threading.Thread | None]:
    """Start code-server if enabled. Returns (manager, port, monitor_thread)."""
    import asyncio

    from vibe.core.code_server import CodeServerManager, State
    from vibe.core.paths import VIBE_HOME

    if not config.code_server.enabled:
        return None, 0, None

    cs_config = config.code_server
    vibe_home = VIBE_HOME.path
    manager = CodeServerManager(
        port=cs_config.port,
        data_dir=vibe_home / "code-server-data",
        binary_path=cs_config.binary_path,
        auto_install=cs_config.auto_install,
    )

    # Spawn uses a temporary loop (no monitor task)
    asyncio.run(manager.spawn(Path.cwd()))

    if manager.state == State.STOPPED:
        rprint("[yellow]code-server failed to start — file browsing disabled[/]")
        return None, 0, None

    rprint(f"[green]code-server started on internal port {manager.port}[/]")

    # Run monitor loop in a background thread
    monitor_loop = asyncio.new_event_loop()

    def _run_monitor() -> None:
        asyncio.set_event_loop(monitor_loop)
        try:
            monitor_loop.run_until_complete(manager.run_monitor())
        finally:
            monitor_loop.close()

    thread = threading.Thread(target=_run_monitor, daemon=True)
    thread.start()
    return manager, manager.port, thread


def _shutdown_code_server(
    manager: CodeServerManager | None, monitor_thread: threading.Thread | None
) -> None:
    """Stop code-server if it was started."""
    import asyncio

    if not manager:
        return
    asyncio.run(manager.shutdown())
    if monitor_thread:
        monitor_thread.join(timeout=5)


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
    code_server_manager, code_server_port, monitor_thread = _spawn_code_server(
        agent_loop.config
    )

    # Mirror of run_textual_ui() VibeApp construction — kept inline to minimize
    # diff against origin/main. Update both sites if VibeApp gains new params.
    update_notifier = PyPIUpdateGateway(project_name="mistral-vibe")
    update_cache_repository = FileSystemUpdateCacheRepository()
    plan_offer_gateway = HttpWhoAmIGateway(base_url=agent_loop.config.console_base_url)
    tui_app = VibeApp(
        agent_loop=agent_loop,
        startup=StartupOptions(
            initial_prompt=args.initial_prompt or stdin_prompt,
            teleport_on_start=args.teleport,
        ),
        update_notifier=update_notifier,
        update_cache_repository=update_cache_repository,
        plan_offer_gateway=plan_offer_gateway,
    )

    base_path = args.web_base_path
    if not base_path.startswith("/"):
        base_path = "/" + base_path
    if len(base_path) > 1 and not base_path.endswith("/"):
        base_path += "/"

    rprint(
        f"\n[green]Starting Web UI on port {args.web_port} (base path: {base_path})...[/]\n"
    )
    cs_workdir = ""
    if code_server_manager and code_server_manager.workdir:
        cs_workdir = str(code_server_manager.workdir)
    web_server_thread, stop_web_server = run_web_server_in_background(
        port=args.web_port,
        token=token,
        base_path=base_path,
        agent_loop=agent_loop,
        tui_app=tui_app,
        code_server_port=code_server_port,
        code_server_workdir=cs_workdir,
    )
    rprint(
        f"[green]Web UI started at http://localhost:{args.web_port}{base_path.rstrip('/')}/login[/]\n"
    )

    session_id = tui_app.run()
    print_session_resume_message(
        session_id, agent_loop.stats, agent_loop.config.session_logging
    )
    stop_web_server()
    web_server_thread.join(timeout=5)
    _shutdown_code_server(code_server_manager, monitor_thread)
    if tui_app._restart_pending:
        os.execv(
            sys.executable, [sys.executable, "-m", "vibe.cli.entrypoint"] + sys.argv[1:]
        )


def _run_programmatic_mode(
    args: argparse.Namespace,
    config: VibeConfig,
    initial_agent_name: str,
    hook_config_result: HookConfigResult,
    loaded_session: tuple[list[LLMMessage], Path] | None,
    stdin_prompt: str | None,
) -> None:
    warn_if_workdir_trust_is_unset()
    config.disabled_tools = [
        *config.disabled_tools,
        "ask_user_question",
        "exit_plan_mode",
    ]
    programmatic_prompt = args.prompt or stdin_prompt
    if not programmatic_prompt:
        print("Error: No prompt provided for programmatic mode", file=sys.stderr)
        sys.exit(1)
    output_format = OutputFormat(args.output if hasattr(args, "output") else "text")

    try:
        final_response = run_programmatic(
            config=config,
            prompt=programmatic_prompt or "",
            max_turns=args.max_turns,
            max_price=args.max_price,
            max_session_tokens=args.max_tokens,
            output_format=output_format,
            previous_messages=loaded_session[0] if loaded_session else None,
            agent_name=initial_agent_name,
            teleport=args.teleport and config.vibe_code_enabled,
            headless=True,
            hook_config_result=hook_config_result,
        )
        if final_response:
            print(final_response)
        sys.exit(0)
    except ConversationLimitException as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    except TeleportError as e:
        print(f"Teleport error: {e}", file=sys.stderr)
        sys.exit(1)
    except (RuntimeError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _maybe_run_startup_update_prompt(
    config: VibeConfig, repository: UpdateCacheRepository
) -> None:
    if not config.enable_update_checks:
        return

    try:
        latest_version = asyncio.run(
            get_pending_update_from_cache(repository, __version__)
        )
    except OSError as exc:
        logger.debug("Failed to read pending update from cache", exc_info=exc)
        return

    if latest_version is None:
        return

    result = ask_update_prompt(__version__, latest_version, theme=config.theme)

    match result:
        case UpdatePromptResult.CONTINUE:
            try:
                asyncio.run(mark_update_as_dismissed(repository, latest_version))
            except OSError as exc:
                logger.debug("Failed to persist dismissed update", exc_info=exc)
            return
        case UpdatePromptResult.QUIT:
            sys.exit(0)
        case UpdatePromptResult.UPDATED:
            rprint(
                f"[green]✔ Vibe was updated from {__version__} to "
                f"{latest_version}.[/]\n  Run [bold]vibe[/] to start using the "
                "new version."
            )
            sys.exit(0)
        case UpdatePromptResult.UPDATE_FAILED:
            rprint("[red]✗ Vibe could not be updated automatically.[/]")
            sys.exit(1)


def run_cli(args: argparse.Namespace) -> None:
    load_dotenv_values()
    bootstrap_config_files()

    if args.setup:
        run_onboarding(entrypoint_metadata=_build_cli_entrypoint_metadata())
        sys.exit(0)

    try:
        is_interactive = args.prompt is None
        config = load_config_or_exit(interactive=is_interactive)
        update_cache_repository = FileSystemUpdateCacheRepository()

        if is_interactive:
            _maybe_run_startup_update_prompt(config, update_cache_repository)

        initial_agent_name = get_initial_agent_name(args, config)
        hook_config_result = load_hooks_from_fs(config)
        setup_tracing(config)

        if args.enabled_tools:
            config.enabled_tools = args.enabled_tools

        loaded_session = load_session(args, config)

        stdin_prompt = get_prompt_from_stdin()
        if is_interactive:
            try:
                agent_loop = AgentLoop(
                    config,
                    agent_name=initial_agent_name,
                    enable_streaming=True,
                    entrypoint_metadata=_build_cli_entrypoint_metadata(),
                    defer_heavy_init=True,
                    hook_config_result=hook_config_result,
                )
            except ValueError as e:
                rprint(f"[red]Error:[/] {e}")
                sys.exit(1)

            if loaded_session:
                prompt_recalculated = _resume_previous_session(
                    agent_loop, *loaded_session
                )
            else:
                prompt_recalculated = False

            if args.web:
                _run_interactive_mode_with_web(args, agent_loop, stdin_prompt)
                return

            run_textual_ui(
                agent_loop=agent_loop,
                update_cache_repository=update_cache_repository,
                startup=StartupOptions(
                    initial_prompt=args.initial_prompt or stdin_prompt,
                    teleport_on_start=args.teleport,
                    show_resume_picker=args.resume is True,
                    is_resuming_session=loaded_session is not None,
                    system_prompt_recalculated=prompt_recalculated,
                ),
            )
        else:
            _run_programmatic_mode(
                args=args,
                config=config,
                initial_agent_name=initial_agent_name,
                hook_config_result=hook_config_result,
                loaded_session=loaded_session,
                stdin_prompt=stdin_prompt,
            )

    except (KeyboardInterrupt, EOFError):
        rprint("\n[dim]Bye![/]")
        sys.exit(0)
