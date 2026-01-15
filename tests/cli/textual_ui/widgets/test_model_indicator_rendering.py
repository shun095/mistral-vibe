"""Test the ModelIndicator widget rendering."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from vibe.cli.textual_ui.widgets.model_indicator import ModelIndicator


class TestModelIndicatorRendering:
    """Test the ModelIndicator widget rendering and appearance."""

    def test_model_indicator_has_correct_css_class(self):
        """Test that ModelIndicator has the model-indicator CSS class."""
        indicator = ModelIndicator()
        
        # Check that the widget has the correct CSS class
        assert "model-indicator" in indicator.classes

    def test_model_indicator_update_changes_content(self):
        """Test that updating the model changes the displayed content."""
        indicator = ModelIndicator()
        original_content = indicator.content
        
        # Update to a new model
        indicator.update_model("test-model-v2")
        
        # Content should have changed
        assert indicator.content != original_content
        assert "test-model-v2" in indicator.content


class TestModelIndicatorInApp:
    """Test ModelIndicator integration in the app layout."""

    def test_model_indicator_in_bottom_bar(self):
        """Test that ModelIndicator is properly placed in the bottom bar."""
        from vibe.cli.textual_ui.app import VibeApp
        from vibe.core.config import VibeConfig
        
        # Create a minimal test app
        config = VibeConfig.load()
        app = VibeApp(config=config)
        
        # Get the compose result to check the widget hierarchy
        import inspect
        compose_source = inspect.getsource(VibeApp.compose)
        
        # Verify ModelIndicator is in the bottom-bar
        bottom_bar_section = compose_source[
            compose_source.find('with Horizontal(id="bottom-bar"):'):
            compose_source.find('with Horizontal(id="bottom-bar"):') + 500
        ]
        
        assert 'ModelIndicator()' in bottom_bar_section
        assert 'ContextProgress()' in bottom_bar_section
        
        # Verify ordering (ModelIndicator should come before ContextProgress)
        model_pos = bottom_bar_section.find('ModelIndicator()')
        context_pos = bottom_bar_section.find('ContextProgress()')
        assert model_pos < context_pos
