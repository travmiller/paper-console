import os
import platform
from app.config import settings, PRINTER_WIDTH

# Auto-detect platform and use appropriate drivers
_is_raspberry_pi = platform.system() == "Linux" and os.path.exists(
    "/proc/device-tree/model"
)

if _is_raspberry_pi:
    try:
        from app.drivers.printer_serial import PrinterDriver
        from app.drivers.dial_gpio import DialDriver
        from app.drivers.button_gpio import ButtonDriver
    except ImportError:
        from app.drivers.printer_mock import PrinterDriver
        from app.drivers.dial_mock import DialDriver
        from app.drivers.button_mock import ButtonDriver
else:
    from app.drivers.printer_mock import PrinterDriver
    from app.drivers.dial_mock import DialDriver
    from app.drivers.button_mock import ButtonDriver

# Global Hardware Instances
printer = PrinterDriver(
    width=PRINTER_WIDTH,
    font_size=settings.font_size,
    line_spacing=settings.line_spacing,
)
dial = DialDriver()

# Main Interface Button (Print / WiFi Setup / Reset) - GPIO 25 (Pin 22)
button = ButtonDriver(pin=25)


def update_printer_settings():
    """Update printer font settings from current config (call after settings change)."""
    global printer
    printer.font_size = max(8, min(24, settings.font_size))
    printer.line_spacing = max(0, min(8, settings.line_spacing))
    printer.line_height = printer.font_size + printer.line_spacing
    # Reload font with new size
    printer._font = printer._load_font()

