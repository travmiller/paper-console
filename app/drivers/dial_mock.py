from typing import Callable, Optional

class DialDriver:
    def __init__(self):
        self.current_position = 1
        self.callbacks = []
        print("[MOCK DIAL] Initialized at position 1")

    def register_callback(self, callback: Callable[[int], None]):
        """Register a function to be called when the dial changes."""
        self.callbacks.append(callback)

    def read_position(self) -> int:
        return self.current_position

    def set_position(self, position: int):
        """
        Simulates the user turning the dial.
        This is the 'Virtual' input method.
        """
        if 1 <= position <= 8:
            if self.current_position != position:
                self.current_position = position
                print(f"[MOCK DIAL] Turned to position {position}")
                # Notify listeners
                for cb in self.callbacks:
                    cb(position)
        else:
            print(f"[MOCK DIAL] Invalid position {position}")

