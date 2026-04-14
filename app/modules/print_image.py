from datetime import datetime
import logging
import base64
import io
from PIL import Image
from app.drivers.printer_mock import PrinterDriver
from app.module_registry import register_module

logger = logging.getLogger(__name__)

MAX_WIDTH = 384  # Max width for most thermal printers in pixels

@register_module(
    type_id="image",
    label="Image",
    description="Upload and print an image",
    icon="image",
    offline=True,
    category="utilities",
    config_schema={
        "type": "object",
        "properties": {
            "image_data": {
                "type": "string",
                "title": "Image Upload",
                "format": "data-url",
                "description": "Upload a JPG or PNG image to print"
            }
        },
        "required": ["image_data"]
    },
     ui_schema={
        "image_data": {
            "ui:widget": "image",
            "ui:options": {
                "accept": ".jpg,.jpeg,.png"
            }
        }
    }
)
def format_image_receipt(printer: PrinterDriver, config, module_name="IMAGE"):
    image_data = config.get("image_data")
    
    if image_data:
        try:
            # Strip Data URL prefix if present
            if "," in image_data:
                image_data = image_data.split(",")[1]
                
            img_bytes = base64.b64decode(image_data)
            img = Image.open(io.BytesIO(img_bytes))

            print_image_receipt(printer, img, module_name)
        except Exception as e:
            logger.error(f"Failed to decode image from config: {e}")
            printer.print_body(f"Error: Could not load image.")
    else:
        logger.warning("Image module called without image_data in config.")

def resize_and_convert_image(raw_data_uri):
    """Converts raw upload into a compact 1-bit PNG base64 string for config storage."""    
    if "," in raw_data_uri:
        raw_data_uri = raw_data_uri.split(",")[1]

    img_bytes = base64.b64decode(raw_data_uri)

    with Image.open(io.BytesIO(img_bytes)) as img:
        # Resize to printer width (384px) to save space in config.json
        if img.width > MAX_WIDTH:
            ratio = MAX_WIDTH / float(img.width)
            img = img.resize((MAX_WIDTH, int(img.height * ratio)), Image.LANCZOS)
        
        # Convert to 1-bit dithered
        img = img.convert("1")
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"

def print_image_receipt(printer: PrinterDriver, image, title):
    if not image:
        return

    printer.print_header(title)
    printer.feed(1)
    printer.print_image(image)
    printer.feed(1)