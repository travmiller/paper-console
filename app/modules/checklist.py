from typing import Dict, Any, List
from datetime import datetime
from app.drivers.printer_mock import PrinterDriver
from app.module_registry import register_module


@register_module(
    type_id="checklist",
    label="Checklist",
    description="Printable checklist with checkbox items",
    icon="check-square",
    offline=True,
    category="utilities",
)
def format_checklist_receipt(printer: PrinterDriver, config: Dict[str, Any] = None, module_name: str = None):
    """Prints a checklist with items that can be checked off."""
    
    config = config or {}
    items = config.get("items", [])
    
    printer.print_header(module_name or "CHECKLIST", icon="check-square")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()
    
    if not items:
        printer.print_body("No items in checklist.")
        return
    
    # Print each item with a checkbox inline with text
    for item in items:
        checked = item.get("checked", False) if isinstance(item, dict) else False
        item_text = item.get("text", "").strip() if isinstance(item, dict) else str(item).strip()
        
        if not item_text:
            continue
        
        # Print checkbox with text inline - printer will handle wrapping
        printer.print_checkbox_text(item_text, checked=checked, size=14, style="regular")
    
    printer.print_line()

