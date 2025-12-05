class PrinterDriver:
    def __init__(
        self,
        width: int = 32,
        invert: bool = False,
        port: str = None,
        baudrate: int = 9600,
    ):
        self.width = width
        self.invert = invert

    def print_text(self, text: str):
        """Simulates printing a line of text."""
        print(f"[PRINT] {text}")

    def print_line(self):
        """Prints a separator line."""
        print(f"[PRINT] {'-' * self.width}")

    def feed(self, lines: int = 3):
        """Simulates paper feed."""
        for _ in range(lines):
            print("[PRINT] ")

    def print_header(self, text: str):
        """Prints centered header text."""
        padding = max(0, (self.width - len(text)) // 2)
        print(f"[PRINT] {' ' * padding}{text.upper()}")
        self.print_line()

    def flush_buffer(self):
        """Flush the print buffer (for invert mode compatibility)."""
        pass

    def reset_buffer(self):
        """Reset/clear the print buffer."""
        pass

    def feed_direct(self, lines: int = 3):
        """Feed paper directly, bypassing the buffer."""
        self.feed(lines)

    def close(self):
        """Close the connection."""
        pass
