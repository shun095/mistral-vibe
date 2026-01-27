"""Comprehensive tests for terminal_theme module to improve coverage."""

from __future__ import annotations

import os
import re
from unittest.mock import MagicMock, patch, mock_open

import pytest

from vibe.cli.textual_ui.terminal_theme import (
    TerminalColors,
    _OSC_RESPONSE_RE,
    _adjust_brightness,
    _blend,
    _build_color_queries,
    _build_osc_query,
    _hex_to_rgb,
    _luminance,
    _parse_osc_responses,
    _parse_rgb,
    _query_terminal_colors,
    _read_responses,
    _rgb_to_hex,
    _UNIX_AVAILABLE,
    capture_terminal_theme,
)


class TestParseRGB:
    """Test _parse_rgb function."""

    def test_parse_rgb_16bit_success(self) -> None:
        """Test parsing 16-bit RGB values."""
        r_hex = b"ff00"
        g_hex = b"00ff"
        b_hex = b"0000"
        result = _parse_rgb(r_hex, g_hex, b_hex)
        assert result == "#ff0000"  # Takes first 2 chars of 16-bit values

    def test_parse_rgb_8bit_success(self) -> None:
        """Test parsing 8-bit RGB values."""
        r_hex = b"ff"
        g_hex = b"00"
        b_hex = b"00"
        result = _parse_rgb(r_hex, g_hex, b_hex)
        assert result == "#ff0000"

    def test_parse_rgb_invalid_length(self) -> None:
        """Test parsing with invalid length."""
        r_hex = b"fffff"
        g_hex = b"00ff"
        b_hex = b"0000"
        result = _parse_rgb(r_hex, g_hex, b_hex)
        assert result is None

    def test_parse_rgb_invalid_hex(self) -> None:
        """Test parsing with invalid hex characters."""
        r_hex = b"gg"
        g_hex = b"00"
        b_hex = b"00"
        result = _parse_rgb(r_hex, g_hex, b_hex)
        assert result is None

    def test_parse_rgb_empty_values(self) -> None:
        """Test parsing with empty values."""
        r_hex = b""
        g_hex = b""
        b_hex = b""
        result = _parse_rgb(r_hex, g_hex, b_hex)
        assert result is None


class TestReadResponses:
    """Test _read_responses function."""

    @patch("vibe.cli.textual_ui.terminal_theme.select")
    @patch("vibe.cli.textual_ui.terminal_theme.os.read")
    def test_read_responses_with_da1_response(self, mock_read, mock_select) -> None:
        """Test reading responses with DA1 response."""
        # Mock select to return ready
        mock_select.select.return_value = ([99], [], [])
        # Mock os.read to return DA1 response
        mock_read.return_value = b"\x1b[?1;2c"
        
        result = _read_responses(99, timeout=0.1)
        
        assert b"\x1b[?1;2c" in result
        mock_select.select.assert_called()
        mock_read.assert_called()

    @patch("vibe.cli.textual_ui.terminal_theme.select")
    @patch("vibe.cli.textual_ui.terminal_theme.os.read")
    def test_read_responses_timeout(self, mock_read, mock_select) -> None:
        """Test reading responses with timeout."""
        # Mock select to return not ready
        mock_select.select.return_value = ([], [], [])
        # Mock os.read to return empty
        mock_read.return_value = b""
        
        result = _read_responses(99, timeout=0.1)
        
        assert result == b""
        mock_select.select.assert_called()


class TestParseOSCResponses:
    """Test _parse_osc_responses function."""

    def test_parse_osc_responses_with_foreground(self) -> None:
        """Test parsing OSC responses with foreground color."""
        response = b"\x1b]10;rgb:ffff/ffff/ffff\x1b\\"
        result = _parse_osc_responses(response)
        assert result.foreground == "#ffffff"
        assert result.background is None

    def test_parse_osc_responses_with_background(self) -> None:
        """Test parsing OSC responses with background color."""
        response = b"\x1b]11;rgb:0000/0000/0000\x1b\\"
        result = _parse_osc_responses(response)
        assert result.background == "#000000"
        assert result.foreground is None

    def test_parse_osc_responses_with_ansi_colors(self) -> None:
        """Test parsing OSC responses with ANSI colors."""
        response = (
            b"\x1b]4;0;rgb:0000/0000/0000\x1b\\"
            b"\x1b]4;1;rgb:ffff/0000/0000\x1b\\"
            b"\x1b]4;2;rgb:0000/ffff/0000\x1b\\"
        )
        result = _parse_osc_responses(response)
        assert result.black == "#000000"
        assert result.red == "#ff0000"
        assert result.green == "#00ff00"

    def test_parse_osc_responses_with_invalid_format(self) -> None:
        """Test parsing OSC responses with invalid format."""
        response = b"\x1b]10;rgb:invalid/color\x1b\\"
        result = _parse_osc_responses(response)
        assert result.foreground is None

    def test_parse_osc_responses_empty(self) -> None:
        """Test parsing empty OSC responses."""
        response = b""
        result = _parse_osc_responses(response)
        assert result.foreground is None
        assert result.background is None


