from typing import Dict, Any, List
from datetime import datetime
from app.drivers.printer_mock import PrinterDriver


def format_checklist_receipt(printer: PrinterDriver, config: Dict[str, Any] = None, module_name: str = None):
    """Prints a checklist with items that can be checked off."""
    
    config = config or {}
    items = config.get("items", [])
    
    printer.print_header(module_name or "CHECKLIST")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()
    
    if not items:
        printer.print_body("No items in checklist.")
        return
    
    # Print each item with a checkbox
    for item in items:
        checkbox = "□"  # Unicode empty checkbox
        item_text = item.get("text", "").strip() if isinstance(item, dict) else str(item).strip()
        
        if not item_text:
            continue
        
        # Format: □ Item text
        if len(item_text) + 2 > printer.width:
            # Long item - wrap it
            printer.print_body(f"{checkbox} {item_text[:printer.width - 2]}")
            # Continuation with indent
            remaining = item_text[printer.width - 2:]
            while remaining:
                chunk = remaining[:printer.width - 2]
                printer.print_body(f"  {chunk}")
                remaining = remaining[printer.width - 2:]
        else:
            printer.print_body(f"{checkbox} {item_text}")
    
    printer.print_line()

