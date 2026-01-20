"""Shared utility functions for modules."""

from app.hardware import printer, _is_raspberry_pi
from app.config import PRINTER_WIDTH


def wrap_text(text: str, width: int = 42, indent: int = 0, preserve_line_breaks: bool = False) -> list[str]:
    """Wraps text to fit the printer width with optional indentation.
    
    Note: For most use cases, you should pass text directly to printer.print_body()
    or printer.print_text(), which will handle wrapping automatically using font
    metrics (more accurate than character-based wrapping). Use this function only
    when you need character-based pre-wrapping for specific layout requirements.
    
    Args:
        text: The text to wrap
        width: Maximum width for each line (in characters, approximate)
        indent: Number of spaces to indent (reduces available width)
        preserve_line_breaks: If True, preserves explicit line breaks from input
    """
    if preserve_line_breaks:
        # Split by newlines first to preserve explicit line breaks and empty lines
        input_lines = text.split('\n')
        all_lines = []
        
        for input_line in input_lines:
            # Check if this is an empty line (whitespace-only lines are also considered empty)
            words = input_line.split()
            
            # If empty line, preserve it for spacing
            if not words:
                all_lines.append("")
                continue
            
            # Wrap each non-empty line individually
            current_line = ""
            available_width = width - indent

            for word in words:
                if len(current_line) + len(word) + 1 <= available_width:
                    current_line += word + " "
                else:
                    if current_line:
                        all_lines.append(current_line.strip())
                    current_line = word + " "

            # Add the last line if there's content
            if current_line:
                all_lines.append(current_line.strip())
        
        return all_lines
    else:
        # Original behavior: split on all whitespace
        words = text.split()
        lines = []
        current_line = ""
        available_width = width - indent

        for word in words:
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
