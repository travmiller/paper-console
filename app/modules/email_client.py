import imaplib
import email
import socket
import logging
from email.header import decode_header
from email.utils import parseaddr
from bs4 import BeautifulSoup
from typing import Dict, Any, List
from urllib.parse import urlsplit
import re
from app.config import EmailConfig, PRINTER_WIDTH
import app.config
from app.module_registry import register_module

# Set default socket timeout for IMAP operations (30 seconds)
IMAP_TIMEOUT = 30

logger = logging.getLogger(__name__)
_LAST_FETCH_ERROR = None

def clean_text(text):
    """Decodes headers/body to a printable string, removing newlines."""
    if not text:
        return ""
    try:
        decoded_list = decode_header(text)
    except Exception as e:
        logger.error(f"Error decoding header: {e}")
        return str(text)

    decoded_str = ""
    for chunk, charset in decoded_list:
        if isinstance(chunk, bytes):
            try:
                decoded_str += chunk.decode(charset or "utf-8")
            except:
                decoded_str += chunk.decode("utf-8", errors="ignore")
        else:
            decoded_str += str(chunk)
    
    # Critical: Remove newlines and tabs to prevent printer driver issues
    # Replace them with spaces so words don't get stuck together
    decoded_str = " ".join(decoded_str.split())
    
    return decoded_str


