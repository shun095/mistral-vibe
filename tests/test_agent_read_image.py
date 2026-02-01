"""Refactored integration tests for read_image tool using parameterization."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from tests.mock.utils import mock_llm_chunk
from tests.stubs.fake_backend import FakeBackend
from vibe.core.agent_loop import AgentLoop
from vibe.core.agents.models import BuiltinAgentName
from vibe.core.config import SessionLoggingConfig, VibeConfig
from vibe.core.tools.base import ToolPermission
from vibe.core.tools.builtins.read_image import ReadImageToolConfig
from vibe.core.types import (
    AssistantEvent,
    BaseEvent,
    ContinueableUserMessageEvent,
    FunctionCall,
    LLMMessage,
    Role,
    ToolCall,
    ToolCallEvent,
    ToolResultEvent,
    UserMessageEvent,
)


# Helper functions (same as original)
async def act_and_collect_events(agent_loop: AgentLoop, prompt: str) -> list[BaseEvent]:
    """Helper to collect all events from agent loop."""
    return [ev async for ev in agent_loop.act(prompt)]


def make_config(read_image_permission: ToolPermission = ToolPermission.ALWAYS) -> VibeConfig:
    """Create test configuration for read_image tool."""
    return VibeConfig(
        session_logging=SessionLoggingConfig(enabled=False),
        auto_compact_threshold=0,
        enabled_tools=["read_image"],
        tools={"read_image": ReadImageToolConfig(permission=read_image_permission)},
        system_prompt_id="tests",
        include_project_context=False,
        include_prompt_detail=False,
    )


def make_read_image_tool_call(
    call_id: str, index: int = 0, arguments: str | None = None
) -> ToolCall:
    """Create a mock read_image tool call."""
    args = arguments if arguments is not None else '{"image_url": "https://example.com/image.jpg"}'
    return ToolCall(
        id=call_id, index=index, function=FunctionCall(name="read_image", arguments=args)
    )


# Assertion functions for parameterized tests
def assert_http_url_events(events):
    """Assertions for HTTP URL test case."""
    # Verify tool result - HTTP URL should be returned as-is
    assert events[3].result.image_url == "https://example.com/image.jpg"
    assert events[3].result.source_type == "https"
    assert events[3].result.source_path is None
    # Verify image message contains image_url
    assert any(
        item.get("type") == "image_url"
        for item in events[5].content
        if isinstance(item, dict)
    )


def assert_file_url_events(events, tmp_path):
    """Assertions for File URL test case."""
    # Verify base64 encoding
    assert events[3].result.image_url.startswith("data:")
    assert ";base64," in events[3].result.image_url
    assert events[3].result.source_type == "file"
    assert events[3].result.source_path == str(Path(tmp_path) / "test.jpg")
    # Verify image message has base64 data
    image_url_item = next(
        (
            item
            for item in events[5].content
            if isinstance(item, dict) and item.get("type") == "image_url"
        ),
        None,
    )
    assert image_url_item is not None
    assert image_url_item["image_url"]["url"].startswith("data:")
    # Verify the base64 data matches
    data_part = image_url_item["image_url"]["url"].split(";base64,")[1]
    decoded_data = base64.b64decode(data_part)
    assert decoded_data == b"fake_image_data_1234567890"


def assert_conversation_continues(events, tmp_path):
    """Assertions for conversation continues test case."""
    # Verify we get a response to the image
    assert len(events) >= 7
    assert isinstance(events[-1], AssistantEvent)
    # The response should mention the image
    assert "beautiful landscape" in events[-1].content or "image" in events[-1].content.lower()


def assert_invalid_url_scheme(events):
    """Assertions for invalid URL scheme test case."""
    # Verify tool execution failed
    assert isinstance(events[3], ToolResultEvent)
    assert events[3].error is not None
    assert "Unsupported URL scheme: ftp" in events[3].error


def assert_message_construction(events, tmp_path):
    """Assertions for message construction test case."""
    # Verify the message structure
    assert isinstance(events[5], ContinueableUserMessageEvent)
    content = events[5].content
    assert len(content) == 2
    
    # Verify text part
    text_item = content[0]
    assert text_item["type"] == "text"
    assert "This is an image fetched from file://" in text_item["text"]
    
    # Verify image part
    image_item = content[1]
    assert image_item["type"] == "image_url"
    assert image_item["image_url"]["url"].startswith("data:")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "test_case",
    [
        {
            "name": "HTTP URL",
            "image_url": "https://example.com/image.jpg",
            "setup": lambda tmp_path: None,
            "expected_event_types": [
                UserMessageEvent,
                AssistantEvent,
                ToolCallEvent,
                ToolResultEvent,
                AssistantEvent,  # "Understood" message
                ContinueableUserMessageEvent,  # Image message
                AssistantEvent,  # Response to image
            ],
            "assertions": lambda events, tmp_path: assert_http_url_events(events),
        },
        {
            "name": "File URL",
            "image_url": lambda tmp_path: f"file://{tmp_path}/test.jpg",
            "setup": lambda tmp_path: (Path(tmp_path) / "test.jpg").write_bytes(b"fake_image_data_1234567890"),
            "expected_event_types": [
                UserMessageEvent,
                AssistantEvent,
                ToolCallEvent,
                ToolResultEvent,
                AssistantEvent,  # "Understood" message
                ContinueableUserMessageEvent,  # Image message
                AssistantEvent,  # Response to image
            ],
            "assertions": assert_file_url_events,
        },
        {
            "name": "Conversation continues after image",
            "image_url": lambda tmp_path: f"file://{tmp_path}/test.jpg",
            "setup": lambda tmp_path: (Path(tmp_path) / "test.jpg").write_bytes(b"test_data"),
            "expected_event_types": [
                UserMessageEvent,
                AssistantEvent,
                ToolCallEvent,
                ToolResultEvent,
                AssistantEvent,  # "Understood" message
                ContinueableUserMessageEvent,  # Image message
                AssistantEvent,  # Response to image
            ],
            "assertions": lambda events, tmp_path: assert_conversation_continues(events, tmp_path),
        },
        {
            "name": "Invalid URL scheme",
            "image_url": "ftp://example.com/image.jpg",
            "setup": lambda tmp_path: None,
            "expected_event_types": [
                UserMessageEvent,
                AssistantEvent,
                ToolCallEvent,
                ToolResultEvent,  # Should fail
            ],
            "assertions": lambda events, tmp_path: assert_invalid_url_scheme(events),
        },
        {
            "name": "Message construction in agent loop",
            "image_url": lambda tmp_path: f"file://{tmp_path}/test.jpg",
            "setup": lambda tmp_path: (Path(tmp_path) / "test.jpg").write_bytes(b"test_data"),
            "expected_event_types": [
                UserMessageEvent,
                AssistantEvent,
                ToolCallEvent,
                ToolResultEvent,
                AssistantEvent,  # "Understood" message
                ContinueableUserMessageEvent,  # Image message
                AssistantEvent,  # Response to image
            ],
            "assertions": assert_message_construction,
        },
    ],
)
async def test_read_image_integration(tmp_path, monkeypatch, test_case):
    """Test read_image tool integration with agent loop - parameterized version."""
    monkeypatch.chdir(tmp_path)
    
    # Run setup if needed
    if test_case["setup"]:
        test_case["setup"](tmp_path)
    
    # Create agent loop with mock responses
    config = make_config()
    
    # Determine the image URL (may be a lambda)
    image_url = test_case["image_url"](tmp_path) if callable(test_case["image_url"]) else test_case["image_url"]
    
    # Create tool call for read_image with the actual URL
    tool_call = make_read_image_tool_call("call_1", arguments=f'{{"image_url": "{image_url}"}}')
    
    # Mock responses: first call includes tool call, second is final response
    backend = FakeBackend([
        [mock_llm_chunk(content="Understood.", tool_calls=[tool_call])],
        [mock_llm_chunk(content="This is a beautiful landscape image.")],
    ])
    
    agent_loop = AgentLoop(
        config=config,
        backend=backend,
        agent_name=BuiltinAgentName.DEFAULT,
    )
    
    # Act and collect events
    prompt = f"Please analyze this image: {image_url}"
    events = await act_and_collect_events(agent_loop, prompt)
    
    # Verify event types match expectations
    for i, expected_type in enumerate(test_case["expected_event_types"]):
        assert isinstance(events[i], expected_type), f"Event {i} should be {expected_type}, got {type(events[i])}"
    
    # Run scenario-specific assertions
    test_case["assertions"](events, tmp_path)


# Assertion functions for backend message tests
def assert_http_url_messages(messages):
    """Assertions for HTTP URL backend messages test."""
    # Skip system and user messages, verify message 3: Tool result message
    assert messages[3].role == Role.tool
    assert messages[3].tool_call_id == "call_1"
    assert messages[3].name == "read_image"
    
    # Parse the content string (format: key: value\nkey: value)
    content_lines = messages[3].content.strip().split("\n")
    content_dict = {}
    for line in content_lines:
        key, value = line.split(": ", 1)
        content_dict[key] = value
    
    assert content_dict["image_url"] == "https://example.com/image.jpg"
    assert content_dict["source_type"] == "https"
    assert content_dict["source_path"] == "None"
    
    # Verify message 4: Assistant "Understood" message
    assert messages[4].role == Role.assistant
    assert messages[4].content == "Understood."
    assert messages[4].tool_call_id == "call_1"
    
    # Verify message 5: User message with image
    assert messages[5].role == Role.user
    assert isinstance(messages[5].content, list)
    assert len(messages[5].content) == 2
    assert messages[5].tool_call_id == "call_1"
    
    # Verify text part
    text_item = messages[5].content[0]
    assert text_item["type"] == "text"
    assert "This is an image fetched from https://example.com/image.jpg" in text_item["text"]
    
    # Verify image part
    image_item = messages[5].content[1]
    assert image_item["type"] == "image_url"
    assert image_item["image_url"]["url"] == "https://example.com/image.jpg"


def assert_file_url_messages(messages, tmp_path):
    """Assertions for File URL backend messages test."""
    # Skip system and user messages, verify message 3: Tool result message
    assert messages[3].role == Role.tool
    assert messages[3].tool_call_id == "call_1"
    assert messages[3].name == "read_image"
    
    # Parse the content string (format: key: value\nkey: value)
    content_lines = messages[3].content.strip().split("\n")
    content_dict = {}
    for line in content_lines:
        key, value = line.split(": ", 1)
        content_dict[key] = value
    
    assert "image_url" in content_dict
    assert content_dict["source_type"] == "file"
    assert "source_path" in content_dict
    assert tmp_path.as_posix() in content_dict["source_path"]
    
    # Verify message 4: Assistant "Understood" message
    assert messages[4].role == Role.assistant
    assert messages[4].content == "Understood."
    assert messages[4].tool_call_id == "call_1"
    
    # Verify message 5: User message with image (base64 encoded)
    assert messages[5].role == Role.user
    assert isinstance(messages[5].content, list)
    assert len(messages[5].content) == 2
    assert messages[5].tool_call_id == "call_1"
    
    # Verify text part
    text_item = messages[5].content[0]
    assert text_item["type"] == "text"
    assert "This is an image fetched from file://" in text_item["text"]
    
    # Verify image part (should be base64 data URL)
    image_item = messages[5].content[1]
    assert image_item["type"] == "image_url"
    image_url = image_item["image_url"]["url"]
    assert image_url.startswith("data:")
    assert ";base64," in image_url
    
    # Extract and verify the base64 data
    data_part = image_url.split(";base64,")[1]
    decoded_data = base64.b64decode(data_part)
    assert decoded_data == b"fake_image_data_1234567890"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "test_case",
    [
        {
            "name": "HTTP URL",
            "image_url": "https://example.com/image.jpg",
            "assertions": lambda messages, tmp_path: assert_http_url_messages(messages),
        },
        {
            "name": "File URL",
            "image_url": lambda tmp_path: f"file://{tmp_path}/test.jpg",
            "setup": lambda tmp_path: (Path(tmp_path) / "test.jpg").write_bytes(b"fake_image_data_1234567890"),
            "assertions": assert_file_url_messages,
        },
    ],
)
async def test_backend_receives_messages_after_read_image(tmp_path, monkeypatch, test_case):
    """Test that backend receives correct messages after read_image tool call."""
    monkeypatch.chdir(tmp_path)
    
    # Run setup if needed
    if test_case.get("setup"):
        test_case["setup"](tmp_path)
    
    # Create agent loop with mock responses
    config = make_config()
    
    # Determine the image URL (may be a lambda)
    image_url = test_case["image_url"](tmp_path) if callable(test_case["image_url"]) else test_case["image_url"]
    
    # Create tool call for read_image with the actual URL
    tool_call = make_read_image_tool_call("call_1", arguments=f'{{"image_url": "{image_url}"}}')
    
    # Mock responses: first call includes tool call, second is final response
    backend = FakeBackend([
        [mock_llm_chunk(content="Understood.", tool_calls=[tool_call])],
        [mock_llm_chunk(content="This is a beautiful landscape image.")],
    ])
    
    agent_loop = AgentLoop(
        config=config,
        backend=backend,
        agent_name=BuiltinAgentName.DEFAULT,
    )
    
    # Act and collect events
    prompt = f"Please analyze this image: {image_url}"
    events = await act_and_collect_events(agent_loop, prompt)
    
    # Get messages that would be sent to backend (after tool execution)
    # The messages list includes: system message, user message, tool result, assistant response, user image message
    messages = agent_loop.messages
    
    # Run scenario-specific assertions
    test_case["assertions"](messages, tmp_path)


@pytest.mark.asyncio
async def test_read_image_with_permission_denied(tmp_path, monkeypatch):
    """Test read_image tool with permission denied."""
    monkeypatch.chdir(tmp_path)
    
    # Create agent loop with permission denied
    config = make_config(read_image_permission=ToolPermission.NEVER)
    backend = FakeBackend([
        [mock_llm_chunk(content="I cannot analyze images.")],
    ])
    agent_loop = AgentLoop(
        config=config,
        backend=backend,
        agent_name=BuiltinAgentName.DEFAULT,
    )
    
    # Try to use read_image tool
    prompt = "Please analyze this image: https://example.com/image.jpg"
    events = await act_and_collect_events(agent_loop, prompt)
    
    # Should not call the tool
    assert len(events) == 2  # User message and assistant response
    assert isinstance(events[0], UserMessageEvent)
    assert isinstance(events[1], AssistantEvent)
    assert "read_image" not in events[1].content.lower()


@pytest.mark.asyncio
async def test_read_image_with_invalid_url(tmp_path, monkeypatch):
    """Test read_image tool with invalid URL."""
    monkeypatch.chdir(tmp_path)
    
    # Create agent loop
    config = make_config()
    backend = FakeBackend([
        [mock_llm_chunk(content="The URL 'not-a-valid-url' is not valid.")],
    ])
    agent_loop = AgentLoop(
        config=config,
        backend=backend,
        agent_name=BuiltinAgentName.DEFAULT,
    )
    
    # Try to use read_image tool with invalid URL
    prompt = "Please analyze this image: not-a-valid-url"
    events = await act_and_collect_events(agent_loop, prompt)
    
    # Should handle gracefully
    assert len(events) >= 2
    assert isinstance(events[0], UserMessageEvent)
    assert isinstance(events[1], AssistantEvent)
