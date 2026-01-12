"""Shared utility functions for modules."""

from app.hardware import printer, _is_raspberry_pi
from app.config import PRINTER_WIDTH


def wrap_text(text: str, width: int = 42, indent: int = 0) -> list[str]:
    """Wraps text to fit the printer width with optional indentation."""
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        available_width = width - indent

        if len(current_line) + len(word) + 1 <= available_width:
            current_line += word + " "
        else:
            if current_line:
                lines.append(current_line.strip())
            current_line = word + " "

    if current_line:
        lines.append(current_line.strip())

    return lines


def print_setup_instructions_sync():
    """
    Prints WiFi setup instructions to the thermal printer.
    This function is safe to call from background tasks.
    """
    try:
        printer.feed(1)

        def center(text):
            padding = max(0, (PRINTER_WIDTH - len(text)) // 2)
            return " " * padding + text

        printer.print_text(center("PC-1 SETUP MODE"))
        printer.print_text(center("=" * 20))
        printer.feed(1)
        printer.print_text(center("Connect to WiFi:"))

        # Get device ID for SSID
        ssid_suffix = "XXXX"
        try:
            if _is_raspberry_pi:
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if line.startswith("Serial"):
                            ssid_suffix = line.split(":")[1].strip()[-4:]
                            break
        except Exception:
            pass

        ssid = f"PC-1-Setup-{ssid_suffix}"

        printer.print_text(center(ssid))
        printer.print_text(center("Password: setup1234"))
        printer.feed(1)
        printer.print_text(center("Then visit:"))
        printer.print_text(center("http://pc-1.local"))
        printer.print_text(center("OR"))
        printer.print_text(center("http://10.42.0.1"))
        printer.feed(3)

        # Flush buffer to print
        if hasattr(printer, "flush_buffer"):
            printer.flush_buffer()

    except Exception:
        pass
