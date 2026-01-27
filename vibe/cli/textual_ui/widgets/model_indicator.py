from __future__ import annotations

from typing import Any

from textual.widgets import Static

from vibe.core.config import VibeConfig


class ModelIndicator(Static):
    """Displays the current active model with info-colored indicator."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.can_focus = False
        self._config = VibeConfig.load()
        self._update_display()

    def _update_display(self) -> None:
        """Update the display with the current active model."""
        model_name = self._config.active_model
        self.update(f"🤖 {model_name}")
        self.add_class("model-indicator")

    def update_model(self, model_name: str) -> None:
        """Update the displayed model name."""
        self._config.active_model = model_name
        self._update_display()
    
    def refresh_display(self) -> None:
        """Refresh the display from the current config."""
        # Reload config to get latest changes
        self._config = VibeConfig.load()
        self._update_display()
