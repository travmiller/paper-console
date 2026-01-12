class PrinterDriver:
    # Fixed spacing constants (match serial driver)
    FONT_SIZE = 16  # Increased from 14 to match IBM Plex Mono
    LINE_HEIGHT = 20  # Adjusted for larger font
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

    def print_maze(self, grid: list, cell_size: int = 8):
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

    def print_sudoku(self, grid: list, cell_size: int = 16):
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

    def print_weather_forecast(self, forecast: list):
        """Simulates printing a 7-day weather forecast."""
        icons = {"sun": "☀", "cloud": "☁", "rain": "🌧", "snow": "❄", "storm": "⛈"}
        
        def get_icon(condition):
            condition = (condition or "").lower()
            if "clear" in condition: return "☀"
            if "rain" in condition: return "🌧"
            if "snow" in condition: return "❄"
            if "storm" in condition: return "⛈"
            return "☁"
        
        # Header row
        days = [d.get("day", "--")[:3] for d in forecast[:7]]
        print(f"[PRINT] {' '.join(f'{d:^5}' for d in days)}")
        
        # Icon row
        icons_row = [get_icon(d.get("condition")) for d in forecast[:7]]
        print(f"[PRINT] {' '.join(f'{i:^5}' for i in icons_row)}")
        
        # High temps
        highs = [f"{d.get('high', '--')}°" for d in forecast[:7]]
        print(f"[PRINT] {' '.join(f'{h:^5}' for h in highs)}")
        
        # Low temps
        lows = [f"{d.get('low', '--')}°" for d in forecast[:7]]
        print(f"[PRINT] {' '.join(f'{l:^5}' for l in lows)}")
        
        self.lines_printed += 4

    def print_hourly_forecast(self, hourly_forecast: list):
        """Simulates printing a 24-hour hourly weather forecast."""
        icons = {"sun": "☀", "cloud": "☁", "rain": "🌧", "snow": "❄", "storm": "⛈"}
        
        def get_icon(condition):
            condition = (condition or "").lower()
            if "clear" in condition: return "☀"
            if "rain" in condition: return "🌧"
            if "snow" in condition: return "❄"
            if "storm" in condition: return "⛈"
            return "☁"
        
        # Group into rows of 6 hours each
        hours_per_row = 6
        for i in range(0, len(hourly_forecast), hours_per_row):
            row = hourly_forecast[i:i + hours_per_row]
            
            # Time row
            times = [h.get("time", "--") for h in row]
            print(f"[PRINT] {' '.join(f'{t:^6}' for t in times)}")
            
            # Icon row
            icons_row = [get_icon(h.get("condition")) for h in row]
            print(f"[PRINT] {' '.join(f'{i:^6}' for i in icons_row)}")
            
            # Temp row
            temps = [f"{h.get('temperature', '--')}°" for h in row]
            print(f"[PRINT] {' '.join(f'{t:^6}' for t in temps)}")
            
            self.lines_printed += 3

    def print_progress_bar(self, value: float, max_value: float = 100, 
                         width: int = None, height: int = 12, label: str = ""):
        """Simulates printing a progress bar."""
        if width is None:
            width = self.width - 4
        filled = int((value / max_value) * width) if max_value > 0 else 0
        bar = "█" * filled + "░" * (width - filled)
        label_text = f" {label}" if label else ""
        print(f"[PRINT] [{bar}]{label_text}")
        self.lines_printed += 1

    def print_calendar_grid(self, weeks: int = 4, cell_size: int = 8, 
                           start_date=None, events_by_date: dict = None):
        """Simulates printing a calendar grid."""
        print("[PRINT] S M T W T F S")
        print("[PRINT] ┌─┬─┬─┬─┬─┬─┬─┐")
        for _ in range(weeks):
            print("[PRINT] │ │ │ │ │ │ │ │")
        print("[PRINT] └─┴─┴─┴─┴─┴─┴─┘")
        self.lines_printed += weeks + 3

    def print_timeline(self, items: list, item_height: int = 20):
        """Simulates printing a timeline."""
        for item in items:
            year = item.get('year', '')
            text = item.get('text', '')
            print(f"[PRINT] ● {year}  {text[:30]}")
        self.lines_printed += len(items)

    def print_checkbox(self, checked: bool = False, size: int = 12):
        """Simulates printing a checkbox."""
        checkbox = "[✓]" if checked else "[ ]"
        print(f"[PRINT] {checkbox}", end="")
        self.lines_printed += 0  # Will be on same line as text

    def print_separator(self, style: str = "dots", height: int = 8):
        """Simulates printing a separator."""
        if style == "dots":
            print(f"[PRINT] {'·' * self.width}")
        elif style == "dashed":
            print(f"[PRINT] {'─' * self.width}")
        else:
            print(f"[PRINT] {'~' * self.width}")
        self.lines_printed += 1

    def print_bar_chart(self, bars: list, bar_height: int = 12, width: int = None):
        """Simulates printing a bar chart."""
        for bar in bars:
            label = bar.get('label', '')
            value = bar.get('value', 0)
            max_value = bar.get('max_value', 100)
            bar_len = int((value / max_value) * (self.width - 15)) if max_value > 0 else 0
            bar_str = "█" * bar_len
            print(f"[PRINT] {label[:10]:<10} {bar_str} {value:.0f}")
        self.lines_printed += len(bars)

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

    def set_cutter_feed(self, lines: int):
        """Set the cutter feed space (mock - just stores the value)."""
        self.cutter_feed_dots = lines * 24

    def close(self):
        """Close the connection."""
        pass
