"""
QR Code module for printing QR codes offline.

Supports multiple QR code types:
- Plain text
- URLs
- WiFi credentials
- Contact cards (vCard)
- Phone numbers
- SMS
- Email addresses
"""

from app.config import QRCodeConfig
from app.drivers.printer_mock import PrinterDriver
from datetime import datetime
from app.module_registry import register_module


def _generate_wifi_string(ssid: str, password: str, security: str = "WPA", hidden: bool = False) -> str:
    """Generate WiFi QR code string format."""
    # WIFI:T:WPA;S:mynetwork;P:mypass;H:false;;
    hidden_str = "true" if hidden else "false"
    # Escape special characters in SSID and password
    ssid = ssid.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace(":", "\\:")
    password = password.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace(":", "\\:")
    
    if security.upper() == "NOPASS":
        return f"WIFI:T:nopass;S:{ssid};H:{hidden_str};;"
    else:
        return f"WIFI:T:{security};S:{ssid};P:{password};H:{hidden_str};;"


def _generate_vcard(name: str, phone: str = "", email: str = "") -> str:
    """Generate vCard QR code string format."""
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"FN:{name}",
    ]
    if phone:
        lines.append(f"TEL:{phone}")
    if email:
        lines.append(f"EMAIL:{email}")
    lines.append("END:VCARD")
    return "\n".join(lines)


def _generate_phone(phone: str) -> str:
    """Generate phone number QR code string."""
    return f"tel:{phone}"


def _generate_sms(phone: str, message: str = "") -> str:
    """Generate SMS QR code string."""
    if message:
        return f"sms:{phone}?body={message}"
    return f"sms:{phone}"


def _generate_email(email: str, subject: str = "", body: str = "") -> str:
    """Generate email QR code string."""
    result = f"mailto:{email}"
    params = []
    if subject:
        params.append(f"subject={subject}")
    if body:
        params.append(f"body={body}")
    if params:
        result += "?" + "&".join(params)
    return result


@register_module(
    type_id="qrcode",
    label="QR Code",
    description="Generate QR codes for URLs, WiFi, contacts, phone numbers, and more",
    icon="qr-code",
    offline=True,
    category="utilities",
)
def format_qrcode_receipt(printer: PrinterDriver, config: dict, module_name: str = None):
    """Print a QR code based on configuration."""
    qr_config = QRCodeConfig(**config) if isinstance(config, dict) else config
    
    header_label = module_name or "QR CODE"
    
    printer.print_header(header_label)
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()
    
    # Generate QR code data based on type
    qr_type = qr_config.qr_type.lower()
    qr_data = ""
    description = ""
    
    if qr_type == "wifi":
        qr_data = _generate_wifi_string(
            ssid=qr_config.wifi_ssid,
            password=qr_config.wifi_password,
            security=qr_config.wifi_security,
            hidden=qr_config.wifi_hidden
        )
        description = "Scan to connect"
        printer.print_subheader("WiFi Network")
        printer.print_bold(qr_config.wifi_ssid)
        if qr_config.wifi_security.upper() != "NOPASS":
            printer.print_caption(f"Password: {qr_config.wifi_password}")
        else:
            printer.print_caption("(Open network)")
    
    elif qr_type == "contact":
        qr_data = _generate_vcard(
            name=qr_config.contact_name,
            phone=qr_config.contact_phone,
            email=qr_config.contact_email
        )
        description = "Scan to add contact"
        printer.print_subheader("Contact")
        printer.print_bold(qr_config.contact_name)
        if qr_config.contact_phone:
            printer.print_body(qr_config.contact_phone)
        if qr_config.contact_email:
            printer.print_caption(qr_config.contact_email)
    
    elif qr_type == "phone":
        qr_data = _generate_phone(qr_config.content)
        description = "Scan to call"
        printer.print_subheader("Phone")
        printer.print_bold(qr_config.content)
    
    elif qr_type == "sms":
        qr_data = _generate_sms(qr_config.content)
        description = "Scan to text"
        printer.print_subheader("SMS")
        printer.print_bold(qr_config.content)
    
    elif qr_type == "email":
        qr_data = _generate_email(qr_config.content)
        description = "Scan to email"
        printer.print_subheader("Email")
        printer.print_bold(qr_config.content)
    
    elif qr_type == "url":
        qr_data = qr_config.content
        if not qr_data.startswith(("http://", "https://")):
            qr_data = "https://" + qr_data
        description = "Scan to visit"
        printer.print_subheader("Link")
        # Let print_body handle wrapping automatically
        printer.print_body(qr_config.content)
    
    else:  # Default to plain text
        qr_data = qr_config.content
        description = "Scan to view"
        printer.print_subheader("Text")
        content_lines = qr_config.content.split("\n")[:3]
        for line in content_lines:
            if len(line) > printer.width:
                printer.print_body(line[:printer.width - 3] + "...")
            else:
                printer.print_body(line)
        if len(qr_config.content.split("\n")) > 3:
            printer.print_caption("...")
    
    # Validate we have data to encode
    if not qr_data:
        printer.print_body("No content to encode.")
        printer.print_caption("Configure in settings.")
        return
    
    printer.print_line()
    
    # Print the QR code
    printer.print_qr(
        data=qr_data,
        size=qr_config.size,
        error_correction=qr_config.error_correction
    )
