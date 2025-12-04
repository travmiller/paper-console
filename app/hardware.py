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

        print("[SYSTEM] Running on Raspberry Pi - using hardware drivers")
    except ImportError as e:
        print(f"[SYSTEM] Hardware drivers not available: {e}")
        print("[SYSTEM] Falling back to mock drivers")
        from app.drivers.printer_mock import PrinterDriver
        from app.drivers.dial_mock import DialDriver
        from app.drivers.button_mock import ButtonDriver
else:
    from app.drivers.printer_mock import PrinterDriver
    from app.drivers.dial_mock import DialDriver
    from app.drivers.button_mock import ButtonDriver

    print("[SYSTEM] Running on non-Raspberry Pi - using mock drivers")

# Global Hardware Instances
# Note: printer will be reinitialized when settings change
printer = PrinterDriver(
    width=PRINTER_WIDTH, invert=getattr(settings, "invert_print", False)
)
dial = DialDriver()
button = ButtonDriver(pin=18)

