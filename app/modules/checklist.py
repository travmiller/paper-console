from typing import Dict, Any, List
from datetime import datetime
from app.drivers.printer_mock import PrinterDriver


def format_checklist_receipt(printer: PrinterDriver, config: Dict[str, Any] = None, module_name: str = None):
    """Prints a checklist with items that can be checked off."""
    
    config = config or {}
    items = config.get("items", [])
    title = config.get("title", "CHECKLIST")
    
    printer.print_header((module_name or title).upper())
    printer.print_text(datetime.now().strftime("%A, %b %d"))
    printer.print_line()
    
    if not items:
        printer.print_text("No items in checklist.")
        printer.feed(1)
        return
    
    # Print each item with a checkbox
    for i, item in enumerate(items, 1):
        # Format: [ ] Item text
        # Use a simple checkbox character that works on thermal printers
        checkbox = "[ ]"
        item_text = item.get("text", "").strip() if isinstance(item, dict) else str(item).strip()
        
        if not item_text:
            continue
            
        # Format: [ ] 1. Item text
        line = f"{checkbox} {i}. {item_text}"
        
        # Handle long items by wrapping
        if len(line) > printer.width:
            # Print checkbox and number on first line
            prefix = f"{checkbox} {i}."
            printer.print_text(prefix)
            # Print the rest wrapped
            words = item_text.split()
            wrapped_line = "  "  # Indent continuation lines
            for word in words:
                if len(wrapped_line) + len(word) + 1 <= printer.width:
                    wrapped_line += word + " "
                else:
                    if wrapped_line.strip():
                        printer.print_text(wrapped_line)
                    wrapped_line = "  " + word + " "
            if wrapped_line.strip():
                printer.print_text(wrapped_line)
        else:
            printer.print_text(line)
    
    printer.print_line()
    printer.print_text("Check off items as you complete them!")
    printer.feed(1)

