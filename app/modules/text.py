import re
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
    config_schema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "title": "Content",
                "default": "",
            }
        },
    },
    ui_schema={
        "content": {
            "ui:widget": "richtext",
            "ui:placeholder": "Enter text to print...",
        }
    },
)
def format_text_receipt(printer: PrinterDriver, config: TextConfig, module_name: str = None):
    """Prints a static text note with markdown formatting support."""
    from datetime import datetime
    
    header_label = module_name or "NOTE"
    printer.print_header(header_label, icon="note")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()
    
    content = config.content or "No content."
    
    # Parse markdown and print with appropriate styles
    _print_markdown(printer, content)
    
    printer.print_line()


def _print_markdown(printer: PrinterDriver, markdown_text: str):
    """Parse markdown content and print with styled text.
    
    Supports:
    - # Heading (H1)
    - **bold**
    - *italic* or _italic_
    - - bullet list items
    - 1. numbered list items
    - --- horizontal rule
    """
    if not markdown_text:
        return
    
    lines = markdown_text.split('\n')
    
    for line in lines:
        stripped = line.strip()
        
        # Empty line - print blank line
        if not stripped:
            printer.print_text("", "regular")
            continue
        
        # Horizontal rule (3+ dashes, asterisks, or underscores)
        if re.match(r'^[-*_]{3,}$', stripped):
            printer.print_line()
            continue
        
        # Heading (H1)
        if stripped.startswith('# '):
            heading_text = stripped[2:].strip()
            # Process inline formatting within heading
            heading_text = _strip_inline_markdown(heading_text)
            printer.print_text(heading_text, "bold_lg")
            continue
        
        # Checkbox list items (must be before regular bullet list)
        checkbox_match = re.match(r'^- \[([ xX])\] (.+)$', stripped)
        if checkbox_match:
            is_checked = checkbox_match.group(1).lower() == 'x'
            checkbox_text = checkbox_match.group(2)
            checkbox_symbol = '☑' if is_checked else '☐'
            _print_formatted_line(printer, f"{checkbox_symbol} {checkbox_text}")
            continue
        
        # Bullet list
        if stripped.startswith('- ') or stripped.startswith('* '):
            list_text = stripped[2:].strip()
            _print_formatted_line(printer, f"• {list_text}")
            continue
        
        # Numbered list
        numbered_match = re.match(r'^(\d+)\.\s+(.+)$', stripped)
        if numbered_match:
            number = numbered_match.group(1)
            list_text = numbered_match.group(2)
            _print_formatted_line(printer, f"{number}. {list_text}")
            continue
        
        # Regular paragraph - process inline formatting
        _print_formatted_line(printer, stripped)


def _print_formatted_line(printer: PrinterDriver, text: str):
    """Print a line with inline bold/italic formatting.
    
    For simplicity, we print the entire line with the dominant style,
    or fall back to plain text with markdown stripped if mixed.
    """
    # Check for simple cases where entire line is bold or italic
    
    # Fully bold line
    if text.startswith('**') and text.endswith('**') and text.count('**') == 2:
        inner = text[2:-2]
        printer.print_text(inner, "bold")
        return
    
    # Fully italic line (single asterisk)
    if text.startswith('*') and text.endswith('*') and text.count('*') == 2 and not text.startswith('**'):
        inner = text[1:-1]
        printer.print_text(inner, "italic")
        return
    
    # Fully italic line (underscore)
    if text.startswith('_') and text.endswith('_') and text.count('_') == 2:
        inner = text[1:-1]
        printer.print_text(inner, "italic")
        return
    
    # Mixed formatting - parse inline styles and print segments
    _print_mixed_format_line(printer, text)


def _print_mixed_format_line(printer: PrinterDriver, text: str):
    """Parse and print a line with mixed bold/italic formatting."""
    # Pattern to match **bold**, *italic*, or _italic_
    # We'll find segments and print them with appropriate styles
    
    segments = _parse_inline_formatting(text)
    
    for segment_text, style in segments:
        if segment_text:
            printer.print_text(segment_text, style)


def _parse_inline_formatting(text: str):
    """Parse inline markdown formatting into styled segments.
    
    Returns list of (text, style) tuples.
    """
    segments = []
    current_pos = 0
    
    # Pattern for bold (**text**) and italic (*text* or _text_)
    # Bold has higher priority (must check first since ** contains *)
    pattern = re.compile(r'(\*\*(.+?)\*\*)|(\*(.+?)\*)|(_(.+?)_)')
    
    for match in pattern.finditer(text):
        # Add any text before this match as regular
        if match.start() > current_pos:
            segments.append((text[current_pos:match.start()], "regular"))
        
        if match.group(1):  # **bold**
            segments.append((match.group(2), "bold"))
        elif match.group(3):  # *italic*
            segments.append((match.group(4), "italic"))
        elif match.group(5):  # _italic_
            segments.append((match.group(6), "italic"))
        
        current_pos = match.end()
    
    # Add remaining text as regular
    if current_pos < len(text):
        segments.append((text[current_pos:], "regular"))
    
    # If no segments found, return entire text as regular
    if not segments:
        segments.append((text, "regular"))
    
    return segments


def _strip_inline_markdown(text: str) -> str:
    """Strip inline markdown formatting, keeping only the text."""
    # Remove **bold**, *italic*, _italic_
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    return text
