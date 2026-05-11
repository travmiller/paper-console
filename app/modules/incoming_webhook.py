import base64
import io
import json
import logging
from typing import Any, Dict, Optional

import requests
from PIL import Image

from app.config import IncomingWebhookConfig, format_print_datetime
from app.drivers.printer_mock import PrinterDriver
from app.module_registry import register_module

logger = logging.getLogger(__name__)

INCOMING_WEBHOOK_MAX_WIDTH_DOTS = 384
INCOMING_WEBHOOK_DEFAULT_MAX_HEIGHT_DOTS = 4096
INCOMING_WEBHOOK_JSON_MEDIA_TYPE = "application/vnd.pc1.print+json"


def normalize_content_type(content_type: str) -> str:
    return (content_type or "").split(";", 1)[0].strip().lower()


def endpoint_for_module(module_id: str, config: Dict[str, Any]) -> str:
    endpoint_path = (config.get("endpoint_path") or module_id).strip().strip("/")
    return f"/hook/{endpoint_path}"


def prepare_image_for_print(
    image: Image.Image,
    *,
    max_width: int = INCOMING_WEBHOOK_MAX_WIDTH_DOTS,
    max_height: int = INCOMING_WEBHOOK_DEFAULT_MAX_HEIGHT_DOTS,
) -> Image.Image:
    prepared = image.copy()
    prepared.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    return prepared


def _validate_raster_image_bytes(image_bytes: bytes) -> None:
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image.verify()
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            "Unsupported or invalid image. Send a raster image such as PNG or JPEG."
        ) from exc


def _decode_image_data(item: Dict[str, Any]) -> bytes:
    raw_data = item.get("data") or item.get("image_data") or ""
    if not isinstance(raw_data, str) or not raw_data.strip():
        raise ValueError("image_data item requires non-empty 'data'")

    raw_data = raw_data.strip()
    if "," in raw_data and raw_data.lower().startswith("data:"):
        raw_data = raw_data.split(",", 1)[1]

    try:
        return base64.b64decode(raw_data, validate=True)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("image_data item is not valid base64") from exc


def parse_request_payload(
    *,
    content_type: str,
    body: bytes,
    config: IncomingWebhookConfig,
    module_name: str,
) -> Dict[str, Any]:
    normalized_type = normalize_content_type(content_type)

    if normalized_type == "text/plain":
        if not config.accept_text:
            raise ValueError("text/plain is disabled for this module")
        return {
            "job_type": "text",
            "title": config.print_header or module_name,
            "text": body.decode("utf-8", errors="replace"),
        }

    if normalized_type.startswith("image/"):
        if not config.accept_images:
            raise ValueError("image uploads are disabled for this module")
        if normalized_type == "image/svg+xml":
            raise ValueError("SVG is not supported. Send a raster image such as PNG or JPEG.")
        _validate_raster_image_bytes(body)
        return {
            "job_type": "image",
            "title": config.print_header or module_name,
            "image_bytes": body,
        }

    if normalized_type in ("application/json", INCOMING_WEBHOOK_JSON_MEDIA_TYPE):
        if not config.accept_json:
            raise ValueError("JSON payloads are disabled for this module")
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise ValueError("Malformed JSON body") from exc

        if not isinstance(payload, dict):
            raise ValueError("JSON payload must be an object")

        items = payload.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError("JSON payload must include a non-empty 'items' array")

        normalized_items = []
        for raw_item in items:
            if not isinstance(raw_item, dict):
                raise ValueError("Each print item must be an object")

            item_type = (raw_item.get("type") or "").strip().lower()
            if item_type == "text":
                text = raw_item.get("text")
                if not isinstance(text, str) or not text:
                    raise ValueError("text item requires non-empty 'text'")
                normalized_items.append({"type": "text", "text": text})
                continue

            if item_type == "image_url":
                url = raw_item.get("url")
                if not isinstance(url, str) or not url:
                    raise ValueError("image_url item requires non-empty 'url'")
                normalized_items.append({"type": "image_url", "url": url})
                continue

            if item_type == "image_data":
                normalized_items.append(
                    {"type": "image_data", "image_bytes": _decode_image_data(raw_item)}
                )
                continue

            raise ValueError(f"Unsupported print item type: {item_type or 'unknown'}")

        return {
            "job_type": "json",
            "title": str(payload.get("title") or config.print_header or module_name),
            "subtitle": str(payload.get("subtitle") or "").strip(),
            "items": normalized_items,
        }

    raise ValueError(f"Unsupported content type: {normalized_type or 'unknown'}")