class TestQueryTerminalColors:
    """Test _query_terminal_colors function."""

    @patch("vibe.cli.textual_ui.terminal_theme.sys.stdin.isatty")
    @patch("vibe.cli.textual_ui.terminal_theme.sys.stdout.isatty")
    def test_query_terminal_colors_not_a_tty(self, mock_stdout, mock_stdin) -> None:
        """Test querying terminal colors when not a TTY."""
        mock_stdin.return_value = False
        mock_stdout.return_value = True
        
        result = _query_terminal_colors()
        assert result.foreground is None
        assert result.background is None

    @patch("vibe.cli.textual_ui.terminal_theme._read_responses")
    @patch("vibe.cli.textual_ui.terminal_theme._raw_mode")
    @patch("vibe.cli.textual_ui.terminal_theme.sys.stdin.isatty")
    @patch("vibe.cli.textual_ui.terminal_theme.sys.stdout.isatty")
    def test_hex_to_rgb_success(self, mock_stdin, mock_stdout, mock_raw_mode, mock_read_responses) -> None:
        """Test successful hex to RGB conversion."""
        result = _hex_to_rgb("#ff0000")
        assert result == (255, 0, 0)

    def test_hex_to_rgb_without_hash(self) -> None:
        """Test hex to RGB conversion without hash."""
        result = _hex_to_rgb("ff0000")
        assert result == (255, 0, 0)

    def test_hex_to_rgb_min_values(self) -> None:
        """Test hex to RGB conversion with minimum values."""
        result = _hex_to_rgb("#000000")
        assert result == (0, 0, 0)

    def test_hex_to_rgb_max_values(self) -> None:
        """Test hex to RGB conversion with maximum values."""
        result = _hex_to_rgb("#ffffff")
        assert result == (255, 255, 255)


class TestRGBToHex:
    """Test _rgb_to_hex function."""

    def test_rgb_to_hex_success(self) -> None:
        """Test successful RGB to hex conversion."""
        result = _rgb_to_hex(255, 0, 0)
        assert result == "#ff0000"

    def test_rgb_to_hex_min_values(self) -> None:
        """Test RGB to hex conversion with minimum values."""
        result = _rgb_to_hex(0, 0, 0)
        assert result == "#000000"

    def test_rgb_to_hex_max_values(self) -> None:
        """Test RGB to hex conversion with maximum values."""
        result = _rgb_to_hex(255, 255, 255)
        assert result == "#ffffff"


class TestAdjustBrightness:
    """Test _adjust_brightness function."""

    def test_adjust_brightness_increase(self) -> None:
        """Test increasing brightness."""
        result = _adjust_brightness("#000000", 1.5)
        assert result == "#000000"  # 0 * 1.5 = 0

    def test_adjust_brightness_decrease(self) -> None:
        """Test decreasing brightness."""
        result = _adjust_brightness("#ffffff", 0.5)
        assert result == "#7f7f7f"  # Integer division rounds down

    def test_adjust_brightness_no_change(self) -> None:
        """Test no brightness change."""
        result = _adjust_brightness("#808080", 1.0)
        assert result == "#808080"

    def test_adjust_brightness_clip_max(self) -> None:
        """Test brightness adjustment clips at max."""
        result = _adjust_brightness("#ffffff", 2.0)
        assert result == "#ffffff"  # Clipped at 255

    def test_adjust_brightness_clip_min(self) -> None:
        """Test brightness adjustment clips at min."""
        result = _adjust_brightness("#000000", 0.0)
        assert result == "#000000"  # Clipped at 0


