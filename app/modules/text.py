from app.config import TextConfig
from app.drivers.printer_mock import PrinterDriver
from app.module_registry import register_module

@register_module(
    type_id="text",
    label="Text / Note",
    description="Print custom text or notes",
    icon="note",
    offline=True,
    category="utilities",
)
def format_text_receipt(printer: PrinterDriver, config: TextConfig, module_name: str = None):
    """Prints a static text note."""
    from datetime import datetime
    
    header_label = module_name or "NOTE"
    printer.print_header(header_label, icon="note")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()
    
    content = config.content or "No content."
    
    # Pass full content directly - printer will handle wrapping and preserve newlines
    printer.print_body(content)
    
    printer.print_line()

