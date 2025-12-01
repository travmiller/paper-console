from typing import Callable

class ButtonDriver:
    """
    Mock driver for a button.
    """
    def __init__(self, pin: int = 18):
        self.pin = pin
        self.callback = None
        print(f"[MOCK BUTTON] Initialized on virtual pin {pin}")

    def set_callback(self, callback: Callable[[], None]):
        self.callback = callback

    def press(self):
        """Simulate a button press."""
        print("[MOCK BUTTON] Button pressed (virtual)")
        if self.callback:
            self.callback()

    def cleanup(self):
        pass

