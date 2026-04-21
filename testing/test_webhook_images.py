import base64
import io

from PIL import Image
import requests

import app.main as main_module
from app.config import WebhookConfig
from app.modules import webhook


def _png_bytes(width: int = 16, height: int = 8) -> bytes:
    image = Image.new("RGB", (width, height), "black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class _ImageResponse:
    status_code = 200
    headers = {"content-type": "image/png"}
    text = "<binary image>"

    def __init__(self, payload: bytes):
        self.content = payload

    def json(self):
        raise ValueError("image response is not JSON")


class _RecordingPrinter:
    def __init__(self):
        self.images = []
        self.body = []

    def print_header(self, *args, **kwargs):  # noqa: ARG002
        return None

    def print_caption(self, *args, **kwargs):  # noqa: ARG002
        return None

    def print_line(self):
        return None

    def print_body(self, text):
        self.body.append(text)

    def print_image(self, image):
        self.images.append(image.copy())


def test_webhook_prints_image_responses(monkeypatch):
    payload = _png_bytes()
    printer = _RecordingPrinter()

    monkeypatch.setattr(
        webhook.requests,
        "get",
        lambda url, headers=None, timeout=None: _ImageResponse(payload),  # noqa: ARG005
    )

    webhook.run_webhook(
        WebhookConfig(url="https://example.test/image.png"),
        printer,
        module_name="Image Hook",
    )

    assert len(printer.images) == 1
    assert printer.images[0].size == (16, 8)
    assert printer.body == []


def test_webhook_image_response_has_generous_height_cap(monkeypatch):
    monkeypatch.setattr(webhook, "WEBHOOK_IMAGE_MAX_HEIGHT_DOTS", 64)

    payload = _png_bytes(width=100, height=128)
    printer = _RecordingPrinter()

    monkeypatch.setattr(
        webhook.requests,
        "get",
        lambda url, headers=None, timeout=None: _ImageResponse(payload),  # noqa: ARG005
    )

    webhook.run_webhook(
        WebhookConfig(url="https://example.test/very-tall-image.png"),
        printer,
        module_name="Image Hook",
    )

    assert len(printer.images) == 1
    assert printer.images[0].height <= webhook.WEBHOOK_IMAGE_MAX_HEIGHT_DOTS
    assert printer.images[0].size == (50, 64)
    assert printer.body == []


def test_webhook_preview_reports_image_response(monkeypatch):
    payload = _png_bytes(width=12, height=6)

    monkeypatch.setattr(
        requests,
        "get",
        lambda url, headers=None, timeout=None: _ImageResponse(payload),  # noqa: ARG005
    )

    result = main_module._preview_webhook_sync(
        {"url": "https://example.test/image.png"}
    )

    assert result["success"] is True
    assert result["content_type"] == "image"
    assert result["content"] == "Image response: image/png (12x6)"
    assert result["preview_data_url"].startswith("data:image/png;base64,")


def test_webhook_preview_caps_image_data_url(monkeypatch):
    monkeypatch.setattr(webhook, "WEBHOOK_IMAGE_MAX_HEIGHT_DOTS", 64)

    payload = _png_bytes(width=100, height=128)

    monkeypatch.setattr(
        requests,
        "get",
        lambda url, headers=None, timeout=None: _ImageResponse(payload),  # noqa: ARG005
    )

    result = main_module._preview_webhook_sync(
        {"url": "https://example.test/very-tall-image.png"}
    )

    prefix = "data:image/png;base64,"
    assert result["success"] is True
    assert result["preview_data_url"].startswith(prefix)

    preview_bytes = base64.b64decode(result["preview_data_url"][len(prefix):])
    with Image.open(io.BytesIO(preview_bytes)) as preview:
        assert preview.height <= webhook.WEBHOOK_IMAGE_MAX_HEIGHT_DOTS
        assert preview.size == (50, 64)


def test_webhook_presets_include_sample_image():
    preset = webhook.WEBHOOK_PRESETS["sample_image"]

    assert preset["url"] == webhook.SAMPLE_IMAGE_WEBHOOK_URL
    assert preset["method"] == "GET"
    assert preset["json_path"] == ""