class TestBlend:
    """Test _blend function."""

    def test_blend_equal_ratio(self) -> None:
        """Test blending with equal ratio."""
        result = _blend("#ff0000", "#0000ff", 0.5)
        assert result == "#7f007f"  # Integer division rounds down

    def test_blend_custom_colors(self) -> None:
        """Test blending custom colors."""
        result = _blend("#ff00ff", "#00ffff", 0.5)
        assert result == "#7f7fff"  # Integer division rounds down

    def test_blend_full_first_color(self) -> None:
        """Test blending with full first color."""
        result = _blend("#ff0000", "#0000ff", 0.0)
        assert result == "#ff0000"

    def test_blend_full_second_color(self) -> None:
        """Test blending with full second color."""
        result = _blend("#ff0000", "#0000ff", 1.0)
        assert result == "#0000ff"


class TestLuminance:
    """Test _luminance function."""

    def test_luminance_white(self) -> None:
        """Test luminance of white."""
        result = _luminance("#ffffff")
        assert result == 1.0

    def test_luminance_black(self) -> None:
        """Test luminance of black."""
        result = _luminance("#000000")
        assert result == 0.0

    def test_luminance_gray(self) -> None:
        """Test luminance of gray."""
        result = _luminance("#808080")
        # Allow small floating point differences
        assert abs(result - 0.5) < 0.002

    def test_luminance_with_various_colors(self) -> None:
        """Test luminance with various colors."""
        # These are approximate values based on the ITU-R BT.601 formula
        test_cases = [
            ("#ff0000", 0.299),  # Red
            ("#00ff00", 0.587),  # Green
            ("#0000ff", 0.114),  # Blue
            ("#ffff00", 0.886),  # Yellow
            ("#00ffff", 0.701),  # Cyan
            ("#ff00ff", 0.413),  # Magenta
        ]
        
        for color, expected in test_cases:
            result = _luminance(color)
            # Allow small floating point differences
            assert abs(result - expected) < 0.001


class TestCaptureTerminalTheme:
    """Test capture_terminal_theme function."""

    @patch("vibe.cli.textual_ui.terminal_theme._query_terminal_colors")
    def test_capture_terminal_theme_success(self, mock_query) -> None:
        """Test successful terminal theme capture."""
        mock_query.return_value = TerminalColors(
            foreground="#ffffff",
            background="#000000",
            black="#000000",
            red="#ff0000",
            green="#00ff00",
            yellow="#ffff00",
            blue="#0000ff",
            magenta="#ff00ff",
            cyan="#00ffff",
            white="#ffffff",
            bright_black="#555555",
            bright_red="#ff5555",
            bright_green="#55ff55",
            bright_yellow="#ffff55",
            bright_blue="#5555ff",
            bright_magenta="#ff55ff",
            bright_cyan="#55ffff",
            bright_white="#aaaaaa",
        )
        
        result = capture_terminal_theme()
        assert result is not None
        assert result.name == "terminal"

    @patch("vibe.cli.textual_ui.terminal_theme._query_terminal_colors")
    def test_capture_terminal_theme_no_colors(self, mock_query) -> None:
        """Test terminal theme capture with no colors."""
        mock_query.return_value = TerminalColors()
        
        result = capture_terminal_theme()
        assert result is None

    @patch("vibe.cli.textual_ui.terminal_theme._query_terminal_colors")
    def test_capture_terminal_theme_dark_background(self, mock_query) -> None:
        """Test terminal theme capture with dark background."""
        mock_query.return_value = TerminalColors(
            foreground="#000000",
            background="#111111",
        )
        
        result = capture_terminal_theme()
        assert result is not None
        assert result.name == "terminal"

    @patch("vibe.cli.textual_ui.terminal_theme._query_terminal_colors")
    def test_capture_terminal_theme_light_background(self, mock_query) -> None:
        """Test terminal theme capture with light background."""
        mock_query.return_value = TerminalColors(
            foreground="#ffffff",
            background="#eeeeee",
        )
        
        result = capture_terminal_theme()
        assert result is not None
        assert result.name == "terminal"


class TestBuildOSCQuery:
    """Test _build_osc_query function."""

    def test_build_osc_query_foreground(self) -> None:
        """Test building OSC query for foreground."""
        result = _build_osc_query("10")
        assert result == b"\x1b]10;?\x1b\\"

    def test_build_osc_query_background(self) -> None:
        """Test building OSC query for background."""
        result = _build_osc_query("11")
        assert result == b"\x1b]11;?\x1b\\"

    def test_build_osc_query_ansi_color(self) -> None:
        """Test building OSC query for ANSI color."""
        result = _build_osc_query("4;0")
        assert result == b"\x1b]4;0;?\x1b\\"


