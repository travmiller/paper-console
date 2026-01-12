class PrinterDriver:
    def __init__(
        self,
        width: int = 42,  # Characters per line
        port: str = None,
        baudrate: int = 9600,
        font_size: int = 12,  # Font size in pixels (8-24)
        line_spacing: int = 2,  # Extra pixels between lines
    ):
        self.width = width
        self.lines_printed = 0
        self.max_lines = 0
        self.font_size = font_size
        self.line_spacing = line_spacing
        self.line_height = font_size + line_spacing
    
    def _load_font(self):
        """Mock font loading - returns None."""
        return None

    def print_text(self, text: str, style: str = "regular"):
        """Simulates printing styled text.
        
        Available styles: regular, bold, bold_lg, medium, semibold, light, regular_sm
        """
        style_markers = {
            "regular": "",
            "bold": "**",
            "bold_lg": "▓▓",
            "medium": "░░",
            "semibold": "▒▒",
            "light": "··",
            "regular_sm": "  ",
        }
        marker = style_markers.get(style, "")
        prefix = f"{marker} " if marker else ""
        print(f"[PRINT] {prefix}{text}")
        self.lines_printed += text.count("\n") + 1

    def print_header(self, text: str):
        """Prints large bold header text in a full-width drawn box (simulated)."""
        text = text.upper()
        inner_width = self.width - 4  # Full width minus borders
        
        # Simulate the bitmap box with ASCII
        print(f"[PRINT] ┏{'━' * inner_width}┓")
        print(f"[PRINT] ┃{text:^{inner_width}}┃")
        print(f"[PRINT] ┗{'━' * inner_width}┛")
        self.lines_printed += 3
    
    def print_subheader(self, text: str):
        """Prints medium-weight subheader."""
        print(f"[PRINT] ▸ {text}")
        self.lines_printed += 1
    
    def print_body(self, text: str):
        """Prints regular body text."""
        print(f"[PRINT] {text}")
        self.lines_printed += text.count("\n") + 1
    
    def print_caption(self, text: str):
        """Prints small, light caption text."""
        print(f"[PRINT] ⋅ {text}")
        self.lines_printed += 1
    
    def print_bold(self, text: str):
        """Prints bold text at normal size."""
        print(f"[PRINT] ▪ {text}")
        self.lines_printed += 1

    def print_line(self):
        """Prints a decorative separator line."""
        print(f"[PRINT] {'· ' * (self.width // 2)}")
        self.lines_printed += 1
    
    def print_thick_line(self):
        """Prints a bold separator line."""
        print(f"[PRINT] {'━' * self.width}")
        self.lines_printed += 1

    def print_moon_phase(self, phase: float, size: int = 60):
        """Simulates printing a moon phase graphic."""
        # ASCII art moon phases
        phase_normalized = (phase % 28) / 28.0
        
        if phase_normalized < 0.0625:
            moon = "🌑"  # New Moon
            name = "New Moon"
        elif phase_normalized < 0.1875:
            moon = "🌒"  # Waxing Crescent
            name = "Waxing Crescent"
        elif phase_normalized < 0.3125:
            moon = "🌓"  # First Quarter
            name = "First Quarter"
        elif phase_normalized < 0.4375:
            moon = "🌔"  # Waxing Gibbous
            name = "Waxing Gibbous"
        elif phase_normalized < 0.5625:
            moon = "🌕"  # Full Moon
            name = "Full Moon"
        elif phase_normalized < 0.6875:
            moon = "🌖"  # Waning Gibbous
            name = "Waning Gibbous"
        elif phase_normalized < 0.8125:
            moon = "🌗"  # Last Quarter
            name = "Last Quarter"
        elif phase_normalized < 0.9375:
            moon = "🌘"  # Waning Crescent
            name = "Waning Crescent"
        else:
            moon = "🌑"  # New Moon
            name = "New Moon"
        
        print(f"[PRINT]     ╭───────────╮")
        print(f"[PRINT]     │     {moon}     │")
        print(f"[PRINT]     │  {name:^9} │")
        print(f"[PRINT]     ╰───────────╯")
        self.lines_printed += 4

    def print_maze(self, grid: list, cell_size: int = 4):
        """Simulates printing a maze bitmap."""
        print("[PRINT] ┌─────────────────────────────┐")
        for row in grid:
            line = "│"
            for cell in row:
                line += "██" if cell == 1 else "  "
            line += "│"
            print(f"[PRINT] {line}")
        print("[PRINT] └─────────────────────────────┘")
        self.lines_printed += len(grid) + 2

    def print_sudoku(self, grid: list, cell_size: int = 8):
        """Simulates printing a Sudoku grid bitmap."""
        print("[PRINT] ┌───────┬───────┬───────┐")
        for i, row in enumerate(grid):
            if i > 0 and i % 3 == 0:
                print("[PRINT] ├───────┼───────┼───────┤")
            line = "│"
            for j, val in enumerate(row):
                char = str(val) if val != 0 else "·"
                line += f" {char}"
                if (j + 1) % 3 == 0:
                    line += " │"
            print(f"[PRINT] {line}")
        print("[PRINT] └───────┴───────┴───────┘")
        self.lines_printed += 11

    def feed(self, lines: int = 3):
        """Simulates paper feed."""
        for _ in range(lines):
            print("[PRINT] ")

    def print_qr(self, data: str, size: int = 4, error_correction: str = "M", fixed_size: bool = False):
        """Simulates printing a QR code."""
        # Generate ASCII art representation for visual feedback
        try:
            import qrcode
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=1,
                border=1,
            )
            qr.add_data(data)
            qr.make(fit=True)
            
            # Print as ASCII art using block characters
            print(f"[PRINT] ┌{'─' * (self.width - 2)}┐")
            print(f"[PRINT] │{'QR CODE':^{self.width - 2}}│")
            for row in qr.modules:
                line = "".join("██" if cell else "  " for cell in row)
                # Center the QR code
                print(f"[PRINT] {line[:self.width]}")
            print(f"[PRINT] └{'─' * (self.width - 2)}┘")
            print(f"[PRINT] Data: {data[:30]}{'...' if len(data) > 30 else ''}")
        except ImportError:
            # Fallback if qrcode not installed
            print(f"[PRINT] [QR CODE: {data}]")
        self.lines_printed += 5

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

    def was_truncated(self) -> bool:
        """Check if the last print was truncated due to max lines."""
        return False  # Mock doesn't track this

    def feed_direct(self, lines: int = 3):
        """Feed paper directly, bypassing the buffer."""
        self.feed(lines)

    def close(self):
        """Close the connection."""
        pass
