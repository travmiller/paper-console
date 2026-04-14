import base64
import io
from PIL import Image
from app.modules import print_image
from app.drivers.printer_mock import PrinterDriver

def test_resize_and_convert_image_resizes_large_images():
    # Create a 500x500 red image (larger than MAX_WIDTH of 384)
    img = Image.new("RGB", (500, 500), "red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    raw_uri = f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"

    result_uri = print_image.resize_and_convert_image(raw_uri)
    
    # Should have been converted to a data URI with PNG format
    header = result_uri.split(",")[0]
    assert header == "data:image/png;base64"

    # Decode result to verify it was resized and converted to 1-bit
    encoded = result_uri.split(",")[1]
    with Image.open(io.BytesIO(base64.b64decode(encoded))) as processed:
        assert processed.width == 384
        assert processed.mode == "1"  # Should be converted to 1-bit

def test_resize_and_convert_image_preserves_small_images():
    # Create a 100x50 image (smaller than MAX_WIDTH)
    img = Image.new("RGB", (100, 50), "blue")
    buf = io.BytesIO()
    img.save(buf, format="BMP")
    raw_uri = f"data:image/bmp;base64,{base64.b64encode(buf.getvalue()).decode()}"

    result_uri = print_image.resize_and_convert_image(raw_uri)

    # Should have been converted to a data URI with PNG format
    header = result_uri.split(",")[0]
    assert header == "data:image/png;base64"
    
    # Decode result to verify it was resized and converted to 1-bit
    encoded = result_uri.split(",")[1]
    with Image.open(io.BytesIO(base64.b64decode(encoded))) as processed:
        assert processed.width == 100
        assert processed.mode == "1"
