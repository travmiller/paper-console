from app.config import TextConfig
from app.drivers.printer_mock import PrinterDriver

def format_text_receipt(printer: PrinterDriver, config: TextConfig, module_name: str = None):
    """Prints a static text note."""
    from datetime import datetime
    
    # Use module_name if provided, otherwise use config.label, otherwise default
    header_label = (module_name or config.label or "NOTE").upper()
    printer.print_header(header_label)
    printer.print_text(datetime.now().strftime("%A, %b %d"))
    printer.print_line()
    
    content = config.content or "No content."
    
    # Simple wrapping logic (could be shared utility)
    words = content.split()
    line = ""
    for word in words:
        # Handle newlines in the text if user entered them (simple replacement for now)
        # A better way is to split by newline first, then wrap.
        # For this V1, we just wrap words.
        
        if len(line) + len(word) + 1 <= printer.width:
            line += word + " "
        else:
            printer.print_text(line)
            line = word + " "
            
    if line:
        printer.print_text(line)

