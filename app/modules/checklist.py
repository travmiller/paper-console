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
    
    # Print each item with a bitmap checkbox
    for item in items:
        checked = item.get("checked", False) if isinstance(item, dict) else False
        item_text = item.get("text", "").strip() if isinstance(item, dict) else str(item).strip()
        
        if not item_text:
            continue
        
        # Print bitmap checkbox
        printer.print_checkbox(checked=checked, size=14)
        
        # Print item text next to checkbox
        if len(item_text) > printer.width - 20:  # Leave space for checkbox
            # Wrap long items
            from app.utils import wrap_text
            wrapped = wrap_text(item_text, width=printer.width - 20, indent=0)
            for i, line in enumerate(wrapped):
                if i == 0:
                    printer.print_body(f"  {line}")  # First line after checkbox
                else:
                    printer.print_body(f"  {line}")  # Indented continuation
        else:
            printer.print_body(f"  {item_text}")
    
    printer.print_line()

