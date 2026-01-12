from app.config import TextConfig
from app.drivers.printer_mock import PrinterDriver
from app.utils import wrap_text

def format_text_receipt(printer: PrinterDriver, config: TextConfig, module_name: str = None):
    """Prints a static text note."""
    from datetime import datetime
    
    header_label = module_name or config.label or "NOTE"
    printer.print_header(header_label, icon="note")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()
    
    content = config.content or "No content."
    
    # Wrap and print body text
    wrapped_lines = wrap_text(content, width=printer.width, indent=0)
    for line in wrapped_lines:
        printer.print_body(line)
    
    printer.print_line()

