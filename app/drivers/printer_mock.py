class PrinterDriver:
    def __init__(self, width: int = 32):
        self.width = width
        print(f"[MOCK PRINTER] Initialized with width {width}")

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
        # Simple centering logic
        padding = max(0, (self.width - len(text)) // 2)
        print(f"[PRINT] {' ' * padding}{text.upper()}")
        self.print_line()

