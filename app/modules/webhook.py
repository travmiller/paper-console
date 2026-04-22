import requests
import json
import io
import logging
from typing import Optional
from PIL import Image
from app.drivers.printer_mock import PrinterDriver
from app.config import WebhookConfig, format_print_datetime
from app.module_registry import register_module
from app.utils import prepare_image_for_print

logger = logging.getLogger(__name__)

SAMPLE_IMAGE_WEBHOOK_URL = (
    "https://placehold.co/384x192/ffffff/000000.png?text=PC-1+Image+Webhook"
)


# Preset configurations for common webhooks
WEBHOOK_PRESETS = {
    "custom": {
        "label": "Custom",
        "url": "",
        "method": "GET",
        "headers": {},
        "body": "",
        "json_path": "",
        "auth_type": "none",
        "auth_username": "",
        "auth_password": ""
    },
    "dad_jokes": {
        "label": "Dad Jokes",
        "url": "https://icanhazdadjoke.com/",
        "method": "GET",
        "headers": {"Accept": "application/json"},
        "body": "",
        "json_path": "joke",
        "auth_type": "none",
        "auth_username": "",
        "auth_password": ""
    },
    "chuck_norris": {
        "label": "Chuck Norris Facts",
        "url": "https://api.chucknorris.io/jokes/random",
        "method": "GET",
        "headers": {},
        "body": "",
        "json_path": "value",
        "auth_type": "none",
        "auth_username": "",
        "auth_password": ""
    },
    "cat_facts": {
        "label": "Cat Facts",
        "url": "https://catfact.ninja/fact",
        "method": "GET",
        "headers": {},
        "body": "",
        "json_path": "fact",
        "auth_type": "none",
        "auth_username": "",
        "auth_password": ""
    },
    "sample_image": {
        "label": "Sample Image",
        "url": SAMPLE_IMAGE_WEBHOOK_URL,
        "method": "GET",
        "headers": {},
        "body": "",
        "json_path": "",
        "auth_type": "none",
        "auth_username": "",
        "auth_password": ""
    }
}


def _response_content_type(response) -> str:
    return (response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()


def _response_is_image(response) -> bool:
    return _response_content_type(response).startswith("image/")

def _print_image_response(response, printer: PrinterDriver) -> bool:
    try:
        with Image.open(io.BytesIO(response.content)) as image:
            printer.print_image(prepare_image_for_print(image))
        return True
    except Exception as exc:
        logger.error("Failed to print webhook image response: %s", exc)
        printer.print_body("Error: Could not load image.")
        return False


def _webhook_auth(action: WebhookConfig):
    auth_type = (action.auth_type or "none").strip().lower()
    username = action.auth_username or ""
    password = action.auth_password or ""

    if auth_type == "basic":
        return requests.auth.HTTPBasicAuth(username, password)
    if auth_type == "digest":
        return requests.auth.HTTPDigestAuth(username, password)
    return None


def request_webhook_response(action: WebhookConfig):
    headers = action.headers or {}
    auth = _webhook_auth(action)

    if action.method.upper() == "POST":
        json_body = None
        if action.body:
            try:
                json_body = json.loads(action.body)
            except json.JSONDecodeError:
                json_body = {}

        return requests.post(
            action.url, json=json_body, headers=headers, auth=auth, timeout=10
        )

    return requests.get(action.url, headers=headers, auth=auth, timeout=10)


@register_module(
    type_id="webhook",
    label="Webhook",
    description="Fetch and print data from any API endpoint",
    icon="plugs",
    offline=False,
    category="utilities",
    config_schema={
        "type": "object",
        "properties": {
             "preset": {
                 "type": "string",
                 "title": "Preset",
                 "enum": ["custom", "dad_jokes", "chuck_norris", "cat_facts", "sample_image"],
                 "default": "custom"
             },
             "url": {"type": "string", "title": "URL"},
             "method": {"type": "string", "title": "Method", "enum": ["GET", "POST"], "default": "GET"},
             "headers": {
                 "type": "object",
                 "title": "Headers",
                 "description": "Custom HTTP headers",
                 "default": {}
             },
             "body": {"type": "string", "title": "Body (JSON)"},
             "json_path": {"type": "string", "title": "JSON Path"},
             "auth_type": {
                 "type": "string",
                 "title": "Auth Type",
                 "enum": ["none", "basic", "digest"],
                 "default": "none"
             },
             "auth_username": {"type": "string", "title": "Username"},
             "auth_password": {"type": "string", "title": "Password"},
             "test_button": {"type": "null", "title": ""}
        },
        "required": ["url"]
    },
    ui_schema={
        "preset": {"ui:widget": "preset-select", "ui:options": {"presets": WEBHOOK_PRESETS}},
        "url": {"ui:placeholder": "https://example.com/api"},
        "headers": {"ui:widget": "key-value-list"},
        "body": {
            "ui:widget": "textarea",
            "ui:placeholder": "{\"message\":\"hello\"}",
            "ui:showWhen": {"field": "method", "value": "POST"}
        },
        "json_path": {"ui:placeholder": "data.message"},
        "auth_username": {
            "ui:placeholder": "admin",
            "ui:showWhen": {"field": "auth_type", "values": ["basic", "digest"]}
        },
        "auth_password": {
            "ui:widget": "password",
            "ui:showWhen": {"field": "auth_type", "values": ["basic", "digest"]}
        },
        "test_button": {"ui:widget": "webhook-test"}
    },
)
def run_webhook(action: WebhookConfig, printer: PrinterDriver, module_name: str = None):
    """
    Executes a custom webhook action and prints the result.
    Supports JSON path extraction to print specific fields.
    """
    header_label = module_name or "WEBHOOK"
    printer.print_header(header_label, icon="plugs")
    printer.print_caption(format_print_datetime())
    printer.print_line()

    try:
        response = request_webhook_response(action)

        if response.status_code >= 400:
            printer.print_bold(f"Error: {response.status_code}")
            printer.print_caption(response.text[:100])
            return

        if _response_is_image(response):
            _print_image_response(response, printer)
            return

        # Success - Parse Content
        content_to_print = ""

        if action.json_path:
            try:
                data = response.json()
                keys = action.json_path.split(".")
                value = data
                for k in keys:
                    if isinstance(value, dict):
                        value = value.get(k, {})
                    elif isinstance(value, list) and k.isdigit():
                        idx = int(k)
                        if 0 <= idx < len(value):
                            value = value[idx]
                        else:
                            value = None
                    else:
                        value = None
                        break

                if value and not isinstance(value, (dict, list)):
                    content_to_print = str(value)
                else:
                    content_to_print = f"Path '{action.json_path}' not found."
            except Exception as e:
                content_to_print = f"JSON Parse Error: {e}"
        else:
            try:
                data = response.json()
                content_to_print = json.dumps(data, indent=2)
            except:
                content_to_print = response.text

        # Print result with styled text - pass directly, printer will handle wrapping and newlines
        if content_to_print:
            printer.print_body(content_to_print)

    except Exception:
        printer.print_caption("Could not connect.")
