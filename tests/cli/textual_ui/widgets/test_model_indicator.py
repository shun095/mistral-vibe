"""Test the ModelIndicator widget."""

import pytest
from textual.widgets import Static

from vibe.cli.textual_ui.widgets.model_indicator import ModelIndicator
from vibe.core.config import VibeConfig


class TestModelIndicator:
    """Test the ModelIndicator widget functionality."""

    def test_model_indicator_initialization(self):
        """Test that ModelIndicator initializes correctly."""
        indicator = ModelIndicator()
        assert isinstance(indicator, Static)
        assert not indicator.can_focus
        assert indicator._config is not None

    def test_model_indicator_display(self):
        """Test that ModelIndicator displays the correct model name."""
        indicator = ModelIndicator()
        # The indicator should display the active model from config
        config = VibeConfig.load()
        expected_display = f"🤖 {config.active_model}"
        # Check the actual text content
        assert indicator.content == expected_display

    def test_model_indicator_update(self):
        """Test that ModelIndicator can update the displayed model."""
        indicator = ModelIndicator()
        new_model = "test-model"
        indicator.update_model(new_model)
        expected_display = f"🤖 {new_model}"
        # Check the actual text content
        assert indicator.content == expected_display

    def test_model_indicator_css_class(self):
        """Test that ModelIndicator has the correct CSS class."""
        indicator = ModelIndicator()
        assert "model-indicator" in indicator.classes
