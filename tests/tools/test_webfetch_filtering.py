from __future__ import annotations

import httpx
import pytest
import respx

from tests.mock.utils import collect_result
from vibe.core.tools.base import BaseToolState, ToolError
from vibe.core.tools.builtins.webfetch import WebFetch, WebFetchArgs, WebFetchConfig


@pytest.fixture
def webfetch():
    config = WebFetchConfig()
    return WebFetch(config=config, state=BaseToolState())


@pytest.mark.asyncio
@respx.mock
async def test_pattern_filter_returns_matching_lines_with_numbers(webfetch):
    content = "line one\nline two\nerror found\nanother line\nerror again"
    respx.get("https://example.com").mock(
        return_value=httpx.Response(
            200, text=content, headers={"Content-Type": "text/plain"}
        )
    )
    result = await collect_result(
        webfetch.run(WebFetchArgs(url="https://example.com", pattern="error"))
    )
    assert result.content == "3: error found\n5: error again"


@pytest.mark.asyncio
@respx.mock
async def test_pattern_filter_with_regex(webfetch):
    content = "price: $10\nprice: $20\ncost: $30"
    respx.get("https://example.com").mock(
        return_value=httpx.Response(
            200, text=content, headers={"Content-Type": "text/plain"}
        )
    )
    result = await collect_result(
        webfetch.run(WebFetchArgs(url="https://example.com", pattern=r"\$\d+"))
    )
    assert "1: price: $10" in result.content
    assert "2: price: $20" in result.content
    assert "3: cost: $30" in result.content


@pytest.mark.asyncio
@respx.mock
async def test_pattern_filter_no_matches(webfetch):
    content = "line one\nline two\nline three"
    respx.get("https://example.com").mock(
        return_value=httpx.Response(
            200, text=content, headers={"Content-Type": "text/plain"}
        )
    )
    result = await collect_result(
        webfetch.run(WebFetchArgs(url="https://example.com", pattern="notfound"))
    )
    assert result.content == ""


@pytest.mark.asyncio
@respx.mock
async def test_pattern_filter_invalid_regex(webfetch):
    respx.get("https://example.com").mock(
        return_value=httpx.Response(
            200, text="content", headers={"Content-Type": "text/plain"}
        )
    )
    with pytest.raises(ToolError, match="Invalid regex pattern"):
        await collect_result(
            webfetch.run(WebFetchArgs(url="https://example.com", pattern="["))
        )


@pytest.mark.asyncio
@respx.mock
async def test_offset_filter(webfetch):
    content = "line1\nline2\nline3\nline4\nline5"
    respx.get("https://example.com").mock(
        return_value=httpx.Response(
            200, text=content, headers={"Content-Type": "text/plain"}
        )
    )
    result = await collect_result(
        webfetch.run(WebFetchArgs(url="https://example.com", offset=2))
    )
    assert result.content == "3: line3\n4: line4\n5: line5"


@pytest.mark.asyncio
@respx.mock
async def test_offset_with_limit(webfetch):
    content = "line1\nline2\nline3\nline4\nline5\nline6\nline7"
    respx.get("https://example.com").mock(
        return_value=httpx.Response(
            200, text=content, headers={"Content-Type": "text/plain"}
        )
    )
    result = await collect_result(
        webfetch.run(WebFetchArgs(url="https://example.com", offset=1, limit=3))
    )
    assert result.content == "2: line2\n3: line3\n4: line4"


@pytest.mark.asyncio
@respx.mock
async def test_limit_only(webfetch):
    content = "line1\nline2\nline3\nline4\nline5"
    respx.get("https://example.com").mock(
        return_value=httpx.Response(
            200, text=content, headers={"Content-Type": "text/plain"}
        )
    )
    result = await collect_result(
        webfetch.run(WebFetchArgs(url="https://example.com", limit=3))
    )
    assert result.content == "1: line1\n2: line2\n3: line3"


@pytest.mark.asyncio
@respx.mock
async def test_offset_beyond_content(webfetch):
    content = "line1\nline2"
    respx.get("https://example.com").mock(
        return_value=httpx.Response(
            200, text=content, headers={"Content-Type": "text/plain"}
        )
    )
    result = await collect_result(
        webfetch.run(WebFetchArgs(url="https://example.com", offset=9))
    )
    assert result.content == ""


@pytest.mark.asyncio
@respx.mock
async def test_offset_zero(webfetch):
    content = "line1\nline2\nline3"
    respx.get("https://example.com").mock(
        return_value=httpx.Response(
            200, text=content, headers={"Content-Type": "text/plain"}
        )
    )
    result = await collect_result(
        webfetch.run(WebFetchArgs(url="https://example.com", offset=0))
    )
    assert result.content == "1: line1\n2: line2\n3: line3"


# Removed: test_pattern_filter_takes_precedence_over_line_range
# Pattern with custom offset/limit is now rejected by validation


@pytest.mark.asyncio
@respx.mock
async def test_filter_with_html_content(webfetch):
    html = "<html><body><h1>Title</h1><p>Content</p></body></html>"
    respx.get("https://example.com").mock(
        return_value=httpx.Response(
            200, text=html, headers={"Content-Type": "text/html"}
        )
    )
    result = await collect_result(
        webfetch.run(WebFetchArgs(url="https://example.com", pattern="Title"))
    )
    assert "# Title" in result.content


@pytest.mark.asyncio
async def test_pattern_with_custom_offset_rejected(webfetch):
    with pytest.raises(ToolError, match="Cannot use 'pattern' with custom 'offset'"):
        await collect_result(
            webfetch.run(
                WebFetchArgs(url="https://example.com", pattern="error", offset=99)
            )
        )


@pytest.mark.asyncio
async def test_pattern_with_custom_limit_rejected(webfetch):
    with pytest.raises(ToolError, match="Cannot use 'pattern' with custom"):
        await collect_result(
            webfetch.run(
                WebFetchArgs(url="https://example.com", pattern="error", limit=50)
            )
        )


@pytest.mark.asyncio
async def test_pattern_with_defaults_allowed(webfetch):
    # Pattern with default offset=0 and limit=1000 should work
    with respx.mock:
        respx.get("https://example.com").mock(
            return_value=httpx.Response(
                200, text="line1\nerror2\nline3", headers={"Content-Type": "text/plain"}
            )
        )
        result = await collect_result(
            webfetch.run(WebFetchArgs(url="https://example.com", pattern="error"))
        )
        assert "2: error2" in result.content
