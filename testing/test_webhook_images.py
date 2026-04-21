import asyncio
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


def test_webhook_preview_reports_image_response(monkeypatch):
    payload = _png_bytes(width=12, height=6)

    monkeypatch.setattr(
        requests,
        "get",
        lambda url, headers=None, timeout=None: _ImageResponse(payload),  # noqa: ARG005
    )

    result = asyncio.run(
        main_module.preview_webhook({"url": "https://example.test/image.png"})
    )

    assert result["success"] is True
    assert result["content_type"] == "image"
    assert result["content"] == "Image response: image/png (12x6)"
