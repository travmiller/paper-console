from typing import Callable


class ButtonDriver:
    """Mock driver for a button."""

    def __init__(self, pin: int = 18):
        self.pin = pin
        self.callback = None
        self.long_press_callback = None
        self.long_press_ready_callback = None
        self.factory_reset_callback = None

    def set_callback(self, callback: Callable[[], None]):
        self.callback = callback

    def set_long_press_callback(self, callback: Callable[[], None]):
        self.long_press_callback = callback

    def set_long_press_ready_callback(self, callback: Callable[[], None]):
        self.long_press_ready_callback = callback

    def set_factory_reset_callback(self, callback: Callable[[], None]):
        self.factory_reset_callback = callback

    def press(self):
        """Simulate a button press."""
        if self.callback:
            self.callback()

    def cleanup(self):
        pass
