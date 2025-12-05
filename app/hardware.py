import os
import platform
from app.config import settings, PRINTER_WIDTH

# Auto-detect platform and use appropriate drivers
_is_raspberry_pi = platform.system() == "Linux" and os.path.exists(
    "/proc/device-tree/model"
)

print(f"[HARDWARE] Platform: {platform.system()}, Is RPi: {_is_raspberry_pi}")

if _is_raspberry_pi:
    try:
        from app.drivers.printer_serial import PrinterDriver
        from app.drivers.dial_gpio import DialDriver
        from app.drivers.button_gpio import ButtonDriver
        print("[HARDWARE] Loaded REAL hardware drivers")
    except ImportError as e:
        print(f"[HARDWARE] Import error, falling back to mock: {e}")
        from app.drivers.printer_mock import PrinterDriver
        from app.drivers.dial_mock import DialDriver
        from app.drivers.button_mock import ButtonDriver
else:
    print("[HARDWARE] Not on RPi, using mock drivers")
    from app.drivers.printer_mock import PrinterDriver
    from app.drivers.dial_mock import DialDriver
    from app.drivers.button_mock import ButtonDriver

# Global Hardware Instances
printer = PrinterDriver(
    width=PRINTER_WIDTH, invert=getattr(settings, "invert_print", False)
)
dial = DialDriver()
button = ButtonDriver(pin=18)