def strip_html(html_content):
    """Removes HTML tags to return clean text, preserving newlines."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        # Use separator="\n" to preserve paragraph structure from HTML
        # This converts <p>, <br>, <div> etc. to newlines
        text = soup.get_text(separator="\n", strip=False)
        # Normalize multiple newlines but preserve structure
        import re
        text = re.sub(r'\n{3,}', '\n\n', text)  # Max 2 consecutive newlines
        return text.strip()
    except Exception as e:
        logger.error(f"Error stripping HTML: {e}")
        return html_content


def format_sender(sender_raw: str) -> str:
    """Normalize sender field to a compact printable representation."""
    sender_raw = clean_text(sender_raw or "")
    name, addr = parseaddr(sender_raw)
    name = clean_text(name)
    addr = clean_text(addr)
    if name and addr:
        return f"{name} <{addr}>"
    if addr:
        return addr
    return sender_raw or "Unknown"


def _shorten_url(url: str, max_len: int = 56) -> str:
    try:
        parts = urlsplit(url)
        if not parts.scheme or not parts.netloc:
            return url[:max_len]
        base = f"{parts.scheme}://{parts.netloc}{parts.path or ''}"
        if len(base) > max_len:
            return base[: max_len - 3] + "..."
        return base
    except Exception:
        return url[:max_len]


def sanitize_email_body_for_print(body: str, max_lines: int = 10, max_chars: int = 700) -> str:
    """Reduce email body noise for thermal print readability."""
    if not body:
        return "No content."

    text = body.replace("\r\n", "\n").replace("\r", "\n")

    # Common quoted-printable artifacts in security alert emails.
    text = text.replace("=\n", "").replace("=3D", "=")

    # Collapse long URLs into compact form.
    def _url_repl(match):
        return _shorten_url(match.group(0), max_len=42)

    text = re.sub(r"https?://\S+", _url_repl, text)

    # Normalize excessive whitespace while preserving paragraph breaks.
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if ln]

    if not lines:
        return "No content."

    clipped_lines = []
    char_count = 0
    for line in lines:
        if len(clipped_lines) >= max_lines:
            break
        next_count = char_count + len(line)
        if next_count > max_chars:
            remaining = max(0, max_chars - char_count)
            if remaining > 12:
                clipped_lines.append(line[: remaining - 3] + "...")
            break
        clipped_lines.append(line)
        char_count = next_count

    if len(lines) > len(clipped_lines):
        clipped_lines.append("... (message truncated)")

    return "\n".join(clipped_lines)


def clip_wrapped_text(text: str, width: int, max_lines: int) -> str:
    """Wrap then clip text to a fixed line count, adding ellipsis if clipped."""
    wrapped = wrap_text(text or "", width=width)
    if not wrapped:
        return ""
    if len(wrapped) <= max_lines:
        return "\n".join(wrapped)

    clipped = wrapped[:max_lines]
    tail = clipped[-1]
    if len(tail) >= width - 3:
        tail = tail[: width - 3]
    clipped[-1] = tail + "..."
    return "\n".join(clipped)


# Use wrap_text from utils instead of duplicating
from app.utils import wrap_text

# --- REAL IMAP LOGIC ---
def fetch_emails(config: Dict[str, Any] = None) -> List[Dict[str, str]]:
    """
    Fetches unread emails from the inbox.
    Returns a list of dicts: {'from', 'subject', 'body'}
    """

    global _LAST_FETCH_ERROR
    _LAST_FETCH_ERROR = None

    # Backwards compatibility / Direct Call support
    if config is None:
        for _, chan in app.config.settings.channels.items():
            if chan.type == "email":
                config = chan.config
                break
        if config is None:
            logger.warning("fetch_emails called but no email configuration found")
            _LAST_FETCH_ERROR = "config_missing"
            return []

    try:
        if not config.get("email_user") or not config.get("email_password"):
            logger.warning("Missing email_user or email_password in config")
            _LAST_FETCH_ERROR = "auth_config_missing"
            return []

        # Provider Mapping
        service = config.get("email_service", "Custom")
        if service == "Gmail":
            config["email_host"] = "imap.gmail.com"
            config["email_port"] = 993
        elif service == "Outlook":
            config["email_host"] = "outlook.office365.com"
            config["email_port"] = 993
        elif service == "Yahoo":
            config["email_host"] = "imap.mail.yahoo.com"
            config["email_port"] = 993
        elif service == "iCloud":
            config["email_host"] = "imap.mail.me.com"
            config["email_port"] = 993
        
        # Default fallback for old configs or Custom without host
        if not config.get("email_host"):
             config["email_host"] = "imap.gmail.com"

        email_config = EmailConfig(**config)
    except Exception as e:
        logger.error(f"Invalid email configuration: {e}")
        _LAST_FETCH_ERROR = "config_invalid"
        return []

    if not email_config.email_user or not email_config.email_password:
        _LAST_FETCH_ERROR = "auth_config_missing"
        return []

    mail = None
    # Set socket timeout to prevent hanging forever
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(IMAP_TIMEOUT)

    try:
        logger.info(f"Connecting to IMAP server: {email_config.email_host}")
        mail = imaplib.IMAP4_SSL(email_config.email_host)
        mail.login(email_config.email_user, email_config.email_password)

        status, _ = mail.select("inbox")
        if status != "OK":
            logger.error(f"Failed to select inbox. Status: {status}")
            return []

        # Search for unread messages
        status, messages = mail.search(None, "UNSEEN")
        if status != "OK":
            logger.error(f"Failed to search for UNSEEN messages. Status: {status}")
            return []

        if not messages or not messages[0]:
            # No new emails
            return []

        msg_ids = messages[0].split()
        if not msg_ids:
            return []

        results = []
        fetched_msg_ids = []

        # Limit to last 5 (most recent)
        logger.info(f"Found {len(msg_ids)} unread messages. Fetching last 5.")
        for num in msg_ids[-5:]:
            try:
                status, msg_data = mail.fetch(num, "(RFC822)")
                if status != "OK":
                    logger.warning(f"Failed to fetch message {num}")
                    continue

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])

                        subject = clean_text(msg["Subject"])
                        sender = format_sender(msg["From"])
                        
                        logger.info(f"Processing email from: {sender}, subject: {subject}")

                        body = "No content."
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disposition = str(part.get("Content-Disposition"))

                                if "attachment" not in content_disposition:
                                    try:
                                        payload = part.get_payload(decode=True)
                                        if payload:
                                            decoded_payload = payload.decode(errors="replace")
                                            if content_type == "text/plain":
                                                body = decoded_payload
                                                break # Prefer plain text
                                            elif content_type == "text/html":
                                                body = strip_html(decoded_payload)
                                    except Exception as e:
                                        logger.warning(f"Error extracting body part: {e}")
                        else:
                            try:
                                payload = msg.get_payload(decode=True)
                                if payload:
                                    decoded_payload = payload.decode(errors="replace")
                                    if msg.get_content_type() == "text/html":
                                        body = strip_html(decoded_payload)
                                    else:
                                        body = decoded_payload
                            except Exception as e:
                                logger.warning(f"Error extracting message body: {e}")

                        body = sanitize_email_body_for_print(body)

                        results.append(
                            {
                                "from": sender,
                                "subject": subject,
                                "body": body,
                            }
                        )
                        fetched_msg_ids.append(num)
            except Exception as e:
                logger.error(f"Error processing message {num}: {e}")
                continue

        # Mark fetched emails as read
        if fetched_msg_ids:
            try:
                for msg_id in fetched_msg_ids:
                    mail.store(msg_id, "+FLAGS", "\\Seen")
            except Exception as e:
                logger.error(f"Error marking messages as seen: {e}")

        return results
    except imaplib.IMAP4.error as e:
        err = str(e).upper()
        if "AUTHENTICATIONFAILED" in err or "AUTH FAILED" in err:
            _LAST_FETCH_ERROR = "auth_failed"
        else:
            _LAST_FETCH_ERROR = "imap_error"
        logger.error(f"IMAP error: {e}")
        return []
    except Exception as e:
        _LAST_FETCH_ERROR = "imap_error"
        logger.error(f"IMAP error: {e}")
        return []
    finally:
        # Restore socket timeout
        socket.setdefaulttimeout(old_timeout)
        if mail:
            try:
                mail.close()
                mail.logout()
            except Exception:
                pass


# --- FORMATTER ---
@register_module(
    type_id="email",
    label="Email Inbox",
    description="Print unread emails from IMAP inbox",
    icon="envelope",
    offline=False,
    category="content",
    config_schema={
        "type": "object",
        "properties": {
            "email_service": {
                "type": "string", 
                "title": "Service Provider", 
                "default": "Gmail",
                "enum": ["Gmail", "Outlook", "Yahoo", "iCloud", "Custom"]
            },
            "email_user": {"type": "string", "title": "Email Address"},
            "email_password": {"type": "string", "title": "Password / App Password"},
            "email_host": {"type": "string", "title": "IMAP Host", "default": "imap.gmail.com"},
            "email_port": {"type": "integer", "title": "IMAP Port", "default": 993},
            "email_use_ssl": {"type": "boolean", "title": "Use SSL", "default": True},
            "auto_print_new": {"type": "boolean", "title": "Auto Print New Emails", "default": False}
        },
        "required": ["email_user", "email_password"]
    },
    ui_schema={
        "email_user": {"ui:placeholder": "you@example.com"},
        "email_password": {"ui:widget": "password"},
        "email_host": {
            "ui:placeholder": "imap.example.com",
            "ui:showWhen": {"field": "email_service", "value": "Custom"}
        },
        "email_port": {
            "ui:showWhen": {"field": "email_service", "value": "Custom"}
        },
        "email_use_ssl": {
            "ui:showWhen": {"field": "email_service", "value": "Custom"}
        }
    }
)
def format_email_receipt(
    printer, messages=None, config: Dict[str, Any] = None, module_name: str = None
):
    """Prints the unread email queue.

    Args:
        printer: The printer driver instance
        messages: Optional pre-fetched messages list. If None, fetches emails.
        config: Optional configuration override
        module_name: Optional custom module name for header
    """
    if messages is None:
        messages = fetch_emails(config)

    from datetime import datetime

    header_name = module_name or "EMAIL"

    if not messages:
        printer.print_header(header_name, icon="envelope")
        printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
        printer.print_line()
        if _LAST_FETCH_ERROR == "auth_failed":
            printer.print_body("Authentication failed.")
            printer.print_caption("Check email and app password.")
        elif _LAST_FETCH_ERROR == "auth_config_missing":
            printer.print_body("Email credentials missing.")
            printer.print_caption("Set email and app password.")
        else:
            printer.print_body("No new messages.")
        return

    printer.print_header(f"{header_name} ({len(messages)})", icon="envelope-open")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()

    for i, msg in enumerate(messages):
        raw_sender = msg.get("from", "")
        sender_name, sender_addr = parseaddr(raw_sender)
        sender_name = clean_text(sender_name)
        sender_addr = clean_text(sender_addr)
        if sender_addr and sender_name:
            printer.print_subheader(f"From: {sender_name}")
            printer.print_caption(f"  <{sender_addr}>")
        elif sender_addr:
            printer.print_subheader(f"From: {sender_addr}")
        else:
            sender = format_sender(raw_sender)
            printer.print_subheader(f"From: {sender or 'Unknown'}")

        subject = clean_text(msg.get("subject", "")) or "(No subject)"
        subject = clip_wrapped_text(subject, width=34, max_lines=2)
        body = sanitize_email_body_for_print(msg.get("body", ""), max_lines=6, max_chars=420)

        printer.print_bold(f"Subject: {subject}")
        printer.print_body(body)

        # Add separator line ONLY if this is not the last message
        if i < len(messages) - 1:
            printer.print_line()
