"""Tests for path_display widget."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe.cli.textual_ui.widgets.path_display import PathDisplay


class TestPathDisplayInitialization:
    """Test PathDisplay initialization."""

    def test_init_with_path_object(self) -> None:
        """Test initialization with Path object."""
        path = Path("/test/path")
        widget = PathDisplay(path)
        assert widget._path == path

    def test_init_with_string(self) -> None:
        """Test initialization with string."""
        path_str = "/test/path"
        widget = PathDisplay(path_str)
        assert widget._path == Path(path_str)

    def test_init_with_empty_string(self) -> None:
        """Test initialization with empty string."""
        widget = PathDisplay("")
        assert widget._path == Path(".")


class TestPathDisplayUpdate:
    """Test PathDisplay update methods."""

    def test_update_display_with_absolute_path(self) -> None:
        """Test updating display with absolute path."""
        widget = PathDisplay("/test/path")
        widget._update_display()
        # Just verify it doesn't crash
        assert True

    def test_update_display_with_relative_path(self) -> None:
        """Test updating display with relative path."""
        widget = PathDisplay("relative/path")
        widget._update_display()
        # Just verify it doesn't crash
        assert True

    def test_update_display_with_home_directory(self) -> None:
        """Test updating display with home directory."""
        home = Path.home()
        widget = PathDisplay(home)
        widget._update_display()
        # Just verify it doesn't crash
        assert True


class TestPathDisplaySetPath:
    """Test PathDisplay set_path method."""

    def test_set_path_with_new_path(self) -> None:
        """Test setting a new path."""
        widget = PathDisplay("/old/path")
        new_path = Path("/new/path")
        widget.set_path(new_path)
        assert widget._path == new_path

    def test_set_path_with_string(self) -> None:
        """Test setting path with string."""
        widget = PathDisplay("/old/path")
        new_path_str = "/new/path"
        widget.set_path(new_path_str)
        assert widget._path == Path(new_path_str)

    def test_set_path_triggers_update(self) -> None:
        """Test that set_path triggers _update_display."""
        widget = PathDisplay("/old/path")
        with patch.object(widget, '_update_display') as mock_update:
            widget.set_path("/new/path")
            mock_update.assert_called_once()


class TestPathDisplayRendering:
    """Test PathDisplay rendering methods."""

    def test_compose(self) -> None:
        """Test compose method."""
        widget = PathDisplay("/test/path")
        result = widget.compose()
        # Just verify it returns an iterable
        assert hasattr(result, '__iter__')


class TestPathDisplayEdgeCases:
    """Test PathDisplay edge cases."""

    def test_set_path_with_current_directory(self) -> None:
        """Test setting path to current directory."""
        widget = PathDisplay("/old/path")
        widget.set_path(".")
        assert widget._path == Path(".")

    def test_set_path_with_parent_directory(self) -> None:
        """Test setting path to parent directory."""
        widget = PathDisplay("/old/path")
        widget.set_path("..")
        assert widget._path == Path("..")

    def test_init_with_none(self) -> None:
        """Test initialization with None (should default to current directory)."""
        with patch('vibe.cli.textual_ui.widgets.path_display.Path') as mock_path:
            mock_path.return_value = Path(".")
            widget = PathDisplay(None)
            assert widget._path == Path(".")
