import serial
import platform
import os
from typing import Optional

class PrinterDriver:
    """
    Real hardware driver for thermal receipt printer (QR204/CSN-A2).
    Uses serial communication (TTL/USB) or direct USB device file.
    """
    
    def __init__(self, width: int = 32, port: Optional[str] = None, baudrate: int = 9600, invert: bool = False):
        self.width = width
        self.invert = invert
        self.ser = None
        self.usb_file = None
        self.usb_fd = None
        # Buffer for print operations when invert is enabled
        # Each item is a tuple: ('text', line) or ('feed', count)
        self.print_buffer = [] if invert else None
        
        # Auto-detect serial port if not specified
        if port is None:
            # Common ports for thermal printers
            if platform.system() == "Linux":
                # Check specifically for USB Printer device first
                if os.path.exists("/dev/usb/lp0"):
                    port = "/dev/usb/lp0"
                else:
                    # Try common Linux serial ports
                    possible_ports = ["/dev/ttyUSB0", "/dev/ttyACM0", "/dev/serial0", "/dev/ttyAMA0"]
                    # Use the first one that exists
                    for p in possible_ports:
                        if os.path.exists(p):
                            port = p
                            break
                    if not port:
                        port = "/dev/ttyUSB0" # Default fallback
            elif platform.system() == "Windows":
                # Windows COM ports
                possible_ports = [f"COM{i}" for i in range(1, 10)]
                port = possible_ports[0]
            else:
                possible_ports = ["/dev/tty.usbserial", "/dev/ttyUSB0"]
                port = possible_ports[0]
            
            print(f"[PRINTER] Auto-detecting port, defaulting to {port}")
        
        # Handle USB Line Printer (/dev/usb/lp0) differently from Serial
        if port and "lp" in port and platform.system() == "Linux":
            try:
                # Open as a raw binary file using low-level os.open
                # This avoids Python buffering entirely
                self.usb_fd = os.open(port, os.O_RDWR)
                self.usb_file = None # distinct from file object
                print(f"[PRINTER] Connected to {port} (Direct USB via os.open)")
                self._initialize_printer()
                return
            except Exception as e:
                 print(f"[PRINTER ERROR] Failed to open USB printer {port}: {e}")
                 print("[PRINTER] Falling back to console output")
                 return

        # Fallback to Serial
        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            print(f"[PRINTER] Connected to {port} at {baudrate} baud")
            
            # Initialize printer (ESC/POS commands)
            self._initialize_printer()
            
        except serial.SerialException as e:
            print(f"[PRINTER ERROR] Failed to connect to {port}: {e}")
            print("[PRINTER] Falling back to console output")
            self.ser = None
    
    def _write(self, data: bytes):
        """Internal helper to write bytes to the correct interface."""
        try:
            if hasattr(self, 'usb_fd') and self.usb_fd is not None:
                os.write(self.usb_fd, data)
            elif self.usb_file:
                self.usb_file.write(data)
                self.usb_file.flush()
            elif self.ser:
                self.ser.write(data)
                self.ser.flush()
            else:
                # Console fallback
                pass
        except Exception as e:
            print(f"[PRINTER ERROR] Write failed: {e}")

    def _initialize_printer(self):
        """Send initialization commands to the printer."""
        try:
            # Reset printer
            self._write(b'\x1B\x40')  # ESC @ (Initialize printer)
            # Set character encoding (UTF-8)
            self._write(b'\x1B\x74\x01')  # ESC t 1 (Select character code table: PC437)
            # Set default line spacing
            self._write(b'\x1B\x32')  # ESC 2 (Set line spacing to default)
            
            # Apply rotation if needed (180 degree rotation)
            if self.invert:
                # Try ESC i (some printers support this for 180° rotation)
                # Alternative: ESC { n where n=1 enables rotation
                # We'll try both common methods
                self._write(b'\x1B\x7B\x01')  # ESC { 1 (Enable rotation on some printers)
                # Also try ESC i (alternative rotation command)
                self._write(b'\x1B\x69')  # ESC i (180° rotation on some printers)
                print("[PRINTER] Rotation enabled (180 degrees)")
        except Exception as e:
            print(f"[PRINTER] Warning: Initialization error: {e}")
    
    def _write_text_line(self, line: str):
        """Internal method to write a single line of text to the printer."""
        try:
            # Encode text - try UTF-8 first, fallback to GBK if needed
            try:
                encoded = line.encode('utf-8')
            except UnicodeEncodeError:
                encoded = line.encode('gbk', errors='replace')
            
            self._write(encoded)
            self._write(b'\n')  # Line feed
        except Exception as e:
            print(f"[PRINTER ERROR] Failed to print text: {e}")
            print(f"[PRINT] {line}")  # Fallback to console
    
    def print_text(self, text: str):
        """Print a line of text. Handles multi-line strings by splitting them."""
        # If invert is enabled, buffer the entire text (including newlines) as a single operation
        # This preserves line order within multi-line content
        if self.invert and self.print_buffer is not None:
            self.print_buffer.append(('text', text))
            return
        
        # Normal printing (when not inverted) - split and print each line
        lines = text.split('\n')
        for line in lines:
            self._write_text_line(line)
    
    def print_line(self):
        """Print a separator line."""
        line = '-' * self.width
        self.print_text(line)
    
    def _write_feed(self, count: int):
        """Internal method to feed paper."""
        try:
            for _ in range(count):
                self._write(b'\n')  # Line feed
        except Exception as e:
            print(f"[PRINTER ERROR] Failed to feed paper: {e}")
            for _ in range(count):
                print("[PRINT] ")
    
    def feed(self, lines: int = 3):
        """Feed paper (advance lines)."""
        # If invert is enabled, buffer the operation instead of printing immediately
        if self.invert and self.print_buffer is not None:
            self.print_buffer.append(('feed', lines))
            return
        
        # Normal feed (when not inverted)
        self._write_feed(lines)
    
    def flush_buffer(self):
        """Flush the print buffer in reverse order (for invert mode)."""
        if not self.invert or self.print_buffer is None or len(self.print_buffer) == 0:
            return
        
        # Reverse the entire sequence of operations
        reversed_ops = list(reversed(self.print_buffer))
        self.print_buffer.clear()
        
        # Execute all operations in reverse order
        # Note: We reverse the ORDER of operations, and also reverse lines within each text operation
        # This handles both cases:
        # - Line-by-line printing (each line = separate operation, reversed by operation order)
        # - Multi-line strings (one operation with multiple lines, reversed by line order within)
        for op_type, op_data in reversed_ops:
            if op_type == 'text':
                # Handle multi-line text by splitting and reversing lines within the operation
                lines = op_data.split('\n')
                reversed_lines = list(reversed(lines))
                for line in reversed_lines:
                    self._write_text_line(line)
            elif op_type == 'feed':
                self._write_feed(op_data)
    
    def reset_buffer(self):
        """Reset/clear the print buffer (call at start of new print job)."""
        if self.print_buffer is not None:
            self.print_buffer.clear()
    
    def feed_direct(self, lines: int = 3):
        """Feed paper directly, bypassing the buffer (for use after flushing in invert mode)."""
        try:
            # ESC/POS: Feed n lines directly
            for _ in range(lines):
                self._write(b'\n')  # Line feed
        except Exception as e:
            print(f"[PRINTER ERROR] Failed to feed paper: {e}")
            for _ in range(lines):
                print("[PRINT] ")
    
    def print_header(self, text: str):
        """Print centered header text."""
        # Simple centering logic
        padding = max(0, (self.width - len(text)) // 2)
        header_text = ' ' * padding + text.upper()
        self.print_text(header_text)
        self.print_line()
    
    def close(self):
        """Close the connection."""
        if self.ser and self.ser.is_open:
            self.ser.close()
        if self.usb_file:
            try:
                self.usb_file.close()
            except:
                pass
        if hasattr(self, 'usb_fd') and self.usb_fd is not None:
            try:
                os.close(self.usb_fd)
            except:
                pass
        print("[PRINTER] Connection closed")
