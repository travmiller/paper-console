import requests
import json
from typing import Optional
from app.drivers.printer_mock import PrinterDriver
from app.config import WebhookConfig
from app.utils import wrap_text


def run_webhook(action: WebhookConfig, printer: PrinterDriver, module_name: str = None):
    """
    Executes a custom webhook action and prints the result.
    Supports JSON path extraction to print specific fields.
    """
    from datetime import datetime

    # Use module_name if provided, otherwise use action.label, otherwise default
    header_label = (module_name or action.label or "WEBHOOK").upper()
    printer.print_header(header_label)
    printer.print_text(datetime.now().strftime("%A, %b %d"))
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
            printer.print_text(f"Error: {response.status_code}")
            printer.print_text(response.text[:100])  # Truncate error
            return

        # Success - Parse Content
        content_to_print = ""

        if action.json_path:
            try:
                data = response.json()
                # Simple dot notation support (e.g. "slip.advice")
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
                    content_to_print = (
                        f"Path '{action.json_path}' not found or complex."
                    )
            except Exception as e:
                content_to_print = f"JSON Parse Error: {e}"
        else:
            # No path, try to print clean text or raw body
            # If it's JSON, pretty print it
            try:
                data = response.json()
                content_to_print = json.dumps(data, indent=2)
            except:
                content_to_print = response.text

        # Print the result with proper text wrapping to prevent word splitting
        if content_to_print:
            # Split by newlines first (preserve existing line breaks)
            for original_line in content_to_print.split("\n"):
                # Wrap each line to fit printer width
                wrapped_lines = wrap_text(original_line, width=printer.width, indent=0)
                for wrapped_line in wrapped_lines:
                    printer.print_text(wrapped_line)

    except Exception:
        printer.print_text("Could not connect.")
