import asyncio
import io
from typing import Optional

import pytest
from fastapi import BackgroundTasks, HTTPException
from PIL import Image
from starlette.requests import Request

import app.main as main_module
from app.config import ChannelConfig, ChannelModuleAssignment, IncomingWebhookConfig, ModuleInstance
from app.modules import incoming_webhook


def _make_request(
    body: bytes,
    *,
    content_type: str,
    token: Optional[str] = None,
) -> Request:
    headers = [(b"content-type", content_type.encode("latin-1"))]
    if token is not None:
        headers.append((b"authorization", f"Bearer {token}".encode("latin-1")))

    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/hook/front-door",
        "raw_path": b"/hook/front-door",
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
    }
    return Request(scope, receive)


def _incoming_module(
    module_id: str = "incoming-1",
    *,
    endpoint_path: str = "front-door",
    token: str = "secret-token",
    name: str = "Front Door",
    **config_overrides,
) -> ModuleInstance:
    config = {
        "token": token,
        "endpoint_path": endpoint_path,
        "accept_text": True,
        "accept_images": True,
        "accept_json": True,
        "max_image_height_dots": 96,
    }
    config.update(config_overrides)
    return ModuleInstance(
        id=module_id,
        type="incoming_webhook",
        name=name,
        config=config,
    )


class _RecordingPrinter:
    def __init__(self):
        self.headers = []
        self.captions = []
        self.lines = 0
        self.body = []
        self.images = []
        self.reset_calls = []
        self.flushed = 0

    def print_header(self, text, icon=None, icon_size=24):  # noqa: ARG002
        self.headers.append(text)

    def print_caption(self, text):
        self.captions.append(text)

    def print_line(self):
        self.lines += 1

    def print_body(self, text):
        self.body.append(text)

    def print_image(self, image):
        self.images.append(image.copy())

    def reset_buffer(self, max_lines=0):
        self.reset_calls.append(max_lines)

    def flush_buffer(self):
        self.flushed += 1


