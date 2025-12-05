from typing import Callable


class DialDriver:
    def __init__(self):
        self.current_position = 1
        self.callbacks = []

    def register_callback(self, callback: Callable[[int], None]):
        """Register a function to be called when the dial changes."""
        self.callbacks.append(callback)

    def read_position(self) -> int:
        return self.current_position

    def set_position(self, position: int):
        """Simulates the user turning the dial."""
        if 1 <= position <= 8:
            if self.current_position != position:
                self.current_position = position
                for cb in self.callbacks:
                    cb(position)

    def cleanup(self):
        """Clean up resources."""
        pass
