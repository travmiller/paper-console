import math
import os
import platform
import random
import time
import unicodedata
from datetime import datetime, date
from typing import List, Optional, Any

import serial
from PIL import Image, ImageDraw, ImageFont
import app.config
import app.selection_mode


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
        # Each item is a tuple: ('text', line) or ('feed', count) or ('qr', data).
        self.print_buffer = []
        # Line tracking for max print length
        self.lines_printed = 0
        self.max_lines = 0  # 0 = no limit, set by reset_buffer
        self._max_lines_hit = False  # Flag set when max lines exceeded during flush

        # Cutter feed space in dots (24 dots ~= 1 line).
        # Applied as an explicit post-print feed command for reliability.
        # Can be updated via set_cutter_feed() method.
        self.cutter_feed_dots = 12 * 24  # 12 lines * 24 dots/line = 288 dots

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
        # IBM Plex Mono has: Regular, Medium, SemiBold, Bold, Italic
        # Using Medium as base weight, SemiBold and Bold for headings
        font_variants = {
            "regular": "IBMPlexMono-Medium.ttf",  # Medium as base weight
            "bold": "IBMPlexMono-Bold.ttf",  # Bold for headings
            "medium": "IBMPlexMono-Medium.ttf",
            "light": "IBMPlexMono-Medium.ttf",  # Map light to Medium (base weight)
            "semibold": "IBMPlexMono-SemiBold.ttf",  # SemiBold for headings
            "italic": "IBMPlexMono-MediumItalic.ttf",  # Italic for emphasis
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

    def _get_left_margin(self) -> int:
        """Get the left margin, which increases when in selection mode."""
        if app.selection_mode.is_selection_mode_active():
            # 2px dashed line + 6px gap + 2px standard margin
            return 10
        return 2

    def _get_content_width(self) -> int:
        """Get the available width for content."""
        # Total width - left margin - right margin (2px)
        return self.PRINTER_WIDTH_DOTS - self._get_left_margin() - 2

    def _render_op(self, img: Image.Image, draw: ImageDraw.Draw, y: int, op_type: str, op_data: Any, dry_run: bool = False) -> tuple[int, int]:
        """Render a single operation or calculate its dimensions.
        
        Returns:
            tuple: (content_height, spacing_after)
        """
        if op_type == "styled":
            return self._render_op_styled(draw, y, op_data, dry_run)
        elif op_type == "text":
            return self._render_op_text_legacy(draw, y, op_data, dry_run)
        elif op_type == "box":
            return self._render_op_box(img, draw, y, op_data, dry_run)
        elif op_type == "icon":
            return self._render_op_icon(draw, y, op_data, dry_run)
        elif op_type == "image":
            return self._render_op_image(img, y, op_data, dry_run)
        elif op_type == "article_block":
            return self._render_op_article_block(img, draw, y, op_data, dry_run)
        elif op_type == "qr":
            return self._render_op_qr(img, y, op_data, dry_run)
        elif op_type == "feed":
            return (op_data * self.SPACING_LARGE, 0)
        
        return (0, 0)

    def _render_op_styled(self, draw: ImageDraw.Draw, y: int, op_data: dict, dry_run: bool) -> tuple[int, int]:
        clean_text = self._sanitize_text(op_data["text"])
        style = op_data.get("style", "regular")
        font = self._get_font(style)
        line_height = self._get_line_height_for_style(style)
        
        current_height = 0
        
        paragraphs = clean_text.split("\n")
        content_width = self._get_content_width()
        left_margin = self._get_left_margin()

        for paragraph in paragraphs:
            if not paragraph.strip():
                current_height += line_height
            else:
                wrapped_lines = self._wrap_text_by_width(paragraph, font, content_width)
                for line in wrapped_lines:
                    if not dry_run and draw:
                        if font:
                            draw.text((left_margin, y + current_height), line, font=font, fill=0)
                        else:
                            draw.text((left_margin, y + current_height), line, fill=0)
                    current_height += line_height
        
        return (current_height, 0)

    def _render_op_text_legacy(self, draw: ImageDraw.Draw, y: int, op_data: str, dry_run: bool) -> tuple[int, int]:
        clean_text = self._sanitize_text(op_data)
        font = self._get_font("regular")
        current_height = 0
        
        paragraphs = clean_text.split("\n")
        content_width = self._get_content_width()
        left_margin = self._get_left_margin()

        for paragraph in paragraphs:
            if not paragraph.strip():
                current_height += self.line_height
                if not dry_run:
                    self.lines_printed += 1
            else:
                wrapped_lines = self._wrap_text_by_width(paragraph, font, content_width)
                for line in wrapped_lines:
                    if not dry_run and draw:
                        if font:
                            draw.text((left_margin, y + current_height), line, font=font, fill=0)
                        else:
                            draw.text((left_margin, y + current_height), line, fill=0)
                    current_height += self.line_height
                    if not dry_run:
                        self.lines_printed += 1
        
        return (current_height, 0)

    def _render_op_box(self, img: Image.Image, draw: ImageDraw.Draw, y: int, op_data: dict, dry_run: bool) -> tuple[int, int]:
        text = self._sanitize_text(op_data.get("text", ""))
        style = op_data.get("style", "bold_lg")
        padding = op_data.get("padding", self.SPACING_MEDIUM)
        border = op_data.get("border", 2)
        icon_type = op_data.get("icon")
        icon_size = op_data.get("icon_size", 24) if icon_type else 0
        font = self._get_font(style)
        text_height = self._get_line_height_for_style(style)

        content_width = self._get_content_width()
        left_margin = self._get_left_margin()
        
        # Adjust box width to fit within content area
        # Box uses SPACING_SMALL as right margin relative to content width? 
        # Original: box_width = self.PRINTER_WIDTH_DOTS - self.SPACING_SMALL
        # This implies a right margin of SPACING_SMALL (4px)
        # So we should use content_width - (SPACING_SMALL - 2)? 
        # If content_width accounts for right margin of 2px.
        # Let's keep the box width relative to content width.
        box_width = content_width - (self.SPACING_SMALL - 2)
        
        box_height = max(text_height, icon_size) + (padding * 2) + (border * 2)
        
        if not dry_run and draw:
            box_x = left_margin
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

            # Calculate content layout
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

        # 2px margin top + box height
        return (2 + box_height, self.SPACING_MEDIUM)

    def _render_op_icon(self, draw: ImageDraw.Draw, y: int, op_data: dict, dry_run: bool) -> tuple[int, int]:
        icon_type = op_data.get("type", "sun")
        size = op_data.get("size", 32)
        
        if not dry_run and draw:
            # Center within content area
            icon_x = self._get_left_margin() + (self._get_content_width() - size) // 2
            # SPACING_SMALL top margin
            icon_y = y + self.SPACING_SMALL
            self._draw_icon(draw, icon_x, icon_y, icon_type, size)
            
        # Top margin + icon size
        return (self.SPACING_SMALL + size, self.SPACING_SMALL)

    def _render_op_image(self, img: Image.Image, y: int, op_data: dict, dry_run: bool) -> tuple[int, int]:
        image = op_data.get("image")
        if not image:
            return (0, 0)
            
        target_width = self._get_content_width()
        final_height = image.height
        
        if image.width > target_width:
             ratio = target_width / image.width
             final_height = int(image.height * ratio)
             
        if not dry_run and img:
            img_to_draw = image
            if img_to_draw.width > target_width:
                 img_to_draw = img_to_draw.resize((target_width, final_height), Image.Resampling.LANCZOS)
            
            if img_to_draw.mode != "1":
                img_to_draw = img_to_draw.convert("1")
                
            img_x = self._get_left_margin() + (target_width - img_to_draw.width) // 2
            # SPACING_SMALL top margin
            img_y = y + self.SPACING_SMALL
            img.paste(img_to_draw, (img_x, img_y))
        
        return (final_height + self.SPACING_SMALL, self.SPACING_MEDIUM)  # Height + top margin

    def _render_op_qr(self, img: Image.Image, y: int, op_data: dict, dry_run: bool) -> tuple[int, int]:
        # Reuse key if already generated
        qr_img = op_data.get("_qr_img")
        if not qr_img:
            qr_img = self._generate_qr_image(
                op_data["data"],
                op_data["size"],
                op_data["ec"],
                op_data.get("fixed", False),
            )
            op_data["_qr_img"] = qr_img
            
        if not qr_img:
            return (0, 0)

        # For height calc we assume scaling happens same way
        max_qr_width = self._get_content_width()
        qr_width = qr_img.width
        qr_height = qr_img.height
        if qr_width > max_qr_width:
             # re-sim resize
             scale_factor = max_qr_width / qr_width
             qr_width = int(qr_width * scale_factor)
             qr_height = int(qr_height * scale_factor)

        if not dry_run and img:
            # Check constraints and flush if needed logic is upstream
            # But here we assume it fits or is resized.
            
            # Since we recalculated qr_width/qr_height for constraint, use it for resize
            if qr_img.width > max_qr_width:
                qr_img = qr_img.resize((qr_width, qr_height), Image.NEAREST)
            
            # Center in content area
            qr_x = self._get_left_margin() + (self._get_content_width() - qr_width) // 2
            qr_y = y + self.SPACING_SMALL
            img.paste(qr_img, (qr_x, qr_y))

        return (qr_height + self.SPACING_SMALL, self.SPACING_SMALL)

    def _render_op_article_block(self, img: Image.Image, draw: ImageDraw.Draw, y: int, op_data: dict, dry_run: bool) -> tuple[int, int]:
        qr_size = op_data.get("qr_size", 64)
        
        # 1. QR Gen
        qr_img = op_data.get("_qr_img")
        if not qr_img and "url" in op_data:
             qr_raw = self._generate_qr_image(op_data.get("url", ""), 10, "M", False)
             if qr_raw:
                 qr_img = qr_raw.resize((qr_size, qr_size), Image.LANCZOS)
             op_data["_qr_img"] = qr_img
        
        # 2. Text Layout
        # Respect left margin + SPACING_SMALL indent
        text_x = self._get_left_margin() + self.SPACING_SMALL
        current_offset = 2 # Start 2px down
        
        right_margin = self.SPACING_SMALL
        # Available width is Total - text_start - right_margin
        available_text_width = self.PRINTER_WIDTH_DOTS - text_x - right_margin
        
        # Source
        source = op_data.get("source", "")
        source_font = self._get_font("caption")
        source_height = self._get_line_height_for_style("caption")
        
        if source and source_font and not dry_run and draw:
            source_text = source.upper()
            # Truncate
            max_source_width = available_text_width
            while source_text and source_font.getlength(source_text) > max_source_width:
                source_text = source_text[:-1]
            draw.text((text_x, y + current_offset), source_text, font=source_font, fill=0)

        if source:
             current_offset += source_height
        
        # Title
        title_font = self._get_font("bold")
        title_line_height = self._get_line_height_for_style("bold")
        title_text = op_data.get("title", "")
        
        title_lines = self._wrap_text_by_width(title_text, title_font, available_text_width) if title_font else []
        
        if not dry_run and draw and title_font:
             for line in title_lines:
                 draw.text((text_x, y + current_offset), line, font=title_font, fill=0)
                 current_offset += title_line_height
        else:
             current_offset += len(title_lines) * title_line_height
             
        # Summary
        summary_font = self._get_font("regular_sm")
        summary_line_height = self._get_line_height_for_style("regular_sm")
        summary_text = op_data.get("summary", "")
        max_summary_lines = op_data.get("max_summary_lines", 3)
        
        summary_lines = self._wrap_text_by_width(summary_text, summary_font, available_text_width)[:max_summary_lines] if summary_font else []
        
        if not dry_run and draw and summary_font:
             for line in summary_lines:
                 draw.text((text_x, y + current_offset), line, font=summary_font, fill=0)
                 current_offset += summary_line_height
        else:
             current_offset += len(summary_lines) * summary_line_height
             
        # QR
        if qr_img:
            current_offset += self.SPACING_SMALL
            if not dry_run and img:
                 # Center QR in content area? Or maintain simple center?
                 # Let's simple center in content width
                 qr_x = self._get_left_margin() + (self._get_content_width() - qr_img.width) // 2
                 img.paste(qr_img, (qr_x, y + current_offset))
            current_offset += qr_img.height + self.SPACING_SMALL
        else:
            current_offset += self.SPACING_SMALL
            
        return (current_offset, self.SPACING_MEDIUM)

    def _render_unified_bitmap(self, ops: list) -> Image.Image:
        """Render ALL buffer operations into one unified bitmap.

        Refactored to use a 2-pass system with dry-run capabilities
        to ensure height calculation perfectly matches drawing.
        """
        import qrcode as qr_lib

        if not ops:
            return None

        # Pass 1: Measure
        measured_content_height = 0
        last_spacing = 0
        for op_type, op_data in ops:
             h, s = self._render_op(None, None, 0, op_type, op_data, dry_run=True)
             if h > 0:
                 measured_content_height += h + s
                 last_spacing = s
             
        # Remove trailing spacing
        measured_content_height -= last_spacing
        
        # Content-only bitmap height. Cutter feed is now applied explicitly
        # after bitmap transmission for more consistent behavior across printers.
        total_height = measured_content_height + (self.SPACING_LARGE * 2)
        
        # Create Image
        width = self.PRINTER_WIDTH_DOTS
        img = Image.new("1", (width, total_height), 1)
        draw = ImageDraw.Draw(img)
        
        # Pass 2: Draw content from top (y=0); bottom = white = tear-edge clearance
        current_y = 0
        for op_type, op_data in ops:
             h, s = self._render_op(img, draw, current_y, op_type, op_data, dry_run=False)
             if h > 0:
                 current_y += h + s
        
        # Draw Selection Mode Visual Indicator
        if app.selection_mode.is_selection_mode_active():
            # Draw a thin dashed line along the left side
            # 2px wide, dashed
            
            line_x = 0
            line_width = 2
            dash_length = 8
            gap_length = 4
            
            for y in range(0, current_y, dash_length + gap_length):
                segment_end = min(y + dash_length, current_y)
                if segment_end > y:
                    draw.rectangle(
                        [line_x, y, line_x + line_width - 1, segment_end - 1], 
                        fill=0
                    )

        # Rotate
        img = img.rotate(180)
        return img



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
            # Generate at higher resolution (box_size) for better quality when scaling
            box_size = max(size, 8) if fixed_size else size
            qr = qrcode.QRCode(
                version=1,
                error_correction=ec_level,
                box_size=box_size,
                border=1,
            )
            qr.add_data(data)
            qr.make(fit=True)

            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_img = qr_img.convert("1")

            # If fixed_size, resize all QR codes to the same dimensions
            if fixed_size:
                # Target size: 80x80 pixels for consistent appearance (for standalone QR codes)
                target_size = 80
                # Use LANCZOS for better quality when scaling
                qr_img = qr_img.resize((target_size, target_size), Image.LANCZOS)

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

            # Send entire image in chunks to prevent buffer overflow
            print(f"[DEBUG] Sending bitmap: {width}x{height} ({len(command)} bytes)")
            CHUNK_SIZE = 4096
            total_sent = 0
            for i in range(0, len(command), CHUNK_SIZE):
                chunk = command[i : i + CHUNK_SIZE]
                self._write(bytes(chunk))
                total_sent += len(chunk)
                # Small yield to let hardware buffer drain slightly
                time.sleep(0.01)
            print(f"[DEBUG] Bitmap send complete. Total bytes: {total_sent}")


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
        except Exception as e:
            print(f"[ERROR] Serial write failed: {e}")

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

        Handles multi-line text by splitting on newlines. Each line/paragraph
        will be wrapped to fit the printer width using font metrics.

        Available styles:
            - "regular": Normal body text
            - "bold": Bold text
            - "bold_lg": Large bold text (for headers)
            - "medium": Medium weight
            - "semibold": Semi-bold
            - "light": Light weight
            - "regular_sm": Small regular text
        """
        if not text:
            return

        # Split by newlines to handle multi-line text properly
        # Empty lines are preserved as blank lines for spacing
        lines = text.split("\n")

        # Safety: prevent unbounded buffer growth
        for line in lines:
            if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
                self.flush_buffer()
            # Buffer each line separately with the same style
            # Empty strings represent blank lines (preserved for spacing)
            self.print_buffer.append(("styled", {"text": line, "style": style}))

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
        # Use ASCII-only pattern so separators survive text sanitization.
        line = ". " * (self.width // 2)
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
        """Print an article with QR code below the text on a new line.

        Args:
            source: News source name
            title: Article headline
            summary: Article summary/description
            url: URL to encode as QR code
            qr_size: Size of QR code in pixels (default 64)
            title_width: Characters per line for title wrapping (fallback, uses pixel-based wrapping)
            summary_width: Characters per line for summary wrapping (fallback, uses pixel-based wrapping)
            max_summary_lines: Maximum summary lines to show
        """
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()

        # Wrap title and summary (fallback for pixel-based wrapping in renderer)
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
            "summary": summary,  # Store raw summary for pixel-based re-wrapping
            "title_wrapped": title_wrapped,
            "summary_wrapped": summary_wrapped,
            "url": url,
            "qr_size": qr_size,
            "max_summary_lines": max_summary_lines,
            "title_lines": len(title_wrapped),
            "summary_lines": len(summary_wrapped),
        }

        self.print_buffer.append(("article_block", article_data))

    def print_thick_line(self):
        """Print a bold separator line."""
        line = "━" * self.width
        self.print_text(line, "bold")





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





    def print_image(self, image: Image.Image):
        """Print a generic PIL Image.

        The image will be:
        1. Resized to fit the paper width if too wide (maintaining aspect ratio).
        2. Centered horizontally.
        3. Converted to 1-bit monochrome if not already.

        Args:
            image: PIL Image object
        """
        if not image:
            return
            
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()
            
        self.print_buffer.append(
            (
                "image",
                {
                    "image": image,
                },
            )
        )



    def feed(self, lines: int = 3):
        """Feed paper (advance lines). Buffers for reverse-order printing."""
        self.print_buffer.append(("feed", lines))

    def flush_buffer(self):
        """Flush the print buffer as ONE unified bitmap for speed.

        All text, feeds, and QR codes are rendered into a single tall image,
        rotated 180°, and sent as one raster graphics command.
        """
        if not self.print_buffer:
            print("[DEBUG] Flush called on empty buffer.")
            return

        print(f"[DEBUG] Flushing buffer with {len(self.print_buffer)} ops...")


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
            print(f"[DEBUG] Rendered unified bitmap: {img.size}")
            self._send_bitmap(img)
            # Ensure all data is transmitted before returning
            if self.ser and self.ser.is_open:
                try:
                    self.ser.flush()
                except Exception as e:
                    print(f"[ERROR] Serial flush failed: {e}")
            # Explicit post-print feed for cutter clearance.
            # Use feed_direct() because it sends both ESC d and ESC J variants
            # for better compatibility across printer firmwares.
            feed_lines = max(0, int(self.cutter_feed_dots / 24))
            if feed_lines > 0:
                try:
                    self.feed_direct(feed_lines)
                except Exception as e:
                    print(f"[ERROR] Post-print feed failed: {e}")
        else:
            print("[DEBUG] No bitmap rendered from ops.")


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

    def feed_dots(self, dots: int = 12):
        """Feed paper by raw dot count (12 dots ~= half line)."""
        if dots <= 0:
            return
        remaining = int(dots)
        try:
            while remaining > 0:
                chunk = min(remaining, 255)
                self._write(b"\x1b\x4a" + bytes([chunk]))  # ESC J n
                remaining -= chunk
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



    def close(self):
        """Close the serial connection."""
        if self.ser and self.ser.is_open:
            self.ser.close()