class TestBuildColorQueries:
    """Test _build_color_queries function."""

    def test_build_color_queries_structure(self) -> None:
        """Test structure of built color queries."""
        queries, mapping = _build_color_queries()
        
        assert isinstance(queries, bytes)
        assert isinstance(mapping, dict)
        assert b"\x1b]10;?\x1b\\" in queries
        assert b"\x1b]11;?\x1b\\" in queries
        assert b"\x1b]4;0;?\x1b\\" in queries
        assert b"\x1b]4;15;?\x1b\\" in queries  # Last ANSI color
        
        assert mapping[b"10"] == "foreground"
        assert mapping[b"11"] == "background"
        assert mapping[b"4;0"] == "black"
        assert mapping[b"4;15"] == "bright_white"


class TestOSCResponseRegex:
    """Test _OSC_RESPONSE_RE regex pattern."""

    def test_osc_response_re_matches_foreground(self) -> None:
        """Test regex matches foreground response."""
        response = b"\x1b]10;rgb:ffff/ffff/ffff\x1b\\"
        matches = list(_OSC_RESPONSE_RE.finditer(response))
        assert len(matches) == 1
        assert matches[0].groups() == (b"10", b"ffff", b"ffff", b"ffff")

    def test_osc_response_re_matches_background(self) -> None:
        """Test regex matches background response."""
        response = b"\x1b]11;rgb:0000/0000/0000\x1b\\"
        matches = list(_OSC_RESPONSE_RE.finditer(response))
        assert len(matches) == 1
        assert matches[0].groups() == (b"11", b"0000", b"0000", b"0000")

    def test_osc_response_re_matches_ansi_color(self) -> None:
        """Test regex matches ANSI color response."""
        response = b"\x1b]4;1;rgb:ffff/0000/0000\x1b\\"
        matches = list(_OSC_RESPONSE_RE.finditer(response))
        assert len(matches) == 1
        assert matches[0].groups() == (b"4;1", b"ffff", b"0000", b"0000")

    def test_osc_response_re_multiple_matches(self) -> None:
        """Test regex matches multiple responses."""
        response = (
            b"\x1b]10;rgb:ffff/ffff/ffff\x1b\\"
            b"\x1b]11;rgb:0000/0000/0000\x1b\\"
            b"\x1b]4;0;rgb:0000/0000/0000\x1b\\"
        )
        matches = list(_OSC_RESPONSE_RE.finditer(response))
        assert len(matches) == 3
        assert matches[0].groups()[0] == b"10"
        assert matches[1].groups()[0] == b"11"
        assert matches[2].groups()[0] == b"4;0"

    def test_osc_response_re_no_match(self) -> None:
        """Test regex doesn't match invalid format."""
        response = b"\x1b]10;invalid\x1b\\"
        matches = list(_OSC_RESPONSE_RE.finditer(response))
        assert len(matches) == 0


class TestTerminalColors:
    """Test TerminalColors dataclass."""

    def test_terminal_colors_defaults(self) -> None:
        """Test TerminalColors with default values."""
        colors = TerminalColors()
        assert colors.foreground is None
        assert colors.background is None
        assert colors.black is None
        assert colors.is_complete() is False

    def test_terminal_colors_complete(self) -> None:
        """Test TerminalColors with all values."""
        colors = TerminalColors(
            foreground="#ffffff",
            background="#000000",
            black="#000000",
            red="#ff0000",
            green="#00ff00",
            yellow="#ffff00",
            blue="#0000ff",
            magenta="#ff00ff",
            cyan="#00ffff",
            white="#ffffff",
            bright_black="#555555",
            bright_red="#ff5555",
            bright_green="#55ff55",
            bright_yellow="#ffff55",
            bright_blue="#5555ff",
            bright_magenta="#ff55ff",
            bright_cyan="#55ffff",
            bright_white="#aaaaaa",
        )
        assert colors.is_complete() is True

    def test_terminal_colors_partial(self) -> None:
        """Test TerminalColors with partial values."""
        colors = TerminalColors(foreground="#ffffff", background="#000000")
        assert colors.is_complete() is False


class TestUnixAvailability:
    """Test _UNIX_AVAILABLE flag."""

    def test_unix_available_flag(self) -> None:
        """Test _UNIX_AVAILABLE flag is set correctly."""
        # This test just verifies the flag exists
        assert isinstance(_UNIX_AVAILABLE, bool)
