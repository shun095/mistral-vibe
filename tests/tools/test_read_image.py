from __future__ import annotations

import base64
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest

from tests.mock.utils import collect_result
from vibe.core.llm.format import ResolvedToolCall
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
    assert result.source_url == "http://example.com/image.jpg"
    assert result.source_type == "http"


@pytest.mark.asyncio
async def test_https_url_validation(read_image_tool):
    """Test that HTTPS URLs are validated and returned as-is."""
    result = await collect_result(
        read_image_tool.run(ReadImageArgs(image_url="https://example.com/image.jpg"))
    )

    assert isinstance(result, ReadImageResult)
    assert result.source_url == "https://example.com/image.jpg"
    assert result.source_type == "https"


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
    """Test that file:// URLs are validated and returned."""
    # Create a test image file
    test_image = tmp_path / "test.jpg"
    test_image.write_bytes(b"fake_image_data_1234567890")

    result = await collect_result(
        read_image_tool.run(ReadImageArgs(image_url=f"file://{test_image}"))
    )

    assert isinstance(result, ReadImageResult)
    assert result.source_type == "file"
    assert result.source_url == f"file://{test_image}"


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
    # The URL should contain the path
    assert "subdir" in result.source_url
    assert "image.jpg" in result.source_url


@pytest.mark.asyncio
async def test_allowlist_denylist_for_http_urls():
    """Test allowlist/denylist filtering for HTTP URLs."""
    config = ReadImageToolConfig(
        allowlist=["https://trusted.com/*"], denylist=["https://malicious.com/*"]
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

    config = ReadImageToolConfig(allowlist=["*/allowed.jpg"], denylist=["*/denied.jpg"])
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
async def test_message_construction(tmp_path, monkeypatch):
    """Test that message construction works correctly."""
    from vibe.core.types import Role

    monkeypatch.chdir(tmp_path)

    # Create a mock tool call
    class MockToolCall:
        def __init__(self):
            self.call_id = "test_call_123"
            self.tool_name = "read_image"
            self.args_dict = {"image_url": "https://example.com/image.jpg"}

    # Test HTTP URL - mock the HTTP request
    result_http = ReadImageResult(
        source_url="https://example.com/image.jpg", source_type="http"
    )

    # Mock httpx.get to return test data
    mock_response = type(
        "MockResponse",
        (),
        {
            "content": b"http_test_image_data",
            "headers": {"content-type": "image/jpeg"},
            "raise_for_status": lambda self: None,
        },
    )()

    with monkeypatch.context() as mp:
        mp.setattr("httpx.get", lambda *args, **kwargs: mock_response)

        llm_messages_http = ReadImage._construct_llm_message(
            cast(ResolvedToolCall, MockToolCall()), result_http
        )
        assert isinstance(llm_messages_http, list)
        assert len(llm_messages_http) == 2
        assert llm_messages_http[0].role == Role.assistant
        assert llm_messages_http[0].content == "Understood."
        assert llm_messages_http[0].tool_call_id == "test_call_123"

        # Verify user message contains base64 encoded image
        assert llm_messages_http[1].role == Role.user
        assert llm_messages_http[1].tool_call_id == "test_call_123"

        # Check that the content has text and image_url
        assert isinstance(llm_messages_http[1].content, list)
        assert len(llm_messages_http[1].content) == 2

        # Second item is image_url with base64 data
        image_content = llm_messages_http[1].content[1]
        assert isinstance(image_content, dict)
        assert image_content["type"] == "image_url"
        data_url = image_content["image_url"]["url"]
        assert data_url.startswith("data:image/jpeg;base64,")

        # Decode and verify the data
        data_part = data_url.split(";base64,")[1]
        decoded_data = base64.b64decode(data_part)
        assert decoded_data == b"http_test_image_data"

    # Test file URL - create a test image and verify base64 encoding
    test_image = tmp_path / "test.jpg"
    test_image.write_bytes(b"fake_image_data_1234567890")

    result_file = ReadImageResult(source_url=f"file://{test_image}", source_type="file")

    # Create a new mock tool call with file URL
    class MockToolCallFile:
        def __init__(self):
            self.call_id = "test_call_456"
            self.tool_name = "read_image"
            self.args_dict = {"image_url": f"file://{test_image}"}

    llm_messages_file = ReadImage._construct_llm_message(
        cast(ResolvedToolCall, MockToolCallFile()), result_file
    )
    assert isinstance(llm_messages_file, list)
    assert len(llm_messages_file) == 2

    # Verify user message contains base64 encoded data
    user_message = llm_messages_file[1]
    assert user_message.role == Role.user

    # Check that the content has text and image_url
    assert isinstance(user_message.content, list)
    assert len(user_message.content) == 2

    # First item is text description
    text_content = user_message.content[0]
    assert isinstance(text_content, dict)
    assert text_content["type"] == "text"
    assert "file://" in text_content["text"]

    # Second item is image_url
    image_content = user_message.content[1]
    assert isinstance(image_content, dict)
    assert image_content["type"] == "image_url"
    assert isinstance(image_content["image_url"], dict)
    data_url = image_content["image_url"]["url"]
    assert data_url.startswith("data:image/jpeg;base64,")

    # Decode and verify the data
    data_part = data_url.split(";base64,")[1]
    decoded_data = base64.b64decode(data_part)
    assert decoded_data == b"fake_image_data_1234567890"


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


@pytest.mark.asyncio
async def test_cache_avoids_refetch():
    """Test that the cache prevents re-fetching the same image."""
    # Clear cache first
    ReadImage._fetch_cache.clear()

    # Mock httpx.get to track calls
    call_count = 0
    mock_response = type(
        "MockResponse",
        (),
        {
            "content": b"cached_image_data",
            "headers": {"content-type": "image/png"},
            "raise_for_status": lambda self: None,
        },
    )()

    def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_response

    with patch("httpx.get", mock_get):
        # First call should fetch
        data1, type1 = ReadImage._fetch_http_image_sync("https://example.com/test.png")
        assert call_count == 1
        assert data1 == b"cached_image_data"
        assert type1 == "image/png"

        # Second call should use cache
        data2, type2 = ReadImage._fetch_http_image_sync("https://example.com/test.png")
        assert call_count == 1  # Still 1, no re-fetch
        assert data2 == b"cached_image_data"
        assert type2 == "image/png"

        # Different URL should fetch again
        data3, type3 = ReadImage._fetch_http_image_sync("https://example.com/other.png")
        assert call_count == 2  # Now 2, fetched again
        assert data3 == b"cached_image_data"

        # Clear cache
        ReadImage.clear_fetch_cache(["https://example.com/test.png"])
        assert "https://example.com/test.png" not in ReadImage._fetch_cache
        assert "https://example.com/other.png" in ReadImage._fetch_cache

        # Clear all
        ReadImage.clear_fetch_cache()
        assert len(ReadImage._fetch_cache) == 0
