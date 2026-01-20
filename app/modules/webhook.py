import requests
import json
from typing import Optional
from app.drivers.printer_mock import PrinterDriver
from app.config import WebhookConfig
from app.module_registry import register_module


# Preset configurations for common webhooks
WEBHOOK_PRESETS = {
    "custom": {
        "label": "Custom",
        "url": "",
        "method": "GET",
        "headers": {},
        "body": "",
        "json_path": ""
    },
    "dad_jokes": {
        "label": "Dad Jokes",
        "url": "https://icanhazdadjoke.com/",
        "method": "GET",
        "headers": {"Accept": "application/json"},
        "body": "",
        "json_path": "joke"
    },
    "chuck_norris": {
        "label": "Chuck Norris Facts",
        "url": "https://api.chucknorris.io/jokes/random",
        "method": "GET",
        "headers": {},
        "body": "",
        "json_path": "value"
    },
    "cat_facts": {
        "label": "Cat Facts",
        "url": "https://catfact.ninja/fact",
        "method": "GET",
        "headers": {},
        "body": "",
        "json_path": "fact"
    }
}


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
                 "enum": ["custom", "dad_jokes", "chuck_norris", "cat_facts"],
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
             "test_button": {"type": "null", "title": ""}
        },
        "required": ["url"]
    },
    ui_schema={
        "preset": {"ui:widget": "preset-select", "ui:options": {"presets": WEBHOOK_PRESETS}},
        "headers": {"ui:widget": "key-value-list"},
        "body": {"ui:widget": "textarea", "ui:showWhen": {"field": "method", "value": "POST"}},
        "test_button": {"ui:widget": "webhook-test"}
    },
)
def run_webhook(action: WebhookConfig, printer: PrinterDriver, module_name: str = None):
    """
    Executes a custom webhook action and prints the result.
    Supports JSON path extraction to print specific fields.
    """
    from datetime import datetime

    header_label = module_name or "WEBHOOK"
    printer.print_header(header_label, icon="plugs")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()

    try:
        response = None
        headers = action.headers or {}

        if action.method.upper() == "POST":
            json_body = None
            if action.body:
                try:
                    json_body = json.loads(action.body)
                except json.JSONDecodeError:
                    json_body = {}

            response = requests.post(
                action.url, json=json_body, headers=headers, timeout=10
            )
        else:
            response = requests.get(action.url, headers=headers, timeout=10)

        if response.status_code >= 400:
            printer.print_bold(f"Error: {response.status_code}")
            printer.print_caption(response.text[:100])
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
