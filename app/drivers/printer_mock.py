from datetime import datetime

class PrinterDriver:
    # Fixed spacing constants (match serial driver)
    FONT_SIZE = 18  # Increased for better readability
    LINE_HEIGHT = 22  # Adjusted for larger font
    SPACING_SMALL = 4
    SPACING_MEDIUM = 8
    SPACING_LARGE = 16

    def __init__(
        self,
        width: int = 42,  # Characters per line
        port: str = None,
        baudrate: int = 9600,
    ):
        self.width = width
        self.lines_printed = 0
        self.max_lines = 0
        self.font_size = self.FONT_SIZE
        self.line_spacing = self.LINE_HEIGHT - self.FONT_SIZE
        self.line_height = self.LINE_HEIGHT
    
    def _load_font(self):
        """Mock font loading - returns None."""
        return None

    def print_text(self, text: str, style: str = "regular"):
        """Simulates printing styled text.
        
        Handles multi-line text by splitting on newlines. Each line/paragraph
        will be printed separately with the same style.
        
        Available styles: regular, bold, bold_lg, medium, semibold, light, regular_sm
        """
        if not text:
            return
            
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
        
        # Split by newlines to handle multi-line text properly
        lines = text.split('\n')
        for line in lines:
            # Print all lines (including blank lines for spacing)
            print(f"[PRINT] {prefix}{line}")
            self.lines_printed += 1

    def print_header(self, text: str, icon: str = None, icon_size: int = 24):
        """Prints large bold header text in a full-width drawn box (simulated)."""
        text = text.upper()
        inner_width = self.width - 4  # Full width minus borders
        
        # Add icon if provided
        if icon:
            icons = {
                "check": "✓", "home": "⌂", "wifi": "📶", "settings": "⚙",
                "arrow_right": "→", "sun": "☀", "cloud": "☁"
            }
            icon_char = icons.get(icon.lower(), "•")
            header_text = f"{icon_char} {text}"
        else:
            header_text = text
        
        # Simulate the bitmap box with ASCII
        print(f"[PRINT] ┏{'━' * inner_width}┓")
        print(f"[PRINT] ┃{header_text:^{inner_width}}┃")
        print(f"[PRINT] ┗{'━' * inner_width}┛")
        self.lines_printed += 3
    
    def print_subheader(self, text: str):
        """Prints medium-weight subheader."""
        print(f"[PRINT] ▸ {text}")
        self.lines_printed += 1
    
    def print_body(self, text: str):
        """Prints regular body text."""
        self.print_text(text, "regular")
    
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

    def print_article_block(
        self,
        source: str,
        title: str,
        summary: str = "",
        url: str = "",
        qr_size: int = 64,
        title_width: int = 28,
        summary_width: int = 32,
        max_summary_lines: int = 3,
    ):
        """Prints an article with QR code inline on the left (simulated)."""
        print(f"[PRINT] ┌────────┬{'─' * 28}┐")
        print(f"[PRINT] │        │ {source.upper()[:26]:<26} │")
        
        # Wrap title
        words = title.split()
        lines = []
        current = ""
        for word in words:
            if len(current) + len(word) + 1 <= title_width:
                current = f"{current} {word}".strip()
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        
        for i, line in enumerate(lines[:3]):
            if i == 0:
                print(f"[PRINT] │ [QR]   │ {line:<26} │")
            else:
                print(f"[PRINT] │        │ {line:<26} │")
        
        # Summary preview
        if summary:
            print(f"[PRINT] │        │ {summary[:26]:<26} │")
        
        print(f"[PRINT] └────────┴{'─' * 28}┘")
        self.lines_printed += len(lines) + 4
    
    def print_thick_line(self):
        """Prints a bold separator line."""
        print(f"[PRINT] {'━' * self.width}")
        self.lines_printed += 1

    def print_image(self, image):
        """Simulates printing a generic PIL Image."""
        if not image:
            return
        print(f"[PRINT] [IMAGE] Size: {image.size} Mode: {image.mode}")
        # Could attempt ASCII art render here, but size/mode log is sufficient for mock
        self.lines_printed += int(image.height / 24) + 1  # Estimate lines










    def print_icon(self, icon_type: str, size: int = 32):
        """Simulates printing an icon."""
        icons = {
            "sun": "☀", "cloud": "☁", "rain": "🌧", "snow": "❄", 
            "storm": "⛈", "clear": "○", "email": "✉", "mail": "✉",
            "calendar": "📅", "clock": "🕐", "time": "🕐", "wifi": "📶",
            "battery": "🔋", "check": "✓", "checkmark": "✓", "x": "✗",
            "close": "✗", "star": "★", "heart": "♥", "settings": "⚙",
            "gear": "⚙", "home": "⌂", "location": "📍", "pin": "📍",
            "arrow_right": "→", "arrow_left": "←", "arrow_up": "↑", "arrow_down": "↓",
            "user": "👤", "trash": "🗑", "search": "🔍", "menu": "☰",
            "printer": "🖨", "cpu": "💻", "floppy": "💾", "save": "💾",
            "play": "▶", "pause": "⏸", "volume": "🔊", "speaker": "🔊"
        }
        icon = icons.get(icon_type.lower(), "?")
        print(f"[PRINT]     [{icon}]")
        self.lines_printed += 1





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

    def feed_dots(self, dots: int = 12):
        """Simulate dot feed (12 dots ~= half line)."""
        lines = max(1, int(round(dots / 24.0)))
        self.feed(lines)

    def set_cutter_feed(self, lines: int):
        """Set the cutter feed space (mock - just stores the value)."""
        self.cutter_feed_dots = lines * 24

    def close(self):
        """Close the connection."""
        pass
