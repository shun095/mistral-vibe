"""FastAPI route definitions for WebUI."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import queue
import re
import time
from typing import TYPE_CHECKING, Any
import uuid

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from vibe.cli.history_manager import HistoryManager
from vibe.cli.textual_ui.widgets.mcp_app import collect_mcp_tool_index
from vibe.cli.web_ui.config import AUTH_COOKIE_NAME
from vibe.cli.web_ui.serializers import (
    MAX_HISTORY_ENTRIES,
    _load_prompt_history,
    messages_to_events,
    serialize_event,
)
from vibe.core.config import VibeConfig
from vibe.core.paths import HISTORY_FILE
from vibe.core.session.session_loader import SessionLoader
from vibe.core.tools.mcp_settings import persist_mcp_toggle
from vibe.core.utils.mime import get_mime_type

if TYPE_CHECKING:
    from vibe.core.types import BaseEvent


def register_routes(  # noqa: PLR0915
    app: FastAPI,
    auth_token: str,
    templates: Jinja2Templates,
    agent_loop: Any | None = None,
    base_path: str = "/",
) -> None:
    """Register all WebUI routes on the FastAPI app."""
    prefix = base_path.rstrip("/") if base_path != "/" else ""

    def event_listener(event: BaseEvent) -> None:
        """Enqueue event for broadcast on Uvicorn's event loop."""
        try:
            serialized = serialize_event(event)
            message = json.dumps({"type": "event", "event": serialized})
            app.state._broadcast_queue.put_nowait(message)
        except queue.Full:
            pass
        except Exception:
            pass

    if agent_loop is not None:
        agent_loop.add_event_listener(event_listener)

    # Auth
    async def verify_request_auth(request: Request) -> None:
        auth_cookie = request.cookies.get(AUTH_COOKIE_NAME)
        if auth_cookie != auth_token:
            raise HTTPException(
                status_code=401, detail="Invalid or missing authentication cookie"
            )

    async def verify_websocket_auth(websocket: WebSocket) -> None:
        auth_cookie = websocket.cookies.get(AUTH_COOKIE_NAME)
        if auth_cookie != auth_token:
            await websocket.close(
                code=401, reason="Invalid or missing authentication cookie"
            )

    # Auth routes
    @app.get(f"{prefix}/login", response_class=HTMLResponse)
    def login_page(request: Request) -> HTMLResponse:
        auth_cookie = request.cookies.get(AUTH_COOKIE_NAME)
        if auth_cookie == auth_token:
            raise HTTPException(status_code=307, headers={"Location": prefix or "/"})
        return templates.TemplateResponse(
            request, "login.html", {"base_path": base_path}
        )

    @app.post(f"{prefix}/api/login")
    def login(request: Request, token_data: dict) -> JSONResponse:
        token = token_data.get("token", "")
        if token != auth_token:
            return JSONResponse(
                {"success": False, "error": "Invalid token"}, status_code=401
            )
        response = JSONResponse({"success": True})
        response.set_cookie(
            key=AUTH_COOKIE_NAME,
            value=token,
            httponly=True,
            secure=request.url.scheme == "https",
            max_age=86400,
            samesite="lax",
        )
        return response

    @app.post(f"{prefix}/api/logout")
    def logout() -> JSONResponse:
        response = JSONResponse({"success": True})
        response.delete_cookie(key=AUTH_COOKIE_NAME)
        return response

    # Static routes
    @app.get(f"{prefix}/", response_class=HTMLResponse, response_model=None)
    def index(request: Request) -> HTMLResponse | RedirectResponse:
        auth_cookie = request.cookies.get(AUTH_COOKIE_NAME)
        if auth_cookie != auth_token:
            return RedirectResponse(url=f"{prefix}/login", status_code=307)
        return templates.TemplateResponse(
            request, "index.html", {"base_path": base_path}
        )

    @app.get(f"{prefix}/health")
    def health() -> JSONResponse:
        return JSONResponse({"status": "healthy"})

    @app.get(f"{prefix}/api/stats")
    def get_stats(_request: Request = Depends(verify_request_auth)) -> JSONResponse:  # noqa: B008
        return JSONResponse({"stats": {}})

    # Agent status routes
    @app.get(f"{prefix}/api/status")
    def get_status(_request: Request = Depends(verify_request_auth)) -> JSONResponse:  # noqa: B008
        tui_app = getattr(app.state, "tui_app", None)
        if tui_app is not None:
            running = tui_app.is_agent_running()
            agent_loop_ref = getattr(tui_app, "agent_loop", None)
            if agent_loop_ref is not None:
                return JSONResponse({
                    "running": running,
                    "context_tokens": agent_loop_ref.stats.context_tokens,
                    "max_tokens": agent_loop_ref.config.get_active_model().auto_compact_threshold,
                })
            return JSONResponse({
                "running": running,
                "context_tokens": 0,
                "max_tokens": 0,
            })

        agent_loop_ref = getattr(app.state, "agent_loop", None)
        if agent_loop_ref is not None:
            running = getattr(agent_loop_ref, "_agent_running", False)
            return JSONResponse({
                "running": running,
                "context_tokens": agent_loop_ref.stats.context_tokens,
                "max_tokens": agent_loop_ref.config.get_active_model().auto_compact_threshold,
            })

        return JSONResponse({"running": False, "context_tokens": 0, "max_tokens": 0})

    @app.post(f"{prefix}/api/interrupt")
    def interrupt_agent(
        _request: Request = Depends(verify_request_auth),  # noqa: B008
    ) -> JSONResponse:
        tui_app = getattr(app.state, "tui_app", None)
        if tui_app is None:
            return JSONResponse({"success": False, "error": "No TUI app available"})
        tui_app.request_interrupt_from_web()
        return JSONResponse({"success": True})

    # Command routes
    @app.get(f"{prefix}/api/commands")
    def list_commands(_request: Request = Depends(verify_request_auth)) -> JSONResponse:  # noqa: B008
        tui_app = getattr(app.state, "tui_app", None)
        if tui_app is None:
            return JSONResponse({"commands": []})
        commands = []
        for cmd_name, cmd in tui_app.commands.commands.items():
            commands.append({
                "name": cmd_name,
                "aliases": sorted(list(cmd.aliases)),
                "description": cmd.description,
                "enabled": True,
            })
        return JSONResponse({"commands": commands})

    @app.post(f"{prefix}/api/command/execute")
    async def execute_command(
        command_data: dict,
        _request: Request = Depends(verify_request_auth),  # noqa: B008
    ) -> JSONResponse:
        tui_app = getattr(app.state, "tui_app", None)
        if tui_app is None:
            return JSONResponse({"success": False, "error": "No TUI app available"})
        command_name = command_data.get("command", "")
        command_args = command_data.get("args", "")
        command_text = f"/{command_name}"
        if command_args:
            command_text = f"{command_text} {command_args}"
        tui_app.submit_message_from_web(command_text)
        return JSONResponse({"success": True})

    @app.post(f"{prefix}/api/translate")
    async def translate_text(
        text_data: dict,
        _request: Request = Depends(verify_request_auth),  # noqa: B008
    ) -> JSONResponse:
        tui_app = getattr(app.state, "tui_app", None)
        if tui_app is None:
            return JSONResponse({"success": False, "error": "No TUI app available"})
        original_text = text_data.get("text", "").strip()
        if not original_text:
            return JSONResponse({"success": False, "error": "No text to translate"})
        try:
            translated_text = await tui_app.do_translation(original_text)
            history = HistoryManager(HISTORY_FILE.path)
            history.add(original_text)
            if translated_text:
                history.add(translated_text)
            return JSONResponse({
                "success": True,
                "translated": translated_text or "",
                "original_length": len(original_text),
                "translated_length": len(translated_text or ""),
            })
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)})

    # File download route
    @app.get(f"{prefix}/api/download")
    async def download_file(
        file_path: str,
        _request: Request = Depends(verify_request_auth),  # noqa: B008
    ) -> FileResponse:
        try:
            path = Path(file_path).expanduser()
            resolved_path = path.resolve()
            project_dir = Path.cwd().resolve()
            session_dir = None
            tui_app = getattr(app.state, "tui_app", None)
            if (
                tui_app
                and hasattr(tui_app, "agent_loop")
                and tui_app.agent_loop.session_logger
            ):
                session_dir = tui_app.agent_loop.session_logger.session_dir.resolve()
            is_allowed = False
            for allowed_dir in [project_dir, session_dir]:
                if allowed_dir is None:
                    continue
                try:
                    if resolved_path.is_relative_to(allowed_dir):
                        is_allowed = True
                        break
                except ValueError:
                    continue
            if not is_allowed:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: file path outside allowed directories",
                )
            if not resolved_path.exists():
                raise HTTPException(status_code=404, detail="File not found")
            if not resolved_path.is_file():
                raise HTTPException(status_code=400, detail="Not a file")
            mime_type = get_mime_type(resolved_path.name)
            return FileResponse(
                path=str(resolved_path),
                media_type=mime_type,
                filename=resolved_path.name,
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Session routes
    @app.get(f"{prefix}/api/sessions")
    def list_sessions(_request: Request = Depends(verify_request_auth)) -> JSONResponse:  # noqa: B008
        tui_app = getattr(app.state, "tui_app", None)
        if tui_app is None:
            return JSONResponse({"sessions": []})
        try:
            session_config = tui_app.config.session_logging
            cwd = str(Path.cwd())
            raw_sessions = SessionLoader.list_sessions(session_config, cwd=cwd)
            if not raw_sessions:
                return JSONResponse({"sessions": []})
            sessions = sorted(
                raw_sessions, key=lambda s: s.get("end_time") or "", reverse=True
            )
            latest_messages = {
                s["session_id"]: SessionLoader.get_first_user_message(
                    s["session_id"], session_config
                )
                for s in sessions
            }
            sessions_data = []
            for session in sessions:
                sessions_data.append({
                    "session_id": session["session_id"],
                    "short_id": session["session_id"][:8],
                    "title": session.get("title"),
                    "end_time": session.get("end_time"),
                    "first_message": latest_messages.get(session["session_id"], ""),
                })
            return JSONResponse({"sessions": sessions_data})
        except Exception as e:
            logging.warning("Error listing sessions: %s", e)
            return JSONResponse({"sessions": []})

    @app.post(f"{prefix}/api/sessions/{{session_id}}/resume")
    async def resume_session(
        session_id: str,
        _request: Request = Depends(verify_request_auth),  # noqa: B008
    ) -> JSONResponse:
        try:
            uuid.UUID(session_id)
        except ValueError:
            if not re.match(r"^[0-9a-fA-F]{8,64}$", session_id):
                return JSONResponse(
                    {"success": False, "error": "Invalid session ID format."},
                    status_code=400,
                )
        tui_app = getattr(app.state, "tui_app", None)
        if tui_app is None:
            return JSONResponse({"success": False, "error": "No TUI app available"})
        try:
            tui_app.resume_session_from_web(session_id)
            return JSONResponse({"success": True, "session_id": session_id})
        except Exception as e:
            logging.warning("Error resuming session: %s", e)
            return JSONResponse({"success": False, "error": str(e)})

    # History routes
    @app.get(f"{prefix}/api/messages")
    def get_messages(_request: Request = Depends(verify_request_auth)) -> JSONResponse:  # noqa: B008
        agent_loop_ref = getattr(app.state, "agent_loop", None)
        if agent_loop_ref is None:
            return JSONResponse({"events": []})
        try:
            events = messages_to_events(
                agent_loop_ref.messages, agent_loop_ref.tool_manager
            )
            serialized_events = [serialize_event(event) for event in events]
            return JSONResponse({"events": serialized_events})
        except Exception as e:
            logging.warning("Error converting messages to events: %s", e)
            return JSONResponse({"events": []})

    @app.get(f"{prefix}/api/prompt-history")
    def get_prompt_history(
        _request: Request = Depends(verify_request_auth),  # noqa: B008
    ) -> JSONResponse:
        history = _load_prompt_history(HISTORY_FILE.path)
        limited_history = history[-MAX_HISTORY_ENTRIES:][::-1]
        return JSONResponse({"entries": limited_history})

    # Model routes
    @app.get(f"{prefix}/api/models")
    def list_models(_request: Request = Depends(verify_request_auth)) -> JSONResponse:  # noqa: B008
        tui_app = getattr(app.state, "tui_app", None)
        if tui_app is None:
            return JSONResponse({"models": [], "active_model": ""})
        config = tui_app.config
        models = [
            {"alias": m.alias, "name": m.name, "provider": m.provider}
            for m in config.models
        ]
        return JSONResponse({"models": models, "active_model": config.active_model})

    @app.post(f"{prefix}/api/models/switch")
    def switch_model(
        model_data: dict,
        _request: Request = Depends(verify_request_auth),  # noqa: B008
    ) -> JSONResponse:
        tui_app = getattr(app.state, "tui_app", None)
        if tui_app is None:
            return JSONResponse({"success": False, "error": "No TUI app available"})
        alias = model_data.get("alias", "")
        if not alias:
            return JSONResponse({"success": False, "error": "No model alias provided"})
        try:
            VibeConfig.save_updates({"active_model": alias})
            tui_app.reload_config()
            return JSONResponse({"success": True, "active_model": alias})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)})

    # Config routes
    @app.get(f"{prefix}/api/config")
    def get_config(_request: Request = Depends(verify_request_auth)) -> JSONResponse:  # noqa: B008
        tui_app = getattr(app.state, "tui_app", None)
        if tui_app is None:
            return JSONResponse({"success": False, "error": "No TUI app available"})
        config = tui_app.config
        active_model = config.get_active_model()
        cs_port = getattr(app.state, "code_server_port", 0) or 0
        cs_workdir = getattr(app.state, "code_server_workdir", "") or ""
        return JSONResponse({
            "active_model": config.active_model,
            "thinking": active_model.thinking,
            "autocopy_to_clipboard": config.autocopy_to_clipboard,
            "file_watcher_for_autocomplete": config.file_watcher_for_autocomplete,
            "voice_mode_enabled": config.voice_mode_enabled,
            "narrator_enabled": config.narrator_enabled,
            "auto_approve": config.auto_approve,
            "enable_notifications": config.enable_notifications,
            "enable_web_notifications": config.enable_web_notifications,
            "loop_detection_enabled": config.loop_detection_enabled,
            "context_warnings": config.context_warnings,
            "code_server_enabled": cs_port > 0,
            "code_server_workdir": cs_workdir if cs_workdir else None,
        })

    @app.post(f"{prefix}/api/config")
    def save_config(
        config_data: dict,
        _request: Request = Depends(verify_request_auth),  # noqa: B008
    ) -> JSONResponse:
        tui_app = getattr(app.state, "tui_app", None)
        if tui_app is None:
            return JSONResponse({"success": False, "error": "No TUI app available"})
        try:
            updates: dict[str, Any] = {}
            allowed_keys = {
                "autocopy_to_clipboard",
                "file_watcher_for_autocomplete",
                "voice_mode_enabled",
                "narrator_enabled",
                "auto_approve",
                "enable_notifications",
                "enable_web_notifications",
                "loop_detection_enabled",
                "context_warnings",
            }
            for key in allowed_keys:
                if key in config_data:
                    updates[key] = config_data[key]
            if not updates:
                return JSONResponse({"success": False, "error": "No valid config keys"})
            VibeConfig.save_updates(updates)
            tui_app.reload_config()
            return JSONResponse({"success": True, "updated": list(updates.keys())})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)})

    @app.post(f"{prefix}/api/thinking/switch")
    def switch_thinking(
        thinking_data: dict,
        _request: Request = Depends(verify_request_auth),  # noqa: B008
    ) -> JSONResponse:
        tui_app = getattr(app.state, "tui_app", None)
        if tui_app is None:
            return JSONResponse({"success": False, "error": "No TUI app available"})
        level = thinking_data.get("level", "")
        if not level:
            return JSONResponse({
                "success": False,
                "error": "No thinking level provided",
            })
        try:
            tui_app.config.set_thinking(level)
            tui_app.reload_config()
            return JSONResponse({"success": True, "thinking": level})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)})

    # MCP routes
    @app.get(f"{prefix}/api/mcp")
    def list_mcp(_request: Request = Depends(verify_request_auth)) -> JSONResponse:  # noqa: B008
        tui_app = getattr(app.state, "tui_app", None)
        if tui_app is None:
            return JSONResponse({"servers": [], "connectors": []})
        try:
            config = tui_app.config
            agent_loop_ref = getattr(tui_app, "agent_loop", None)
            tool_manager = (
                getattr(agent_loop_ref, "tool_manager", None)
                if agent_loop_ref
                else None
            )

            connector_names = (
                [c.name for c in config.connectors] if config.connectors else []
            )

            index = (
                collect_mcp_tool_index(
                    config.mcp_servers, tool_manager, connector_names
                )
                if tool_manager is not None
                else None
            )

            servers = []
            for server in config.mcp_servers:
                tools = []
                if index is not None:
                    for tool_name, _tool_cls in index.server_tools.get(server.name, []):
                        enabled = tool_name in index.enabled_tools
                        tools.append({"name": tool_name, "enabled": enabled})
                servers.append({
                    "name": server.name,
                    "transport": getattr(server, "transport", "stdio"),
                    "disabled": server.disabled,
                    "tools": tools,
                    "tool_count": len(tools),
                })

            connectors = []
            for connector in config.connectors:
                tools = []
                if index is not None:
                    for tool_name, _tool_cls in index.connector_tools.get(
                        connector.name, []
                    ):
                        enabled = tool_name in index.enabled_tools
                        tools.append({"name": tool_name, "enabled": enabled})
                connectors.append({
                    "name": connector.name,
                    "disabled": connector.disabled,
                    "connected": not connector.disabled,
                    "tools": tools,
                    "tool_count": len(tools),
                })

            return JSONResponse({"servers": servers, "connectors": connectors})
        except Exception as e:
            logging.warning("Error listing MCP: %s", e)
            return JSONResponse({"servers": [], "connectors": []})

    @app.post(f"{prefix}/api/mcp/toggle")
    def toggle_mcp(
        toggle_data: dict,
        _request: Request = Depends(verify_request_auth),  # noqa: B008
    ) -> JSONResponse:
        tui_app = getattr(app.state, "tui_app", None)
        if tui_app is None:
            return JSONResponse({"success": False, "error": "No TUI app available"})
        try:
            name = toggle_data.get("name", "")
            is_connector = toggle_data.get("is_connector", False)
            disabled = toggle_data.get("disabled", False)
            tool_name = toggle_data.get("tool_name")

            if not name:
                return JSONResponse({"success": False, "error": "No name provided"})

            persist_mcp_toggle(
                tui_app.config,
                name=name,
                is_connector=is_connector,
                disabled=disabled,
                tool_name=tool_name,
            )
            agent_loop_ref = getattr(tui_app, "agent_loop", None)
            if agent_loop_ref is not None:
                agent_loop_ref.refresh_config()
            return JSONResponse({"success": True})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)})

    # Rewind routes
    @app.get(f"{prefix}/api/rewind/state")
    async def get_rewind_state(
        _request: Request = Depends(verify_request_auth),  # noqa: B008
    ) -> JSONResponse:
        tui_app = getattr(app.state, "tui_app", None)
        if tui_app is None:
            return JSONResponse({"success": False, "error": "No TUI app available"})
        try:
            result = await tui_app.get_rewind_state_info()
            if result is None:
                return JSONResponse({
                    "success": False,
                    "error": "No user messages to rewind to",
                })
            return JSONResponse(result)
        except Exception as e:
            logging.warning("Error getting rewind state: %s", e)
            return JSONResponse({"success": False, "error": str(e)})

    @app.post(f"{prefix}/api/rewind/execute")
    async def execute_rewind(
        rewind_data: dict,
        _request: Request = Depends(verify_request_auth),  # noqa: B008
    ) -> JSONResponse:
        tui_app = getattr(app.state, "tui_app", None)
        if tui_app is None:
            return JSONResponse({"success": False, "error": "No TUI app available"})
        try:
            msg_index = rewind_data.get("message_index")
            restore_files = rewind_data.get("restore_files", False)
            if msg_index is None:
                return JSONResponse({"success": False, "error": "No message index"})

            agent_loop_ref = getattr(tui_app, "agent_loop", None)
            rewind_mgr = (
                getattr(agent_loop_ref, "rewind_manager", None)
                if agent_loop_ref
                else None
            )
            if rewind_mgr is None:
                return JSONResponse({"success": False, "error": "No rewind manager"})

            content, errors = await rewind_mgr.rewind_to_message(
                msg_index, restore_files=restore_files
            )

            error_msgs = [str(e) for e in errors] if errors else []
            return JSONResponse({
                "success": True,
                "message_content": content,
                "restore_errors": error_msgs,
            })
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)})

    # WebSocket
    @app.websocket(f"{prefix}/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:  # noqa: PLR0914, PLR0912, PLR0915
        await verify_websocket_auth(websocket)
        await websocket.accept()

        agent_loop_ref = getattr(app.state, "agent_loop", None)
        if agent_loop_ref is not None:
            try:
                # Signal client to clear DOM before streaming history
                await websocket.send_json({"type": "reset"})

                historical_events = messages_to_events(
                    agent_loop_ref.messages, agent_loop_ref.tool_manager
                )
                for event in historical_events:
                    serialized = serialize_event(event)
                    message = json.dumps({"type": "event", "event": serialized})
                    await websocket.send_text(message)
            except (json.JSONDecodeError, TypeError, AttributeError) as e:
                logging.debug("Error streaming history: %s", e)
            except Exception as e:
                logging.warning("Unexpected error streaming history: %s", e)

        await websocket.send_json({"type": "connected"})

        # Add to broadcast set only after history is sent to avoid duplicates
        app.state.websocket_clients.add(websocket)

        tui_app = getattr(app.state, "tui_app", None)
        if tui_app:
            pending_approval = getattr(tui_app, "get_pending_approval_state", None)
            if pending_approval:
                approval_state = pending_approval()
                if approval_state and approval_state.popup_id:
                    from vibe.core.ui_events import ApprovalPopupEvent

                    event = ApprovalPopupEvent(
                        popup_id=approval_state.popup_id,
                        tool_name=approval_state.tool_name or "",
                        tool_args=approval_state.args or {},
                        timestamp=time.time(),
                    )
                    serialized = serialize_event(event)
                    message = json.dumps({"type": "event", "event": serialized})
                    await websocket.send_text(message)

            pending_question = getattr(tui_app, "get_pending_question_state", None)
            if pending_question:
                question_state = pending_question()
                if question_state and question_state.popup_id:
                    from vibe.core.ui_events import QuestionPopupEvent

                    event = QuestionPopupEvent(
                        popup_id=question_state.popup_id,
                        questions=question_state.args.get("questions", [])
                        if question_state.args
                        else [],
                        content_preview=None,
                        timestamp=time.time(),
                    )
                    serialized = serialize_event(event)
                    message = json.dumps({"type": "event", "event": serialized})
                    await websocket.send_text(message)

        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)

                if message.get("type") == "user_message":
                    content = message.get("content", "")
                    image_data = message.get("image")
                    if (
                        (content or image_data)
                        and hasattr(app.state, "tui_app")
                        and app.state.tui_app
                    ):
                        app.state.tui_app.submit_message_from_web(content, image_data)

                elif message.get("type") == "approval_response":
                    popup_id = message.get("popup_id")
                    response = message.get("response")
                    feedback = message.get("feedback")
                    approval_type = message.get("approval_type", "once")
                    if (
                        popup_id
                        and response
                        and hasattr(app.state, "tui_app")
                        and app.state.tui_app
                    ):
                        from vibe.core.types import ApprovalResponse

                        approval_resp = ApprovalResponse(response)
                        app.state.tui_app.handle_web_approval_response(
                            popup_id, approval_resp, feedback, approval_type
                        )

                elif message.get("type") == "question_response":
                    popup_id = message.get("popup_id")
                    answers_data = message.get("answers", [])
                    cancelled = message.get("cancelled", False)
                    if popup_id and hasattr(app.state, "tui_app") and app.state.tui_app:
                        from vibe.core.tools.builtins.ask_user_question import Answer

                        answers = [Answer(**a) for a in answers_data]
                        app.state.tui_app.handle_web_question_response(
                            popup_id, answers, cancelled
                        )
        except WebSocketDisconnect:
            app.state.websocket_clients.discard(websocket)
        except Exception:
            app.state.websocket_clients.discard(websocket)

    # E2E test mode endpoints
    if os.environ.get("VIBE_E2E_TEST") == "true":
        _register_e2e_routes(app, verify_request_auth, prefix)