def _print_image_bytes(
    printer: PrinterDriver,
    image_bytes: bytes,
    *,
    max_height: int,
) -> None:
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            printer.print_image(
                prepare_image_for_print(image, max_height=max(1, int(max_height)))
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to print incoming webhook image: %s", exc)
        printer.print_body("Error: Could not load image.")


def print_parsed_job(
    printer: PrinterDriver,
    job: Dict[str, Any],
    config: IncomingWebhookConfig,
    module_name: str,
) -> None:
    header = (job.get("title") or config.print_header or module_name or "WEBHOOK").strip()
    printer.print_header(header, icon="plugs")
    printer.print_caption(format_print_datetime())

    subtitle = (job.get("subtitle") or "").strip()
    if subtitle:
        printer.print_caption(subtitle)

    for line in job.get("metadata_lines") or []:
        if line:
            printer.print_caption(line)

    printer.print_line()

    if job["job_type"] == "text":
        printer.print_body(job.get("text") or "")
        return

    if job["job_type"] == "image":
        _print_image_bytes(
            printer,
            job.get("image_bytes") or b"",
            max_height=config.max_image_height_dots,
        )
        return

    if job["job_type"] != "json":
        printer.print_body("Error: Unsupported incoming webhook job.")
        return

    for item in job.get("items") or []:
        item_type = item.get("type")
        if item_type == "text":
            printer.print_body(item.get("text") or "")
        elif item_type == "image_url":
            try:
                response = requests.get(item["url"], timeout=10)
                response.raise_for_status()
                _print_image_bytes(
                    printer,
                    response.content,
                    max_height=config.max_image_height_dots,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to fetch incoming webhook image_url: %s", exc)
                printer.print_body("Error: Could not load remote image.")
        elif item_type == "image_data":
            _print_image_bytes(
                printer,
                item.get("image_bytes") or b"",
                max_height=config.max_image_height_dots,
            )
        else:
            printer.print_body(f"Error: Unsupported item type '{item_type}'.")

    if not job.get("items"):
        printer.print_body("No content.")


@register_module(
    type_id="incoming_webhook",
    label="Incoming Webhook",
    description="Receive webhooks and print their text or images immediately",
    icon="plugs-connected",
    offline=False,
    category="utilities",
    config_schema={
        "type": "object",
        "description": "Print incoming webhook payloads immediately when this module is on the active dial channel.",
        "properties": {
            "endpoint_path": {
                "type": "string",
                "title": "Endpoint Path",
                "description": "Unique URL suffix for this webhook. Final route is /hook/<endpoint_path>.",
            },
            "token": {
                "type": "string",
                "title": "Bearer Token",
                "description": "Optional. If set, send it as Authorization: Bearer <token>. Leave blank to accept unauthenticated requests.",
            },
            "print_header": {
                "type": "string",
                "title": "Printed Header",
                "description": "Optional header shown on printed receipts when the payload does not provide a title.",
            },
            "print_sender_ip": {
                "type": "boolean",
                "title": "Print Sender IP",
                "default": False,
            },
            "print_content_type": {
                "type": "boolean",
                "title": "Print Content Type",
                "default": False,
            },
            "print_user_agent": {
                "type": "boolean",
                "title": "Print User Agent",
                "default": False,
            },
            "accept_text": {
                "type": "boolean",
                "title": "Accept text/plain",
                "default": True,
            },
            "accept_images": {
                "type": "boolean",
                "title": "Accept image/*",
                "default": True,
            },
            "accept_json": {
                "type": "boolean",
                "title": "Accept JSON print jobs",
                "default": True,
            },
            "max_image_height_dots": {
                "type": "integer",
                "title": "Max Image Height (dots)",
                "default": INCOMING_WEBHOOK_DEFAULT_MAX_HEIGHT_DOTS,
                "minimum": 64,
                "maximum": 8192,
            },
            "delivery_help": {"type": "null", "title": ""},
        },
        "required": ["endpoint_path"],
    },
    ui_schema={
        "token": {"ui:widget": "password"},
        "endpoint_path": {"ui:placeholder": "front-door-camera"},
        "print_header": {"ui:placeholder": "Front Door"},
        "delivery_help": {"ui:widget": "incoming-webhook-help"},
    },
)
def format_incoming_webhook_receipt(
    printer: PrinterDriver,
    config: Optional[Dict[str, Any]] = None,
    module_name: str = None,
    module_id: str = None,
) -> None:
    config = config or {}
    module_name = module_name or "INCOMING WEBHOOK"

    printer.print_header(module_name, icon="plugs")
    printer.print_caption(format_print_datetime())
    printer.print_line()
    printer.print_body("Waiting for inbound webhooks.")
    printer.print_caption(f"Endpoint: {endpoint_for_module(module_id or 'MODULE_ID', config)}")
    printer.print_caption("Send Authorization: Bearer <token>")
