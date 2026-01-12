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
                        fonts[variant_name] = ImageFont.truetype(font_path, self.font_size)
                        # Load at header size (6px larger for clear hierarchy)
                        fonts[f"{variant_name}_lg"] = ImageFont.truetype(font_path, self.font_size + 6)
                        # Load at small/caption size (4px smaller)
                        fonts[f"{variant_name}_sm"] = ImageFont.truetype(font_path, max(10, self.font_size - 4))
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
                        fonts["regular_lg"] = ImageFont.truetype(path, self.font_size + 6)
                        fonts["regular_sm"] = ImageFont.truetype(path, max(10, self.font_size - 4))
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
        if font and hasattr(font, 'size'):
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
        qr_images = []  # Store pre-rendered QR codes with their positions
        
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
                text_height = self._get_line_height_for_style(style)
                box_height = border + padding + text_height + padding + border
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
            elif op_type == "feed":
                total_height += op_data * self.line_height
            elif op_type == "qr":
                # Pre-render QR code to get its height
                qr_img = self._generate_qr_image(
                    op_data["data"],
                    op_data["size"],
                    op_data["ec"],
                    op_data.get("fixed", False),
                )
                if qr_img:
                    qr_images.append((len(qr_images), qr_img))
                    total_height += qr_img.height + 4  # +4 for spacing

        # Create the unified image
        width = self.PRINTER_WIDTH_DOTS
        img = Image.new("1", (width, total_height), 1)  # White background
        draw = ImageDraw.Draw(img)

        # Second pass: draw everything
        y = 2
        qr_idx = 0
        
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
                font = self._get_font(style)
                text_height = self._get_line_height_for_style(style)
                
                # Full width box
                box_width = width - 4  # Leave 2px margin on each side
                box_height = text_height + (padding * 2) + (border * 2)
                
                box_x = 2  # Small left margin
                box_y = y + 2  # Small top margin
                
                # Draw outer rectangle (black border)
                draw.rectangle(
                    [box_x, box_y, box_x + box_width, box_y + box_height],
                    fill=0  # Black
                )
                # Draw inner rectangle (white) - creates the border effect
                draw.rectangle(
                    [box_x + border, box_y + border, 
                     box_x + box_width - border, box_y + box_height - border],
                    fill=1  # White
                )
                
                # Center text horizontally within the box
                if font:
                    bbox = font.getbbox(text)
                    text_width = bbox[2] - bbox[0] if bbox else len(text) * 10
                else:
                    text_width = len(text) * 10
                
                text_x = box_x + (box_width - text_width) // 2
                text_y = box_y + border + padding
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
                    
                    self._draw_sudoku_grid(draw, sudoku_x, sudoku_y, grid, cell_size, font)
                    
                    y += sudoku_size + 8
            elif op_type == "feed":
                y += op_data * self.line_height
            elif op_type == "qr":
                if qr_idx < len(qr_images):
                    _, qr_img = qr_images[qr_idx]
                    # Center QR code horizontally
                    x_offset = (width - qr_img.width) // 2
                    img.paste(qr_img, (x_offset, y + 2))
                    y += qr_img.height + 4
                    qr_idx += 1

        # Rotate 180° for upside-down printing
        img = img.rotate(180)

        return img

    def _draw_moon_phase(self, draw: ImageDraw.Draw, x: int, y: int, size: int, phase: float):
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
            shadow_width = int((1 - illumination * 2) * radius) if illumination < 0.5 else 0
            
            if shadow_width > 0:
                # Draw shadow on the left side
                # Use an ellipse that gets narrower as moon waxes
                for px in range(x + 2, center_x):
                    # Calculate how much of this column is in shadow
                    dist_from_center = center_x - px
                    shadow_depth = shadow_width * (dist_from_center / radius) if radius > 0 else 0
                    
                    if dist_from_center > shadow_width:
                        # Full shadow for this column
                        col_height = int(math.sqrt(max(0, radius**2 - (px - center_x)**2)))
                        if col_height > 0:
                            draw.line([(px, center_y - col_height), (px, center_y + col_height)], fill=0)
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
                        col_height = int(math.sqrt(max(0, radius**2 - (px - center_x)**2)))
                        if col_height > 0:
                            draw.line([(px, center_y - col_height), (px, center_y + col_height)], fill=0)
        
        # Redraw outline to ensure clean edges
        draw.ellipse([x, y, x + size, y + size], outline=0, width=2)

    def _draw_maze(self, draw: ImageDraw.Draw, x: int, y: int, grid: List[List[int]], cell_size: int):
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
                    # Wall - draw filled black rectangle
                    draw.rectangle(
                        [cell_x, cell_y, cell_x + cell_size - 1, cell_y + cell_size - 1],
                        fill=0  # Black
                    )
                else:
                    # Path - draw white rectangle (or leave blank)
                    draw.rectangle(
                        [cell_x, cell_y, cell_x + cell_size - 1, cell_y + cell_size - 1],
                        fill=1,  # White
                        outline=0,  # Black border
                        width=1
                    )
        
        # Draw entrance marker (top center)
        if rows > 0 and cols > 1:
            entrance_col = 1  # Usually second column
            entrance_x = x + entrance_col * cell_size
            entrance_y = y
            # Draw arrow pointing down
            draw.line([entrance_x + cell_size // 2, entrance_y, 
                      entrance_x + cell_size // 2, entrance_y + cell_size // 2], fill=0, width=2)
            # Arrow head
            arrow_size = 3
            arrow_x = entrance_x + cell_size // 2
            arrow_y = entrance_y + cell_size // 2
            draw.line([arrow_x, arrow_y, arrow_x - arrow_size, arrow_y - arrow_size], fill=0, width=2)
            draw.line([arrow_x, arrow_y, arrow_x + arrow_size, arrow_y - arrow_size], fill=0, width=2)
        
        # Draw exit marker (bottom)
        if rows > 0 and cols > 1:
            exit_col = cols - 2  # Usually second-to-last column
            exit_x = x + exit_col * cell_size
            exit_y = y + (rows - 1) * cell_size
            # Draw arrow pointing down
            arrow_x = exit_x + cell_size // 2
            arrow_y = exit_y + cell_size - cell_size // 2
            draw.line([arrow_x, arrow_y - cell_size // 2, arrow_x, arrow_y], fill=0, width=2)
            # Arrow head pointing down
            draw.line([arrow_x, arrow_y, arrow_x - arrow_size, arrow_y + arrow_size], fill=0, width=2)
            draw.line([arrow_x, arrow_y, arrow_x + arrow_size, arrow_y + arrow_size], fill=0, width=2)

    def _draw_sudoku_grid(self, draw: ImageDraw.Draw, x: int, y: int, grid: List[List[int]], 
                          cell_size: int, font):
        """Draw a Sudoku grid as a bitmap.
        
        Args:
            draw: ImageDraw object
            x, y: Top-left corner of grid
            grid: 9x9 grid where 0 = empty, 1-9 = number
            cell_size: Size of each cell in pixels
            font: Font for drawing numbers
        """
        border_width = 2  # Thick border for outer edges
        thin_width = 1     # Thin border for inner cells
        
        total_size = 9 * cell_size + 2 * border_width
        
        # Draw outer border
        draw.rectangle([x, y, x + total_size, y + total_size], outline=0, width=border_width)
        
        # Draw grid lines and numbers
        for row in range(9):
            for col in range(9):
                cell_x = x + border_width + col * cell_size
                cell_y = y + border_width + row * cell_size
                
                # Determine border width (thick for 3x3 boundaries)
                top_width = border_width if row % 3 == 0 else thin_width
                left_width = border_width if col % 3 == 0 else thin_width
                bottom_width = border_width if row == 8 else (border_width if (row + 1) % 3 == 0 else thin_width)
                right_width = border_width if col == 8 else (border_width if (col + 1) % 3 == 0 else thin_width)
                
                # Draw cell borders
                # Top
                if row == 0 or row % 3 == 0:
                    draw.line([cell_x, cell_y, cell_x + cell_size, cell_y], fill=0, width=top_width)
                # Left
                if col == 0 or col % 3 == 0:
                    draw.line([cell_x, cell_y, cell_x, cell_y + cell_size], fill=0, width=left_width)
                # Bottom
                draw.line([cell_x, cell_y + cell_size, cell_x + cell_size, cell_y + cell_size], fill=0, width=bottom_width)
                # Right
                draw.line([cell_x + cell_size, cell_y, cell_x + cell_size, cell_y + cell_size], fill=0, width=right_width)
                
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

    def _generate_qr_image(
        self, data: str, size: int, error_correction: str, fixed_size: bool
    ) -> Image.Image:
        """Generate a QR code as a PIL Image."""
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
        except Exception:
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

    def print_header(self, text: str):
        """Print large bold header text in a drawn box."""
        # Add a box operation to the buffer
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()
        self.print_buffer.append(("box", {
            "text": text.upper(),
            "style": "bold_lg",
            "padding": 8,  # pixels of padding inside box
            "border": 2,   # border thickness in pixels
        }))
    
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
        self.print_buffer.append(("moon", {
            "phase": phase,
            "size": size,
        }))

    def print_maze(self, grid: List[List[int]], cell_size: int = 4):
        """Print a maze as a bitmap graphic.
        
        Args:
            grid: 2D list where 1 = wall, 0 = path
            cell_size: Size of each cell in pixels (default 4)
        """
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()
        self.print_buffer.append(("maze", {
            "grid": grid,
            "cell_size": cell_size,
        }))

    def print_sudoku(self, grid: List[List[int]], cell_size: int = 8):
        """Print a Sudoku grid as a bitmap graphic.
        
        Args:
            grid: 9x9 grid where 0 = empty, 1-9 = number
            cell_size: Size of each cell in pixels (default 8)
        """
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()
        self.print_buffer.append(("sudoku", {
            "grid": grid,
            "cell_size": cell_size,
        }))

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
        if len(self.print_buffer) == 0:
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

    def print_header(self, text: str):
        """Print large bold header text in a drawn box."""
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()
        self.print_buffer.append(("box", {
            "text": text.upper(),
            "style": "bold_lg",
            "padding": 8,
            "border": 2,
        }))
        self.print_line()

    def close(self):
        """Close the serial connection."""
        if self.ser and self.ser.is_open:
            self.ser.close()