def _register_e2e_routes(app: FastAPI, verify_request_auth: Any, prefix: str) -> None:
    """Register E2E test mode endpoints."""

    @app.post(f"{prefix}/api/test/mock-data")
    def register_mock_data(
        mock_data: dict,
        _request: Request = Depends(verify_request_auth),  # noqa: B008
    ) -> JSONResponse:
        from vibe.core.llm.backend.mock import get_mock_store
        from vibe.core.types import LLMUsage

        store = get_mock_store()
        response_text = mock_data.get("response_text", "Default mock response")
        tool_calls = mock_data.get("tool_calls")
        usage_data = mock_data.get("usage")
        usage = None
        if usage_data:
            usage = LLMUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
            )
        store.register_response(
            response_text=response_text, tool_calls=tool_calls, usage=usage
        )
        return JSONResponse({"success": True, "message": "Mock data registered"})

    @app.post(f"{prefix}/api/test/mock-data/reset")
    def reset_mock_data(
        _request: Request = Depends(verify_request_auth),  # noqa: B008
    ) -> JSONResponse:
        from vibe.core.llm.backend.mock import reset_mock_store

        reset_mock_store()
        return JSONResponse({"success": True, "message": "Mock data reset"})

    @app.get(f"{prefix}/api/test/mock-data/usage")
    def get_mock_data_usage(
        _request: Request = Depends(verify_request_auth),  # noqa: B008
    ) -> JSONResponse:
        from vibe.core.llm.backend.mock import get_mock_store

        store = get_mock_store()
        usage = store.get_usage()
        return JSONResponse({"usage": usage})

    @app.post(f"{prefix}/api/test/mock-events")
    async def broadcast_mock_event(
        event_data: dict,
        _request: Request = Depends(verify_request_auth),  # noqa: B008
    ) -> JSONResponse:
        clients = getattr(app.state, "websocket_clients", set())
        if not clients:
            return JSONResponse({"success": True, "message": "No connected clients"})
        message = json.dumps({"type": "event", "event": event_data})
        disconnected: list = []
        for ws in clients:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            clients.discard(ws)
        return JSONResponse({"success": True, "message": "Event broadcast"})
