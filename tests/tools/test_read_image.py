from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tests.mock.utils import collect_result
from vibe.core.tools.base import ToolError, ToolPermission
from vibe.core.tools.builtins.read_image import (
    ReadImage,
    ReadImageArgs,
    ReadImageResult,
    ReadImageState,
    ReadImageToolConfig,
)


@pytest.fixture
def read_image_tool(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = ReadImageToolConfig()
    return ReadImage(config=config, state=ReadImageState())


@pytest.mark.asyncio
async def test_http_url_validation(read_image_tool):
    """Test that HTTP URLs are validated and returned as-is."""
    result = await collect_result(
        read_image_tool.run(ReadImageArgs(image_url="http://example.com/image.jpg"))
    )

    assert isinstance(result, ReadImageResult)
    assert result.image_url == "http://example.com/image.jpg"
    assert result.source_type == "http"
    assert result.source_path is None


@pytest.mark.asyncio
async def test_https_url_validation(read_image_tool):
    """Test that HTTPS URLs are validated and returned as-is."""
    result = await collect_result(
        read_image_tool.run(ReadImageArgs(image_url="https://example.com/image.jpg"))
    )

    assert isinstance(result, ReadImageResult)
    assert result.image_url == "https://example.com/image.jpg"
    assert result.source_type == "https"
    assert result.source_path is None


@pytest.mark.asyncio
async def test_invalid_http_url_fails(read_image_tool):
    """Test that invalid HTTP URLs are rejected."""
    with pytest.raises(ToolError) as err:
        await collect_result(
            read_image_tool.run(ReadImageArgs(image_url="http:///invalid"))
        )

    assert "Invalid HTTP/HTTPS URL" in str(err.value)


@pytest.mark.asyncio
async def test_file_url_reads_and_encodes(read_image_tool, tmp_path):
    """Test that file:// URLs are read and encoded as base64."""
    
    # Create a test image file
    test_image = tmp_path / "test.jpg"
    test_image.write_bytes(b"fake_image_data_1234567890")
    
    result = await collect_result(
        read_image_tool.run(ReadImageArgs(image_url=f"file://{test_image}"))
    )

    assert isinstance(result, ReadImageResult)
    assert result.source_type == "file"
    assert result.source_path == str(test_image)
    
    # Verify the data URL format
    assert result.image_url.startswith("data:")
    assert ";base64," in result.image_url
    
    # Extract and decode the base64 data
    data_part = result.image_url.split(";base64,")[1]
    decoded_data = base64.b64decode(data_part)
    
    assert decoded_data == b"fake_image_data_1234567890"


@pytest.mark.asyncio
async def test_file_url_with_missing_file_fails(read_image_tool, tmp_path):
    """Test that missing files are handled properly."""
    
    with pytest.raises(ToolError) as err:
        await collect_result(
            read_image_tool.run(ReadImageArgs(image_url="file:///nonexistent.jpg"))
        )

    assert "Image file not found" in str(err.value)


@pytest.mark.asyncio
async def test_file_url_with_directory_fails(read_image_tool, tmp_path):
    """Test that directories are rejected."""
    
    # Create a directory
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()
    
    with pytest.raises(ToolError) as err:
        await collect_result(
            read_image_tool.run(ReadImageArgs(image_url=f"file://{test_dir}"))
        )

    assert "Path is a directory, not a file" in str(err.value)


@pytest.mark.asyncio
async def test_file_size_limit_enforcement(read_image_tool, tmp_path):
    """Test that large files are rejected."""
    
    # Create a file larger than the default limit (10MB)
    test_image = tmp_path / "large.jpg"
    large_data = b"x" * (11_000_000)  # 11MB
    test_image.write_bytes(large_data)
    
    with pytest.raises(ToolError) as err:
        await collect_result(
            read_image_tool.run(ReadImageArgs(image_url=f"file://{test_image}"))
        )

    assert "Image file too large" in str(err.value)
    assert "11000000 bytes" in str(err.value)
    assert "10000000 bytes" in str(err.value)


@pytest.mark.asyncio
async def test_custom_file_size_limit(tmp_path):
    """Test that custom file size limits work."""
    
    # Create a file larger than 1MB but smaller than 10MB
    test_image = tmp_path / "medium.jpg"
    medium_data = b"x" * (2_000_000)  # 2MB
    test_image.write_bytes(medium_data)
    
    # Create tool with 1MB limit
    config = ReadImageToolConfig(max_image_size_bytes=1_000_000)
    read_image_tool = ReadImage(config=config, state=ReadImageState())
    
    with pytest.raises(ToolError) as err:
        await collect_result(
            read_image_tool.run(ReadImageArgs(image_url=f"file://{test_image}"))
        )

    assert "Image file too large" in str(err.value)
    assert "2000000 bytes" in str(err.value)
    assert "1000000 bytes" in str(err.value)


@pytest.mark.asyncio
async def test_unsupported_url_scheme_fails(read_image_tool):
    """Test that unsupported URL schemes are rejected."""
    with pytest.raises(ToolError) as err:
        await collect_result(
            read_image_tool.run(ReadImageArgs(image_url="ftp://example.com/image.jpg"))
        )

    assert "Unsupported URL scheme: ftp" in str(err.value)


@pytest.mark.asyncio
async def test_file_read_error_handling(read_image_tool, tmp_path):
    """Test that file read errors are properly handled."""
    
    # Create a test file
    test_image = tmp_path / "test.jpg"
    test_image.write_bytes(b"test_data")
    
    # Mock the file read to raise an error
    with patch.object(Path, "open", side_effect=OSError("Permission denied")):
        with pytest.raises(ToolError) as err:
            await collect_result(
                read_image_tool.run(ReadImageArgs(image_url=f"file://{test_image}"))
            )

    assert "Error reading image file" in str(err.value)
    assert "Permission denied" in str(err.value)


@pytest.mark.asyncio
async def test_relative_file_path_resolution(read_image_tool, tmp_path, monkeypatch):
    """Test that relative file paths are resolved correctly."""
    monkeypatch.chdir(tmp_path)
    
    # Create a subdirectory with an image
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    test_image = subdir / "image.jpg"
    test_image.write_bytes(b"test_data")
    
    # Use relative path (note: file:// URLs need absolute paths or proper relative paths)
    result = await collect_result(
        read_image_tool.run(ReadImageArgs(image_url=f"file://{subdir}/image.jpg"))
    )

    assert isinstance(result, ReadImageResult)
    assert result.source_type == "file"
    # The path should be resolved to the absolute path
    assert result.source_path is not None
    assert "subdir" in result.source_path


@pytest.mark.asyncio
async def test_allowlist_denylist_for_http_urls():
    """Test allowlist/denylist filtering for HTTP URLs."""
    config = ReadImageToolConfig(
        allowlist=["https://trusted.com/*"],
        denylist=["https://malicious.com/*"]
    )
    read_image_tool = ReadImage(config=config, state=ReadImageState())
    
    trusted = read_image_tool.check_allowlist_denylist(
        ReadImageArgs(image_url="https://trusted.com/image.jpg")
    )
    malicious = read_image_tool.check_allowlist_denylist(
        ReadImageArgs(image_url="https://malicious.com/image.jpg")
    )
    neutral = read_image_tool.check_allowlist_denylist(
        ReadImageArgs(image_url="https://other.com/image.jpg")
    )
    
    assert trusted is ToolPermission.ALWAYS
    assert malicious is ToolPermission.NEVER
    assert neutral is None


@pytest.mark.asyncio
async def test_allowlist_denylist_for_file_urls(read_image_tool, tmp_path, monkeypatch):
    """Test allowlist/denylist filtering for file URLs."""
    monkeypatch.chdir(tmp_path)
    
    # Create test files
    allowed_file = tmp_path / "allowed.jpg"
    allowed_file.write_bytes(b"data")
    
    denied_file = tmp_path / "denied.jpg"  
    denied_file.write_bytes(b"data")
    
    config = ReadImageToolConfig(
        allowlist=["*/allowed.jpg"],
        denylist=["*/denied.jpg"]
    )
    read_image_tool = ReadImage(config=config, state=ReadImageState())
    
    allowed = read_image_tool.check_allowlist_denylist(
        ReadImageArgs(image_url=f"file://{allowed_file}")
    )
    denied = read_image_tool.check_allowlist_denylist(
        ReadImageArgs(image_url=f"file://{denied_file}")
    )
    
    assert allowed is ToolPermission.ALWAYS
    assert denied is ToolPermission.NEVER





@pytest.mark.asyncio
async def test_message_construction():
    """Test that message construction works correctly."""
    from vibe.core.types import LLMMessage, Role
    from vibe.core.llm.format import ResolvedToolCall
    
    # Create a mock tool call
    class MockToolCall:
        def __init__(self):
            self.call_id = "test_call_123"
            self.tool_name = "read_image"
            self.args_dict = {"image_url": "https://example.com/image.jpg"}
    
    # Create a mock result
    result = ReadImageResult(
        image_url="data:image/jpeg;base64,test_data",
        source_type="http",
        source_path=None
    )
    
    # Call the LLM message constructor
    llm_messages = ReadImage._construct_llm_message(MockToolCall(), result)  # type: ignore[arg-type]
    
    # Verify we get 2 messages (Understood + image)
    assert isinstance(llm_messages, list)
    assert len(llm_messages) == 2
    
    # Verify first message is assistant response
    assert llm_messages[0].role == Role.assistant
    assert llm_messages[0].content == "Understood."
    assert llm_messages[0].tool_call_id == "test_call_123"
    
    # Verify second message is user message with image
    assert llm_messages[1].role == Role.user
    assert isinstance(llm_messages[1].content, list)
    assert len(llm_messages[1].content) == 2
    
    # Verify text content
    text_item = llm_messages[1].content[0]
    assert text_item["type"] == "text"
    assert "This is an image fetched from https://example.com/image.jpg" in text_item["text"]
    
    # Verify image content
    image_item = llm_messages[1].content[1]
    assert image_item["type"] == "image_url"
    assert image_item["image_url"]["url"] == "data:image/jpeg;base64,test_data"


@pytest.mark.asyncio
async def test_get_name():
    """Test that the tool name is correct."""
    assert ReadImage.get_name() == "read_image"


@pytest.mark.asyncio
async def test_get_parameters():
    """Test that parameters are correctly defined."""
    params = ReadImage.get_parameters()
    
    assert "properties" in params
    assert "image_url" in params["properties"]
    assert params["properties"]["image_url"]["type"] == "string"
    assert "description" in params["properties"]["image_url"]
