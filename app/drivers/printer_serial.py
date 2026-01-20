import math
import os
import platform
import random
import time
import unicodedata
from datetime import datetime, date
from typing import List, Optional

import serial
from PIL import Image, ImageDraw, ImageFont
import app.config


class PrinterDriver:
    """
    Real hardware driver for thermal receipt printer (QR204/CSN-A2).
    Uses serial communication via GPIO pins or USB-to-serial adapters.
    """

    # Maximum buffer size to prevent memory issues (roughly 1000 lines)
    MAX_BUFFER_SIZE = 1000

    # Character translation table: maps problematic Unicode chars to ASCII equivalents
    # Using Unicode escapes to prevent formatter corruption
    CHAR_REPLACEMENTS = str.maketrans(
        {
            "\u201c": '"',  # Left double quote "
            "\u201d": '"',  # Right double quote "
            "\u2018": "'",  # Left single quote '
            "\u2019": "'",  # Right single quote '
            "\u2013": "-",  # En dash –
            "\u2014": "-",  # Em dash —
            "\u2026": "...",  # Ellipsis …
            "\u2022": "*",  # Bullet •
            "\u00b0": "o",  # Degree °
            "\u00a9": "(c)",  # Copyright ©
            "\u00ae": "(R)",  # Registered ®
            "\u2122": "(TM)",  # Trademark ™
            "\u00d7": "x",  # Multiplication ×
            "\u00f7": "/",  # Division ÷
            "\u20ac": "EUR",  # Euro €
            "\u00a3": "GBP",  # Pound £
            "\u00a5": "JPY",  # Yen ¥
            "\u00a0": " ",  # Non-breaking space
            "\u200b": "",  # Zero-width space
            "\u200c": "",  # Zero-width non-joiner
            "\u200d": "",  # Zero-width joiner
            "\ufeff": "",  # BOM
        }
    )

    # Printer physical specs
    PRINTER_DPI = 203  # dots per inch
    PRINTER_WIDTH_DOTS = 384  # 58mm paper at 203 DPI

    # Fixed typography and spacing constants (pixels)
    FONT_SIZE = 18  # Base font size for body text (increased for better readability)
    LINE_HEIGHT = 22  # Font size + line spacing (adjusted for larger font)
    SPACING_SMALL = 4  # Tight spacing (after inline elements)
    SPACING_MEDIUM = 8  # Standard spacing (between content blocks)
    SPACING_LARGE = 16  # Section spacing (between modules)

    def __init__(
        self,
        width: int = 42,  # Characters per line
        port: Optional[str] = None,
        baudrate: int = 9600,  # QR204 only supports 9600
    ):
        self.width = width
        self.ser = None
        # Buffer for print operations (prints are always inverted/reversed)
        # Each item is a tuple: ('text', line) or ('feed', count) or ('qr', data)
        self.print_buffer = []
        # Line tracking for max print length
        self.lines_printed = 0
        self.max_lines = 0  # 0 = no limit, set by reset_buffer
        self._max_lines_hit = False  # Flag set when max lines exceeded during flush

        # Cutter feed space (pixels to add at end of print for cutter clearance)
        # Can be updated via set_cutter_feed() method
        self.cutter_feed_dots = 7 * 24  # Default: 7 lines * 24 dots/line = 168 dots

        # Font settings (fixed values)
        self.font_size = self.FONT_SIZE
        self.line_spacing = self.LINE_HEIGHT - self.FONT_SIZE
        self.line_height = self.LINE_HEIGHT

        # Load font family for styled text
        self._fonts = self._load_font_family()

        # Auto-detect serial port if not specified
        if port is None:
            if platform.system() == "Linux":
                # Try GPIO serial first (primary interface)
                possible_ports = [
                    "/dev/serial0",  # GPIO serial - needs console disabled
                    "/dev/ttyUSB0",
                    "/dev/ttyUSB1",
                    "/dev/ttyACM0",
                    "/dev/ttyACM1",
                ]
                # Use the first one that exists
                for p in possible_ports:
                    if os.path.exists(p):
                        port = p
                        break
                if not port:
                    port = "/dev/serial0"  # Default for GPIO serial
            elif platform.system() == "Windows":
                # Windows COM ports
                possible_ports = [f"COM{i}" for i in range(1, 10)]
                port = possible_ports[0]
            else:
                possible_ports = ["/dev/tty.usbserial", "/dev/ttyUSB0"]
                port = possible_ports[0]

        # Initialize serial connection
        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1,
            )

            if self.ser.in_waiting:
                self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            time.sleep(0.5)
            self._initialize_printer()

        except serial.SerialException:
            self.ser = None

    def _load_font_family(self) -> dict:
        """Load IBM Plex Mono font family with multiple weights.

        IBM Plex Mono is a monospace font designed for technical and display purposes.
        Place font files in: web/public/fonts/IBM_Plex_Mono/
        Required files: IBMPlexMono-Medium.ttf (used as base), IBMPlexMono-SemiBold.ttf, IBMPlexMono-Bold.ttf
        Uses Medium as base weight, SemiBold and Bold for headings.
        """
        # Get the project root directory (parent of app/)
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        project_root = os.path.dirname(app_dir)

        fonts = {}

        # Font variants we want to load
        # IBM Plex Mono has: Regular, Medium, SemiBold, Bold
        # Using Medium as base weight, SemiBold and Bold for headings
        font_variants = {
            "regular": "IBMPlexMono-Medium.ttf",  # Medium as base weight
            "bold": "IBMPlexMono-Bold.ttf",  # Bold for headings
            "medium": "IBMPlexMono-Medium.ttf",
            "light": "IBMPlexMono-Medium.ttf",  # Map light to Medium (base weight)
            "semibold": "IBMPlexMono-SemiBold.ttf",  # SemiBold for headings
        }

        # Base paths to search
        base_paths = [
            os.path.join(project_root, "web/public/fonts/IBM_Plex_Mono"),
            os.path.join(project_root, "web/dist/fonts/IBM_Plex_Mono"),
            os.path.join(project_root, "fonts/IBM_Plex_Mono"),  # Alternative location
        ]

        # Load each variant at different sizes
        # Size jumps: +6 for headers, -4 for captions (visible hierarchy)
        for variant_name, filename in font_variants.items():
            font_loaded = False
            for base_path in base_paths:
                font_path = os.path.join(base_path, filename)
                if os.path.exists(font_path):
                    try:
                        # Load at regular size
                        fonts[variant_name] = ImageFont.truetype(
                            font_path, self.font_size
                        )
                        # Load at header size (6px larger for clear hierarchy)
                        fonts[f"{variant_name}_lg"] = ImageFont.truetype(
                            font_path, self.font_size + 6
                        )
                        # Load at small/caption size (3px smaller, but minimum 14px for readability)
                        fonts[f"{variant_name}_sm"] = ImageFont.truetype(
                            font_path, max(14, self.font_size - 3)
                        )
                        font_loaded = True
                        break
                    except Exception:
                        continue

            # Fallback for semibold if SemiBold not found
            if variant_name == "semibold" and not font_loaded:
                # Try using Bold as fallback (heavier than Medium)
                if "bold" in fonts:
                    fonts["semibold"] = fonts["bold"]
                    fonts["semibold_lg"] = fonts.get("bold_lg", fonts["bold"])
                    fonts["semibold_sm"] = fonts.get("bold_sm", fonts["bold"])
                elif "medium" in fonts:
                    fonts["semibold"] = fonts["medium"]
                    fonts["semibold_lg"] = fonts.get("medium_lg", fonts["medium"])
                    fonts["semibold_sm"] = fonts.get("medium_sm", fonts["medium"])

        # Fallback to system fonts if IBM Plex Mono not found
        if "regular" not in fonts:
            # Try common system font locations for IBM Plex Mono
            # Prefer Medium as base weight
            system_font_paths = [
                # Linux - try Medium first
                "/usr/share/fonts/truetype/ibm-plex/IBMPlexMono-Medium.ttf",
                "/usr/share/fonts/TTF/IBMPlexMono-Medium.ttf",
                "~/.fonts/IBMPlexMono-Medium.ttf",
                # Windows - try Medium first
                "C:/Windows/Fonts/IBMPlexMono-Medium.ttf",
                # Fallback to Regular if Medium not found
                "/usr/share/fonts/truetype/ibm-plex/IBMPlexMono-Regular.ttf",
                "/usr/share/fonts/TTF/IBMPlexMono-Regular.ttf",
                "~/.fonts/IBMPlexMono-Regular.ttf",
                "C:/Windows/Fonts/IBMPlexMono-Regular.ttf",
                "C:/Windows/Fonts/ibmplexmono.ttf",
                # macOS
                "~/Library/Fonts/IBMPlexMono-Medium.ttf",
                "/Library/Fonts/IBMPlexMono-Medium.ttf",
                "~/Library/Fonts/IBMPlexMono-Regular.ttf",
                "/Library/Fonts/IBMPlexMono-Regular.ttf",
            ]
            for path in system_font_paths:
                expanded_path = os.path.expanduser(path)
                if os.path.exists(expanded_path):
                    try:
                        fonts["regular"] = ImageFont.truetype(
                            expanded_path, self.font_size
                        )
                        # Try to find Bold and SemiBold variants for headings
                        bold_path = expanded_path.replace("Regular", "Bold").replace(
                            "Medium", "Bold"
                        )
                        semibold_path = expanded_path.replace(
                            "Regular", "SemiBold"
                        ).replace("Medium", "SemiBold")
                        fonts["bold"] = (
                            ImageFont.truetype(bold_path, self.font_size)
                            if os.path.exists(bold_path)
                            else fonts["regular"]
                        )
                        fonts["semibold"] = (
                            ImageFont.truetype(semibold_path, self.font_size)
                            if os.path.exists(semibold_path)
                            else fonts["bold"]
                        )
                        fonts["regular_lg"] = ImageFont.truetype(
                            expanded_path, self.font_size + 6
                        )
                        fonts["regular_sm"] = ImageFont.truetype(
                            expanded_path, max(14, self.font_size - 3)
                        )
                        break
                    except Exception:
                        continue

            # If still not found, try generic monospace fonts
            if "regular" not in fonts:
                fallback_paths = [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
                    "C:/Windows/Fonts/consola.ttf",
                    "C:/Windows/Fonts/cour.ttf",
                ]
            for path in fallback_paths:
                if os.path.exists(path):
                    try:
                        fonts["regular"] = ImageFont.truetype(path, self.font_size)
                        fonts["bold"] = fonts["regular"]  # No bold variant
                        fonts["regular_lg"] = ImageFont.truetype(
                            path, self.font_size + 6
                        )
                        fonts["regular_sm"] = ImageFont.truetype(
                            path, max(14, self.font_size - 3)
                        )
                        break
                    except Exception:
                        continue

        # Ultimate fallback
        if "regular" not in fonts:
            try:
                default_font = ImageFont.load_default()
                fonts["regular"] = default_font
                fonts["bold"] = default_font
            except Exception:
                pass

        return fonts

    def _get_font(self, style: str = "regular") -> ImageFont.FreeTypeFont:
        """Get a font by style name."""
        return self._fonts.get(style, self._fonts.get("regular"))

    def _wrap_text_by_width(
        self, text: str, font: ImageFont.FreeTypeFont, max_width_pixels: int
    ) -> List[str]:
        """Wrap text to fit within max_width_pixels using font metrics.

        Args:
            text: Text to wrap
            font: PIL ImageFont to measure text width
            max_width_pixels: Maximum width in pixels (accounting for margins)

        Returns:
            List of wrapped lines
        """
        if not text:
            return []

        # Account for left margin (2px) and right margin (2px)
        available_width = max_width_pixels - 4

        lines = []
        words = text.split()
        current_line = ""

        for word in words:
            # Test if adding this word fits
            test_line = current_line + (" " if current_line else "") + word

            # Measure text width using font metrics
            if font:
                try:
                    # Use getbbox for accurate measurement (PIL 8.0+)
                    bbox = font.getbbox(test_line)
                    text_width = bbox[2] - bbox[0] if bbox else 0
                except AttributeError:
                    # Fallback for older PIL versions
                    try:
                        text_width = font.getlength(test_line)
                    except AttributeError:
                        # Ultimate fallback: estimate based on character count
                        text_width = (
                            len(test_line)
                            * (font.size if hasattr(font, "size") else self.font_size)
                            * 0.6
                        )
            else:
                # No font: estimate based on character count
                text_width = len(test_line) * self.font_size * 0.6

            if text_width <= available_width:
                current_line = test_line
            else:
                # Current line is full, start new line
                if current_line:
                    lines.append(current_line)

                # Measure word width to decide if we need to break it
                if font:
                    try:
                        bbox = font.getbbox(word)
                        word_width = bbox[2] - bbox[0] if bbox else 0
                    except AttributeError:
                        try:
                            word_width = font.getlength(word)
                        except AttributeError:
                            word_width = (
                                len(word)
                                * (
                                    font.size
                                    if hasattr(font, "size")
                                    else self.font_size
                                )
                                * 0.6
                            )
                else:
                    word_width = len(word) * self.font_size * 0.6

                # Only break words if they're longer than a full line (like URLs)
                if word_width > available_width:
                    # Word is too long for even a single line, break it character by character
                    current_word = ""
                    for char in word:
                        test_char = current_word + char
                        if font:
                            try:
                                bbox = font.getbbox(test_char)
                                char_width = bbox[2] - bbox[0] if bbox else 0
                            except AttributeError:
                                try:
                                    char_width = font.getlength(test_char)
                                except AttributeError:
                                    char_width = (
                                        len(test_char)
                                        * (
                                            font.size
                                            if hasattr(font, "size")
                                            else self.font_size
                                        )
                                        * 0.6
                                    )
                        else:
                            char_width = len(test_char) * self.font_size * 0.6

                        if char_width <= available_width:
                            current_word = test_char
                        else:
                            if current_word:
                                lines.append(current_word)
                            current_word = char
                    current_line = current_word
                else:
                    # Word fits on a line (even if slightly over), put it on its own line
                    current_line = word

        if current_line:
            lines.append(current_line)

        return lines if lines else [""]

    def _render_text_bitmap(self, lines: list) -> Image.Image:
        """Render text lines to a bitmap image, rotated 180° for upside-down printing."""
        if not lines:
            return None

        # Calculate image dimensions
        height = len(lines) * self.line_height + 4  # +4 for padding
        width = self.PRINTER_WIDTH_DOTS

        # Create white background image
        img = Image.new("1", (width, height), 1)  # 1-bit, white background
        draw = ImageDraw.Draw(img)

        # Draw lines in order - after 180° rotation, first line will be at bottom
        # (Content appears at tear-off edge, headers appear after when viewing upside-down)
        y = 2  # Start with small padding
        for line in lines:
            if self._font:
                draw.text((2, y), line, font=self._font, fill=0)  # Black text
            else:
                draw.text((2, y), line, fill=0)
            y += self.line_height

        # Rotate 180° for upside-down printing
        img = img.rotate(180)

        return img

    def _get_line_height_for_style(self, style: str) -> int:
        """Get the line height for a given font style."""
        font = self._get_font(style)
        if font and hasattr(font, "size"):
            return font.size + self.line_spacing
        # Estimate based on style name
        if "_lg" in style:
            return self.font_size + 6 + self.line_spacing
        elif "_sm" in style:
            return max(14, self.font_size - 3) + self.line_spacing
        return self.line_height

    def _render_unified_bitmap(self, ops: list) -> Image.Image:
        """Render ALL buffer operations into one unified bitmap.

        This is faster than multiple small bitmaps because:
        - Single GS v 0 command overhead
        - Continuous data stream to printer

        Supports styled text with different fonts and sizes.
        Uses fixed spacing constants for consistency:
        - SPACING_SMALL (4px): after inline elements
        - SPACING_MEDIUM (8px): between content blocks
        - SPACING_LARGE (16px): between sections/modules
        """
        import qrcode as qr_lib

        if not ops:
            return None

        # First pass: calculate total height needed
        # Note: bitmap is rotated 180° before printing, so:
        #   - Top of bitmap (y=0) = printed LAST (end of print)
        #   - Bottom of bitmap = printed FIRST (start of print)
        # We want content at TOP (printed last) and padding at BOTTOM (printed first)
        # So we calculate content height, then add 5 lines padding at the end
        total_height = 0  # Start with content height only
        last_spacing = (
            0  # Track spacing added by last operation to remove it (start padding)
        )

        for op_type, op_data in ops:
            if op_type == "styled":
                clean_text = self._sanitize_text(op_data["text"])
                style = op_data.get("style", "regular")
                font = self._get_font(style)
                line_height = self._get_line_height_for_style(style)

                # Calculate wrapped lines for accurate height
                paragraphs = clean_text.split("\n")
                total_wrapped_lines = 0
                for paragraph in paragraphs:
                    wrapped_lines = self._wrap_text_by_width(
                        paragraph, font, self.PRINTER_WIDTH_DOTS
                    )
                    total_wrapped_lines += len(wrapped_lines)

                total_height += total_wrapped_lines * line_height
                last_spacing = 0  # Text has no trailing spacing
            elif op_type == "text":
                clean_text = self._sanitize_text(op_data)
                font = self._get_font("regular")

                # Calculate wrapped lines for accurate height
                paragraphs = clean_text.split("\n")
                total_wrapped_lines = 0
                for paragraph in paragraphs:
                    wrapped_lines = self._wrap_text_by_width(
                        paragraph, font, self.PRINTER_WIDTH_DOTS
                    )
                    total_wrapped_lines += len(wrapped_lines)

                total_height += total_wrapped_lines * self.line_height
                last_spacing = 0
            elif op_type == "box":
                style = op_data.get("style", "bold_lg")
                padding = op_data.get("padding", self.SPACING_MEDIUM)
                border = op_data.get("border", 2)
                icon_type = op_data.get("icon")
                text_height = self._get_line_height_for_style(style)
                icon_size = op_data.get("icon_size", 24) if icon_type else 0
                box_height = (
                    border + padding + max(text_height, icon_size) + padding + border
                )
                # +2 accounts for the box_y = y + 2 margin in the drawing code
                total_height += 2 + box_height + self.SPACING_MEDIUM
                last_spacing = self.SPACING_MEDIUM
            elif op_type == "moon":
                size = op_data.get("size", 60)
                # SPACING_SMALL accounts for moon_y = y + SPACING_SMALL in drawing
                total_height += self.SPACING_SMALL + size + self.SPACING_MEDIUM
                last_spacing = self.SPACING_MEDIUM
            elif op_type == "sun_path":
                height = op_data.get("height", 120)
                # SPACING_SMALL accounts for sun_path_y = y + SPACING_SMALL in drawing
                total_height += self.SPACING_SMALL + height + self.SPACING_MEDIUM
                last_spacing = self.SPACING_MEDIUM
            elif op_type == "maze":
                grid = op_data.get("grid", [])
                cell_size = op_data.get("cell_size", 4)
                if grid:
                    maze_height = len(grid) * cell_size
                    # SPACING_SMALL accounts for maze_y = y + SPACING_SMALL in drawing
                    total_height += (
                        self.SPACING_SMALL + maze_height + self.SPACING_MEDIUM
                    )
                    last_spacing = self.SPACING_MEDIUM
            elif op_type == "sudoku":
                grid = op_data.get("grid", [])
                cell_size = op_data.get("cell_size", 8)
                if grid:
                    sudoku_size = 9 * cell_size + self.SPACING_SMALL
                    # SPACING_SMALL accounts for sudoku_y = y + SPACING_SMALL in drawing
                    total_height += (
                        self.SPACING_SMALL + sudoku_size + self.SPACING_MEDIUM
                    )
                    last_spacing = self.SPACING_MEDIUM
            elif op_type == "icon":
                icon_type = op_data.get("type", "sun")
                size = op_data.get("size", 32)
                # SPACING_SMALL accounts for icon_y = y + SPACING_SMALL in drawing
                total_height += self.SPACING_SMALL + size + self.SPACING_SMALL
                last_spacing = self.SPACING_SMALL
            elif op_type == "weather_forecast":
                # Day height is 114px (as set in _draw_weather_forecast, updated for 24px icon)
                total_height += 114 + self.SPACING_MEDIUM
                last_spacing = self.SPACING_MEDIUM
            elif op_type == "hourly_forecast":
                hourly_forecast = op_data.get("hourly_forecast", [])
                # Calculate actual height: 4 hours per row, 86px entry height, 10px row spacing
                hours_per_row = 4
                entry_height = 86
                row_spacing = 10
                num_rows = (len(hourly_forecast) + hours_per_row - 1) // hours_per_row
                # Total height = (num_rows * entry_height) + ((num_rows - 1) * row_spacing)
                if num_rows > 0:
                    forecast_height = (num_rows * entry_height) + ((num_rows - 1) * row_spacing)
                else:
                    forecast_height = 0
                total_height += forecast_height + self.SPACING_MEDIUM
                last_spacing = self.SPACING_MEDIUM
            elif op_type == "progress_bar":
                height = op_data.get("height", 12)
                total_height += height + self.SPACING_SMALL
                last_spacing = self.SPACING_SMALL
            elif op_type == "calendar_grid":
                weeks = op_data.get("weeks", 4)
                cell_size = op_data.get("cell_size", 8)
                # Account for header (12px) + weeks * cell_size + spacing
                grid_height = 12 + weeks * cell_size + self.SPACING_SMALL
                total_height += grid_height + self.SPACING_MEDIUM
                last_spacing = self.SPACING_MEDIUM
            elif op_type == "calendar_day_timeline":
                height = op_data.get("height", 120)
                total_height += height + self.SPACING_MEDIUM
                last_spacing = self.SPACING_MEDIUM
            elif op_type == "timeline":
                items = op_data.get("items", [])
                item_height = op_data.get("item_height", 20)
                total_height += len(items) * item_height + self.SPACING_MEDIUM
                last_spacing = self.SPACING_MEDIUM
            elif op_type == "checkbox":
                size = op_data.get("size", 12)
                total_height += size + 2
                last_spacing = 2
            elif op_type == "separator":
                height = op_data.get("height", self.SPACING_MEDIUM)
                total_height += height + self.SPACING_SMALL
                last_spacing = self.SPACING_SMALL
            elif op_type == "bar_chart":
                bars = op_data.get("bars", [])
                bar_height = op_data.get("bar_height", 12)
                chart_height = (
                    len(bars) * (bar_height + self.SPACING_SMALL) + self.SPACING_MEDIUM
                )
                total_height += chart_height
                last_spacing = self.SPACING_MEDIUM
            elif op_type == "feed":
                total_height += op_data * self.SPACING_LARGE
                last_spacing = op_data * self.SPACING_LARGE
            elif op_type == "article_block":
                qr_size = op_data.get("qr_size", 64)
                qr_img = self._generate_qr_image(op_data.get("url", ""), 2, "L", True)
                if qr_img:
                    qr_img = qr_img.resize((qr_size, qr_size), Image.NEAREST)
                op_data["_qr_img"] = qr_img

                source_height = self._get_line_height_for_style("caption")
                title_lines = op_data.get("title_lines", 1)
                title_height = title_lines * self._get_line_height_for_style("bold")
                summary_lines = op_data.get("summary_lines", 0)
                summary_height = summary_lines * self._get_line_height_for_style(
                    "regular_sm"
                )

                text_height = (
                    source_height + title_height + summary_height + self.SPACING_SMALL
                )
                block_height = max(qr_size + self.SPACING_SMALL, text_height)
                total_height += block_height + self.SPACING_MEDIUM
                last_spacing = self.SPACING_MEDIUM
            elif op_type == "qr":
                qr_img = self._generate_qr_image(
                    op_data["data"],
                    op_data["size"],
                    op_data["ec"],
                    op_data.get("fixed", False),
                )
                op_data["_qr_img"] = qr_img
                if qr_img:
                    total_height += qr_img.height + self.SPACING_SMALL
                    last_spacing = self.SPACING_SMALL

        # Remove last operation's trailing spacing (it becomes START padding after 180° rotation)
        total_height -= last_spacing

        # Add safety buffer to account for any calculation discrepancies
        # This prevents content from being cut off due to rounding or wrapping differences
        # Use a larger buffer to ensure all content fits
        total_height += self.SPACING_LARGE * 2  # 32px safety buffer

        # Add 7 lines (168 dots) of padding at the TOP of original bitmap (y=0)
        # After 180° rotation: top of original → bottom of rotated → printed LAST (end spacing)
        # This provides consistent spacing at the end of every print job
        padding_dots = 7 * 24  # 168 dots
        total_height += padding_dots

        # Create the unified image
        width = self.PRINTER_WIDTH_DOTS
        img = Image.new("1", (width, total_height), 1)  # White background
        draw = ImageDraw.Draw(img)

        # Second pass: draw everything
        # Start drawing content BELOW the padding (at top of original bitmap)
        # After 180° rotation:
        #   - Padding (y=0 to y=120) → bottom of rotated → printed LAST ✓
        #   - Content (y=120+) → top of rotated → printed FIRST ✓
        y = padding_dots  # Start content below padding

        for op_type, op_data in ops:
            if op_type == "styled":
                clean_text = self._sanitize_text(op_data["text"])
                style = op_data.get("style", "regular")
                font = self._get_font(style)
                line_height = self._get_line_height_for_style(style)

                # Split by newlines first, then wrap each paragraph
                paragraphs = clean_text.split("\n")
                for paragraph in paragraphs:
                    # Wrap each paragraph to fit printer width
                    wrapped_lines = self._wrap_text_by_width(paragraph, font, width)
                    for line in wrapped_lines:
                        if font:
                            draw.text((2, y), line, font=font, fill=0)
                        else:
                            draw.text((2, y), line, fill=0)
                        y += line_height
            elif op_type == "text":
                # Legacy support
                clean_text = self._sanitize_text(op_data)
                font = self._get_font("regular")
                # Split by newlines first, then wrap each paragraph
                paragraphs = clean_text.split("\n")
                for paragraph in paragraphs:
                    # Wrap each paragraph to fit printer width
                    wrapped_lines = self._wrap_text_by_width(paragraph, font, width)
                    for line in wrapped_lines:
                        if font:
                            draw.text((2, y), line, font=font, fill=0)
                        else:
                            draw.text((2, y), line, fill=0)
                        y += self.line_height
                        self.lines_printed += 1
            elif op_type == "box":
                # Draw a full-width box with text centered inside
                text = self._sanitize_text(op_data.get("text", ""))
                style = op_data.get("style", "bold_lg")
                padding = op_data.get("padding", self.SPACING_MEDIUM)
                border = op_data.get("border", 2)
                icon_type = op_data.get("icon")
                icon_size = op_data.get("icon_size", 24) if icon_type else 0
                font = self._get_font(style)
                text_height = self._get_line_height_for_style(style)

                box_width = width - self.SPACING_SMALL
                box_height = max(text_height, icon_size) + (padding * 2) + (border * 2)
                box_x = 2
                box_y = y + 2

                # Draw outer rectangle (black border)
                draw.rectangle(
                    [box_x, box_y, box_x + box_width, box_y + box_height], fill=0
                )
                # Draw inner rectangle (white) - creates border effect
                draw.rectangle(
                    [
                        box_x + border,
                        box_y + border,
                        box_x + box_width - border,
                        box_y + box_height - border,
                    ],
                    fill=1,
                )

                # Calculate text width
                if font:
                    bbox = font.getbbox(text)
                    text_width = bbox[2] - bbox[0] if bbox else len(text) * 10
                else:
                    text_width = len(text) * 10

                icon_spacing = 6 if icon_type else 0
                total_content_width = (
                    text_width + icon_size + icon_spacing if icon_type else text_width
                )

                content_start_x = box_x + (box_width - total_content_width) // 2
                content_y = box_y + border + padding

                if icon_type:
                    icon_x = content_start_x
                    icon_y = content_y + (text_height - icon_size) // 2
                    self._draw_icon(draw, icon_x, icon_y, icon_type, icon_size)

                text_x = (
                    content_start_x + icon_size + icon_spacing
                    if icon_type
                    else content_start_x
                )
                text_y = content_y
                if font:
                    draw.text((text_x, text_y), text, font=font, fill=0)
                else:
                    draw.text((text_x, text_y), text, fill=0)

                # +2 matches the box_y = y + 2 offset
                y += 2 + box_height + self.SPACING_MEDIUM
            elif op_type == "moon":
                phase = op_data.get("phase", 0)
                size = op_data.get("size", 60)
                moon_x = (width - size) // 2
                moon_y = y + self.SPACING_SMALL
                self._draw_moon_phase(draw, moon_x, moon_y, size, phase)
                y += self.SPACING_SMALL + size + self.SPACING_MEDIUM
            elif op_type == "sun_path":
                sun_path = op_data.get("sun_path", [])
                sunrise = op_data.get("sunrise")
                sunset = op_data.get("sunset")
                current_time = op_data.get("current_time")
                current_altitude = op_data.get("current_altitude", 0)
                sunrise_time = op_data.get("sunrise_time", "")
                sunset_time = op_data.get("sunset_time", "")
                day_length = op_data.get("day_length", "")
                path_height = op_data.get("height", 120)
                path_x = self.SPACING_SMALL
                path_y = y + self.SPACING_SMALL
                path_width = width - (2 * self.SPACING_SMALL)
                self._draw_sun_path(
                    draw,
                    path_x,
                    path_y,
                    path_width,
                    path_height,
                    sun_path,
                    sunrise,
                    sunset,
                    current_time,
                    current_altitude,
                    sunrise_time,
                    sunset_time,
                    day_length,
                    self._get_font("bold"),
                    self._get_font("regular_sm"),
                    self._get_font("light"),
                )
                y += self.SPACING_SMALL + path_height + self.SPACING_MEDIUM
            elif op_type == "maze":
                grid = op_data.get("grid", [])
                cell_size = op_data.get("cell_size", 4)
                if grid:
                    maze_width = len(grid[0]) * cell_size if grid else 0
                    maze_height = len(grid) * cell_size
                    maze_x = (width - maze_width) // 2
                    maze_y = y + self.SPACING_SMALL
                    self._draw_maze(draw, maze_x, maze_y, grid, cell_size)
                    y += self.SPACING_SMALL + maze_height + self.SPACING_MEDIUM
            elif op_type == "sudoku":
                grid = op_data.get("grid", [])
                cell_size = op_data.get("cell_size", 8)
                font = self._get_font("regular")
                if grid:
                    sudoku_size = 9 * cell_size + self.SPACING_SMALL
                    sudoku_x = (width - sudoku_size) // 2
                    sudoku_y = y + self.SPACING_SMALL
                    self._draw_sudoku_grid(
                        draw, sudoku_x, sudoku_y, grid, cell_size, font
                    )
                    y += self.SPACING_SMALL + sudoku_size + self.SPACING_MEDIUM
            elif op_type == "icon":
                icon_type = op_data.get("type", "sun")
                size = op_data.get("size", 32)
                icon_x = (width - size) // 2
                icon_y = y + self.SPACING_SMALL
                self._draw_icon(draw, icon_x, icon_y, icon_type, size)
                y += self.SPACING_SMALL + size + self.SPACING_SMALL
            elif op_type == "weather_forecast":
                forecast = op_data.get("forecast", [])
                self._draw_weather_forecast(draw, 0, y, width, forecast)
                # Day height is 114px (as set in _draw_weather_forecast, updated for 24px icon)
                y += 114 + self.SPACING_MEDIUM
            elif op_type == "hourly_forecast":
                hourly_forecast = op_data.get("hourly_forecast", [])
                self._draw_hourly_forecast(draw, 0, y, width, hourly_forecast)
                # Calculate actual height: 4 hours per row, 86px entry height, 10px row spacing
                hours_per_row = 4
                entry_height = 86
                row_spacing = 10
                num_rows = (len(hourly_forecast) + hours_per_row - 1) // hours_per_row
                # Total height = (num_rows * entry_height) + ((num_rows - 1) * row_spacing)
                if num_rows > 0:
                    total_height = (num_rows * entry_height) + ((num_rows - 1) * row_spacing)
                else:
                    total_height = 0
                y += total_height + self.SPACING_MEDIUM
            elif op_type == "progress_bar":
                value = op_data.get("value", 0)
                max_value = op_data.get("max_value", 100)
                bar_width = op_data.get("width", width - self.SPACING_MEDIUM)
                bar_height = op_data.get("height", 12)
                label = op_data.get("label", "")
                bar_x = (width - bar_width) // 2
                bar_y = y + self.SPACING_SMALL
                self._draw_progress_bar(
                    draw,
                    bar_x,
                    bar_y,
                    bar_width,
                    bar_height,
                    value,
                    max_value,
                    label,
                    self._get_font("regular_sm"),
                )
                y += bar_height + self.SPACING_MEDIUM
            elif op_type == "calendar_grid":
                weeks = op_data.get("weeks", 4)
                requested_cell_size = op_data.get("cell_size", 8)
                start_date = op_data.get("start_date")
                events_by_date = op_data.get("events_by_date", {})
                highlight_date = op_data.get("highlight_date")
                month_start = op_data.get("month_start")
                month_end = op_data.get("month_end")

                # Calculate full width available (minus margins)
                available_width = width - (2 * self.SPACING_SMALL)
                # Calculate cell size to fill full width (7 days)
                cell_size = available_width // 7

                grid_x = self.SPACING_SMALL
                grid_y = y + self.SPACING_SMALL
                self._draw_calendar_grid(
                    draw,
                    grid_x,
                    grid_y,
                    weeks,
                    cell_size,
                    start_date,
                    events_by_date,
                    self._get_font("regular_sm"),
                    highlight_date,
                    month_start,
                    month_end,
                )
                grid_height = 12 + weeks * cell_size + self.SPACING_SMALL
                y += grid_height + self.SPACING_MEDIUM
            elif op_type == "calendar_day_timeline":
                day = op_data.get("day")
                events = op_data.get("events", [])
                compact = op_data.get("compact", False)
                timeline_height = op_data.get("height", 120)
                timeline_x = self.SPACING_SMALL
                timeline_y = y + self.SPACING_SMALL
                self._draw_calendar_day_timeline(
                    draw,
                    timeline_x,
                    timeline_y,
                    width - 2 * self.SPACING_SMALL,
                    timeline_height,
                    day,
                    events,
                    compact,
                    self._get_font("regular"),
                    self._get_font("regular_sm"),
                )
                y += timeline_height + self.SPACING_MEDIUM
            elif op_type == "timeline":
                items = op_data.get("items", [])
                item_height = op_data.get("item_height", 20)
                timeline_x = self.SPACING_MEDIUM
                timeline_y = y + self.SPACING_SMALL
                self._draw_timeline(
                    draw,
                    timeline_x,
                    timeline_y,
                    items,
                    item_height,
                    self._get_font("regular"),
                )
                y += len(items) * item_height + self.SPACING_MEDIUM
            elif op_type == "checkbox":
                checked = op_data.get("checked", False)
                size = op_data.get("size", 12)
                checkbox_x = self.SPACING_SMALL
                checkbox_y = y + 2
                self._draw_checkbox(draw, checkbox_x, checkbox_y, size, checked)
                y += size + self.SPACING_SMALL
            elif op_type == "separator":
                style = op_data.get("style", "dots")
                sep_height = op_data.get("height", self.SPACING_MEDIUM)
                sep_x = self.SPACING_SMALL
                sep_y = y + 2
                self._draw_separator(
                    draw, sep_x, sep_y, width - self.SPACING_MEDIUM, sep_height, style
                )
                y += sep_height + self.SPACING_SMALL
            elif op_type == "bar_chart":
                bars = op_data.get("bars", [])
                bar_height = op_data.get("bar_height", 12)
                chart_width = op_data.get("width", width - self.SPACING_MEDIUM)
                chart_x = (width - chart_width) // 2
                chart_y = y + self.SPACING_SMALL
                self._draw_bar_chart(
                    draw,
                    chart_x,
                    chart_y,
                    chart_width,
                    bar_height,
                    bars,
                    self._get_font("regular_sm"),
                )
                y += len(bars) * (bar_height + self.SPACING_SMALL) + self.SPACING_MEDIUM
            elif op_type == "feed":
                # feed(n) adds n * SPACING_LARGE for module separation
                y += op_data * self.SPACING_LARGE
            elif op_type == "article_block":
                qr_size = op_data.get("qr_size", 64)
                qr_img = op_data.get("_qr_img")
                qr_x = self.SPACING_SMALL
                qr_y = y + 2
                text_x = qr_size + 12
                text_y = y + 2

                if qr_img:
                    img.paste(qr_img, (qr_x, qr_y))

                source = op_data.get("source", "")
                source_font = self._get_font("caption")
                source_height = self._get_line_height_for_style("caption")
                if source and source_font:
                    draw.text(
                        (text_x, text_y), source.upper()[:24], font=source_font, fill=0
                    )
                text_y += source_height

                title_font = self._get_font("bold")
                title_line_height = self._get_line_height_for_style("bold")
                title_lines = op_data.get("title_wrapped", [op_data.get("title", "")])
                for line in title_lines:
                    if title_font:
                        draw.text((text_x, text_y), line, font=title_font, fill=0)
                    text_y += title_line_height

                summary_lines = op_data.get("summary_wrapped", [])
                summary_font = self._get_font("regular_sm")
                summary_line_height = self._get_line_height_for_style("regular_sm")
                for line in summary_lines:
                    if summary_font:
                        draw.text((text_x, text_y), line, font=summary_font, fill=0)
                    text_y += summary_line_height

                text_height = text_y - (y + 2)
                block_height = max(qr_size + self.SPACING_SMALL, text_height)
                y += block_height + self.SPACING_MEDIUM
            elif op_type == "qr":
                qr_img = op_data.get("_qr_img")
                if qr_img:
                    img.paste(qr_img, (self.SPACING_SMALL, y + 2))
                    y += qr_img.height + self.SPACING_SMALL

        # Rotate 180° for upside-down printing
        img = img.rotate(180)

        return img

    def _draw_moon_phase(
        self, draw: ImageDraw.Draw, x: int, y: int, size: int, phase: float
    ):
        """Draw a moon phase graphic with smooth terminator and surface detail.

        Args:
            draw: ImageDraw object
            x, y: Top-left corner of bounding box
            size: Diameter of moon in pixels
            phase: Moon phase value (0-28 day cycle)
                   0/28 = New Moon (dark)
                   7 = First Quarter (right half lit)
                   14 = Full Moon (fully lit)
                   21 = Last Quarter (left half lit)
        """
        # Normalize phase to 0-1 (0 = new, 0.5 = full, 1 = new)
        phase_normalized = (phase % 28) / 28.0

        # Calculate illumination (0 = new moon, 1 = full moon)
        # illumination follows a cosine curve
        illumination = (1 - math.cos(phase_normalized * 2 * math.pi)) / 2

        center_x = x + size // 2
        center_y = y + size // 2
        radius = size // 2
        inner_radius = radius - 2  # Account for outline

        # Draw the moon outline (black circle)
        draw.ellipse([x, y, x + size, y + size], outline=0, width=2)

        # Handle new moon (completely dark)
        if illumination < 0.01:
            # Just draw the outline, leave interior dark
            return

        # Fill the whole moon white first (lit portion)
        draw.ellipse([x + 2, y + 2, x + size - 2, y + size - 2], fill=1)

        # Calculate terminator position using proper geometry
        # The terminator is a vertical line that moves across the moon
        # At new moon: terminator at right edge (illumination = 0)
        # At full moon: terminator at left edge (illumination = 1)

        # Terminator X position: moves from right edge to left edge as illumination increases
        # At illumination=0 (new): terminator_x = right edge
        # At illumination=1 (full): terminator_x = left edge
        terminator_x = center_x - (illumination * 2 - 1) * inner_radius

        # Draw shadow efficiently using pixel-by-pixel for smooth terminator
        if phase_normalized < 0.5:
            # Waxing: right side illuminated, left side dark
            # Shadow is on the left side (px < terminator_x)
            for py in range(y + 2, y + size - 2):
                for px in range(x + 2, min(int(terminator_x) + 1, x + size - 2)):
                    dx = px - center_x
                    dy = py - center_y
                    dist_sq = dx * dx + dy * dy

                    # Check if point is within moon circle and in shadow
                    if dist_sq <= inner_radius * inner_radius and px < terminator_x:
                        draw.point((px, py), fill=0)
        else:
            # Waning: left side illuminated, right side dark
            # Shadow is on the right side (px > terminator_x)
            for py in range(y + 2, y + size - 2):
                for px in range(max(int(terminator_x), x + 2), x + size - 2):
                    dx = px - center_x
                    dy = py - center_y
                    dist_sq = dx * dx + dy * dy

                    # Check if point is within moon circle and in shadow
                    if dist_sq <= inner_radius * inner_radius and px > terminator_x:
                        draw.point((px, py), fill=0)

        # Add subtle surface texture (craters) for realism
        # Only add texture to the lit portion
        random.seed(int(phase * 100))  # Deterministic based on phase

        num_craters = max(3, size // 20)  # Scale with moon size
        for _ in range(num_craters):
            # Random position within moon circle
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(0, inner_radius * 0.7)  # Keep craters away from edge
            crater_x = int(center_x + dist * math.cos(angle))
            crater_y = int(center_y + dist * math.sin(angle))

            # Check if crater is within moon bounds
            dx = crater_x - center_x
            dy = crater_y - center_y
            if dx * dx + dy * dy > inner_radius * inner_radius:
                continue

            # Only draw crater if it's in the lit portion
            if phase_normalized < 0.5:
                # Waxing: right side lit (crater_x > terminator_x)
                if crater_x > terminator_x:
                    crater_size = random.randint(1, max(1, size // 30))
                    draw.ellipse(
                        [
                            crater_x - crater_size,
                            crater_y - crater_size,
                            crater_x + crater_size,
                            crater_y + crater_size,
                        ],
                        fill=0,
                        outline=1,
                        width=1,
                    )
            else:
                # Waning: left side lit (crater_x < terminator_x)
                if crater_x < terminator_x:
                    crater_size = random.randint(1, max(1, size // 30))
                    draw.ellipse(
                        [
                            crater_x - crater_size,
                            crater_y - crater_size,
                            crater_x + crater_size,
                            crater_y + crater_size,
                        ],
                        fill=0,
                        outline=1,
                        width=1,
                    )

        # Redraw outline to ensure clean edges
        draw.ellipse([x, y, x + size, y + size], outline=0, width=2)

    def _draw_maze(
        self,
        draw: ImageDraw.Draw,
        x: int,
        y: int,
        grid: List[List[int]],
        cell_size: int,
    ):
        """Draw a maze as a bitmap.

        Args:
            draw: ImageDraw object
            x, y: Top-left corner of maze
            grid: 2D list where 1 = wall, 0 = path
            cell_size: Size of each cell in pixels
        """
        rows = len(grid)
        cols = len(grid[0]) if grid else 0

        # Draw each cell
        for row_idx, row in enumerate(grid):
            for col_idx, cell in enumerate(row):
                cell_x = x + col_idx * cell_size
                cell_y = y + row_idx * cell_size

                if cell == 1:
                    # Wall - draw 50% grey checkerboard pattern
                    for py in range(cell_size):
                        for px in range(cell_size):
                            # Checkerboard: black if (px + py) is even
                            if (px + py) % 2 == 0:
                                draw.point((cell_x + px, cell_y + py), fill=0)  # Black
                            else:
                                draw.point((cell_x + px, cell_y + py), fill=1)  # White
                else:
                    # Path - draw white rectangle (or leave blank)
                    draw.rectangle(
                        [
                            cell_x,
                            cell_y,
                            cell_x + cell_size - 1,
                            cell_y + cell_size - 1,
                        ],
                        fill=1,  # White
                        outline=None,
                    )

        # Draw entrance marker (top center)
        if rows > 0 and cols > 1:
            entrance_col = 1  # Usually second column
            entrance_x = x + entrance_col * cell_size
            entrance_y = y
            # Draw arrow pointing down
            draw.line(
                [
                    entrance_x + cell_size // 2,
                    entrance_y,
                    entrance_x + cell_size // 2,
                    entrance_y + cell_size // 2,
                ],
                fill=0,
                width=2,
            )
            # Arrow head
            arrow_size = 3
            arrow_x = entrance_x + cell_size // 2
            arrow_y = entrance_y + cell_size // 2
            draw.line(
                [arrow_x, arrow_y, arrow_x - arrow_size, arrow_y - arrow_size],
                fill=0,
                width=2,
            )
            draw.line(
                [arrow_x, arrow_y, arrow_x + arrow_size, arrow_y - arrow_size],
                fill=0,
                width=2,
            )

        # Draw exit marker (bottom)
        if rows > 0 and cols > 1:
            exit_col = cols - 2  # Usually second-to-last column
            exit_x = x + exit_col * cell_size
            exit_y = y + (rows - 1) * cell_size
            # Draw arrow pointing down
            arrow_x = exit_x + cell_size // 2
            arrow_y = exit_y + cell_size - cell_size // 2
            draw.line(
                [arrow_x, arrow_y - cell_size // 2, arrow_x, arrow_y], fill=0, width=2
            )
            # Arrow head pointing down
            draw.line(
                [arrow_x, arrow_y, arrow_x - arrow_size, arrow_y + arrow_size],
                fill=0,
                width=2,
            )
            draw.line(
                [arrow_x, arrow_y, arrow_x + arrow_size, arrow_y + arrow_size],
                fill=0,
                width=2,
            )

    def _draw_sudoku_grid(
        self,
        draw: ImageDraw.Draw,
        x: int,
        y: int,
        grid: List[List[int]],
        cell_size: int,
        font,
    ):
        """Draw a Sudoku grid as a bitmap.

        Args:
            draw: ImageDraw object
            x, y: Top-left corner of grid
            grid: 9x9 grid where 0 = empty, 1-9 = number
            cell_size: Size of each cell in pixels
            font: Font for drawing numbers
        """
        border_width = 2  # Thick border for outer edges
        thin_width = 1  # Thin border for inner cells

        total_size = 9 * cell_size + 2 * border_width

        # Draw outer border
        draw.rectangle(
            [x, y, x + total_size, y + total_size], outline=0, width=border_width
        )

        # Draw grid lines and numbers
        for row in range(9):
            for col in range(9):
                cell_x = x + border_width + col * cell_size
                cell_y = y + border_width + row * cell_size

                # Determine border width (thick for 3x3 boundaries)
                top_width = border_width if row % 3 == 0 else thin_width
                left_width = border_width if col % 3 == 0 else thin_width
                bottom_width = (
                    border_width
                    if row == 8
                    else (border_width if (row + 1) % 3 == 0 else thin_width)
                )
                right_width = (
                    border_width
                    if col == 8
                    else (border_width if (col + 1) % 3 == 0 else thin_width)
                )

                # Draw cell borders
                # Top
                if row == 0 or row % 3 == 0:
                    draw.line(
                        [cell_x, cell_y, cell_x + cell_size, cell_y],
                        fill=0,
                        width=top_width,
                    )
                # Left
                if col == 0 or col % 3 == 0:
                    draw.line(
                        [cell_x, cell_y, cell_x, cell_y + cell_size],
                        fill=0,
                        width=left_width,
                    )
                # Bottom
                draw.line(
                    [
                        cell_x,
                        cell_y + cell_size,
                        cell_x + cell_size,
                        cell_y + cell_size,
                    ],
                    fill=0,
                    width=bottom_width,
                )
                # Right
                draw.line(
                    [
                        cell_x + cell_size,
                        cell_y,
                        cell_x + cell_size,
                        cell_y + cell_size,
                    ],
                    fill=0,
                    width=right_width,
                )

                # Draw number if present
                value = grid[row][col]
                if value != 0:
                    num_str = str(value)
                    # Center text in cell
                    if font:
                        bbox = font.getbbox(num_str)
                        text_width = bbox[2] - bbox[0] if bbox else cell_size // 2
                        text_height = bbox[3] - bbox[1] if bbox else cell_size // 2
                    else:
                        text_width = cell_size // 2
                        text_height = cell_size // 2

                    text_x = cell_x + (cell_size - text_width) // 2
                    text_y = cell_y + (cell_size - text_height) // 2

                    if font:
                        draw.text((text_x, text_y), num_str, font=font, fill=0)
                    else:
                        draw.text((text_x, text_y), num_str, fill=0)

    def _draw_icon(
        self, draw: ImageDraw.Draw, x: int, y: int, icon_type: str, size: int
    ):
        """Draw an icon bitmap, loading from PNG files in icons/regular folder only.

        Only icons from the icons/regular folder are used. If an icon PNG file is not found,
        the function returns early without drawing anything.

        Args:
            draw: ImageDraw object
            x, y: Top-left corner
            icon_type: Type of icon (sun, cloud, rain, snow, storm, etc.)
            size: Icon size in pixels
        """
        # Map icon names to Phosphor icon file names
        icon_aliases = {
            # Common aliases
            "mail": "envelope",
            "email": "envelope",
            "time": "clock",
            "settings": "gear",
            "location": "map-pin",
            "pin": "map-pin",
            "home": "house",
            "menu": "list",
            "search": "magnifying-glass",
            "magnifying-glass": "magnifying-glass",
            "magnifying_glass": "magnifying-glass",
            "save": "floppy-disk",
            "floppy": "floppy-disk",
            "checkmark": "check",
            "check": "check",
            "close": "x",
            "delete": "trash",
            "refresh": "arrows-clockwise",
            "clear": "sun",
            "note-pencil": "note-pencil",
            "note": "note-pencil",
            "calendar-blank": "calendar-blank",
            "calendar": "calendar-blank",
            "envelope-open": "envelope-open",
            "cloud-sun": "cloud-sun",
            "moon-stars": "moon-stars",
            "grid-nine": "grid-nine",
            "path": "path",
            "hourglass": "hourglass",
            "check-square": "check-square",
            "desktop": "desktop",
            "quotes": "quotes",
            "plugs": "plugs",
            "newspaper": "newspaper",
            "rss": "rss",
            "arrow_right": "arrow-right",
            "wifi": "wifi-high",
            # Weather icons
            "rain": "cloud-rain",
            "snow": "cloud-snow",
            "snowflake": "snowflake",
            "storm": "cloud-lightning",
            "thunder": "cloud-lightning",
            "lightning": "cloud-lightning",
            "cloud-fog": "cloud-fog",
            "fog": "cloud-fog",
            "mist": "cloud-fog",
            "cloud-moon": "cloud-moon",
            "sun-horizon": "sun-horizon",
            "thermometer": "thermometer",
            "thermometer-hot": "thermometer-hot",
            "thermometer-cold": "thermometer-cold",
            "wind": "wind",
            "rainbow": "rainbow",
            "rainbow-cloud": "rainbow-cloud",
        }

        # Use mapped alias or original icon name
        file_name = icon_aliases.get(icon_type.lower(), icon_type.lower())

        # Try to load PNG from icons/regular directory
        # Get project root (go up from app/drivers/ to app/, then up to project root)
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # app/
        project_root = os.path.dirname(app_dir)  # project root
        icon_path = os.path.join(project_root, "icons", "regular", f"{file_name}.png")

        if os.path.exists(icon_path):
            try:
                icon_img = Image.open(icon_path)
                # Resize if needed
                if icon_img.size != (size, size):
                    icon_img = icon_img.resize((size, size), Image.NEAREST)

                # Convert to 1-bit if not already
                if icon_img.mode != "1":
                    icon_img = icon_img.convert("1")

                # Draw pixels onto the main image
                # We need to access the underlying image from ImageDraw
                # ImageDraw has a private `_image` attribute, but safer to use `draw.im`
                # Actually, we can iterate pixels and draw them
                width, height = icon_img.size
                pixels = icon_img.load()
                for py in range(height):
                    for px in range(width):
                        # In PIL '1' mode: 0=black, 1=white
                        # We want to draw black pixels (0) onto white background
                        pixel = pixels[px, py]
                        if pixel == 0:
                            draw.point((x + px, y + py), fill=0)

                return  # Successfully drew from file
            except Exception:
                return  # Failed to load, skip icon

        # PNG file doesn't exist - skip (no programmatic fallback)
        return

    def _draw_weather_forecast(
        self, draw: ImageDraw.Draw, x: int, y: int, total_width: int, forecast: list
    ):
        """Draw a 7-day weather forecast with pill-shaped containers.

        Args:
            draw: ImageDraw object
            x, y: Top-left corner
            total_width: Total width available
            forecast: List of forecast dicts with day, date, high, low, condition, precipitation
        """
        if not forecast:
            return

        # Map conditions to icon types based on WMO weather codes (matches weather module logic)
        def get_icon_type(condition: str) -> str:
            condition_lower = condition.lower() if condition else ""

            # Clear sky (code 0)
            if condition_lower == "clear":
                return "sun"  # Maps to sun.png

            # Mainly clear (code 1) or Partly cloudy (code 2)
            elif (
                condition_lower == "mainly clear" or condition_lower == "partly cloudy"
            ):
                return "cloud-sun"  # Maps to cloud-sun.png

            # Overcast (code 3)
            elif condition_lower == "overcast":
                return "cloud"  # Maps to cloud.png

            # Fog (codes 45, 48)
            elif condition_lower == "fog" or "mist" in condition_lower:
                return "cloud-fog"  # Maps to cloud-fog.png

            # Thunderstorm (codes 95, 96, 99) - check FIRST to avoid false matches
            if (
                "thunderstorm" in condition_lower
                or "thunder" in condition_lower
                or "lightning" in condition_lower
            ):
                return "storm"  # Maps to cloud-lightning.png

            # Snow-related (codes 71, 73, 75, 77, 85, 86) - check before rain
            elif "snow" in condition_lower:
                return (
                    "snowflake"  # Maps to snowflake.png (more specific than cloud-snow)
                )

            # Rain-related (codes 51-67, 80-82): Drizzle, Freezing Drizzle, Rain, Freezing Rain, Rain Showers
            elif (
                "rain" in condition_lower
                or "drizzle" in condition_lower
                or "showers" in condition_lower
            ):
                return "rain"  # Maps to cloud-rain.png

            # Default fallback
            else:
                return "cloud"  # Maps to cloud.png

        num_days = min(len(forecast), 7)
        # Horizontal layout: all 7 days in one row
        col_width = total_width // num_days
        icon_size = 24  # Increased size, matches 24-hour forecast
        day_height = 114  # Recalculated height to accommodate 24px icon (was 110px for 20px icon)
        divider_width = 1  # Width of vertical divider lines

        # Get fonts
        font_sm = self._get_font("regular_sm")
        font_md = self._get_font("regular")  # For temps
        font_lg = self._get_font("bold")  # For high temp

        for i, day_data in enumerate(forecast[:7]):
            # Calculate column position
            col_x = x + i * col_width
            col_center = col_x + col_width // 2
            col_right = col_x + col_width
            day_top = y
            day_bottom = y + day_height  # Full height of the forecast section

            # Get data
            day_label = day_data.get("day", "--")
            date_label = day_data.get("date", "")
            precip = day_data.get("precipitation")
            # Always show precipitation (even if 0%) for consistent alignment
            precip_value = precip if precip is not None else 0
            
            # Count elements to space: High, Low, Icon, Precip (always), Day/Date
            num_elements = 5
            
            # Calculate spacing between elements - use significantly more spacing
            available_height = day_height - 16  # Leave 8px top and bottom padding
            element_spacing = 12  # Fixed larger spacing between elements
            
            current_y = day_top + 8
            
            # 1. High temp (bold, top)
            high = day_data.get("high", "--")
            high_str = f"{high}°" if high != "--" else "--"
            if font_lg:
                bbox = font_lg.getbbox(high_str)
                text_w = bbox[2] - bbox[0] if bbox else 0
                text_x = col_center - text_w // 2
                draw.text((text_x, current_y), high_str, font=font_lg, fill=0)
                current_y = current_y + (bbox[3] - bbox[1] if bbox else 16)
            else:
                current_y = current_y + 16
            
            current_y += element_spacing
            
            # 2. Low temp (medium)
            low = day_data.get("low", "--")
            low_str = f"{low}°" if low != "--" else "--"
            if font_md:
                bbox = font_md.getbbox(low_str)
                text_w = bbox[2] - bbox[0] if bbox else 0
                text_x = col_center - text_w // 2
                draw.text((text_x, current_y), low_str, font=font_md, fill=0)
                current_y = current_y + (bbox[3] - bbox[1] if bbox else 14)
            else:
                current_y = current_y + 14
            
            current_y += element_spacing
            
            # 3. Icon
            icon_x = col_center - icon_size // 2
            icon_y = current_y
            icon_type = get_icon_type(day_data.get("condition", ""))
            self._draw_icon(draw, icon_x, icon_y, icon_type, icon_size)
            current_y = icon_y + icon_size
            
            current_y += element_spacing
            
            # 4. Precipitation probability (always show, even if 0%)
            precip_str = f"{precip_value}%"
            if font_sm:
                bbox = font_sm.getbbox(precip_str)
                text_w = bbox[2] - bbox[0] if bbox else 0
                text_x = col_center - text_w // 2
                draw.text((text_x, current_y), precip_str, font=font_sm, fill=0)
                current_y = current_y + (bbox[3] - bbox[1] if bbox else 10)
            else:
                current_y = current_y + 10
            
            current_y += element_spacing
            
            # 5. Day/Date label (bottom)
            actual_bottom = day_bottom  # Track actual bottom of content
            if font_sm:
                # Day name
                day_bbox = font_sm.getbbox(day_label)
                day_text_w = day_bbox[2] - day_bbox[0] if day_bbox else 0
                day_text_x = col_center - day_text_w // 2
                draw.text((day_text_x, current_y), day_label, font=font_sm, fill=0)
                
                # Date below day (if available)
                if date_label:
                    date_bbox = font_sm.getbbox(date_label)
                    date_text_w = date_bbox[2] - date_bbox[0] if date_bbox else 0
                    date_text_x = col_center - date_text_w // 2
                    date_y = current_y + (day_bbox[3] - day_bbox[1] if day_bbox else 10) + 2
                    draw.text((date_text_x, date_y), date_label, font=font_sm, fill=0)
                    # Update actual bottom to include date
                    actual_bottom = max(actual_bottom, date_y + (date_bbox[3] - date_bbox[1] if date_bbox else 10))
                else:
                    # Update actual bottom to include day label
                    actual_bottom = max(actual_bottom, current_y + (day_bbox[3] - day_bbox[1] if day_bbox else 10))
            
            # Draw vertical divider lines - full height for all columns
            # Use actual_bottom to ensure lines extend to the very bottom of content
            line_bottom = max(day_bottom, actual_bottom)
            
            # Right edge (for all columns except last)
            if i < num_days - 1:
                draw.line(
                    [(col_right - divider_width // 2, day_top), (col_right - divider_width // 2, line_bottom)],
                    fill=0,
                    width=divider_width
                )
            # Left edge for first column
            if i == 0:
                draw.line(
                    [(col_x, day_top), (col_x, line_bottom)],
                    fill=0,
                    width=divider_width
                )
            # Right edge for last column (to complete the grid)
            if i == num_days - 1:
                draw.line(
                    [(col_right - divider_width // 2, day_top), (col_right - divider_width // 2, line_bottom)],
                    fill=0,
                    width=divider_width
                )

    def _draw_hourly_forecast(
        self,
        draw: ImageDraw.Draw,
        x: int,
        y: int,
        total_width: int,
        hourly_forecast: list,
    ):
        """Draw a 24-hour hourly weather forecast in horizontal card style.

        Args:
            draw: ImageDraw object
            x, y: Top-left corner
            total_width: Total width available
            hourly_forecast: List of dicts with keys: time, temperature, condition, precipitation
        """
        if not hourly_forecast:
            return

        # Map conditions to icon types based on WMO weather codes (matches weather module logic)
        def get_icon_type(condition: str) -> str:
            condition_lower = condition.lower() if condition else ""

            # Clear sky (code 0)
            if condition_lower == "clear":
                return "sun"  # Maps to sun.png

            # Mainly clear (code 1) or Partly cloudy (code 2)
            elif (
                condition_lower == "mainly clear" or condition_lower == "partly cloudy"
            ):
                return "cloud-sun"  # Maps to cloud-sun.png

            # Overcast (code 3)
            elif condition_lower == "overcast":
                return "cloud"  # Maps to cloud.png

            # Fog (codes 45, 48)
            elif condition_lower == "fog" or "mist" in condition_lower:
                return "cloud-fog"  # Maps to cloud-fog.png

            # Thunderstorm (codes 95, 96, 99) - check FIRST to avoid false matches
            if (
                "thunderstorm" in condition_lower
                or "thunder" in condition_lower
                or "lightning" in condition_lower
            ):
                return "storm"  # Maps to cloud-lightning.png

            # Snow-related (codes 71, 73, 75, 77, 85, 86) - check before rain
            elif "snow" in condition_lower:
                return (
                    "snowflake"  # Maps to snowflake.png (more specific than cloud-snow)
                )

            # Rain-related (codes 51-67, 80-82): Drizzle, Freezing Drizzle, Rain, Freezing Rain, Rain Showers
            elif (
                "rain" in condition_lower
                or "drizzle" in condition_lower
                or "showers" in condition_lower
            ):
                return "rain"  # Maps to cloud-rain.png

            # Default fallback
            else:
                return "cloud"  # Maps to cloud.png

        # Horizontal layout - show 4 hours per row for much better readability
        hours_per_row = 4
        num_rows = (len(hourly_forecast) + hours_per_row - 1) // hours_per_row
        # Calculate column width with proper margins to avoid cutoff
        # Leave 8px left margin + 8px right margin = 16px total margin
        col_width = (total_width - 16 - (hours_per_row - 1) * 5) // hours_per_row  # Account for spacing between columns
        hour_spacing = 5  # Horizontal spacing between hours
        icon_size = 24  # Increased size, matches 7-day forecast
        entry_height = 86  # Recalculated height to accommodate 24px icon (was 80px for 18px icon)
        row_spacing = 10  # Vertical spacing between rows
        
        # Get fonts
        font_sm = self._get_font("regular_sm")
        font_md = self._get_font("regular")  # For temperature

        # Draw grid lines first (behind content)
        grid_line_width = 1
        
        # Calculate total forecast height
        total_forecast_height = (num_rows * entry_height) + ((num_rows - 1) * row_spacing)
        
        # Calculate actual column positions for grid
        actual_col_positions = []
        left_margin = 8
        right_margin = 8
        for col in range(hours_per_row):
            col_x = x + col * (col_width + hour_spacing) + left_margin
            actual_col_positions.append(col_x)
        # Add right edge - calculate properly to avoid cutoff
        # Use the actual last column position + its width, but ensure it doesn't exceed total_width
        if actual_col_positions:
            last_col_x = actual_col_positions[-1] + col_width
            # Ensure we don't exceed the available width (account for right margin)
            last_col_x = min(last_col_x, x + total_width - right_margin)
            actual_col_positions.append(last_col_x)
        
        # Calculate leftmost and rightmost positions for grid - ensure they're within bounds
        leftmost_x = actual_col_positions[0] if actual_col_positions else x + left_margin
        rightmost_x = min(x + total_width - right_margin, actual_col_positions[-1] if actual_col_positions else x + total_width - right_margin)
        
        # Calculate bottom position for vertical lines (should match bottom horizontal line)
        bottom_y = y + total_forecast_height
        
        # Draw horizontal grid lines (between rows) - start at leftmost vertical line
        for row in range(num_rows + 1):
            line_y = y + row * (entry_height + row_spacing)
            draw.line(
                [(leftmost_x, line_y), (rightmost_x, line_y)],
                fill=0,
                width=grid_line_width
            )
        
        # Draw vertical grid lines (between hours) - extend to bottom horizontal line
        for col_x in actual_col_positions:
            # Only draw if within bounds - ensure we don't exceed total_width
            if col_x < x + total_width:
                draw.line(
                    [(col_x, y), (col_x, bottom_y)],
                    fill=0,
                    width=grid_line_width
                )
        
        # Draw content on top of grid
        for row in range(num_rows):
            row_y = y + row * (entry_height + row_spacing)
            start_idx = row * hours_per_row
            end_idx = min(start_idx + hours_per_row, len(hourly_forecast))

            for col in range(start_idx, end_idx):
                hour_data = hourly_forecast[col]
                col_idx = col - start_idx
                # Calculate position with spacing
                col_x = x + col_idx * (col_width + hour_spacing) + 8  # 8px left margin
                col_center = col_x + col_width // 2

                # Time (top of grid cell)
                time_str = hour_data.get("time", "--")
                time_y = row_y + 2
                if font_sm:
                    bbox = font_sm.getbbox(time_str)
                    text_w = bbox[2] - bbox[0] if bbox else 0
                    text_x = int(col_center - text_w // 2)
                    draw.text((text_x, time_y), time_str, font=font_sm, fill=0)
                    time_height = bbox[3] - bbox[1] if bbox else 10
                else:
                    time_height = 10

                # Icon (below time)
                icon_y = time_y + time_height + 8
                icon_x = int(col_center - icon_size // 2)
                icon_type = get_icon_type(hour_data.get("condition", ""))
                self._draw_icon(draw, icon_x, icon_y, icon_type, icon_size)

                # Temperature (below icon, prominent)
                temp = hour_data.get("temperature", "--")
                temp_str = f"{temp}°" if temp != "--" else "--"
                temp_y = icon_y + icon_size + 8
                if font_md:
                    bbox = font_md.getbbox(temp_str)
                    text_w = bbox[2] - bbox[0] if bbox else 0
                    text_x = int(col_center - text_w // 2)
                    draw.text((text_x, temp_y), temp_str, font=font_md, fill=0)
                    temp_height = bbox[3] - bbox[1] if bbox else 12
                else:
                    temp_height = 12

                # Precipitation probability (below temp, always show)
                precip = hour_data.get("precipitation")
                precip_value = precip if precip is not None else 0
                precip_str = f"{precip_value}%"
                precip_y = temp_y + temp_height + 8
                if font_sm:
                    bbox = font_sm.getbbox(precip_str)
                    text_w = bbox[2] - bbox[0] if bbox else 0
                    text_x = int(col_center - text_w // 2)
                    draw.text((text_x, precip_y), precip_str, font=font_sm, fill=0)

    def _draw_progress_bar(
        self,
        draw: ImageDraw.Draw,
        x: int,
        y: int,
        width: int,
        height: int,
        value: float,
        max_value: float,
        label: str,
        font,
    ):
        """Draw a progress bar.

        Args:
            draw: ImageDraw object
            x, y: Top-left corner
            width: Bar width in pixels
            height: Bar height in pixels
            value: Current value
            max_value: Maximum value
            label: Optional label text
            font: Font for label
        """
        # Draw border
        draw.rectangle([x, y, x + width, y + height], outline=0, width=2)

        # Calculate fill width
        if max_value > 0:
            fill_width = int((value / max_value) * (width - 4))  # -4 for border
            fill_width = max(0, min(fill_width, width - 4))
        else:
            fill_width = 0

        # Draw filled portion (checkerboard pattern for visual interest)
        if fill_width > 0:
            for px in range(x + 2, x + 2 + fill_width):
                for py in range(y + 2, y + height - 2):
                    # Checkerboard pattern
                    if ((px - x) + (py - y)) % 4 < 2:
                        draw.point((px, py), fill=0)

        # Draw label if provided
        if label and font:
            # Position label to the right of bar
            label_x = x + width + 4
            label_y = y + (height - font.size) // 2 if hasattr(font, "size") else y
            draw.text((label_x, label_y), label, font=font, fill=0)

    def _draw_calendar_grid(
        self,
        draw: ImageDraw.Draw,
        x: int,
        y: int,
        weeks: int,
        cell_size: int,
        start_date,
        events_by_date: dict,
        font,
        highlight_date=None,
        month_start=None,
        month_end=None,
    ):
        """Draw a calendar grid.

        Args:
            draw: ImageDraw object
            x, y: Top-left corner
            weeks: Number of weeks to show
            cell_size: Size of each day cell
            start_date: First date to show
            events_by_date: Dict mapping dates to event counts
            font: Font for numbers
            highlight_date: Date to highlight (e.g., today)
        """
        from datetime import datetime, timedelta

        # Day headers (S M T W T F S)
        day_names = ["S", "M", "T", "W", "T", "F", "S"]
        header_y = y + 2
        header_height = 10
        grid_width = 7 * cell_size
        # Draw header background line
        draw.line(
            [
                (x, header_y + header_height),
                (x + grid_width, header_y + header_height),
            ],
            fill=0,
            width=1,
        )
        for i, day_name in enumerate(day_names):
            day_x = x + i * cell_size
            if font:
                bbox = font.getbbox(day_name)
                text_w = bbox[2] - bbox[0] if bbox else cell_size // 2
                text_x = day_x + (cell_size - text_w) // 2
                draw.text((text_x, header_y), day_name, font=font, fill=0)

        # Draw grid cells
        current_date = start_date if start_date else datetime.now().date()
        # Find first Sunday before or on start_date
        days_since_sunday = current_date.weekday() + 1  # Monday=0, so +1
        grid_start = current_date - timedelta(days=days_since_sunday % 7)

        for week in range(weeks):
            for day in range(7):
                cell_x = x + day * cell_size
                cell_y = y + 12 + week * cell_size  # +12 for header

                # Get date for this cell
                cell_date = grid_start + timedelta(days=week * 7 + day)

                # Check if this is the highlighted date (e.g., today)
                is_highlighted = highlight_date and cell_date == highlight_date

                # Check if date is in current month (for month view)
                is_current_month = True
                if month_start and month_end:
                    is_current_month = month_start <= cell_date < month_end
                elif start_date:
                    try:
                        # Check if start_date represents a month start
                        if start_date.day <= 7:  # Likely a month start
                            is_current_month = (
                                cell_date.month == start_date.month
                                and cell_date.year == start_date.year
                            )
                    except:
                        pass

                # Check if date has events
                date_key = cell_date.isoformat()
                has_events = date_key in events_by_date and events_by_date[date_key] > 0

                # Draw cell border
                # Thicker if highlighted (today), medium if has events
                if is_highlighted:
                    border_width = 2
                elif has_events:
                    border_width = 2  # Also thick for events
                else:
                    border_width = 1

                draw.rectangle(
                    [cell_x, cell_y, cell_x + cell_size - 1, cell_y + cell_size - 1],
                    outline=0,
                    width=border_width,
                )

                # Fill cell background if highlighted or has events
                if is_highlighted:
                    # Draw filled rectangle with checkerboard pattern for today
                    for px in range(cell_x + 1, cell_x + cell_size - 1):
                        for py in range(cell_y + 1, cell_y + cell_size - 1):
                            if ((px - cell_x) + (py - cell_y)) % 3 < 2:
                                draw.point((px, py), fill=0)
                elif has_events and is_current_month:
                    # Draw lighter pattern for dates with events
                    for px in range(cell_x + 1, cell_x + cell_size - 1, 2):
                        for py in range(cell_y + 1, cell_y + cell_size - 1, 2):
                            draw.point((px, py), fill=0)

                # Draw day number
                day_num = str(cell_date.day)
                if font:
                    bbox = font.getbbox(day_num)
                    text_w = bbox[2] - bbox[0] if bbox else cell_size // 2
                    text_h = bbox[3] - bbox[1] if bbox else cell_size // 2
                    text_x = cell_x + 2
                    text_y = cell_y + 2
                    # Use inverted fill for highlighted dates, lighter for other months
                    if is_highlighted:
                        text_fill = 1  # White on black
                    elif not is_current_month:
                        text_fill = 0  # Black, but we'll make it lighter with pattern
                        # Draw lighter pattern for other months
                        for px in range(cell_x + 1, cell_x + cell_size - 1, 2):
                            for py in range(cell_y + 1, cell_y + cell_size - 1, 2):
                                draw.point((px, py), fill=0)
                    else:
                        text_fill = 0  # Normal black
                    draw.text((text_x, text_y), day_num, font=font, fill=text_fill)

                # Draw event indicator (dot) - only if not already highlighted
                if has_events and not is_highlighted:
                    dot_x = cell_x + cell_size - 4
                    dot_y = cell_y + cell_size - 4
                    # Draw a small filled circle for events
                    draw.ellipse([dot_x - 2, dot_y - 2, dot_x + 2, dot_y + 2], fill=0)
                elif has_events and is_highlighted:
                    # For highlighted dates with events, draw a larger indicator
                    dot_x = cell_x + cell_size - 5
                    dot_y = cell_y + cell_size - 5
                    # Draw white circle on black background
                    draw.ellipse(
                        [dot_x - 2, dot_y - 2, dot_x + 2, dot_y + 2], fill=1, outline=0
                    )

    def _draw_timeline(
        self, draw: ImageDraw.Draw, x: int, y: int, items: list, item_height: int, font
    ):
        """Draw a timeline graphic.

        Args:
            draw: ImageDraw object
            x, y: Top-left corner
            items: List of dicts with 'year', 'text' keys
            item_height: Height per timeline item
            font: Font for text
        """
        current_y = y  # Track current Y position
        line_height = self._get_line_height_for_style("regular") if font else self.line_height

        for i, item in enumerate(items):
            item_y = current_y
            
            # Draw year label and calculate its width
            year = str(item.get("year", ""))
            year_width = 0
            if font and year and year != "0":
                # Measure year text width
                try:
                    bbox = font.getbbox(year)
                    year_width = bbox[2] - bbox[0] if bbox else len(year) * 8
                except:
                    year_width = len(year) * 8  # Fallback estimate
                draw.text((x, item_y - 4), year, font=font, fill=0)
            
            # Position vertical line after year with padding
            line_x = x + year_width + 12  # 12px padding after year
            text_x = line_x + 10  # Text starts 10px right of line
            
            # Calculate available width for text (from text_x to right margin)
            max_text_width = self.PRINTER_WIDTH_DOTS - text_x - 10  # 10px right margin

            # Draw text (right of line) - wrap it properly
            text = item.get("text", "")
            if font and text:
                # Wrap text to fit available width
                wrapped_lines = self._wrap_text_by_width(text, font, max_text_width)
                
                # Draw each wrapped line
                text_y = item_y - 4
                for line in wrapped_lines:
                    if line.strip():  # Only draw non-empty lines
                        draw.text((text_x, text_y), line, font=font, fill=0)
                        text_y += line_height
                
                # Calculate actual height used for this item
                # Add some padding at the bottom
                actual_height = max(item_height, (len(wrapped_lines) * line_height) + 8)
            else:
                # Fallback if no font
                if text:
                    draw.text((text_x, item_y - 4), text, fill=0)
                actual_height = item_height
            
            # Draw vertical timeline line to next item (if not last item)
            if i < len(items) - 1:
                line_end_y = item_y + actual_height
                draw.line(
                    [(line_x, item_y), (line_x, line_end_y)], fill=0, width=2
                )
            
            # Update position for next item
            current_y += actual_height

    def _draw_calendar_day_timeline(
        self,
        draw: ImageDraw.Draw,
        x: int,
        y: int,
        width: int,
        height: int,
        day: date,
        events: list,
        compact: bool,
        font,
        font_sm,
    ):
        """Draw a timeline visualization for a single calendar day.

        Args:
            draw: ImageDraw object
            x, y: Top-left corner
            width: Timeline width
            height: Timeline height
            day: Date object for the day
            events: List of event dicts with 'time', 'summary', 'datetime', 'is_all_day' keys
            compact: If True, use compact format
            font: Font for event text
            font_sm: Small font for time labels
        """
        from datetime import datetime, time as dt_time
        import pytz

        # Timeline area
        timeline_x = x + 10
        timeline_y = y + 20
        timeline_width = width - 20
        timeline_height = height - 60 if not compact else height - 40

        # Get timezone
        try:
            tz = pytz.timezone(app.config.settings.timezone)
        except:
            tz = pytz.UTC

        # Current time
        now = datetime.now(tz)
        today = now.date()
        is_today = day == today

        # Draw timeline axis (horizontal line)
        axis_y = timeline_y + timeline_height // 2
        draw.line(
            [(timeline_x, axis_y), (timeline_x + timeline_width, axis_y)],
            fill=0,
            width=2,
        )

        # Draw hour markers
        if not compact:
            for hour in [0, 6, 12, 18, 24]:
                if hour == 24:
                    hour = 0
                marker_x = timeline_x + int((hour / 24) * timeline_width)
                # Draw tick mark
                draw.line(
                    [(marker_x, axis_y - 5), (marker_x, axis_y + 5)],
                    fill=0,
                    width=1,
                )
                # Draw hour label
                if font_sm:
                    hour_str = f"{hour:02d}:00"
                    bbox = font_sm.getbbox(hour_str)
                    text_w = bbox[2] - bbox[0] if bbox else 20
                    draw.text(
                        (marker_x - text_w // 2, axis_y + 8),
                        hour_str,
                        font=font_sm,
                        fill=0,
                    )

        # Draw current time indicator (if today)
        if is_today and not compact:
            current_hour = now.hour
            current_minute = now.minute
            current_pos = (current_hour * 60 + current_minute) / (24 * 60)
            current_x = timeline_x + int(current_pos * timeline_width)
            # Draw vertical line
            draw.line(
                [(current_x, timeline_y), (current_x, timeline_y + timeline_height)],
                fill=0,
                width=1,
            )
            # Draw triangle indicator
            triangle_size = 4
            draw.polygon(
                [
                    (current_x, timeline_y),
                    (current_x - triangle_size, timeline_y + triangle_size),
                    (current_x + triangle_size, timeline_y + triangle_size),
                ],
                fill=0,
            )

        # Draw events
        event_y_offset = 0
        for event in events:
            time_str = event.get("time", "")
            summary = event.get("summary", "")
            event_dt = event.get("datetime")
            is_all_day = event.get("is_all_day", False)

            if is_all_day:
                # All-day event: draw full-width bar at top
                bar_y = timeline_y + event_y_offset
                bar_height = 12
                draw.rectangle(
                    [
                        (timeline_x, bar_y),
                        (timeline_x + timeline_width, bar_y + bar_height),
                    ],
                    outline=0,
                    width=1,
                    fill=0,
                )
                # Draw text
                if font_sm:
                    draw.text(
                        (timeline_x + 4, bar_y + 2),
                        f"All Day: {summary[:30]}",
                        font=font_sm,
                        fill=1,  # White text on black background
                    )
                event_y_offset += bar_height + 4
            elif event_dt and not compact:
                # Timed event: position by time
                event_hour = event_dt.hour
                event_minute = event_dt.minute
                event_pos = (event_hour * 60 + event_minute) / (24 * 60)
                event_x = timeline_x + int(event_pos * timeline_width)

                # Draw event marker (circle)
                marker_radius = 4
                marker_y = axis_y
                draw.ellipse(
                    [
                        event_x - marker_radius,
                        marker_y - marker_radius,
                        event_x + marker_radius,
                        marker_y + marker_radius,
                    ],
                    fill=0,
                )

                # Draw event text above or below timeline
                text_y = (
                    marker_y - 20
                    if marker_y > timeline_y + timeline_height // 2
                    else marker_y + 12
                )
                if font_sm:
                    # Truncate summary
                    max_text_width = timeline_width // 3
                    if len(summary) > max_text_width // 6:
                        summary = summary[: max_text_width // 6 - 3] + "..."
                    draw.text((event_x + 6, text_y), summary, font=font_sm, fill=0)
                    # Draw time below
                    draw.text(
                        (event_x + 6, text_y + 12), time_str, font=font_sm, fill=0
                    )
            else:
                # Compact mode: just list events
                if font:
                    text = f"{time_str:<8}{summary[:30]}"
                    draw.text(
                        (timeline_x, timeline_y + event_y_offset),
                        text,
                        font=font,
                        fill=0,
                    )
                    event_y_offset += 18

    def _draw_checkbox(
        self, draw: ImageDraw.Draw, x: int, y: int, size: int, checked: bool
    ):
        """Draw a checkbox.

        Args:
            draw: ImageDraw object
            x, y: Top-left corner
            size: Checkbox size in pixels
            checked: Whether checkbox is checked
        """
        # Draw box border
        draw.rectangle([x, y, x + size, y + size], outline=0, width=2)

        if checked:
            # Draw checkmark (X pattern)
            # Diagonal lines
            draw.line([(x + 2, y + 2), (x + size - 2, y + size - 2)], fill=0, width=2)
            draw.line([(x + size - 2, y + 2), (x + 2, y + size - 2)], fill=0, width=2)

    def _draw_separator(
        self, draw: ImageDraw.Draw, x: int, y: int, width: int, height: int, style: str
    ):
        """Draw a decorative separator.

        Args:
            draw: ImageDraw object
            x, y: Top-left corner
            width: Separator width
            height: Separator height
            style: Style ('dots', 'dashed', 'wave')
        """
        if style == "dots":
            # Dotted line
            dot_spacing = 4
            for px in range(x, x + width, dot_spacing):
                dot_y = y + height // 2
                draw.ellipse([px - 1, dot_y - 1, px + 1, dot_y + 1], fill=0)
        elif style == "dashed":
            # Dashed line
            dash_length = 8
            gap = 4
            px = x
            while px < x + width:
                draw.line(
                    [(px, y + height // 2), (px + dash_length, y + height // 2)],
                    fill=0,
                    width=2,
                )
                px += dash_length + gap
        elif style == "wave":
            # Wavy line
            center_y = y + height // 2
            amplitude = 2
            frequency = 0.1
            for px in range(x, x + width):
                wave_y = center_y + int(amplitude * math.sin(px * frequency))
                draw.point((px, wave_y), fill=0)
                if px > x:
                    prev_y = center_y + int(amplitude * math.sin((px - 1) * frequency))
                    draw.line([(px - 1, prev_y), (px, wave_y)], fill=0, width=1)

    def _draw_bar_chart(
        self,
        draw: ImageDraw.Draw,
        x: int,
        y: int,
        width: int,
        bar_height: int,
        bars: list,
        font,
    ):
        """Draw a simple bar chart.

        Args:
            draw: ImageDraw object
            x, y: Top-left corner
            width: Chart width
            bar_height: Height of each bar
            bars: List of dicts with 'label', 'value', 'max_value' keys
            font: Font for labels
        """
        max_bar_width = width - 40  # Leave space for labels

        for i, bar_data in enumerate(bars):
            bar_y = y + i * (bar_height + 4)
            label = bar_data.get("label", "")
            value = bar_data.get("value", 0)
            max_value = bar_data.get("max_value", 100)

            # Draw label
            if font and label:
                draw.text(
                    (x, bar_y), label[:10], font=font, fill=0
                )  # Truncate long labels

            # Calculate bar width
            bar_width = int((value / max_value) * max_bar_width) if max_value > 0 else 0

            # Draw bar
            bar_x = x + 35  # After label
            draw.rectangle(
                [bar_x, bar_y, bar_x + bar_width, bar_y + bar_height - 2],
                fill=0,
                outline=0,
                width=1,
            )

            # Draw value label
            if font:
                value_str = f"{value:.0f}"
                draw.text((bar_x + bar_width + 4, bar_y), value_str, font=font, fill=0)

    def _draw_sun_path(
        self,
        draw: ImageDraw.Draw,
        x: int,
        y: int,
        width: int,
        height: int,
        sun_path: list,
        sunrise: datetime,
        sunset: datetime,
        current_time: datetime,
        current_altitude: float,
        sunrise_time: str,
        sunset_time: str,
        day_length: str,
        font,
        font_sm,
        font_caption,
    ):
        """Draw a sun path curve visualization.

        Args:
            draw: ImageDraw object
            x, y: Top-left corner
            width: Drawing width
            height: Drawing height (curve area)
            sun_path: List of (datetime, altitude) tuples
            sunrise: Sunrise datetime
            sunset: Sunset datetime
            current_time: Current datetime
            current_altitude: Current sun altitude in degrees
            sunrise_time: Formatted sunrise time string
            sunset_time: Formatted sunset time string
            day_length: Day length string (HH:MM:SS)
            font: Font for labels
            font_sm: Small font for captions
            font_caption: Caption font
        """
        # Calculate drawing area
        curve_height = height - 60  # Leave space for labels and times
        curve_y = y + 20  # Start below title
        curve_bottom = curve_y + curve_height - 20  # Bottom of curve area
        horizon_y = (
            curve_y + (curve_height - 20) // 2
        )  # Horizon line in middle of curve area

        # Find min/max altitude for scaling
        altitudes = [alt for _, alt in sun_path]
        min_alt = min(altitudes) if altitudes else -90
        max_alt = max(altitudes) if altitudes else 90

        # Normalize altitude range to show full sine wave including night
        # Use the actual min/max from the data to show complete day/night cycle
        alt_range = max(max_alt - min_alt, 10)  # At least 10 degrees range
        alt_min = min_alt  # Use actual minimum (can be -90 at night)
        alt_max = max_alt  # Use actual maximum (can be 90 at zenith)

        # Draw title
        if font:
            draw.text((x, y), "SUN", font=font, fill=0)

        # Draw horizon line
        horizon_x_start = x + 10
        horizon_x_end = x + width - 10
        draw.line(
            [(horizon_x_start, horizon_y), (horizon_x_end, horizon_y)], fill=0, width=1
        )

        # Draw sun path curve
        curve_width = horizon_x_end - horizon_x_start
        points = []
        current_point_idx = -1

        # Find time range for normalization
        if sun_path:
            first_time = sun_path[0][0]
            last_time = sun_path[-1][0]
            time_range_seconds = (last_time - first_time).total_seconds()
        else:
            time_range_seconds = 24 * 3600  # Fallback to 24 hours

        # Find current time index
        for i, (dt, alt) in enumerate(sun_path):
            # Normalize time to 0-1 based on actual time range
            if time_range_seconds > 0:
                time_offset = (dt - first_time).total_seconds()
                time_of_day = time_offset / time_range_seconds
            else:
                # Fallback: use hour/minute if range is invalid
                time_of_day = (dt.hour * 60 + dt.minute) / (24 * 60)
            curve_x = horizon_x_start + int(time_of_day * curve_width)

            # Normalize altitude to curve height
            # Altitude: -90 (below) to 90 (zenith)
            # Y position: curve_bottom (min altitude/night) to curve_y (max altitude/day)
            # Horizon (0 altitude) should be at horizon_y (middle)
            if alt_max > alt_min:
                normalized_alt = (alt - alt_min) / (alt_max - alt_min)
            else:
                normalized_alt = 0.5
            # Map normalized altitude to full curve height (from top to bottom)
            curve_y_pos = curve_y + int(
                (1.0 - normalized_alt) * (curve_bottom - curve_y)
            )
            points.append((curve_x, curve_y_pos))

            # Check if this is the current time (within 15 minutes)
            if abs((dt - current_time).total_seconds()) < 15 * 60:
                current_point_idx = i

        # Draw the full 24-hour curve path
        if len(points) > 1:
            # Draw the complete curve (full sine wave including night)
            # Draw past portion (solid) - from start to current time
            if current_point_idx > 0:
                past_points = points[: current_point_idx + 1]
                for i in range(len(past_points) - 1):
                    draw.line([past_points[i], past_points[i + 1]], fill=0, width=2)

            # Draw future portion (dashed) - from current time to end
            if current_point_idx < len(points) - 1:
                future_start = max(0, current_point_idx)
                future_points = points[future_start:]
                # Draw as dashed line
                for i in range(len(future_points) - 1):
                    if i % 2 == 0:  # Draw every other segment for dashed effect
                        draw.line(
                            [future_points[i], future_points[i + 1]], fill=0, width=1
                        )

        # Draw sunrise marker at actual sunrise time
        if sun_path and time_range_seconds > 0:
            sunrise_offset = (sunrise - first_time).total_seconds()
            sunrise_normalized = sunrise_offset / time_range_seconds
            sunrise_x = horizon_x_start + int(sunrise_normalized * curve_width)
        else:
            sunrise_x = horizon_x_start
        sunrise_marker_y = horizon_y
        draw.ellipse(
            [sunrise_x - 3, sunrise_marker_y - 3, sunrise_x + 3, sunrise_marker_y + 3],
            outline=0,
            width=1,
            fill=1,
        )

        # Draw sunset marker at actual sunset time
        if sun_path and time_range_seconds > 0:
            sunset_offset = (sunset - first_time).total_seconds()
            sunset_normalized = sunset_offset / time_range_seconds
            sunset_x = horizon_x_start + int(sunset_normalized * curve_width)
        else:
            sunset_x = horizon_x_end
        sunset_marker_y = horizon_y
        draw.ellipse(
            [sunset_x - 3, sunset_marker_y - 3, sunset_x + 3, sunset_marker_y + 3],
            outline=0,
            width=1,
            fill=1,
        )

        # Draw current sun position marker
        if current_point_idx >= 0 and current_point_idx < len(points):
            current_x, current_y = points[current_point_idx]
            # Draw larger marker with sun icon
            marker_size = 8
            draw.ellipse(
                [
                    current_x - marker_size,
                    current_y - marker_size,
                    current_x + marker_size,
                    current_y + marker_size,
                ],
                outline=0,
                width=2,
                fill=1,
            )
            # Draw simple sun rays (4 lines)
            ray_length = 4
            for angle in [0, 45, 90, 135]:
                rad = math.radians(angle)
                end_x = current_x + int(ray_length * math.cos(rad))
                end_y = current_y + int(ray_length * math.sin(rad))
                draw.line([(current_x, current_y), (end_x, end_y)], fill=0, width=1)

        # Draw sunrise time (bottom left)
        if font and sunrise_time:
            draw.text((x, horizon_y + 25), sunrise_time, font=font, fill=0)
            if font_caption:
                draw.text((x, horizon_y + 45), "Sunrise", font=font_caption, fill=0)

        # Draw sunset time (bottom right)
        if font and sunset_time:
            if font:
                text_bbox = draw.textbbox((0, 0), sunset_time, font=font)
                text_width = text_bbox[2] - text_bbox[0]
            sunset_text_x = x + width - text_width
            draw.text((sunset_text_x, horizon_y + 25), sunset_time, font=font, fill=0)
            if font_caption:
                caption_bbox = draw.textbbox((0, 0), "Sunset", font=font_caption)
                caption_width = caption_bbox[2] - caption_bbox[0]
                draw.text(
                    (x + width - caption_width, horizon_y + 45),
                    "Sunset",
                    font=font_caption,
                    fill=0,
                )

        # Draw day length (centered, inline with sunrise/sunset times)
        if font and day_length:
            duration_text = day_length
            text_bbox = draw.textbbox((0, 0), duration_text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            duration_x = x + (width - text_width) // 2
            draw.text((duration_x, horizon_y + 25), duration_text, font=font, fill=0)
            if font_caption:
                caption_bbox = draw.textbbox((0, 0), "Day Length", font=font_caption)
                caption_width = caption_bbox[2] - caption_bbox[0]
                caption_x = x + (width - caption_width) // 2
                draw.text(
                    (caption_x, horizon_y + 45),
                    "Day Length",
                    font=font_caption,
                    fill=0,
                )

    def _generate_qr_image(
        self, data: str, size: int, error_correction: str, fixed_size: bool
    ) -> Image.Image:
        """Generate a QR code as a PIL Image.

        Args:
            data: Data to encode
            size: Target size in pixels (used when fixed_size=True)
            error_correction: L/M/Q/H
            fixed_size: If True, resize output to consistent dimensions
        """
        if not data:
            return None

        try:
            import qrcode

            ec_map = {
                "L": qrcode.constants.ERROR_CORRECT_L,
                "M": qrcode.constants.ERROR_CORRECT_M,
                "Q": qrcode.constants.ERROR_CORRECT_Q,
                "H": qrcode.constants.ERROR_CORRECT_H,
            }
            ec_level = ec_map.get(
                error_correction.upper(), qrcode.constants.ERROR_CORRECT_L
            )

            # Use version 1 and let it auto-fit, then resize for consistency
            qr = qrcode.QRCode(
                version=1,
                error_correction=ec_level,
                box_size=10,  # Generate at higher resolution for quality
                border=1,
            )
            qr.add_data(data)
            qr.make(fit=True)

            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_img = qr_img.convert("1")

            # If fixed_size, resize all QR codes to the same dimensions
            if fixed_size:
                # Target size: 80x80 pixels for consistent appearance
                target_size = 80
                qr_img = qr_img.resize((target_size, target_size), Image.NEAREST)

            return qr_img
        except Exception:
            return None

    def _send_bitmap(self, img: Image.Image):
        """Send a bitmap image to the printer using GS v 0 raster command.

        Optimized for speed: builds the entire command as one buffer
        and sends it in a single write operation.
        """
        if img is None:
            return

        try:
            width, height = img.size

            # Ensure width is multiple of 8 for byte alignment
            if width % 8 != 0:
                new_width = ((width // 8) + 1) * 8
                new_img = Image.new("1", (new_width, height), 1)
                new_img.paste(img, (0, 0))
                img = new_img
                width = new_width

            # Convert to 1-bit if not already
            img = img.convert("1")

            # Get raw pixel bytes directly (more efficient than iterating)
            pixels = img.tobytes()
            bytes_per_row = width // 8

            # Build complete command in one buffer
            # GS v 0 - Print raster bit image
            xL = bytes_per_row & 0xFF
            xH = (bytes_per_row >> 8) & 0xFF
            yL = height & 0xFF
            yH = (height >> 8) & 0xFF

            # Pre-allocate the complete command buffer
            # Header (8 bytes) + raster data
            command = bytearray(8 + len(pixels))
            command[0:4] = b"\x1d\x76\x30\x00"  # GS v 0 command
            command[4:8] = bytes([xL, xH, yL, yH])

            # PIL 1-bit mode: 0 = black, 255 = white (packed into bytes)
            # Printer expects: 1 = black dot, 0 = white
            # PIL packs 8 pixels per byte, MSB first, but inverted from what printer expects
            # So we need to invert the bytes
            for i, byte in enumerate(pixels):
                command[8 + i] = byte ^ 0xFF  # Invert bits

            # Send entire image in one write
            self._write(bytes(command))

        except Exception:
            pass

    def _write(self, data: bytes):
        """Internal helper to write bytes to serial interface.

        Sends data without waiting for transmission to complete.
        This allows the printer to buffer data while we continue processing.
        """
        try:
            if self.ser and self.ser.is_open:
                # Write all data at once - don't flush() as that blocks
                # until all bytes transmit (slow at 9600 baud)
                self.ser.write(data)
        except Exception:
            pass

    def _read(self, size: int = 1, timeout: float = 1.0) -> bytes:
        """Read bytes from serial interface. Returns empty bytes on error."""
        try:
            if self.ser and self.ser.is_open:
                old_timeout = self.ser.timeout
                self.ser.timeout = timeout
                data = self.ser.read(size)
                self.ser.timeout = old_timeout
                return data
        except Exception:
            pass
        return b""

    def is_printer_busy(self) -> bool:
        """Check if printer is currently busy/printing using DLE EOT 1.

        Returns:
            True if printer is busy (offline), False if ready (online)
            Returns False on error (assume ready to allow printing)
        """
        try:
            # Send DLE EOT 1 - Real-time printer status
            self._write(b"\x10\x04\x01")  # DLE EOT 1

            # Read response (1 byte)
            response = self._read(1, timeout=0.5)

            if len(response) == 0:
                return False  # No response, assume ready

            status_byte = response[0]

            # Bit 3: 0 = Online (ready), 1 = Offline (busy/printing)
            is_offline = (status_byte & 0x08) != 0

            return is_offline

        except Exception:
            return False  # On error, assume ready

    def check_paper_status(self) -> dict:
        """Check paper sensor status using GS r 1 command.

        Returns:
            dict with keys:
                - 'paper_adequate': bool (True if paper is adequate)
                - 'paper_near_end': bool (True if paper is near end)
                - 'paper_out': bool (True if paper is out)
                - 'error': bool (True if error reading status)
        """
        result = {
            "paper_adequate": True,
            "paper_near_end": False,
            "paper_out": False,
            "error": False,
        }

        try:
            # Send GS r 1 - Transmit paper sensor status
            self._write(b"\x1d\x72\x01")  # GS r 1

            # Read response (1 byte)
            response = self._read(1, timeout=0.5)

            if len(response) == 0:
                result["error"] = True
                return result

            status_byte = response[0]

            # Parse status byte (bits 2-3 indicate paper status)
            # Bits 2-3: 00 = paper adequate, 0C (12) = paper near end
            paper_bits = (status_byte >> 2) & 0x03

            if paper_bits == 0x03:  # 0C = 12 decimal = 0b1100, bits 2-3 = 0b11
                result["paper_near_end"] = True
                result["paper_adequate"] = False
            elif paper_bits == 0x00:
                result["paper_adequate"] = True
            else:
                # Unknown status, assume adequate
                result["paper_adequate"] = True

        except Exception:
            result["error"] = True

        return result

    def clear_hardware_buffer(self):
        """Clear the printer's hardware buffer - call at startup to prevent garbage."""
        import time

        try:
            # Clear software buffer
            self.print_buffer.clear()
            self.lines_printed = 0
            self.max_lines = 0

            # Cancel any in-progress print job
            self._write(b"\x18")  # CAN - Cancel print data in page mode
            time.sleep(0.05)

            # ESC @ - Hardware reset (clears all settings and buffer)
            self._write(b"\x1b\x40")
            time.sleep(0.3)

            # Re-apply ASCII mode settings after reset
            self._apply_ascii_settings()
        except Exception:
            pass

    def _apply_ascii_settings(self):
        """Apply ASCII-only mode settings for bitmap rendering."""
        try:
            # Cancel Chinese character mode (confirmed in QR204 manual)
            self._write(b"\x1c\x2e")  # FS . (1C 2E) - Cancel Chinese mode

            # Select USA character set (confirmed in QR204 manual)
            self._write(b"\x1b\x52\x00")  # ESC R 0 (1B 52 00) - USA character set

            # Select code page PC437 (confirmed in QR204 manual)
            self._write(b"\x1b\x74\x00")  # ESC t 0 (1B 74 00) - Code page PC437 (US)

            # Note: No ESC { rotation needed - we rotate bitmaps in software
        except Exception:
            pass

    def _initialize_printer(self):
        """Send initialization commands to ensure ASCII-only mode."""
        import time

        try:
            # Clear any garbage in the printer buffer
            self._write(b"\x00\x00\x00\x00\x00")
            time.sleep(0.1)

            # ESC @ - Hardware reset (clears all settings)
            self._write(b"\x1b\x40")
            time.sleep(0.3)

            # Apply ASCII settings
            self._apply_ascii_settings()
        except Exception:
            pass

    def _ensure_ascii_mode(self):
        """Re-send commands to ensure printer stays in ASCII mode."""
        try:
            # Cancel Chinese mode (confirmed in QR204 manual)
            self._write(b"\x1c\x2e")  # FS . (1C 2E)
            # Note: No rotation command needed - bitmaps are pre-rotated
        except Exception:
            pass

    def _sanitize_text(self, text: str) -> str:
        """
        Convert text to pure ASCII to prevent Chinese character issues.
        Replaces common Unicode chars with ASCII equivalents.
        """
        # Step 1: Apply known character replacements
        text = text.translate(self.CHAR_REPLACEMENTS)

        # Step 2: Normalize Unicode (decompose accented chars like é -> e + accent)
        text = unicodedata.normalize("NFKD", text)

        # Step 3: Keep only printable ASCII (0x20-0x7E) plus newline/tab
        result = []
        for char in text:
            code = ord(char)
            if 0x20 <= code <= 0x7E:  # Printable ASCII
                result.append(char)
            elif char in "\n\r\t":  # Whitespace
                result.append(char)
            # Skip everything else

        return "".join(result)

    def _write_text_line(self, line: str):
        """Internal method to write a single line of text to the printer."""
        try:
            # Sanitize to pure ASCII - prevents Chinese characters
            clean_line = self._sanitize_text(line)

            # Encode as ASCII (safe now that we've sanitized)
            encoded = clean_line.encode("ascii", errors="replace")

            self._write(encoded)
            self._write(b"\n")
            self.lines_printed += 1
        except Exception:
            pass

    def is_max_lines_exceeded(self) -> bool:
        """Check if we've exceeded the maximum print length."""
        if self.max_lines <= 0:
            return False
        return self.lines_printed >= self.max_lines

    def was_truncated(self) -> bool:
        """Check if the last print was truncated due to max lines."""
        return self._max_lines_hit

    def print_text(self, text: str, style: str = "regular"):
        """Print text with specified style. Buffers for unified bitmap rendering.

        Available styles:
            - "regular": Normal body text
            - "bold": Bold text
            - "bold_lg": Large bold text (for headers)
            - "medium": Medium weight
            - "semibold": Semi-bold
            - "light": Light weight
            - "regular_sm": Small regular text
        """
        # Safety: prevent unbounded buffer growth
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()
        self.print_buffer.append(("styled", {"text": text, "style": style}))

    def print_header(self, text: str, icon: str = None, icon_size: int = 24):
        """Print large bold header text in a drawn box.

        Args:
            text: Header text
            icon: Optional icon type to display inline (e.g., "check", "home")
            icon_size: Size of icon in pixels (default 24)
        """
        # Add a box operation to the buffer
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()
        box_data = {
            "text": text.upper(),
            "style": "bold_lg",
            "padding": 8,  # pixels of padding inside box
            "border": 2,  # border thickness in pixels
        }
        if icon:
            box_data["icon"] = icon
            box_data["icon_size"] = icon_size
        self.print_buffer.append(("box", box_data))

    def print_subheader(self, text: str):
        """Print medium-weight subheader."""
        self.print_text(text, "semibold")

    def print_body(self, text: str):
        """Print regular body text."""
        self.print_text(text, "regular")

    def print_caption(self, text: str):
        """Print small, light caption text."""
        self.print_text(text, "light")

    def print_bold(self, text: str):
        """Print bold text at normal size."""
        self.print_text(text, "bold")

    def print_line(self):
        """Print a decorative separator line."""
        # Use a stylish dot pattern instead of plain dashes
        line = "· " * (self.width // 2)
        self.print_text(line.strip(), "light")

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
        """Print an article with QR code inline on the left.

        Args:
            source: News source name
            title: Article headline
            summary: Article summary/description
            url: URL to encode as QR code
            qr_size: Size of QR code in pixels (default 64)
            title_width: Characters per line for title wrapping
            summary_width: Characters per line for summary wrapping
            max_summary_lines: Maximum summary lines to show
        """
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()

        # Wrap title and summary to fit next to QR code
        from app.utils import wrap_text

        title_wrapped = wrap_text(title, width=title_width, indent=0)
        summary_wrapped = []
        if summary:
            summary_wrapped = wrap_text(summary, width=summary_width, indent=0)[
                :max_summary_lines
            ]

        article_data = {
            "source": source,
            "title": title,
            "title_wrapped": title_wrapped,
            "summary_wrapped": summary_wrapped,
            "url": url,
            "qr_size": qr_size,
            "title_lines": len(title_wrapped),
            "summary_lines": len(summary_wrapped),
        }

        self.print_buffer.append(("article_block", article_data))

    def print_thick_line(self):
        """Print a bold separator line."""
        line = "━" * self.width
        self.print_text(line, "bold")

    def print_moon_phase(self, phase: float, size: int = 60):
        """Print a moon phase graphic.

        Args:
            phase: Moon phase value (0-28 day cycle)
            size: Diameter of moon in pixels (default 60)
        """
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()
        self.print_buffer.append(
            (
                "moon",
                {
                    "phase": phase,
                    "size": size,
                },
            )
        )

    def print_sun_path(
        self,
        sun_path: list,
        sunrise: datetime,
        sunset: datetime,
        current_time: datetime,
        current_altitude: float,
        sunrise_time: str,
        sunset_time: str,
        day_length: str,
        height: int = 120,
    ):
        """Print a sun path curve visualization.

        Args:
            sun_path: List of (datetime, altitude) tuples
            sunrise: Sunrise datetime
            sunset: Sunset datetime
            current_time: Current datetime
            current_altitude: Current sun altitude in degrees
            sunrise_time: Formatted sunrise time string
            sunset_time: Formatted sunset time string
            day_length: Day length string (HH:MM:SS)
            height: Height of the visualization in pixels (default 120)
        """
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()
        self.print_buffer.append(
            (
                "sun_path",
                {
                    "sun_path": sun_path,
                    "sunrise": sunrise,
                    "sunset": sunset,
                    "current_time": current_time,
                    "current_altitude": current_altitude,
                    "sunrise_time": sunrise_time,
                    "sunset_time": sunset_time,
                    "day_length": day_length,
                    "height": height,
                },
            )
        )

    def print_maze(self, grid: List[List[int]], cell_size: int = 8):
        """Print a maze as a bitmap graphic.

        Args:
            grid: 2D list where 1 = wall, 0 = path
            cell_size: Size of each cell in pixels (default 8)
        """
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()
        self.print_buffer.append(
            (
                "maze",
                {
                    "grid": grid,
                    "cell_size": cell_size,
                },
            )
        )

    def print_sudoku(self, grid: List[List[int]], cell_size: int = 16):
        """Print a Sudoku grid as a bitmap graphic.

        Args:
            grid: 9x9 grid where 0 = empty, 1-9 = number
            cell_size: Size of each cell in pixels (default 16)
        """
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()
        self.print_buffer.append(
            (
                "sudoku",
                {
                    "grid": grid,
                    "cell_size": cell_size,
                },
            )
        )

    def print_icon(self, icon_type: str, size: int = 32):
        """Print a weather/status icon.

        Args:
            icon_type: Type of icon (sun, cloud, rain, snow, storm, clear)
            size: Icon size in pixels (default 32)
        """
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()
        self.print_buffer.append(
            (
                "icon",
                {
                    "type": icon_type,
                    "size": size,
                },
            )
        )

    def print_weather_forecast(self, forecast: list):
        """Print a 7-day weather forecast with icons.

        Args:
            forecast: List of dicts with keys: day, high, low, condition
        """
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()
        self.print_buffer.append(
            (
                "weather_forecast",
                {
                    "forecast": forecast,
                },
            )
        )

    def print_hourly_forecast(self, hourly_forecast: list):
        """Print a 24-hour hourly weather forecast with icons.

        Args:
            hourly_forecast: List of dicts with keys: time, temperature, condition
        """
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()
        self.print_buffer.append(
            (
                "hourly_forecast",
                {
                    "hourly_forecast": hourly_forecast,
                },
            )
        )

    def print_progress_bar(
        self,
        value: float,
        max_value: float = 100,
        width: int = None,
        height: int = 12,
        label: str = "",
    ):
        """Print a progress bar.

        Args:
            value: Current value
            max_value: Maximum value (default 100)
            width: Bar width in pixels (default: full width minus margins)
            height: Bar height in pixels (default 12)
            label: Optional label text
        """
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()
        if width is None:
            width = self.PRINTER_WIDTH_DOTS - 8  # Full width minus margins
        self.print_buffer.append(
            (
                "progress_bar",
                {
                    "value": value,
                    "max_value": max_value,
                    "width": width,
                    "height": height,
                    "label": label,
                },
            )
        )

    def print_calendar_grid(
        self,
        weeks: int = 4,
        cell_size: int = 8,
        start_date=None,
        events_by_date: dict = None,
        highlight_date=None,
        month_start=None,
        month_end=None,
    ):
        """Print a visual calendar grid.

        Args:
            weeks: Number of weeks to show (default 4)
            cell_size: Size of each day cell in pixels (default 8)
            start_date: First date to show (default: today)
            events_by_date: Dict mapping date strings to event counts
            highlight_date: Date to highlight (e.g., today)
            month_start: Start of month for month view (optional)
            month_end: End of month for month view (optional)
        """
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()
        self.print_buffer.append(
            (
                "calendar_grid",
                {
                    "weeks": weeks,
                    "cell_size": cell_size,
                    "start_date": start_date,
                    "events_by_date": events_by_date or {},
                    "highlight_date": highlight_date,
                    "month_start": month_start,
                    "month_end": month_end,
                },
            )
        )

    def print_calendar_day_timeline(
        self, day: date, events: list, compact: bool = False, height: int = 120
    ):
        """Print a timeline visualization for a single calendar day.

        Args:
            day: Date object for the day
            events: List of event dicts with 'time', 'summary', 'datetime', 'is_all_day' keys
            compact: If True, use compact format (default False)
            height: Height of timeline in pixels (default 120)
        """
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()
        self.print_buffer.append(
            (
                "calendar_day_timeline",
                {
                    "day": day,
                    "events": events,
                    "compact": compact,
                    "height": height,
                },
            )
        )

    def print_timeline(self, items: list, item_height: int = 20):
        """Print a timeline graphic.

        Args:
            items: List of dicts with 'year' and 'text' keys
            item_height: Height per item in pixels (default 20)
        """
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()
        self.print_buffer.append(
            (
                "timeline",
                {
                    "items": items,
                    "item_height": item_height,
                },
            )
        )

    def print_checkbox(self, checked: bool = False, size: int = 12):
        """Print a bitmap checkbox.

        Args:
            checked: Whether checkbox is checked
            size: Checkbox size in pixels (default 12)
        """
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()
        self.print_buffer.append(
            (
                "checkbox",
                {
                    "checked": checked,
                    "size": size,
                },
            )
        )

    def print_separator(self, style: str = "dots", height: int = 8):
        """Print a decorative separator.

        Args:
            style: Style ('dots', 'dashed', 'wave') (default 'dots')
            height: Separator height in pixels (default 8)
        """
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()
        self.print_buffer.append(
            (
                "separator",
                {
                    "style": style,
                    "height": height,
                },
            )
        )

    def print_bar_chart(self, bars: list, bar_height: int = 12, width: int = None):
        """Print a simple bar chart.

        Args:
            bars: List of dicts with 'label', 'value', 'max_value' keys
            bar_height: Height of each bar in pixels (default 12)
            width: Chart width in pixels (default: full width)
        """
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()
        if width is None:
            width = self.PRINTER_WIDTH_DOTS - 8
        self.print_buffer.append(
            (
                "bar_chart",
                {
                    "bars": bars,
                    "bar_height": bar_height,
                    "width": width,
                },
            )
        )

    def _write_feed(self, count: int):
        """Internal method to feed paper."""
        try:
            for _ in range(count):
                self._write(b"\n")
        except Exception:
            pass

    def feed(self, lines: int = 3):
        """Feed paper (advance lines). Buffers for reverse-order printing."""
        self.print_buffer.append(("feed", lines))

    def flush_buffer(self):
        """Flush the print buffer as ONE unified bitmap for speed.

        All text, feeds, and QR codes are rendered into a single tall image,
        rotated 180°, and sent as one raster graphics command.
        """
        if not self.print_buffer:
            return

        # If max_lines is set, trim content from END of buffer
        total_lines_in_buffer = 0
        if self.max_lines > 0:
            for op_type, op_data in self.print_buffer:
                if op_type == "text":
                    total_lines_in_buffer += op_data.count("\n") + 1

            lines_counted = 0
            trim_index = len(self.print_buffer)

            for i, (op_type, op_data) in enumerate(self.print_buffer):
                if op_type == "text":
                    lines_in_item = op_data.count("\n") + 1
                    if lines_counted + lines_in_item > self.max_lines:
                        trim_index = i
                        self._max_lines_hit = True
                        break
                    lines_counted += lines_in_item

            if self._max_lines_hit:
                self.print_buffer = self.print_buffer[:trim_index]

        # Add truncation message if needed
        if self._max_lines_hit:
            self.print_buffer.append(
                ("text", f"-- TRUNCATED ({self.max_lines}/{total_lines_in_buffer}) --")
            )

        # Render everything as one unified bitmap
        ops = list(self.print_buffer)
        self.print_buffer.clear()

        img = self._render_unified_bitmap(ops)
        if img:
            self._send_bitmap(img)
            # Ensure all data is transmitted before returning
            if self.ser and self.ser.is_open:
                self.ser.flush()

    def reset_buffer(self, max_lines: int = 0):
        """Reset/clear the print buffer (call at start of new print job).

        Args:
            max_lines: Maximum lines for this print job (0 = no limit)
        """
        self.print_buffer.clear()
        # Reset line counter
        self.lines_printed = 0
        self.max_lines = max_lines
        self._max_lines_hit = False
        # Re-assert ASCII mode and rotation at start of each print job
        self._ensure_ascii_mode()

    def set_cutter_feed(self, lines: int):
        """Set the cutter feed space (lines of white space at end of print).

        This space is added to the bitmap itself, ensuring reliable paper feed
        after bitmap printing regardless of post-print commands.
        """
        self.cutter_feed_dots = lines * 24  # 24 dots per line at 203 DPI

    def feed_direct(self, lines: int = 3):
        """Feed paper directly, bypassing the buffer (for use after flushing in invert mode).

        After bitmap printing (GS v 0), we need to ensure paper feeds.
        Uses ESC d (Print and feed n lines) which should work after any print command.
        """
        if lines <= 0:
            return

        try:
            # Small delay to let bitmap finish processing
            time.sleep(0.05)

            # ESC d n - Print and feed n lines (0x1B 0x64 n)
            # This command works after bitmap printing because it's a "print and feed" command
            # Even with no data to print, it should still feed the paper
            feed_amount = min(lines, 255)
            self._write(b"\x1b\x64" + bytes([feed_amount]))

            # Backup: Also send ESC J (feed by dots) in case ESC d doesn't work
            dots = lines * 24
            while dots > 0:
                chunk = min(dots, 255)
                self._write(b"\x1b\x4a" + bytes([chunk]))
                dots -= chunk

            # Flush to ensure all data is sent
            if self.ser and self.ser.is_open:
                self.ser.flush()
        except Exception:
            pass

    def blip(self):
        """Short paper feed for tactile feedback."""
        try:
            # ESC J n - Feed paper n dots (n/203 inches, ~24 dots = 1 line)
            self._write(b"\x1b\x4a\x02")
        except Exception:
            pass

    def print_qr(
        self,
        data: str,
        size: int = 4,
        error_correction: str = "M",
        fixed_size: bool = False,
    ):
        """Print a QR code using native ESC/POS commands. Buffers for correct print order.

        Args:
            data: The text/URL to encode in the QR code
            size: Module size 1-16 (each module = n dots, default 4)
            error_correction: Error correction level - L(7%), M(15%), Q(25%), H(30%)
            fixed_size: If True, generates QR with fixed version for consistent sizing
        """
        # Safety: prevent unbounded buffer growth
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()
        # Buffer QR code for proper ordering with text
        self.print_buffer.append(
            (
                "qr",
                {
                    "data": data,
                    "size": size,
                    "ec": error_correction,
                    "fixed": fixed_size,
                },
            )
        )

    def _write_qr(
        self, data: str, size: int, error_correction: str, fixed_size: bool = False
    ):
        """Internal method to write QR code directly to printer."""
        if fixed_size:
            self._write_qr_bitmap(data, size, error_correction)
        else:
            self._write_qr_native(data, size, error_correction)

    def _write_qr_native(self, data: str, size: int, error_correction: str):
        """Write QR code using native ESC/POS commands (variable size based on data)."""
        try:
            # Clamp size to valid range
            size = max(1, min(16, size))

            # Map error correction level to command value
            ec_map = {"L": 48, "M": 49, "Q": 50, "H": 51}
            ec_value = ec_map.get(error_correction.upper(), 49)  # Default to M

            # Encode data as bytes
            data_bytes = data.encode("ascii", errors="replace")
            data_len = len(data_bytes) + 3  # +3 for m (48) byte
            pL = data_len & 0xFF
            pH = (data_len >> 8) & 0xFF

            # Step 1: Set QR code model (Model 2)
            self._write(b"\x1d\x28\x6b\x04\x00\x31\x41\x32\x00")

            # Step 2: Set module size
            self._write(b"\x1d\x28\x6b\x03\x00\x31\x43" + bytes([size]))

            # Step 3: Set error correction level
            self._write(b"\x1d\x28\x6b\x03\x00\x31\x45" + bytes([ec_value]))

            # Step 4: Store QR code data
            self._write(
                b"\x1d\x28\x6b" + bytes([pL, pH]) + b"\x31\x50\x30" + data_bytes
            )

            # Step 5: Print the QR code
            self._write(b"\x1d\x28\x6b\x03\x00\x31\x51\x30")

            # Add a newline after QR code
            self._write(b"\n")

        except Exception:
            pass

    def _write_qr_bitmap(self, data: str, pixel_size: int, error_correction: str):
        """Write QR code as bitmap for fixed, consistent sizing."""
        try:
            import qrcode
            from PIL import Image

            # Map error correction
            ec_map = {
                "L": qrcode.constants.ERROR_CORRECT_L,
                "M": qrcode.constants.ERROR_CORRECT_M,
                "Q": qrcode.constants.ERROR_CORRECT_Q,
                "H": qrcode.constants.ERROR_CORRECT_H,
            }
            ec_level = ec_map.get(
                error_correction.upper(), qrcode.constants.ERROR_CORRECT_L
            )

            # Generate QR with fixed version 4 (33x33 modules) - fits most URLs
            # Version 4 can hold ~78 alphanumeric chars with L correction
            qr = qrcode.QRCode(
                version=4,  # Fixed version for consistent size
                error_correction=ec_level,
                box_size=pixel_size,
                border=1,
            )
            qr.add_data(data)
            qr.make(fit=False)  # Don't auto-fit, use fixed version

            # Create image
            img = qr.make_image(fill_color="black", back_color="white")
            img = img.convert("1")  # Convert to 1-bit black/white

            # Get image dimensions
            width, height = img.size

            # Ensure width is multiple of 8 for byte alignment
            if width % 8 != 0:
                new_width = ((width // 8) + 1) * 8
                new_img = Image.new("1", (new_width, height), 1)  # White background
                new_img.paste(img, (0, 0))
                img = new_img
                width = new_width

            # Convert to bytes (1 bit per pixel, MSB first)
            pixels = list(img.getdata())
            bytes_per_row = width // 8

            # Build raster data
            raster_data = bytearray()
            for y in range(height):
                row_start = y * width
                for x_byte in range(bytes_per_row):
                    byte_val = 0
                    for bit in range(8):
                        pixel_idx = row_start + (x_byte * 8) + bit
                        if pixels[pixel_idx] == 0:  # Black pixel
                            byte_val |= 0x80 >> bit
                    raster_data.append(byte_val)

            # GS v 0 - Print raster bit image
            # Format: GS v 0 m xL xH yL yH d1...dk
            # m = 0 (normal), xL xH = bytes per row, yL yH = rows
            xL = bytes_per_row & 0xFF
            xH = (bytes_per_row >> 8) & 0xFF
            yL = height & 0xFF
            yH = (height >> 8) & 0xFF

            self._write(
                b"\x1d\x76\x30\x00" + bytes([xL, xH, yL, yH]) + bytes(raster_data)
            )
            self._write(b"\n")

        except Exception:
            # Fallback to native if bitmap fails
            self._write_qr_native(data, pixel_size, error_correction)

    def close(self):
        """Close the serial connection."""
        if self.ser and self.ser.is_open:
            self.ser.close()
