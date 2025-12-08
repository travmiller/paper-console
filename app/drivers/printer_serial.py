import serial
import platform
import os
import unicodedata
import time
from typing import Optional


class PrinterDriver:
    """
    Real hardware driver for thermal receipt printer (QR204/CSN-A2).
    Uses serial communication (TTL/USB) or direct USB device file.
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

    # DTR pin for hardware flow control (GPIO 18, Pin 12)
    DTR_PIN = 18

    def __init__(
        self,
        width: int = 32,
        port: Optional[str] = None,
        baudrate: int = 9600,
    ):
        self.width = width
        self.ser = None
        self.usb_file = None
        self.usb_fd = None
        self.dtr_handle = None  # GPIO handle for DTR pin
        # Buffer for print operations (prints are always inverted/reversed)
        # Each item is a tuple: ('text', line) or ('feed', count)
        self.print_buffer = []
        # Line tracking for max print length
        self.lines_printed = 0
        self.max_lines = 0  # 0 = no limit, set by reset_buffer
        self._abort = False  # Flag to abort printing immediately
        self._max_lines_hit = False  # Flag set when max lines exceeded during flush

        # Initialize DTR GPIO pin
        self._init_dtr_gpio()

        # Auto-detect serial port if not specified
        if port is None:
            # Common ports for thermal printers
            if platform.system() == "Linux":
                # Check specifically for USB Printer device first (most common)
                if os.path.exists("/dev/usb/lp0"):
                    port = "/dev/usb/lp0"
                else:
                    # Try ports in order of preference:
                    # 1. USB serial adapters (safest)
                    # 2. GPIO serial (requires console to be disabled)
                    possible_ports = [
                        "/dev/ttyUSB0",
                        "/dev/ttyUSB1",
                        "/dev/ttyACM0",
                        "/dev/ttyACM1",
                        "/dev/serial0",  # GPIO serial - needs console disabled
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

        # Handle USB Line Printer (/dev/usb/lp0) differently from Serial
        if port and "lp" in port and platform.system() == "Linux":
            try:
                import time

                self.usb_fd = os.open(port, os.O_RDWR)
                self.usb_file = None
                time.sleep(0.3)  # Let printer settle after port open
                self._initialize_printer()
                return
            except Exception:
                return

        # Fallback to Serial
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

    def _init_dtr_gpio(self):
        """Initialize DTR GPIO pin for hardware flow control (INPUT to read printer busy)."""
        if platform.system() != "Linux":
            return

        try:
            from app.drivers.gpio_ioctl import (
                GpioChip,
                GPIOHANDLE_REQUEST_INPUT,
            )

            if os.path.exists("/dev/gpiochip0"):
                chip = GpioChip("/dev/gpiochip0")
                self.dtr_handle = chip.request_lines(
                    [self.DTR_PIN], GPIOHANDLE_REQUEST_INPUT, label="printer_dtr"
                )
        except Exception:
            self.dtr_handle = None

    def _is_printer_ready(self) -> bool:
        """Check if printer is ready (DTR HIGH = ready, LOW = busy)."""
        if not self.dtr_handle:
            return True  # No DTR, assume ready
        try:
            values = self.dtr_handle.get_values()
            # HIGH (1) = ready, LOW (0) = busy
            return values[0] == 1
        except Exception:
            return True  # On error, assume ready

    def _wait_for_printer_ready(self, timeout: float = 5.0) -> bool:
        """Wait for printer to be ready (DTR LOW). Returns False if aborted or timeout."""
        import time

        # Check abort FIRST before any waiting
        if self._abort:
            return False

        start = time.time()
        while not self._is_printer_ready():
            if self._abort:
                return False
            if time.time() - start > timeout:
                return True  # Timeout - proceed anyway
            time.sleep(0.01)  # Check every 10ms

        # Check abort again after waiting
        if self._abort:
            return False
        return True

    def _write(self, data: bytes):
        """Internal helper to write bytes to the correct interface."""
        try:
            if hasattr(self, "usb_fd") and self.usb_fd is not None:
                os.write(self.usb_fd, data)
            elif self.usb_file:
                self.usb_file.write(data)
                self.usb_file.flush()
            elif self.ser and self.ser.is_open:
                self.ser.write(data)
                self.ser.flush()
        except Exception:
            pass

    def abort(self):
        """Abort current printing operation immediately."""
        self._abort = True
        # Clear software buffer
        self.print_buffer.clear()

    def was_aborted(self) -> bool:
        """Check if last print was aborted."""
        return self._abort

    def clear_hardware_buffer(self):
        """Clear the printer's hardware buffer - call at startup to prevent garbage."""
        import time

        try:
            # Reset abort flag on clear
            self._abort = False

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
        """Apply ASCII-only mode settings (QR204 confirmed commands only)."""
        try:
            # Cancel Chinese character mode (confirmed in QR204 manual)
            self._write(b"\x1c\x2e")  # FS . (1C 2E) - Cancel Chinese mode

            # Select USA character set (confirmed in QR204 manual)
            self._write(b"\x1b\x52\x00")  # ESC R 0 (1B 52 00) - USA character set

            # Select code page PC437 (confirmed in QR204 manual)
            self._write(b"\x1b\x74\x00")  # ESC t 0 (1B 74 00) - Code page PC437 (US)

            # Set default line spacing (confirmed in QR204 manual)
            self._write(b"\x1b\x32")  # ESC 2 (1B 32) - Default line spacing

            # Enable 180° rotation (standard ESC/POS, required for this unit despite missing from manual)
            self._write(b"\x1b\x7b\x01")  # ESC { 1 - 180° rotation
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
            # Re-apply rotation (required for correct orientation)
            self._write(b"\x1b\x7b\x01")  # ESC { 1
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
        import time

        # Check abort before doing anything
        if self._abort:
            return

        try:
            # Wait for printer to be ready (DTR-based flow control)
            if not self._wait_for_printer_ready():
                return  # Aborted while waiting

            # Check again after wait
            if self._abort:
                return

            # Sanitize to pure ASCII - prevents Chinese characters
            clean_line = self._sanitize_text(line)

            # Encode as ASCII (safe now that we've sanitized)
            encoded = clean_line.encode("ascii", errors="replace")

            self._write(encoded)
            self._write(b"\n")
            self.lines_printed += 1

            # Small yield to allow abort flag to be set from button thread
            time.sleep(0.001)
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

    def print_text(self, text: str):
        """Print a line of text. Buffers for reverse-order printing."""
        # Safety: prevent unbounded buffer growth
        if len(self.print_buffer) >= self.MAX_BUFFER_SIZE:
            self.flush_buffer()
        self.print_buffer.append(("text", text))
        # Note: lines_printed is incremented in _write_text_line() when actually printed
        # to avoid double-counting

    def print_line(self):
        """Print a separator line."""
        line = "-" * self.width
        self.print_text(line)

    def _write_feed(self, count: int):
        """Internal method to feed paper."""
        if self._abort:
            return
        try:
            for _ in range(count):
                if self._abort:
                    return
                # Wait for printer to be ready before each feed
                if not self._wait_for_printer_ready():
                    return  # Aborted
                self._write(b"\n")
        except Exception:
            pass

    def feed(self, lines: int = 3):
        """Feed paper (advance lines). Buffers for reverse-order printing."""
        self.print_buffer.append(("feed", lines))

    def flush_buffer(self):
        """Flush the print buffer in reverse order for inverted printing.

        Hardware handles character rotation (ESC { 1),
        software reverses line order (print last line first).
        """
        # Check if already aborted before starting
        if self._abort:
            return

        if len(self.print_buffer) == 0:
            return

        # Ensure we're in the right mode before printing
        self._ensure_ascii_mode()

        # If max_lines is set, trim content from END of buffer (preserves header at start)
        total_lines_in_buffer = 0
        if self.max_lines > 0:
            # First, count total lines in buffer
            for op_type, op_data in self.print_buffer:
                if op_type == "text":
                    total_lines_in_buffer += op_data.count("\n") + 1

            # Then find trim point
            lines_counted = 0
            trim_index = len(self.print_buffer)

            for i, (op_type, op_data) in enumerate(self.print_buffer):
                if op_type == "text":
                    lines_in_item = op_data.count("\n") + 1
                    if lines_counted + lines_in_item > self.max_lines:
                        # This item would exceed limit - trim here
                        trim_index = i
                        self._max_lines_hit = True
                        break
                    lines_counted += lines_in_item

            # Trim buffer if needed
            if self._max_lines_hit:
                self.print_buffer = self.print_buffer[:trim_index]

        # If truncated, print message FIRST (tear-off edge)
        if self._max_lines_hit:
            self._write(b"\n")
            msg = f"-- MAX LENGTH ({self.max_lines}/{total_lines_in_buffer}) --\n"
            self._write(msg.encode("ascii", errors="replace"))
            self._write(b"\n")

        # Reverse the entire sequence of operations
        reversed_ops = list(reversed(self.print_buffer))
        self.print_buffer.clear()

        for op_type, op_data in reversed_ops:
            if self._abort:
                return

            if op_type == "text":
                # Handle multi-line text by splitting and reversing lines
                lines = op_data.split("\n")
                reversed_lines = list(reversed(lines))
                for line in reversed_lines:
                    if self._abort:
                        return
                    self._write_text_line(line)
            elif op_type == "feed":
                self._write_feed(op_data)

    def reset_buffer(self, max_lines: int = 0):
        """Reset/clear the print buffer (call at start of new print job).

        Args:
            max_lines: Maximum lines for this print job (0 = no limit)
        """
        self.print_buffer.clear()
        # Reset line counter
        self.lines_printed = 0
        self.max_lines = max_lines
        self._abort = False
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
        """Tiny paper feed for tactile feedback."""
        try:
            # ESC J n - Feed paper n dots (n/203 inches on most printers)
            self._write(b"\x1b\x4a\x01")
        except Exception:
            pass

    def print_header(self, text: str):
        """Print centered header text."""
        # Simple centering logic
        padding = max(0, (self.width - len(text)) // 2)
        header_text = " " * padding + text.upper()
        self.print_text(header_text)
        self.print_line()

    def close(self):
        """Close the connection."""
        if self.ser and self.ser.is_open:
            self.ser.close()
        if self.usb_file:
            try:
                self.usb_file.close()
            except Exception:
                pass
        if hasattr(self, "usb_fd") and self.usb_fd is not None:
            try:
                os.close(self.usb_fd)
            except Exception:
                pass
        if self.dtr_handle:
            try:
                self.dtr_handle.close()
            except Exception:
                pass
