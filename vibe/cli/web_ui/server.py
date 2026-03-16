"""FastAPI web server for Mistral Vibe."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, HTTPException, Security, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

if TYPE_CHECKING:
    from vibe.core.agent_loop import AgentLoop
    from vibe.core.types import BaseEvent
    from vibe.cli.textual_ui.app import VibeApp


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
                data['args'] = event.args.model_dump(mode="json", exclude_none=True)
            except Exception:
                data['args'] = str(event.args)
    
    # Handle ToolResultEvent serialization
    elif isinstance(event, ToolResultEvent):
        # Serialize result if present
        if event.result is not None:
            try:
                data['result'] = event.result.model_dump(mode="json", exclude_none=True)
            except Exception:
                data['result'] = str(event.result)
    
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


def _create_pydantic_model_from_dict(data: dict) -> Any:
    """Create a Pydantic model from a dictionary with extra fields allowed.

    Args:
        data: Dictionary to convert to a Pydantic model.

    Returns:
        A Pydantic model instance with the data.
    """
    from pydantic import BaseModel

    class DynamicModel(BaseModel):
        model_config = {"extra": "allow"}

    return DynamicModel(**data)


def messages_to_events(messages, tool_manager) -> list[BaseEvent]:
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
        UserMessageEvent,
        AssistantEvent,
        ReasoningEvent,
        ToolCallEvent,
        ToolResultEvent,
        Role,
    )

    events: list[BaseEvent] = []

    # Build a map of tool_call_id -> tool_name from assistant messages
    tool_call_to_name: dict[str, str] = {}
    for msg in messages:
        if msg.role == Role.assistant and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.id:
                    tool_call_to_name[tc.id] = tc.function.name

    for msg in messages:
        # Skip system messages
        if msg.role == Role.system:
            continue

        # User messages
        if msg.role == Role.user:
            user_content = msg.content if isinstance(msg.content, str) else ""
            events.append(
                UserMessageEvent(
                    content=user_content,
                    message_id=msg.message_id or "",
                )
            )

        # Assistant messages
        elif msg.role == Role.assistant:
            # Add reasoning content if present
            if msg.reasoning_content:
                reasoning_content = msg.reasoning_content if isinstance(msg.reasoning_content, str) else ""
                events.append(
                    ReasoningEvent(
                        content=reasoning_content,
                        message_id=msg.message_id,
                    )
                )

            # Add assistant content if present
            if msg.content and isinstance(msg.content, str):
                events.append(
                    AssistantEvent(
                        content=msg.content,
                        message_id=msg.message_id,
                    )
                )

            # Add tool call events if present
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    tool_class = None

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
                            args_model = _create_pydantic_model_from_dict(args_dict)
                        except (json.JSONDecodeError, ValueError):
                            pass
                    elif isinstance(args, dict):
                        args_model = _create_pydantic_model_from_dict(args)

                    # Send tool call event with args if available
                    events.append(
                        ToolCallEvent(
                            tool_call_id=tc.id or "",
                            tool_name=tool_name,
                            tool_class=tool_class if tool_class else type(tool_manager),
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

            try:
                result_obj = json.loads(msg.content or "{}")
            except (json.JSONDecodeError, ValueError):
                # Fall back to text format parsing
                for line in (msg.content or "").strip().split("\n"):
                    if ": " in line:
                        key, value = line.split(": ", 1)
                        if result_obj is None:
                            result_obj = {}
                        result_obj[key.strip()] = value.strip()

            # Create a result model if we have result data
            result_model: Any = None
            if result_obj:
                result_model = _create_pydantic_model_from_dict(result_obj)

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


def create_app(
    port: int = 9092,
    token: str | None = None,
    agent_loop: AgentLoop | None = None,
    tui_app: "VibeApp | None" = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        port: Port to run the server on (default: 9092).
        token: Authentication token, or None to use VIBE_WEB_TOKEN env var.
        agent_loop: The AgentLoop instance to sync with.
        tui_app: The TUI app instance to submit messages to.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(title="Mistral Vibe Web UI", version="1.0.0")
    app.state.port = port

    # Setup templates and static files
    base_dir = Path(__file__).parent
    templates = Jinja2Templates(directory=base_dir / "templates")
    app.mount("/static", StaticFiles(directory=base_dir / "static"), name="static")

    # Get token for authentication
    auth_token = None
    try:
        auth_token = get_token_from_env_or_arg(token)
        app.state.auth_token = auth_token
    except ValueError:
        # No token set, skip authentication
        pass

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
        if hasattr(agent_loop, '_event_listeners'):
            agent_loop._event_listeners.append(event_listener)

    @app.get("/", response_class=HTMLResponse)
    def index():
        """Serve the main chat interface."""
        return templates.TemplateResponse("index.html", {"request": {}})

    security = HTTPBearer(auto_error=False)

    async def verify_token(
        credentials: HTTPAuthorizationCredentials | None = Security(security),
    ) -> str:
        """Verify the Bearer token."""
        if auth_token is None:
            return ""
        if credentials is None:
            raise HTTPException(status_code=401, detail="Missing authentication token")
        if credentials.credentials != auth_token:
            raise HTTPException(status_code=401, detail="Invalid authentication token")
        return credentials.credentials

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
            Agent status including whether it's running.
        """
        tui_app = getattr(app.state, "tui_app", None)
        if tui_app is None:
            return JSONResponse({"running": False})

        running = tui_app.is_agent_running()
        return JSONResponse({"running": running})

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

    @app.websocket("/ws")
    async def websocket_endpoint(
        websocket: WebSocket,
    ) -> None:
        """WebSocket endpoint for real-time communication.

        Args:
            websocket: The WebSocket connection.
        """
        # Get query parameters
        query_params = dict(websocket.query_params)
        token_param = query_params.get("token")

        # Get token from environment if not in query
        if token_param is None:
            token_param = os.environ.get("VIBE_WEB_TOKEN")

        # Authenticate
        if auth_token and token_param != auth_token:
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

        try:
            while True:
                # Receive messages from client
                data = await websocket.receive_text()
                message = json.loads(data)

                # Handle user messages
                if message.get("type") == "user_message":
                    content = message.get("content", "")
                    if content and hasattr(app.state, "tui_app") and app.state.tui_app:
                        # Submit message to TUI
                        app.state.tui_app.submit_message_from_web(content)
                
                # Handle approval responses
                elif message.get("type") == "approval_response":
                    popup_id = message.get("popup_id")
                    response = message.get("response")
                    feedback = message.get("feedback")
                    if (
                        popup_id
                        and response
                        and hasattr(app.state, "tui_app")
                        and app.state.tui_app
                    ):
                        from vibe.core.types import ApprovalResponse
                        
                        approval_resp = ApprovalResponse(response)
                        app.state.tui_app.handle_web_approval_response(
                            popup_id, approval_resp, feedback
                        )
                
                # Handle question responses
                elif message.get("type") == "question_response":
                    popup_id = message.get("popup_id")
                    answers_data = message.get("answers", [])
                    cancelled = message.get("cancelled", False)
                    if (
                        popup_id
                        and hasattr(app.state, "tui_app")
                        and app.state.tui_app
                    ):
                        from vibe.core.tools.builtins.ask_user_question import Answer
                        
                        answers = [Answer(**a) for a in answers_data]
                        app.state.tui_app.handle_web_question_response(
                            popup_id, answers, cancelled
                        )
        except WebSocketDisconnect:
            app.state.websocket_clients.discard(websocket)
        except Exception:
            app.state.websocket_clients.discard(websocket)

    return app
