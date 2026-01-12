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


def format_qrcode_receipt(printer: PrinterDriver, config: dict, module_name: str = None):
    """Print a QR code based on configuration."""
    qr_config = QRCodeConfig(**config) if isinstance(config, dict) else config
    
    # Determine header label
    header_label = (module_name or qr_config.label or "QR CODE").upper()
    
    # Print header
    printer.print_header(header_label)
    printer.print_text(datetime.now().strftime("%A, %b %d"))
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
        description = f"WiFi: {qr_config.wifi_ssid}"
        if qr_config.wifi_security.upper() != "NOPASS":
            printer.print_text(f"Network: {qr_config.wifi_ssid}")
            printer.print_text(f"Password: {qr_config.wifi_password}")
        else:
            printer.print_text(f"Network: {qr_config.wifi_ssid}")
            printer.print_text("(Open network)")
        printer.print_text("")
    
    elif qr_type == "contact":
        qr_data = _generate_vcard(
            name=qr_config.contact_name,
            phone=qr_config.contact_phone,
            email=qr_config.contact_email
        )
        description = f"Contact: {qr_config.contact_name}"
        printer.print_text(f"Name: {qr_config.contact_name}")
        if qr_config.contact_phone:
            printer.print_text(f"Phone: {qr_config.contact_phone}")
        if qr_config.contact_email:
            printer.print_text(f"Email: {qr_config.contact_email}")
        printer.print_text("")
    
    elif qr_type == "phone":
        qr_data = _generate_phone(qr_config.content)
        description = f"Call: {qr_config.content}"
        printer.print_text(f"Phone: {qr_config.content}")
        printer.print_text("")
    
    elif qr_type == "sms":
        qr_data = _generate_sms(qr_config.content)
        description = f"SMS: {qr_config.content}"
        printer.print_text(f"Text: {qr_config.content}")
        printer.print_text("")
    
    elif qr_type == "email":
        qr_data = _generate_email(qr_config.content)
        description = f"Email: {qr_config.content}"
        printer.print_text(f"Email: {qr_config.content}")
        printer.print_text("")
    
    elif qr_type == "url":
        qr_data = qr_config.content
        # Add protocol if missing
        if not qr_data.startswith(("http://", "https://")):
            qr_data = "https://" + qr_data
        description = "Scan to visit"
        # Truncate long URLs for display
        display_url = qr_config.content[:28] + "..." if len(qr_config.content) > 30 else qr_config.content
        printer.print_text(display_url)
        printer.print_text("")
    
    else:  # Default to plain text
        qr_data = qr_config.content
        description = "Scan to view"
        # Print first few lines of content
        content_lines = qr_config.content.split("\n")[:3]
        for line in content_lines:
            if len(line) > printer.width:
                printer.print_text(line[:printer.width - 3] + "...")
            else:
                printer.print_text(line)
        if len(qr_config.content.split("\n")) > 3:
            printer.print_text("...")
        printer.print_text("")
    
    # Validate we have data to encode
    if not qr_data:
        printer.print_text("No content to encode.")
        printer.print_text("Please configure this")
        printer.print_text("module in settings.")
        return
    
    # Print the QR code
    printer.print_qr(
        data=qr_data,
        size=qr_config.size,
        error_correction=qr_config.error_correction
    )
    
    # Add instruction
    printer.print_text("")
    printer.print_text(description)
