import os
import platform
import threading
import time
from app.config import PRINTER_WIDTH

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
printer = PrinterDriver(width=PRINTER_WIDTH)
dial = DialDriver()

# Main Interface Button (Print / WiFi Setup / Reset) - GPIO 25 (Pin 22)
button = ButtonDriver(pin=25)

# --- PRINT ORCHESTRATION ---

print_lock = threading.Lock()
print_in_progress = False
hold_action_in_progress = False
last_print_time = 0.0
PRINT_DEBOUNCE_SECONDS = 3.0  # Minimum time between print jobs


def is_printer_reserved() -> bool:
    """Return True when the printer is reserved for a print or hold action."""
    return print_in_progress or hold_action_in_progress


def try_begin_print_job(*, debounce: bool = False) -> bool:
    """Reserve the printer for a new print job."""
    global print_in_progress, last_print_time

    with print_lock:
        if is_printer_reserved():
            return False

        current_time = time.time()
        if debounce and (current_time - last_print_time) < PRINT_DEBOUNCE_SECONDS:
            return False

        print_in_progress = True
        last_print_time = current_time
        return True


def reserve_hold_action() -> bool:
    """Reserve the printer once the user crosses a long-hold threshold."""
    global hold_action_in_progress, last_print_time

    with print_lock:
        if print_in_progress:
            return False

        hold_action_in_progress = True
        last_print_time = time.time()
        return True


def promote_hold_to_print_job() -> bool:
    """Convert a hold reservation into an active print job."""
    global print_in_progress, hold_action_in_progress, last_print_time

    with print_lock:
        if print_in_progress:
            return False

        hold_action_in_progress = False
        print_in_progress = True
        last_print_time = time.time()
        return True


def clear_print_reservation(*, clear_hold: bool = True):
    """Release active print/hold reservations."""
    global print_in_progress, hold_action_in_progress

    with print_lock:
        print_in_progress = False
        if clear_hold:
            hold_action_in_progress = False