def _png_bytes(width: int = 16, height: int = 8) -> bytes:
    image = Image.new("RGB", (width, height), "black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_incoming_webhook_module_type_is_registered():
    result = asyncio.run(main_module.get_module_types())

    assert any(
        module_type["id"] == "incoming_webhook"
        for module_type in result["moduleTypes"]
    )


def test_receive_incoming_webhook_returns_404_for_unknown_endpoint(monkeypatch):
    monkeypatch.setattr(main_module.settings, "modules", {})

    request = _make_request(b"hello", content_type="text/plain", token="secret")
    background_tasks = BackgroundTasks()

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(
            main_module.receive_incoming_webhook("missing", request, background_tasks)
        )

    assert excinfo.value.status_code == 404


def test_receive_incoming_webhook_requires_valid_bearer_token(monkeypatch):
    module = _incoming_module()
    monkeypatch.setattr(main_module.settings, "modules", {module.id: module})

    request = _make_request(b"hello", content_type="text/plain", token="wrong")
    background_tasks = BackgroundTasks()

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(
            main_module.receive_incoming_webhook("front-door", request, background_tasks)
        )

    assert excinfo.value.status_code == 401


def test_receive_incoming_webhook_allows_missing_auth_when_token_blank(monkeypatch):
    module = _incoming_module(token="")
    monkeypatch.setattr(main_module.settings, "modules", {module.id: module})
    monkeypatch.setattr(
        main_module.settings,
        "channels",
        {1: ChannelConfig(modules=[ChannelModuleAssignment(module_id=module.id, order=0)])},
    )
    monkeypatch.setattr(main_module.dial, "read_position", lambda: 1)
    monkeypatch.setattr(main_module, "_try_begin_print_job", lambda debounce=False: True)

    request = _make_request(b"hello", content_type="text/plain", token=None)
    background_tasks = BackgroundTasks()

    response = asyncio.run(
        main_module.receive_incoming_webhook("front-door", request, background_tasks)
    )

    assert response.status_code == 202
    assert len(background_tasks.tasks) == 1


def test_receive_incoming_webhook_requires_active_channel(monkeypatch):
    module = _incoming_module()
    monkeypatch.setattr(main_module.settings, "modules", {module.id: module})
    monkeypatch.setattr(
        main_module.settings,
        "channels",
        {2: ChannelConfig(modules=[ChannelModuleAssignment(module_id=module.id, order=0)])},
    )
    monkeypatch.setattr(main_module.dial, "read_position", lambda: 1)

    request = _make_request(
        b"hello",
        content_type="text/plain",
        token=module.config["token"],
    )
    background_tasks = BackgroundTasks()

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(
            main_module.receive_incoming_webhook("front-door", request, background_tasks)
        )

    assert excinfo.value.status_code == 503


def test_receive_incoming_webhook_returns_423_when_printer_busy(monkeypatch):
    module = _incoming_module()
    monkeypatch.setattr(main_module.settings, "modules", {module.id: module})
    monkeypatch.setattr(
        main_module.settings,
        "channels",
        {1: ChannelConfig(modules=[ChannelModuleAssignment(module_id=module.id, order=0)])},
    )
    monkeypatch.setattr(main_module.dial, "read_position", lambda: 1)
    monkeypatch.setattr(main_module, "_try_begin_print_job", lambda debounce=False: False)

    request = _make_request(
        b"hello",
        content_type="text/plain",
        token=module.config["token"],
    )
    background_tasks = BackgroundTasks()

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(
            main_module.receive_incoming_webhook("front-door", request, background_tasks)
        )

    assert excinfo.value.status_code == 423


def test_receive_incoming_webhook_accepts_text_and_schedules_background_print(
    monkeypatch,
):
    module = _incoming_module()
    monkeypatch.setattr(main_module.settings, "modules", {module.id: module})
    monkeypatch.setattr(
        main_module.settings,
        "channels",
        {1: ChannelConfig(modules=[ChannelModuleAssignment(module_id=module.id, order=0)])},
    )
    monkeypatch.setattr(main_module.dial, "read_position", lambda: 1)
    monkeypatch.setattr(main_module, "_try_begin_print_job", lambda debounce=False: True)

    request = _make_request(
        b"Front door motion",
        content_type="text/plain; charset=utf-8",
        token=module.config["token"],
    )
    background_tasks = BackgroundTasks()

    response = asyncio.run(
        main_module.receive_incoming_webhook("front-door", request, background_tasks)
    )

    assert response.status_code == 202
    assert len(background_tasks.tasks) == 1


def test_receive_incoming_webhook_rejects_unknown_json_item_type(monkeypatch):
    module = _incoming_module()
    monkeypatch.setattr(main_module.settings, "modules", {module.id: module})
    monkeypatch.setattr(
        main_module.settings,
        "channels",
        {1: ChannelConfig(modules=[ChannelModuleAssignment(module_id=module.id, order=0)])},
    )
    monkeypatch.setattr(main_module.dial, "read_position", lambda: 1)

    body = (
        b'{"title":"Door","items":[{"type":"video","url":"https://example.test/clip.mp4"}]}'
    )
    request = _make_request(
        body,
        content_type="application/json",
        token=module.config["token"],
    )
    background_tasks = BackgroundTasks()

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(
            main_module.receive_incoming_webhook("front-door", request, background_tasks)
        )

    assert excinfo.value.status_code == 400
    assert "Unsupported print item type" in excinfo.value.detail


def test_receive_incoming_webhook_rejects_svg_with_clear_error(monkeypatch):
    module = _incoming_module()
    monkeypatch.setattr(main_module.settings, "modules", {module.id: module})
    monkeypatch.setattr(
        main_module.settings,
        "channels",
        {1: ChannelConfig(modules=[ChannelModuleAssignment(module_id=module.id, order=0)])},
    )
    monkeypatch.setattr(main_module.dial, "read_position", lambda: 1)

    request = _make_request(
        b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
        content_type="image/svg+xml",
        token=module.config["token"],
    )
    background_tasks = BackgroundTasks()

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(
            main_module.receive_incoming_webhook("front-door", request, background_tasks)
        )

    assert excinfo.value.status_code == 400
    assert "SVG is not supported" in excinfo.value.detail


def test_parse_request_payload_rejects_invalid_raster_bytes():
    module_config = IncomingWebhookConfig(token="secret", endpoint_path="front-door")

    with pytest.raises(ValueError) as excinfo:
        incoming_webhook.parse_request_payload(
            content_type="image/png",
            body=b"not really an image",
            config=module_config,
            module_name="Front Door",
        )

    assert "Unsupported or invalid image" in str(excinfo.value)


def test_parse_request_payload_for_json_print_job_decodes_image_data():
    module_config = IncomingWebhookConfig(token="secret", endpoint_path="front-door")
    image_data = incoming_webhook.base64.b64encode(_png_bytes()).decode("ascii")
    body = (
        '{"title":"Door","subtitle":"Motion","items":['
        '{"type":"text","text":"Someone is here."},'
        f'{{"type":"image_data","data":"{image_data}"}}'
        "]}".encode("utf-8")
    )

    job = incoming_webhook.parse_request_payload(
        content_type="application/vnd.pc1.print+json",
        body=body,
        config=module_config,
        module_name="Front Door",
    )

    assert job["job_type"] == "json"
    assert job["title"] == "Door"
    assert job["subtitle"] == "Motion"
    assert job["items"][0]["type"] == "text"
    assert job["items"][1]["type"] == "image_data"
    assert isinstance(job["items"][1]["image_bytes"], bytes)


def test_print_parsed_job_prints_text_and_remote_image(monkeypatch):
    printer = _RecordingPrinter()
    module_config = IncomingWebhookConfig(
        token="secret",
        endpoint_path="front-door",
        max_image_height_dots=64,
    )
    requested = {}

    class _ImageResponse:
        content = _png_bytes(width=100, height=128)

        def raise_for_status(self):
            return None

    def fake_get(url, timeout=10):  # noqa: ARG001
        requested["url"] = url
        return _ImageResponse()

    monkeypatch.setattr(incoming_webhook.requests, "get", fake_get)

    incoming_webhook.print_parsed_job(
        printer,
        {
            "job_type": "json",
            "title": "Front Door",
            "subtitle": "Motion detected",
            "items": [
                {"type": "text", "text": "Someone is at the door."},
                {"type": "image_url", "url": "https://example.test/snapshot.png"},
            ],
        },
        module_config,
        "Incoming Webhook",
    )

    assert printer.headers == ["Front Door"]
    assert "Motion detected" in printer.captions
    assert printer.body == ["Someone is at the door."]
    assert requested["url"] == "https://example.test/snapshot.png"
    assert len(printer.images) == 1
    assert printer.images[0].size == (50, 64)


def test_print_parsed_job_prints_request_metadata_lines():
    printer = _RecordingPrinter()
    module_config = IncomingWebhookConfig(
        token="secret",
        endpoint_path="front-door",
        print_sender_ip=True,
        print_content_type=True,
        print_user_agent=True,
    )

    incoming_webhook.print_parsed_job(
        printer,
        {
            "job_type": "text",
            "title": "Front Door",
            "text": "Motion detected",
            "metadata_lines": [
                "From: 127.0.0.1",
                "Type: application/json",
                "UA: curl/8.7.1",
            ],
        },
        module_config,
        "Incoming Webhook",
    )

    assert "From: 127.0.0.1" in printer.captions
    assert "Type: application/json" in printer.captions
    assert "UA: curl/8.7.1" in printer.captions


def test_build_incoming_webhook_metadata_lines_respects_config():
    request = _make_request(
        b"hello",
        content_type="text/plain; charset=utf-8",
        token=None,
    )
    request.scope["headers"].append((b"user-agent", b"curl/8.7.1"))
    config = IncomingWebhookConfig(
        endpoint_path="front-door",
        print_sender_ip=True,
        print_content_type=True,
        print_user_agent=True,
    )

    lines = main_module._build_incoming_webhook_metadata_lines(request, config)

    assert lines == [
        "From: 127.0.0.1",
        "Type: text/plain",
        "UA: curl/8.7.1",
    ]


def test_run_incoming_webhook_print_job_clears_reservation(monkeypatch):
    module = _incoming_module()
    printer = _RecordingPrinter()
    cleared = []

    monkeypatch.setattr(main_module.settings, "modules", {module.id: module})
    monkeypatch.setattr(main_module.settings, "max_print_lines", 200)
    monkeypatch.setattr(main_module, "printer", printer)
    monkeypatch.setattr(
        main_module,
        "_clear_print_reservation",
        lambda clear_hold=False: cleared.append(clear_hold),
    )

    asyncio.run(
        main_module._run_incoming_webhook_print_job(
            module.id,
            {
                "job_type": "text",
                "title": "Front Door",
                "text": "Motion detected",
            },
        )
    )

    assert printer.reset_calls == [200]
    assert printer.headers == ["Front Door"]
    assert printer.body == ["Motion detected"]
    assert printer.flushed == 1
    assert cleared == [False]
