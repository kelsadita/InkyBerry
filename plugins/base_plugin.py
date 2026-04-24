"""
InkyBerry Base Plugin
All plugins must inherit from this class and implement render().
"""

from abc import ABC, abstractmethod
import logging


class BasePlugin(ABC):
    """Abstract base class for InkyBerry plugins."""

    # Override these in your plugin
    name = "Base Plugin"
    description = "Override this"
    refresh_interval = 300  # seconds between auto-refreshes

    def __init__(self, config, display):
        self.config = config
        self.display = display
        self.logger = logging.getLogger(f"inkyberry.plugin.{self.name}")
        self._last_data = None

    @abstractmethod
    def render(self):
        """
        Render the plugin's content to a PIL Image.
        Must return a PIL Image object ready for display.
        """
        pass

    def on_button(self, button):
        """
        Handle a button press. Override for custom behavior.
        button: 'A', 'B', 'C', or 'D'
        Returns True if the plugin handled the button (prevents default action).
        """
        return False

    def update_data(self):
        """
        Fetch/update data without rendering.
        Override to separate data fetching from rendering.
        Called before render() on refresh.
        """
        pass

    def cleanup(self):
        """Called when the plugin is deactivated. Override if needed."""
        pass
