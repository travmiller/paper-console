import serial
import platform
from typing import Optional

class PrinterDriver:
    """
    Real hardware driver for thermal receipt printer (QR204/CSN-A2).
    Uses serial communication (TTL/USB) with ESC/POS commands.
    """
    
    def __init__(self, width: int = 32, port: Optional[str] = None, baudrate: int = 19200):
        self.width = width
        
        # Auto-detect serial port if not specified
        if port is None:
            # Common ports for thermal printers
            if platform.system() == "Linux":
                # Try common Linux serial ports
                possible_ports = ["/dev/ttyUSB0", "/dev/ttyACM0", "/dev/serial0", "/dev/ttyAMA0"]
            elif platform.system() == "Windows":
                # Windows COM ports
                possible_ports = [f"COM{i}" for i in range(1, 10)]
            else:
                possible_ports = ["/dev/tty.usbserial", "/dev/ttyUSB0"]
            
            port = possible_ports[0]  # Default to first option
            print(f"[PRINTER] Auto-detecting port, defaulting to {port}")
        
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
    
    def _initialize_printer(self):
        """Send initialization commands to the printer."""
        if self.ser is None:
            return
        
        try:
            # Reset printer
            self.ser.write(b'\x1B\x40')  # ESC @ (Initialize printer)
            # Set character encoding (UTF-8)
            self.ser.write(b'\x1B\x74\x01')  # ESC t 1 (Select character code table: PC437)
            # Set default line spacing
            self.ser.write(b'\x1B\x32')  # ESC 2 (Set line spacing to default)
        except Exception as e:
            print(f"[PRINTER] Warning: Initialization error: {e}")
    
    def print_text(self, text: str):
        """Print a line of text."""
        if self.ser is None:
            print(f"[PRINT] {text}")
            return
        
        try:
            # Encode text - try UTF-8 first, fallback to GBK if needed
            try:
                encoded = text.encode('utf-8')
            except UnicodeEncodeError:
                encoded = text.encode('gbk', errors='replace')
            
            self.ser.write(encoded)
            self.ser.write(b'\n')  # Line feed
            self.ser.flush()
        except Exception as e:
            print(f"[PRINTER ERROR] Failed to print text: {e}")
            print(f"[PRINT] {text}")  # Fallback to console
    
    def print_line(self):
        """Print a separator line."""
        line = '-' * self.width
        self.print_text(line)
    
    def feed(self, lines: int = 3):
        """Feed paper (advance lines)."""
        if self.ser is None:
            for _ in range(lines):
                print("[PRINT] ")
            return
        
        try:
            # ESC/POS: Feed n lines
            for _ in range(lines):
                self.ser.write(b'\n')  # Line feed
            self.ser.flush()
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
        """Close the serial connection."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("[PRINTER] Serial connection closed")

