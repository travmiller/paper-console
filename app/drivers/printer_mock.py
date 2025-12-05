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
        self.lines_printed = 0
        self.max_lines = 0

    def print_text(self, text: str):
        """Simulates printing a line of text."""
        print(f"[PRINT] {text}")
        self.lines_printed += text.count("\n") + 1

    def print_line(self):
        """Prints a separator line."""
        print(f"[PRINT] {'-' * self.width}")
        self.lines_printed += 1

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

    def reset_buffer(self, max_lines: int = 0):
        """Reset/clear the print buffer."""
        self.lines_printed = 0
        self.max_lines = max_lines

    def clear_hardware_buffer(self):
        """Clear hardware buffer (no-op for mock)."""
        pass

    def is_max_lines_exceeded(self) -> bool:
        """Check if we've exceeded the maximum print length."""
        if self.max_lines <= 0:
            return False
        return self.lines_printed >= self.max_lines

    def feed_direct(self, lines: int = 3):
        """Feed paper directly, bypassing the buffer."""
        self.feed(lines)

    def close(self):
        """Close the connection."""
        pass
