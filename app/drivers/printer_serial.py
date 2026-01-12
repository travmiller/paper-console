import serial
import platform
import os
import unicodedata
import time
from typing import Optional, List
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO


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

    def __init__(
        self,
        width: int = 42,  # Characters per line
        port: Optional[str] = None,
        baudrate: int = 9600,  # QR204 only supports 9600
        font_size: int = 12,  # Font size in pixels (8-24)
        line_spacing: int = 2,  # Extra pixels between lines
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

        # Font settings for bitmap rendering (configurable)
        self.font_size = max(8, min(24, font_size))  # Clamp to valid range
        self.line_spacing = max(0, min(8, line_spacing))  # Clamp to valid range
        self.line_height = self.font_size + self.line_spacing

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

            import time

            time.sleep(0.5)

            self._initialize_printer()

        except serial.SerialException:
            self.ser = None

    def _load_font_family(self) -> dict:
        """Load IBM Plex Mono font family with multiple weights."""
        import os

        # Get the project root directory (parent of app/)
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        project_root = os.path.dirname(app_dir)

        fonts = {}

        # Font variants we want to load
        font_variants = {
            "regular": "IBMPlexMono-Regular.ttf",
            "bold": "IBMPlexMono-Bold.ttf",
            "medium": "IBMPlexMono-Medium.ttf",
            "light": "IBMPlexMono-Light.ttf",
            "semibold": "IBMPlexMono-SemiBold.ttf",
        }

        # Base paths to search
        base_paths = [
            os.path.join(project_root, "web/public/fonts/IBM_Plex_Mono"),
            os.path.join(project_root, "web/dist/fonts/IBM_Plex_Mono"),
        ]

        # Load each variant at different sizes
        # Size jumps: +6 for headers, -4 for captions (visible hierarchy)
        for variant_name, filename in font_variants.items():
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
                        # Load at small/caption size (4px smaller)
                        fonts[f"{variant_name}_sm"] = ImageFont.truetype(
                            font_path, max(10, self.font_size - 4)
                        )
                        break
                    except Exception:
                        continue

        # Fallback to system fonts if IBM Plex not found
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
                            path, max(10, self.font_size - 4)
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
            return max(10, self.font_size - 4) + self.line_spacing
        return self.line_height

    def _render_unified_bitmap(self, ops: list) -> Image.Image:
        """Render ALL buffer operations into one unified bitmap.

        This is faster than multiple small bitmaps because:
        - Single GS v 0 command overhead
        - Continuous data stream to printer

        Supports styled text with different fonts and sizes.
        """
        import qrcode as qr_lib

        if not ops:
            return None

        # First pass: calculate total height needed
        total_height = 4  # Padding

        for op_type, op_data in ops:
            if op_type == "styled":
                clean_text = self._sanitize_text(op_data["text"])
                line_count = len(clean_text.split("\n"))
                style = op_data.get("style", "regular")
                total_height += line_count * self._get_line_height_for_style(style)
            elif op_type == "text":
                # Legacy support for plain text
                clean_text = self._sanitize_text(op_data)
                line_count = len(clean_text.split("\n"))
                total_height += line_count * self.line_height
            elif op_type == "box":
                # Box with text inside: border + padding + text + padding + border
                style = op_data.get("style", "bold_lg")
                padding = op_data.get("padding", 8)
                border = op_data.get("border", 2)
                icon_type = op_data.get("icon")  # Optional inline icon
                text_height = self._get_line_height_for_style(style)
                # If icon, make box taller to accommodate icon
                icon_size = op_data.get("icon_size", 24) if icon_type else 0
                box_height = (
                    border + padding + max(text_height, icon_size) + padding + border
                )
                total_height += box_height + 4  # +4 for spacing around box
            elif op_type == "moon":
                # Moon phase graphic: circle with shadow
                size = op_data.get("size", 60)  # Diameter in pixels
                total_height += size + 8  # Moon + spacing
            elif op_type == "maze":
                # Maze graphic: grid of cells
                grid = op_data.get("grid", [])
                cell_size = op_data.get("cell_size", 4)  # Pixels per cell
                if grid:
                    maze_height = len(grid) * cell_size
                    total_height += maze_height + 8  # Maze + spacing
            elif op_type == "sudoku":
                # Sudoku grid: 9x9 with thick borders
                grid = op_data.get("grid", [])
                cell_size = op_data.get("cell_size", 8)  # Pixels per cell
                if grid:
                    # 9 cells * cell_size + borders
                    sudoku_size = 9 * cell_size + 4  # +4 for borders
                    total_height += sudoku_size + 8  # Sudoku + spacing
            elif op_type == "icon":
                # Small icon graphic
                icon_type = op_data.get("type", "sun")
                size = op_data.get("size", 32)
                total_height += size + 4  # Icon + spacing
            elif op_type == "weather_forecast":
                # 7-day weather forecast row
                # Each day: icon (24px) + day name + high/low temps
                # Height = icon + text lines + spacing
                total_height += (
                    24 + 12 + 12 + 12 + 8
                )  # icon + day + high + low + spacing
            elif op_type == "hourly_forecast":
                # 24-hour hourly forecast
                # Group into rows of 6 hours each
                hourly_forecast = op_data.get("hourly_forecast", [])
                num_rows = (len(hourly_forecast) + 5) // 6  # 6 hours per row
                # Each row: icon (20px) + time + temp
                total_height += num_rows * (20 + 12 + 8)  # icon + text + spacing
            elif op_type == "progress_bar":
                # Progress bar graphic
                height = op_data.get("height", 12)
                total_height += height + 4  # Bar + spacing
            elif op_type == "calendar_grid":
                # Calendar grid view
                weeks = op_data.get("weeks", 4)
                cell_size = op_data.get("cell_size", 8)
                grid_height = weeks * cell_size + 4  # +4 for header
                total_height += grid_height + 8
            elif op_type == "timeline":
                # Timeline graphic
                items = op_data.get("items", [])
                item_height = op_data.get("item_height", 20)
                total_height += len(items) * item_height + 8
            elif op_type == "checkbox":
                # Bitmap checkbox
                size = op_data.get("size", 12)
                total_height += size + 2
            elif op_type == "separator":
                # Decorative separator
                height = op_data.get("height", 8)
                total_height += height + 4
            elif op_type == "bar_chart":
                # Simple bar chart
                bars = op_data.get("bars", [])
                bar_height = op_data.get("bar_height", 12)
                chart_height = (
                    len(bars) * (bar_height + 4) + 8
                )  # +4 spacing between bars
                total_height += chart_height
            elif op_type == "feed":
                total_height += op_data * self.line_height
            elif op_type == "qr":
                # Pre-render QR code to get its height and store in op_data
                qr_img = self._generate_qr_image(
                    op_data["data"],
                    op_data["size"],
                    op_data["ec"],
                    op_data.get("fixed", False),
                )
                # Store QR image directly in op_data for later use
                op_data["_qr_img"] = qr_img
                if qr_img:
                    total_height += qr_img.height + 4  # +4 for spacing

        # Create the unified image
        width = self.PRINTER_WIDTH_DOTS
        img = Image.new("1", (width, total_height), 1)  # White background
        draw = ImageDraw.Draw(img)

        # Second pass: draw everything
        y = 2

        for op_type, op_data in ops:
            if op_type == "styled":
                clean_text = self._sanitize_text(op_data["text"])
                style = op_data.get("style", "regular")
                font = self._get_font(style)
                line_height = self._get_line_height_for_style(style)

                for line in clean_text.split("\n"):
                    if font:
                        draw.text((2, y), line, font=font, fill=0)
                    else:
                        draw.text((2, y), line, fill=0)
                    y += line_height
            elif op_type == "text":
                # Legacy support
                clean_text = self._sanitize_text(op_data)
                font = self._get_font("regular")
                for line in clean_text.split("\n"):
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
                padding = op_data.get("padding", 8)
                border = op_data.get("border", 2)
                icon_type = op_data.get("icon")  # Optional inline icon
                icon_size = op_data.get("icon_size", 24) if icon_type else 0
                font = self._get_font(style)
                text_height = self._get_line_height_for_style(style)

                # Full width box
                box_width = width - 4  # Leave 2px margin on each side
                box_height = max(text_height, icon_size) + (padding * 2) + (border * 2)

                box_x = 2  # Small left margin
                box_y = y + 2  # Small top margin

                # Draw outer rectangle (black border)
                draw.rectangle(
                    [box_x, box_y, box_x + box_width, box_y + box_height],
                    fill=0,  # Black
                )
                # Draw inner rectangle (white) - creates the border effect
                draw.rectangle(
                    [
                        box_x + border,
                        box_y + border,
                        box_x + box_width - border,
                        box_y + box_height - border,
                    ],
                    fill=1,  # White
                )

                # Calculate text width
                if font:
                    bbox = font.getbbox(text)
                    text_width = bbox[2] - bbox[0] if bbox else len(text) * 10
                else:
                    text_width = len(text) * 10

                # Calculate total width (text + icon + spacing)
                icon_spacing = 6 if icon_type else 0
                total_content_width = (
                    text_width + icon_size + icon_spacing if icon_type else text_width
                )

                # Center everything together
                content_start_x = box_x + (box_width - total_content_width) // 2
                content_y = box_y + border + padding

                # Draw icon if present (to the left of text)
                if icon_type:
                    icon_x = content_start_x
                    icon_y = content_y + (text_height - icon_size) // 2
                    self._draw_icon(draw, icon_x, icon_y, icon_type, icon_size)

                # Draw text (to the right of icon, or centered if no icon)
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

                y += box_height + 4  # Move past box + spacing
            elif op_type == "moon":
                # Draw moon phase graphic
                phase = op_data.get("phase", 0)  # 0-28 day cycle
                size = op_data.get("size", 60)

                # Center moon horizontally
                moon_x = (width - size) // 2
                moon_y = y + 4

                # Draw moon using ellipses to create the phase effect
                self._draw_moon_phase(draw, moon_x, moon_y, size, phase)

                y += size + 8
            elif op_type == "maze":
                # Draw maze bitmap
                grid = op_data.get("grid", [])
                cell_size = op_data.get("cell_size", 4)

                if grid:
                    maze_width = len(grid[0]) * cell_size if grid else 0
                    maze_height = len(grid) * cell_size

                    # Center maze horizontally
                    maze_x = (width - maze_width) // 2
                    maze_y = y + 4

                    self._draw_maze(draw, maze_x, maze_y, grid, cell_size)

                    y += maze_height + 8
            elif op_type == "sudoku":
                # Draw sudoku grid bitmap
                grid = op_data.get("grid", [])
                cell_size = op_data.get("cell_size", 8)
                font = self._get_font("regular")

                if grid:
                    sudoku_size = 9 * cell_size + 4  # +4 for borders
                    # Center sudoku horizontally
                    sudoku_x = (width - sudoku_size) // 2
                    sudoku_y = y + 4

                    self._draw_sudoku_grid(
                        draw, sudoku_x, sudoku_y, grid, cell_size, font
                    )

                    y += sudoku_size + 8
            elif op_type == "icon":
                # Draw weather/status icon
                icon_type = op_data.get("type", "sun")
                size = op_data.get("size", 32)

                # Center icon horizontally
                icon_x = (width - size) // 2
                icon_y = y + 4

                self._draw_icon(draw, icon_x, icon_y, icon_type, size)

                y += size + 8
            elif op_type == "weather_forecast":
                # Draw 7-day weather forecast
                forecast = op_data.get("forecast", [])
                self._draw_weather_forecast(draw, 0, y, width, forecast)
                y += 24 + 12 + 12 + 12 + 8  # icon + day + high + low + spacing
            elif op_type == "hourly_forecast":
                # Draw 24-hour hourly forecast
                hourly_forecast = op_data.get("hourly_forecast", [])
                self._draw_hourly_forecast(draw, 0, y, width, hourly_forecast)
                # Calculate height based on number of rows (6 hours per row)
                num_rows = (len(hourly_forecast) + 5) // 6
                y += num_rows * (20 + 12 + 8)  # icon + text + spacing
            elif op_type == "progress_bar":
                # Draw progress bar
                value = op_data.get("value", 0)  # 0-100
                max_value = op_data.get("max_value", 100)
                bar_width = op_data.get("width", width - 8)
                bar_height = op_data.get("height", 12)
                label = op_data.get("label", "")

                # Center bar horizontally
                bar_x = (width - bar_width) // 2
                bar_y = y + 4

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

                y += bar_height + 8
            elif op_type == "calendar_grid":
                # Draw calendar grid
                weeks = op_data.get("weeks", 4)
                cell_size = op_data.get("cell_size", 8)
                start_date = op_data.get("start_date")
                events_by_date = op_data.get("events_by_date", {})

                grid_x = 4
                grid_y = y + 4

                self._draw_calendar_grid(
                    draw,
                    grid_x,
                    grid_y,
                    weeks,
                    cell_size,
                    start_date,
                    events_by_date,
                    self._get_font("regular_sm"),
                )

                grid_height = weeks * cell_size + 4
                y += grid_height + 8
            elif op_type == "timeline":
                # Draw timeline
                items = op_data.get("items", [])
                item_height = op_data.get("item_height", 20)
                timeline_x = 8
                timeline_y = y + 4

                self._draw_timeline(
                    draw,
                    timeline_x,
                    timeline_y,
                    items,
                    item_height,
                    self._get_font("regular"),
                )

                y += len(items) * item_height + 8
            elif op_type == "checkbox":
                # Draw checkbox
                checked = op_data.get("checked", False)
                size = op_data.get("size", 12)
                checkbox_x = 4
                checkbox_y = y + 2

                self._draw_checkbox(draw, checkbox_x, checkbox_y, size, checked)

                y += size + 4
            elif op_type == "separator":
                # Draw decorative separator
                style = op_data.get("style", "dots")
                sep_height = op_data.get("height", 8)
                sep_x = 4
                sep_y = y + 2

                self._draw_separator(draw, sep_x, sep_y, width - 8, sep_height, style)

                y += sep_height + 4
            elif op_type == "bar_chart":
                # Draw bar chart
                bars = op_data.get("bars", [])
                bar_height = op_data.get("bar_height", 12)
                chart_width = op_data.get("width", width - 8)
                chart_x = (width - chart_width) // 2
                chart_y = y + 4

                self._draw_bar_chart(
                    draw,
                    chart_x,
                    chart_y,
                    chart_width,
                    bar_height,
                    bars,
                    self._get_font("regular_sm"),
                )

                y += len(bars) * (bar_height + 4) + 8
            elif op_type == "feed":
                y += op_data * self.line_height
            elif op_type == "qr":
                # Get the pre-rendered QR image from op_data
                qr_img = op_data.get("_qr_img")
                if qr_img:
                    # Center QR code horizontally
                    x_offset = (width - qr_img.width) // 2
                    img.paste(qr_img, (x_offset, y + 2))
                    y += qr_img.height + 4

        # Rotate 180° for upside-down printing
        img = img.rotate(180)

        return img

    def _draw_moon_phase(
        self, draw: ImageDraw.Draw, x: int, y: int, size: int, phase: float
    ):
        """Draw a moon phase graphic.

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
        import math

        # Normalize phase to 0-1 (0 = new, 0.5 = full, 1 = new)
        phase_normalized = (phase % 28) / 28.0

        # Calculate illumination (0 = new moon, 1 = full moon)
        # illumination follows a cosine curve
        illumination = (1 - math.cos(phase_normalized * 2 * math.pi)) / 2

        center_x = x + size // 2
        center_y = y + size // 2
        radius = size // 2

        # Draw the moon outline (black circle)
        draw.ellipse([x, y, x + size, y + size], outline=0, width=2)

        if phase_normalized < 0.5:
            # Waxing: right side illuminated, left side dark
            # Draw white (lit) right half
            # Then overlay dark portion from left

            # Fill the whole moon white first
            draw.ellipse([x + 2, y + 2, x + size - 2, y + size - 2], fill=1)

            # Calculate the terminator (shadow edge) position
            # At new moon (phase=0), shadow covers everything
            # At first quarter (phase=0.25), shadow covers left half
            # At full moon (phase=0.5), no shadow
            shadow_width = (
                int((1 - illumination * 2) * radius) if illumination < 0.5 else 0
            )

            if shadow_width > 0:
                # Draw shadow on the left side
                # Use an ellipse that gets narrower as moon waxes
                for px in range(x + 2, center_x):
                    # Calculate how much of this column is in shadow
                    dist_from_center = center_x - px
                    shadow_depth = (
                        shadow_width * (dist_from_center / radius) if radius > 0 else 0
                    )

                    if dist_from_center > shadow_width:
                        # Full shadow for this column
                        col_height = int(
                            math.sqrt(max(0, radius**2 - (px - center_x) ** 2))
                        )
                        if col_height > 0:
                            draw.line(
                                [
                                    (px, center_y - col_height),
                                    (px, center_y + col_height),
                                ],
                                fill=0,
                            )
        else:
            # Waning: left side illuminated, right side dark
            # Fill the whole moon white first
            draw.ellipse([x + 2, y + 2, x + size - 2, y + size - 2], fill=1)

            # Calculate shadow width for waning phase
            wane_progress = (phase_normalized - 0.5) * 2  # 0 at full, 1 at new
            shadow_width = int(wane_progress * radius)

            if shadow_width > 0:
                # Draw shadow on the right side
                for px in range(center_x, x + size - 2):
                    dist_from_center = px - center_x

                    if dist_from_center > (radius - shadow_width):
                        # Shadow for this column
                        col_height = int(
                            math.sqrt(max(0, radius**2 - (px - center_x) ** 2))
                        )
                        if col_height > 0:
                            draw.line(
                                [
                                    (px, center_y - col_height),
                                    (px, center_y + col_height),
                                ],
                                fill=0,
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
                        outline=0,  # Black border
                        width=1,
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
        import math
        import os

        # Map aliases to file names (Phosphor icon naming)
        icon_map = {
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
            "snowflake": "snowflake",  # More specific icon for snow conditions
            "storm": "cloud-lightning",
            "thunder": "cloud-lightning",
            "lightning": "cloud-lightning",
            "cloud-fog": "cloud-fog",
            "fog": "cloud-fog",
            "mist": "cloud-fog",
            "cloud-moon": "cloud-moon",  # For night conditions
            "sun-horizon": "sun-horizon",  # For sunrise/sunset
            "thermometer": "thermometer",  # For temperature display
            "thermometer-hot": "thermometer-hot",  # For hot temperatures
            "thermometer-cold": "thermometer-cold",  # For cold temperatures
            "wind": "wind",  # For wind information
            "rainbow": "rainbow",  # For rainbow conditions
            "rainbow-cloud": "rainbow-cloud",  # Alternative rainbow icon
        }

        # Use mapped name or original
        file_name = icon_map.get(icon_type.lower(), icon_type.lower())

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
            except Exception as e:
                # Log error but don't fall back to programmatic drawing
                import logging
                try:
                    logging.warning(f"Failed to load icon {file_name}.png: {e}")
                except:
                    pass
                # Return early - only use PNG icons from icons/regular folder
                return

        # If PNG file doesn't exist, return early (no programmatic fallback)
        # Only icons from icons/regular folder are used
        import logging
        try:
            logging.warning(f"Icon not found: {file_name}.png (requested as {icon_type})")
        except:
            pass
        return

    def _draw_weather_forecast(
        self, draw: ImageDraw.Draw, x: int, y: int, total_width: int, forecast: list
    ):
        """Draw a 7-day weather forecast row with icons.

        Args:
            draw: ImageDraw object
            x, y: Top-left corner
            total_width: Total width available
            forecast: List of forecast dicts with day, high, low, condition
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
            elif condition_lower == "mainly clear" or condition_lower == "partly cloudy":
                return "cloud-sun"  # Maps to cloud-sun.png
            
            # Overcast (code 3)
            elif condition_lower == "overcast":
                return "cloud"  # Maps to cloud.png
            
            # Fog (codes 45, 48)
            elif condition_lower == "fog" or "mist" in condition_lower:
                return "cloud-fog"  # Maps to cloud-fog.png
            
            # Thunderstorm (codes 95, 96, 99) - check FIRST to avoid false matches
            if "thunderstorm" in condition_lower or "thunder" in condition_lower or "lightning" in condition_lower:
                return "storm"  # Maps to cloud-lightning.png
            
            # Snow-related (codes 71, 73, 75, 77, 85, 86) - check before rain
            elif "snow" in condition_lower:
                return "snowflake"  # Maps to snowflake.png (more specific than cloud-snow)
            
            # Rain-related (codes 51-67, 80-82): Drizzle, Freezing Drizzle, Rain, Freezing Rain, Rain Showers
            elif "rain" in condition_lower or "drizzle" in condition_lower or "showers" in condition_lower:
                return "rain"  # Maps to cloud-rain.png
            
            # Default fallback
            else:
                return "cloud"  # Maps to cloud.png

        num_days = min(len(forecast), 7)
        col_width = total_width // num_days
        icon_size = 24

        # Get small font for text
        font = self._get_font("regular_sm")

        for i, day_data in enumerate(forecast[:7]):
            col_x = x + i * col_width
            col_center = col_x + col_width // 2

            # Day name (e.g., "Mon")
            day_name = day_data.get("day", "--")[:3]
            if font:
                bbox = font.getbbox(day_name)
                text_w = bbox[2] - bbox[0] if bbox else 0
                text_x = col_center - text_w // 2
                draw.text((text_x, y), day_name, font=font, fill=0)

            # Icon
            icon_y = y + 12
            icon_x = col_center - icon_size // 2
            icon_type = get_icon_type(day_data.get("condition", ""))
            self._draw_icon(draw, icon_x, icon_y, icon_type, icon_size)

            # High temp
            high = day_data.get("high", "--")
            high_str = f"{high}°" if high != "--" else "--"
            high_y = icon_y + icon_size + 2
            if font:
                bbox = font.getbbox(high_str)
                text_w = bbox[2] - bbox[0] if bbox else 0
                text_x = col_center - text_w // 2
                draw.text((text_x, high_y), high_str, font=font, fill=0)

            # Low temp (lighter/smaller - using same font but we'll draw lighter)
            low = day_data.get("low", "--")
            low_str = f"{low}°" if low != "--" else "--"
            low_y = high_y + 12
            if font:
                bbox = font.getbbox(low_str)
                text_w = bbox[2] - bbox[0] if bbox else 0
                text_x = col_center - text_w // 2
                # Draw with a dithered pattern for "lighter" appearance
                # Just draw normally for now
                draw.text((text_x, low_y), low_str, font=font, fill=0)

    def _draw_hourly_forecast(
        self, draw: ImageDraw.Draw, x: int, y: int, total_width: int, hourly_forecast: list
    ):
        """Draw a 24-hour hourly weather forecast in rows.

        Args:
            draw: ImageDraw object
            x, y: Top-left corner
            total_width: Total width available
            hourly_forecast: List of dicts with keys: time, temperature, condition
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
            elif condition_lower == "mainly clear" or condition_lower == "partly cloudy":
                return "cloud-sun"  # Maps to cloud-sun.png
            
            # Overcast (code 3)
            elif condition_lower == "overcast":
                return "cloud"  # Maps to cloud.png
            
            # Fog (codes 45, 48)
            elif condition_lower == "fog" or "mist" in condition_lower:
                return "cloud-fog"  # Maps to cloud-fog.png
            
            # Thunderstorm (codes 95, 96, 99) - check FIRST to avoid false matches
            if "thunderstorm" in condition_lower or "thunder" in condition_lower or "lightning" in condition_lower:
                return "storm"  # Maps to cloud-lightning.png
            
            # Snow-related (codes 71, 73, 75, 77, 85, 86) - check before rain
            elif "snow" in condition_lower:
                return "snowflake"  # Maps to snowflake.png (more specific than cloud-snow)
            
            # Rain-related (codes 51-67, 80-82): Drizzle, Freezing Drizzle, Rain, Freezing Rain, Rain Showers
            elif "rain" in condition_lower or "drizzle" in condition_lower or "showers" in condition_lower:
                return "rain"  # Maps to cloud-rain.png
            
            # Default fallback
            else:
                return "cloud"  # Maps to cloud.png

        # Group into rows of 6 hours each
        hours_per_row = 6
        num_rows = (len(hourly_forecast) + hours_per_row - 1) // hours_per_row
        col_width = total_width // hours_per_row
        icon_size = 20
        row_height = icon_size + 12 + 8  # icon + text + spacing

        # Get small font for text
        font = self._get_font("regular_sm")

        for row in range(num_rows):
            row_y = y + row * row_height
            start_idx = row * hours_per_row
            end_idx = min(start_idx + hours_per_row, len(hourly_forecast))

            for col in range(start_idx, end_idx):
                hour_data = hourly_forecast[col]
                col_idx = col - start_idx
                col_x = x + col_idx * col_width
                col_center = col_x + col_width // 2

                # Icon
                icon_y = row_y
                icon_x = int(col_center - icon_size // 2)
                icon_type = get_icon_type(hour_data.get("condition", ""))
                self._draw_icon(draw, icon_x, icon_y, icon_type, icon_size)

                # Time (e.g., "2PM")
                time_str = hour_data.get("time", "--")
                time_y = icon_y + icon_size + 2
                if font:
                    bbox = font.getbbox(time_str)
                    text_w = bbox[2] - bbox[0] if bbox else 0
                    text_x = int(col_center - text_w // 2)
                    draw.text((text_x, time_y), time_str, font=font, fill=0)

                # Temperature
                temp = hour_data.get("temperature", "--")
                temp_str = f"{temp}°" if temp != "--" else "--"
                temp_y = time_y + 10
                if font:
                    bbox = font.getbbox(temp_str)
                    text_w = bbox[2] - bbox[0] if bbox else 0
                    text_x = int(col_center - text_w // 2)
                    draw.text((text_x, temp_y), temp_str, font=font, fill=0)

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
        """
        from datetime import datetime, timedelta

        # Day headers (S M T W T F S)
        day_names = ["S", "M", "T", "W", "T", "F", "S"]
        header_y = y
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
                cell_y = y + 8 + week * cell_size  # +8 for header

                # Draw cell border
                draw.rectangle(
                    [cell_x, cell_y, cell_x + cell_size - 1, cell_y + cell_size - 1],
                    outline=0,
                    width=1,
                )

                # Get date for this cell
                cell_date = grid_start + timedelta(days=week * 7 + day)

                # Draw day number
                day_num = str(cell_date.day)
                if font:
                    bbox = font.getbbox(day_num)
                    text_w = bbox[2] - bbox[0] if bbox else cell_size // 2
                    text_h = bbox[3] - bbox[1] if bbox else cell_size // 2
                    text_x = cell_x + 2
                    text_y = cell_y + 2
                    draw.text((text_x, text_y), day_num, font=font, fill=0)

                # Draw event indicator (dot)
                date_key = cell_date.isoformat()
                if date_key in events_by_date and events_by_date[date_key] > 0:
                    dot_x = cell_x + cell_size - 4
                    dot_y = cell_y + cell_size - 4
                    draw.ellipse([dot_x - 1, dot_y - 1, dot_x + 1, dot_y + 1], fill=0)

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
        line_x = x + 20  # Vertical line position

        for i, item in enumerate(items):
            item_y = y + i * item_height

            # Draw vertical timeline line
            if i < len(items) - 1:
                draw.line(
                    [(line_x, item_y), (line_x, item_y + item_height)], fill=0, width=2
                )

            # Draw circle/node on timeline
            node_radius = 4
            draw.ellipse(
                [
                    line_x - node_radius,
                    item_y - node_radius,
                    line_x + node_radius,
                    item_y + node_radius,
                ],
                fill=0,
            )

            # Draw year label (left of line)
            year = str(item.get("year", ""))
            if font and year:
                draw.text((x, item_y - 4), year, font=font, fill=0)

            # Draw text (right of line)
            text = item.get("text", "")
            if font and text:
                # Truncate if too long
                max_width = self.PRINTER_WIDTH_DOTS - line_x - 30
                if len(text) > max_width // 6:  # Rough estimate
                    text = text[: max_width // 6 - 3] + "..."
                draw.text((line_x + 10, item_y - 4), text, font=font, fill=0)

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
            import math

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

    def _generate_qr_image(
        self, data: str, size: int, error_correction: str, fixed_size: bool
    ) -> Image.Image:
        """Generate a QR code as a PIL Image."""
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

            qr = qrcode.QRCode(
                version=4 if fixed_size else 1,
                error_correction=ec_level,
                box_size=max(1, min(16, size)),
                border=1,
            )
            qr.add_data(data)
            qr.make(fit=not fixed_size)

            qr_img = qr.make_image(fill_color="black", back_color="white")
            return qr_img.convert("1")
        except Exception as e:
            import logging
            logging.warning(f"Failed to generate QR code for data: {data[:50]}... Error: {e}")
            return None

    def _send_bitmap(self, img: Image.Image):
        """Send a bitmap image to the printer using GS v 0 raster command."""
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

            # Get pixel data
            pixels = list(img.getdata())
            bytes_per_row = width // 8

            # Build raster data (1 = white, 0 = black in PIL, but printer wants 1 = black)
            raster_data = bytearray()
            for y in range(height):
                row_start = y * width
                for x_byte in range(bytes_per_row):
                    byte_val = 0
                    for bit in range(8):
                        pixel_idx = row_start + (x_byte * 8) + bit
                        if pixels[pixel_idx] == 0:  # Black pixel in PIL
                            byte_val |= 0x80 >> bit
                    raster_data.append(byte_val)

            # GS v 0 - Print raster bit image
            xL = bytes_per_row & 0xFF
            xH = (bytes_per_row >> 8) & 0xFF
            yL = height & 0xFF
            yH = (height >> 8) & 0xFF

            self._write(
                b"\x1d\x76\x30\x00" + bytes([xL, xH, yL, yH]) + bytes(raster_data)
            )

        except Exception:
            pass

    def _write(self, data: bytes):
        """Internal helper to write bytes to serial interface."""
        try:
            if self.ser and self.ser.is_open:
                self.ser.write(data)
                self.ser.flush()
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
    ):
        """Print a visual calendar grid.

        Args:
            weeks: Number of weeks to show (default 4)
            cell_size: Size of each day cell in pixels (default 8)
            start_date: First date to show (default: today)
            events_by_date: Dict mapping date strings to event counts
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
        import logging
        logger = logging.getLogger(__name__)
        
        if len(self.print_buffer) == 0:
            return

        try:
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
            else:
                logger.error("flush_buffer: _render_unified_bitmap returned None")
        except Exception as e:
            logger.error(f"flush_buffer error: {e}", exc_info=True)
            # Re-raise so the caller knows something went wrong
            raise

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

    def feed_direct(self, lines: int = 3):
        """Feed paper directly, bypassing the buffer (for use after flushing in invert mode)."""
        try:
            for _ in range(lines):
                self._write(b"\n")
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
