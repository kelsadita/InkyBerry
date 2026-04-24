"""
InkyBerry Button Handler
Handles the 4 GPIO buttons on the Inky Impression 7.3".
Supports single press and long press (hold 2+ seconds).
"""

import logging
import time
import threading

logger = logging.getLogger("inkyberry.buttons")

# Button labels
BUTTON_A = "A"
BUTTON_B = "B"
BUTTON_C = "C"
BUTTON_D = "D"

LONG_PRESS_TIME = 2.0  # seconds


class ButtonHandler:
    """Handles GPIO button input with debouncing and long-press detection."""

    def __init__(self, config, callback):
        """
        config: full app config dict
        callback: function(button_label, long_press=False)
        """
        self.callback = callback
        self._running = False
        self._thread = None

        btn_cfg = config.get("buttons", {})
        self.pin_map = {
            btn_cfg.get("A", 5): BUTTON_A,
            btn_cfg.get("B", 6): BUTTON_B,
            btn_cfg.get("C", 16): BUTTON_C,
            btn_cfg.get("D", 24): BUTTON_D,
        }

        self._gpio_available = False
        self._buttons = {}
        self._init_gpio()

    def _init_gpio(self):
        """Initialize GPIO buttons."""
        try:
            from gpiozero import Button
            for pin, label in self.pin_map.items():
                btn = Button(pin, pull_up=True, bounce_time=0.1)
                btn.when_pressed = lambda p=pin: self._on_press(p)
                self._buttons[pin] = btn
                logger.info(f"Button {label} registered on GPIO {pin}")
            self._gpio_available = True
        except Exception as e:
            logger.warning(f"GPIO not available: {e}")
            logger.warning("Buttons will not work (headless mode)")

    def _on_press(self, pin):
        """Handle a button press event."""
        label = self.pin_map.get(pin, "?")
        logger.info(f"Button {label} pressed (GPIO {pin})")

        # Check for long press
        btn = self._buttons.get(pin)
        if btn:
            press_start = time.time()
            while btn.is_pressed and (time.time() - press_start) < LONG_PRESS_TIME:
                time.sleep(0.05)
            is_long = (time.time() - press_start) >= LONG_PRESS_TIME
        else:
            is_long = False

        if is_long:
            logger.info(f"Button {label} long press detected")

        try:
            self.callback(label, long_press=is_long)
        except Exception as e:
            logger.error(f"Error in button callback: {e}")

    def cleanup(self):
        """Clean up GPIO resources."""
        for btn in self._buttons.values():
            try:
                btn.close()
            except Exception:
                pass
        logger.info("Buttons cleaned up")
