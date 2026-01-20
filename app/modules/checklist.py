from typing import Dict, Any, List
from datetime import datetime
from app.drivers.printer_mock import PrinterDriver
from app.drivers.printer_mock import PrinterDriver
from app.module_registry import register_module
from PIL import Image, ImageDraw
from app.utils import wrap_text_pixels


@register_module(
    type_id="checklist",
    label="Checklist",
    description="Printable checklist with checkbox items",
    icon="check-square",
    offline=True,
    category="utilities",
    config_schema={
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "title": "Items",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "title": "Item Text"},
                        "checked": {"type": "boolean", "title": "Checked", "default": False},
                    },
                },
            }
        },
    },
    ui_schema={
        "items": {
            "ui:options": {
                "orderable": True,
                "removable": True,
                "addable": True,
            }
        }
    },
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
        width = getattr(printer, "PRINTER_WIDTH_DOTS", 384)
        font = getattr(printer, "_get_font", lambda s: None)("regular")
        
        img = draw_checklist_item_image(
            width, 
            item_text, 
            checked=checked, 
            size=14, 
            font=font
        )
        printer.print_image(img)
    
    printer.print_line()


def draw_checklist_item_image(
    width: int,
    text: str,
    checked: bool,
    size: int,
    font
) -> Image.Image:
    """Draw a checklist item with checkbox and text to an image."""
    
    SPACING_SMALL = 4
    
    # Calculate positions
    checkbox_x = 2
    checkbox_y = 0  # Relative to image top
    text_start_x = checkbox_x + size + SPACING_SMALL + 2
    
    # Available width for text
    text_width = width - text_start_x - 2
    
    # Calculate text height
    line_height = getattr(font, "size", 24) if font else 24
    
    if text:
        wrapped_lines = wrap_text_pixels(text, font, text_width)
        text_height = len(wrapped_lines) * line_height
    else:
        wrapped_lines = []
        text_height = 0
        
    # Total image height
    total_height = max(size, text_height) + SPACING_SMALL
    
    # Create image
    img = Image.new("1", (width, total_height), 1)  # White background
    draw = ImageDraw.Draw(img)
    
    # Draw checkbox
    draw.rectangle(
        [checkbox_x, checkbox_y, checkbox_x + size - 1, checkbox_y + size - 1],
        outline=0,
        width=2
    )
    if checked:
        # Draw checkmark (or X)
        draw.line(
            [checkbox_x + 2, checkbox_y + 2, checkbox_x + size - 3, checkbox_y + size - 3],
            fill=0,
            width=2
        )
        draw.line(
            [checkbox_x + size - 3, checkbox_y + 2, checkbox_x + 2, checkbox_y + size - 3],
            fill=0,
            width=2
        )
        
    # Draw text
    if text and wrapped_lines:
        current_y = 0
        for line in wrapped_lines:
            if line.strip():
                if font:
                    draw.text((text_start_x, current_y), line, font=font, fill=0)
                else:
                    draw.text((text_start_x, current_y), line, fill=0)
            current_y += line_height
            
    return img

