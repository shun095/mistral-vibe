"""FastAPI web server for Mistral Vibe."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any, cast

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Security,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

if TYPE_CHECKING:
    from vibe.core.agent_loop import AgentLoop
    from vibe.core.tools.base import BaseTool
    from vibe.core.types import BaseEvent, LLMMessage

from vibe.core.session.session_loader import SessionLoader


def get_token_from_env_or_arg(token: str | None) -> str:
    """Get authentication token from argument or environment variable.

    Args:
        token: Token passed as argument, or None to use env var.

    Returns:
        The authentication token.

    Raises:
        ValueError: If no token is provided.
    """
    if token:
        return token
    env_token = os.environ.get("VIBE_WEB_TOKEN")
    if env_token:
        return env_token
    raise ValueError("No token provided. Set VIBE_WEB_TOKEN environment variable.")


def serialize_event(event: BaseEvent) -> dict:
    """Serialize an event to a dictionary for JSON transmission.

    Args:
        event: The event to serialize.

    Returns:
        Dictionary representation of the event.
    """
    from vibe.core.types import ToolCallEvent, ToolResultEvent

    # Determine which fields to exclude (tool_class can't be serialized)
    exclude_fields: set[str] = set()
    if isinstance(event, (ToolCallEvent, ToolResultEvent)):
        exclude_fields.add("tool_class")

    # Get event data without private attributes
    if exclude_fields:
        data = event.model_dump(mode="json", exclude_none=True, exclude=exclude_fields)
    else:
        data = event.model_dump(mode="json", exclude_none=True)

    # Handle ToolCallEvent args serialization
    if isinstance(event, ToolCallEvent):
        if event.args is not None:
            try:
                data["args"] = cast(BaseModel, event.args).model_dump(
                    mode="json", exclude_none=True
                )
            except Exception:
                data["args"] = str(event.args)

    # Handle ToolResultEvent serialization
    elif isinstance(event, ToolResultEvent):
        # Serialize result if present
        if event.result is not None:
            try:
                data["result"] = cast(BaseModel, event.result).model_dump(
                    mode="json", exclude_none=True
                )
            except Exception:
                data["result"] = str(event.result)

    # Add event type for client-side deserialization
    data["__type"] = event.__class__.__name__
    return data


async def broadcast_to_clients(app: FastAPI, message: str) -> None:
    """Broadcast a message to all connected WebSocket clients.

    Args:
        app: The FastAPI app instance.
        message: The JSON message to broadcast.
    """
    clients = getattr(app.state, "websocket_clients", set())
    for websocket in list(clients):
        try:
            await websocket.send_text(message)
        except Exception:
            # Client disconnected, remove from set
            clients.discard(websocket)


def _create_pydantic_model_from_dict(data: dict, tool_name: str | None = None) -> Any:
    """Create a Pydantic model from a dictionary with extra fields allowed.

    For known tools with proper result models, use the actual model class.
    Otherwise, fall back to a dynamic model.

    Args:
        data: Dictionary to convert to a Pydantic model.
        tool_name: Optional tool name to use the proper result model.

    Returns:
        A Pydantic model instance with the data.
    """
    from pydantic import BaseModel

    # Try to use the proper result model for known tools
    if tool_name == "ask_user_question":
        from vibe.core.tools.builtins.ask_user_question import AskUserQuestionResult

        return AskUserQuestionResult.model_validate(data)

    # Fall back to dynamic model for unknown tools
    class DynamicModel(BaseModel):
        model_config = {"extra": "allow"}

    return DynamicModel(**data)


# Multi-line fields: text blobs that span multiple lines
# All other fields are treated as single-line by default
def _parse_tool_output(
    content: str, tool_name: str | None = None, tool_manager: Any = None
) -> dict:
    """Parse tool output text into a dictionary, handling multi-line values.

    Tool output format is typically:
        key1: value1
        key2: value2 (may span multiple lines)

    Only keys that exist in the tool's Result model are recognized as field
    delimiters. All other lines are treated as value continuations. This
    prevents false positives when field values contain lines like "file: ...".

    Args:
        content: The tool output text to parse.
        tool_name: Optional tool name to look up Result model fields.
        tool_manager: Optional ToolManager to look up the tool class.

    Returns:
        Dictionary with parsed key-value pairs.
    """
    result: dict = {}

    # Get known field names from tool's Result model if available
    known_fields: set[str] | None = None
    if tool_name and tool_manager:
        try:
            tool_instance = tool_manager.get(tool_name)
            tool_class = type(tool_instance)
            _, result_class = tool_class._get_tool_args_results()
            if hasattr(result_class, "model_fields"):
                known_fields = set(result_class.model_fields.keys())
        except Exception:
            pass

    lines = content.strip().split("\n")
    current_key: str | None = None
    current_value_lines: list[str] = []

    for line in lines:
        # Check if this line starts a new key-value pair
        # A new key must:
        # 1. Not start with whitespace
        # 2. Contain ": "
        # 3. Have a known field name before the ": "
        if (
            line
            and not line.startswith(" ")
            and not line.startswith("\t")
            and ": " in line
        ):
            # Extract potential key
            colon_idx = line.index(": ")
            potential_key = line[:colon_idx].strip()

            # Only treat as new key if it's a known field from Result model
            if known_fields is not None and potential_key in known_fields:
                # Save previous key-value pair if exists
                if current_key is not None:
                    result[current_key] = "\n".join(current_value_lines).strip()

                # Start new key-value pair
                current_key = potential_key
                value_start = line[colon_idx + 2 :]
                current_value_lines = [value_start] if value_start else []
            elif current_key is not None:
                # Not a known key, append to current value (multi-line continuation)
                current_value_lines.append(line)
        elif current_key is not None:
            # Continuation line (starts with whitespace or no ": ")
            current_value_lines.append(line)

    # Save last key-value pair
    if current_key is not None:
        result[current_key] = "\n".join(current_value_lines).strip()

    return result


def messages_to_events(  # noqa: PLR0912, PLR0915
    messages: list[LLMMessage], tool_manager: Any
) -> list[BaseEvent]:
    """Convert a list of LLMMessage objects to equivalent BaseEvent objects.

    This function iterates through the message history and generates the
    corresponding events that would have been emitted during normal processing.

    Args:
        messages: List of LLMMessage objects from agent_loop.messages.
        tool_manager: The ToolManager to look up tool classes.

    Returns:
        List of BaseEvent objects in chronological order.
    """
    from vibe.core.types import (
        AssistantEvent,
        ContinueableUserMessageEvent,
        ReasoningEvent,
        Role,
        ToolCallEvent,
        ToolResultEvent,
        UserMessageEvent,
    )

    events: list[BaseEvent] = []

    # Build a map of tool_call_id -> tool_name from assistant messages
    tool_call_to_name: dict[str, str] = {}
    for msg in messages:
        if msg.role == Role.assistant and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.id and tc.function.name:
                    tool_call_to_name[tc.id] = tc.function.name

    for msg in messages:  # noqa: PLR1702
        # Skip system messages
        if msg.role == Role.system:
            continue

        # User messages
        if msg.role == Role.user:
            # Preserve list content (e.g., for images) or use string content
            user_content = msg.content if msg.content else ""

            # Messages with tool_call_id are ContinueableUserMessageEvent (e.g., from read_image tool)
            if msg.tool_call_id:
                events.append(
                    ContinueableUserMessageEvent(
                        content=user_content, message_id=msg.message_id
                    )
                )
            else:
                events.append(
                    UserMessageEvent(
                        content=user_content, message_id=msg.message_id or ""
                    )
                )

        # Assistant messages
        elif msg.role == Role.assistant:
            # Add reasoning content if present
            if msg.reasoning_content:
                reasoning_content = (
                    msg.reasoning_content
                    if isinstance(msg.reasoning_content, str)
                    else ""
                )
                if msg.message_id:
                    events.append(
                        ReasoningEvent(
                            content=reasoning_content, message_id=msg.message_id
                        )
                    )

            # Add assistant content if present
            if msg.content and isinstance(msg.content, str):
                if msg.message_id:
                    events.append(
                        AssistantEvent(content=msg.content, message_id=msg.message_id)
                    )

            # Add tool call events if present
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    if not tool_name:
                        continue
                    tool_class: type[BaseTool] | None = None

                    # Look up the tool class from tool_manager
                    try:
                        tool_instance = tool_manager.get(tool_name)
                        tool_class = type(tool_instance)
                    except Exception:
                        pass

                    # Parse arguments if they're a string
                    args = tc.function.arguments
                    args_model: Any = None
                    if isinstance(args, str):
                        try:
                            args_dict = json.loads(args)
                            args_model = _create_pydantic_model_from_dict(
                                args_dict, tool_name
                            )
                        except (json.JSONDecodeError, ValueError):
                            pass
                    elif isinstance(args, dict):
                        args_model = _create_pydantic_model_from_dict(args, tool_name)

                    # Send tool call event with args if available
                    if tool_class is None:
                        try:
                            tool_class = type(tool_manager.get("bash"))
                        except Exception:
                            # Fallback: use the first available tool class
                            try:
                                first_tool = next(
                                    iter(tool_manager._available.values())
                                )
                                tool_class = first_tool
                            except StopIteration:
                                pass  # No tools available, will fail below

                    if tool_class is not None:
                        events.append(
                            ToolCallEvent(
                                tool_call_id=tc.id or "",
                                tool_name=tool_name,
                                tool_class=tool_class,
                                args=args_model,
                                tool_call_index=tc.index,
                            )
                        )

        # Tool messages (results)
        elif msg.role == Role.tool and msg.tool_call_id:
            # Get the tool name from the map
            tool_name = tool_call_to_name.get(msg.tool_call_id, "")

            # Parse the result content
            result_obj: dict | None = None

            # Convert content to string for json.loads
            content_str = msg.content if isinstance(msg.content, str) else "{}"
            try:
                # Try JSON first (new format)
                result_obj = json.loads(content_str)
            except (json.JSONDecodeError, ValueError):
                # Fall back to text format parsing with multi-line value support (legacy format)
                # Pass tool_name and tool_manager for dynamic field detection
                result_obj = _parse_tool_output(
                    content_str, tool_name=tool_name, tool_manager=tool_manager
                )

            # Create a result model if we have result data
            result_model: Any = None
            if result_obj:
                result_model = _create_pydantic_model_from_dict(result_obj, tool_name)

            if msg.tool_call_id:
                events.append(
                    ToolResultEvent(
                        tool_name=tool_name,
                        tool_class=None,
                        result=result_model,
                        error=None,
                        skipped=False,
                        tool_call_id=msg.tool_call_id,
                    )
                )

    return events


def create_app(  # noqa: PLR0915
    port: int = 9092,
    token: str | None = None,
    agent_loop: AgentLoop | None = None,
    tui_app: Any | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        port: Port to run the server on (default: 9092).
        token: Authentication token, or None to use VIBE_WEB_TOKEN env var.
        agent_loop: The AgentLoop instance to sync with (required for standalone mode).
        tui_app: Optional TUI app instance for integrated mode. If None, WebUI runs
            in standalone mode and interacts directly with agent_loop.

    Returns:
        Configured FastAPI application instance.

    Raises:
        ValueError: If neither agent_loop nor tui_app is provided.
    """
    app = FastAPI(title="Mistral Vibe Web UI", version="1.0.0")
    app.state.port = port

    # Setup templates and static files
    base_dir = Path(__file__).parent
    templates = Jinja2Templates(directory=base_dir / "templates")
    app.mount("/static", StaticFiles(directory=base_dir / "static"), name="static")

    # Get token for authentication - mandatory for security
    try:
        auth_token = get_token_from_env_or_arg(token)
        app.state.auth_token = auth_token
    except ValueError as e:
        # Log error and exit - authentication is mandatory
        logging.error("WebUI authentication is required. %s", str(e))
        logging.error(
            "Set the VIBE_WEB_TOKEN environment variable or pass the 'token' argument."
        )
        raise SystemExit(1) from e

    # Track connected WebSocket clients
    app.state.websocket_clients = set()  # type: ignore

    # Store agent loop and TUI app references
    app.state.agent_loop = agent_loop
    app.state.tui_app = tui_app

    # Set up event listener if agent_loop is provided
    if agent_loop is not None:

        def event_listener(event: BaseEvent) -> None:
            """Broadcast events to all connected WebSocket clients."""
            try:
                serialized = serialize_event(event)
                message = json.dumps({"type": "event", "event": serialized})
                # Schedule broadcast to all clients
                asyncio.create_task(broadcast_to_clients(app, message))
            except Exception:
                pass

        # Add event listener to agent loop
        agent_loop.add_event_listener(event_listener)

    security = HTTPBearer(auto_error=False)

    async def verify_token(
        credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: B008
    ) -> str:
        """Verify the Bearer token."""
        if credentials is None:
            raise HTTPException(status_code=401, detail="Missing authentication token")
        if credentials.credentials != auth_token:
            raise HTTPException(status_code=401, detail="Invalid authentication token")
        return credentials.credentials

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request) -> HTMLResponse:
        """Serve the login page."""
        return templates.TemplateResponse(request, "login.html")

    @app.post("/api/login")
    def login(token_data: dict) -> JSONResponse:
        """Handle login request and set authentication cookie."""
        token = token_data.get("token", "")

        if token != auth_token:
            return JSONResponse(
                {"success": False, "error": "Invalid token"}, status_code=401
            )

        # Set authentication cookie (httpOnly, secure in production)
        response = JSONResponse({"success": True})
        response.set_cookie(
            key="vibe_auth",
            value=token,
            httponly=True,
            max_age=86400,  # 24 hours
            samesite="lax",
        )
        return response

    @app.post("/api/logout")
    def logout() -> JSONResponse:
        """Handle logout request and clear authentication cookie."""
        response = JSONResponse({"success": True})
        response.delete_cookie(key="vibe_auth")
        return response

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        """Serve the main chat interface."""
        # Check authentication via cookie
        auth_cookie = request.cookies.get("vibe_auth")
        if auth_cookie == auth_token:
            return templates.TemplateResponse(request, "index.html")

        # URL token auth is for testing/E2E only, disabled in production by default
        # WARNING: Never enable in production - tokens in URLs can be logged, cached, or leaked
        allow_url_token = (
            os.environ.get("VIBE_ALLOW_URL_TOKEN", "false").lower() == "true"
        )
        if allow_url_token:
            token_param = request.query_params.get("token")
            if token_param == auth_token:
                return templates.TemplateResponse(request, "index.html")

        # Redirect to login page if no valid authentication
        raise HTTPException(status_code=307, headers={"Location": "/login"})

    @app.get("/health")
    def health() -> JSONResponse:
        return JSONResponse({"status": "healthy"})

    @app.get("/api/stats")
    def get_stats(token: str = Security(verify_token)) -> JSONResponse:
        return JSONResponse({"stats": {}})

    @app.get("/api/status")
    def get_status(token: str = Security(verify_token)) -> JSONResponse:
        """Get the current agent status.

        Args:
            token: Authentication token.

        Returns:
            Agent status including whether it's running and context token usage.
        """
        # Try TUI first (integrated mode)
        tui_app = getattr(app.state, "tui_app", None)
        if tui_app is not None:
            running = tui_app.is_agent_running()
            agent_loop = getattr(tui_app, "agent_loop", None)
            if agent_loop is not None:
                return JSONResponse({
                    "running": running,
                    "context_tokens": agent_loop.stats.context_tokens,
                    "max_tokens": agent_loop.config.get_active_model().auto_compact_threshold,
                })
            # TUI exists but no agent_loop, return with zero tokens
            return JSONResponse({
                "running": running,
                "context_tokens": 0,
                "max_tokens": 0,
            })

        # Fall back to agent_loop (standalone mode)
        agent_loop = getattr(app.state, "agent_loop", None)
        if agent_loop is not None:
            # Check if agent_loop has a running flag or task
            running = getattr(agent_loop, "_agent_running", False)
            return JSONResponse({
                "running": running,
                "context_tokens": agent_loop.stats.context_tokens,
                "max_tokens": agent_loop.config.get_active_model().auto_compact_threshold,
            })

        # No agent_loop available, return with zero tokens
        return JSONResponse({"running": False, "context_tokens": 0, "max_tokens": 0})

    @app.post("/api/interrupt")
    def interrupt_agent(token: str = Security(verify_token)) -> JSONResponse:
        """Request an interrupt of the current agent operation.

        Args:
            token: Authentication token.

        Returns:
            Status of the interrupt request.
        """
        tui_app = getattr(app.state, "tui_app", None)
        if tui_app is None:
            return JSONResponse({"success": False, "error": "No TUI app available"})

        tui_app.request_interrupt_from_web()
        return JSONResponse({"success": True})

    @app.get("/api/commands")
    def list_commands(token: str = Security(verify_token)) -> JSONResponse:
        """List available slash commands.

        Args:
            token: Authentication token.

        Returns:
            List of commands with descriptions and aliases.
        """
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

    @app.post("/api/command/execute")
    async def execute_command(
        command_data: dict, token: str = Security(verify_token)
    ) -> JSONResponse:
        """Execute a slash command via the TUI app.

        Args:
            command_data: Command name and arguments.
            token: Authentication token.

        Returns:
            Execution result.
        """
        tui_app = getattr(app.state, "tui_app", None)
        if tui_app is None:
            return JSONResponse({"success": False, "error": "No TUI app available"})

        command_name = command_data.get("command", "")
        command_args = command_data.get("args", "")

        # Submit to TUI for processing - it will handle slash commands properly
        command_text = f"/{command_name}"
        if command_args:
            command_text = f"{command_text} {command_args}"

        tui_app.submit_message_from_web(command_text)
        return JSONResponse({"success": True})

    @app.get("/api/sessions")
    def list_sessions(token: str = Security(verify_token)) -> JSONResponse:
        """List available sessions for resuming.

        Args:
            token: Authentication token.

        Returns:
            List of sessions with metadata.
        """
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

    @app.post("/api/sessions/{session_id}/resume")
    async def resume_session(
        session_id: str, token: str = Security(verify_token)
    ) -> JSONResponse:
        """Resume a specific session by submitting to TUI for processing.

        Args:
            session_id: The session ID to resume.
            token: Authentication token.

        Returns:
            Success status. TUI will broadcast MessageResetEvent when complete.
        """
        tui_app = getattr(app.state, "tui_app", None)
        if tui_app is None:
            return JSONResponse({"success": False, "error": "No TUI app available"})

        try:
            session_config = tui_app.config.session_logging
            session_path = SessionLoader.find_session_by_id(session_id, session_config)

            if not session_path:
                return JSONResponse({
                    "success": False,
                    "error": f"Session {session_id[:8]} not found",
                })

            # Submit to TUI for processing - it will handle the resume and broadcast events
            tui_app.submit_message_from_web(f"/resume {session_id}")
            return JSONResponse({"success": True, "session_id": session_id})
        except ValueError as e:
            return JSONResponse({"success": False, "error": str(e)})
        except Exception as e:
            logging.warning("Error resuming session: %s", e)
            return JSONResponse({"success": False, "error": str(e)})

    @app.get("/api/messages")
    def get_messages(token: str = Security(verify_token)) -> JSONResponse:
        """Get current message history as events.

        Args:
            token: Authentication token.

        Returns:
            List of events representing the message history.
        """
        agent_loop = getattr(app.state, "agent_loop", None)
        if agent_loop is None:
            return JSONResponse({"events": []})

        try:
            events = messages_to_events(agent_loop.messages, agent_loop.tool_manager)
            serialized_events = [serialize_event(event) for event in events]
            return JSONResponse({"events": serialized_events})
        except Exception as e:
            logging.warning("Error converting messages to events: %s", e)
            return JSONResponse({"events": []})

    @app.websocket("/ws")
    async def websocket_endpoint(  # noqa: PLR0914, PLR0912, PLR0915
        websocket: WebSocket,
    ) -> None:
        """WebSocket endpoint for real-time communication.

        Args:
            websocket: The WebSocket connection.
        """
        # Get query parameters
        query_params = dict(websocket.query_params)
        token_param = query_params.get("token")

        # Authenticate - token is mandatory
        if token_param is None or token_param != auth_token:
            await websocket.close(code=401, reason="Invalid or missing token")
            return

        await websocket.accept()
        app.state.websocket_clients.add(websocket)

        # Stream historical events from agent_loop before sending connected message
        agent_loop = getattr(app.state, "agent_loop", None)
        if agent_loop is not None:
            try:
                # Convert messages to events
                historical_events = messages_to_events(
                    agent_loop.messages, agent_loop.tool_manager
                )

                # Stream each event to the client
                for event in historical_events:
                    serialized = serialize_event(event)
                    message = json.dumps({"type": "event", "event": serialized})
                    await websocket.send_text(message)
            except (json.JSONDecodeError, TypeError, AttributeError) as e:
                # Log specific errors but continue anyway
                logging.debug("Error streaming history: %s", e)
            except Exception as e:
                # Catch any unexpected errors but don't fail the connection
                logging.warning("Unexpected error streaming history: %s", e)

        # Send connected message after history is streamed
        await websocket.send_json({"type": "connected"})

        # Re-emit pending popups if any
        tui_app = getattr(app.state, "tui_app", None)
        if tui_app:
            # Re-emit pending approval popup
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

            # Re-emit pending question popup
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
                # Receive messages from client
                data = await websocket.receive_text()
                message = json.loads(data)

                # Handle user messages
                if message.get("type") == "user_message":
                    content = message.get("content", "")
                    image_data = message.get("image")
                    if (
                        (content or image_data)
                        and hasattr(app.state, "tui_app")
                        and app.state.tui_app
                    ):
                        # Submit message to TUI
                        app.state.tui_app.submit_message_from_web(content, image_data)

                # Handle approval responses
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

                # Handle question responses
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

    # Test mode endpoints - only available when VIBE_E2E_TEST is set
    if os.environ.get("VIBE_E2E_TEST") == "true":

        @app.post("/api/test/mock-data")
        def register_mock_data(
            mock_data: dict, token: str = Security(verify_token)
        ) -> JSONResponse:
            """Register mock data for E2E tests.

            Args:
                mock_data: Mock response data with fields:
                    - response_text: str - The response text to return
                    - tool_calls: list[dict] - Optional list of tool calls
                    - usage: dict - Optional token usage data
                token: Authentication token.

            Returns:
                Confirmation of registration.
            """
            from vibe.core.llm.backend.mock import get_mock_store
            from vibe.core.types import LLMUsage

            store = get_mock_store()
            response_text = mock_data.get("response_text", "Default mock response")

            # Parse tool calls if provided
            tool_calls = mock_data.get("tool_calls")

            # Parse usage if provided
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

        @app.post("/api/test/mock-data/reset")
        def reset_mock_data(token: str = Security(verify_token)) -> JSONResponse:
            """Reset the mock data store.

            Args:
                token: Authentication token.

            Returns:
                Confirmation of reset.
            """
            from vibe.core.llm.backend.mock import reset_mock_store

            reset_mock_store()
            return JSONResponse({"success": True, "message": "Mock data reset"})

        @app.get("/api/test/mock-data/usage")
        def get_mock_data_usage(token: str = Security(verify_token)) -> JSONResponse:
            """Get mock data store usage statistics.

            Args:
                token: Authentication token.

            Returns:
                Usage statistics.
            """
            from vibe.core.llm.backend.mock import get_mock_store

            store = get_mock_store()
            usage = store.get_usage()
            return JSONResponse({"usage": usage})

    return app
