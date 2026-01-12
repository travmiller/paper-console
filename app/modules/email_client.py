import imaplib
import email
import socket
import logging
from email.header import decode_header
from bs4 import BeautifulSoup
from typing import Dict, Any, List
from app.config import EmailConfig, PRINTER_WIDTH
import app.config

# Set default socket timeout for IMAP operations (30 seconds)
IMAP_TIMEOUT = 30

logger = logging.getLogger(__name__)

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
    """Removes HTML tags to return clean text."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        return soup.get_text(separator=" ", strip=True)
    except Exception as e:
        logger.error(f"Error stripping HTML: {e}")
        return html_content

def wrap_text(text: str, width: int = 42) -> List[str]:
    """Wraps text into lines of specified width."""
    words = text.split()
    lines = []
    current_line = ""
    
    for word in words:
        if len(current_line) + len(word) + 1 <= width:
            current_line += (word + " ")
        else:
            if current_line:
                lines.append(current_line.rstrip())
            current_line = word + " "
            
            # Handle single words longer than width
            while len(current_line) > width:
                lines.append(current_line[:width])
                current_line = current_line[width:]
    
    if current_line:
        lines.append(current_line.rstrip())
        
    return lines

# --- REAL IMAP LOGIC ---
def fetch_emails(config: Dict[str, Any] = None) -> List[Dict[str, str]]:
    """
    Fetches unread emails from the inbox.
    Returns a list of dicts: {'from', 'subject', 'body'}
    """

    # Backwards compatibility / Direct Call support
    if config is None:
        for _, chan in app.config.settings.channels.items():
            if chan.type == "email":
                config = chan.config
                break
        if config is None:
            logger.warning("fetch_emails called but no email configuration found")
            return []

    try:
        if not config.get("email_user") or not config.get("email_password"):
            logger.warning("Missing email_user or email_password in config")
            return []

        email_config = EmailConfig(**config)
    except Exception as e:
        logger.error(f"Invalid email configuration: {e}")
        return []

    if not email_config.email_user or not email_config.email_password:
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
                        sender = clean_text(msg["From"])
                        
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

                        # Clean up body whitespace (newlines to spaces)
                        body = " ".join(body.split())

                        results.append(
                            {
                                "from": sender,
                                "subject": subject,
                                "body": body[:500],  # Truncate to prevent huge prints
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
    except Exception as e:
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
        printer.print_header(header_name)
        printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
        printer.print_line()
        printer.print_body("No new messages.")
        return

    printer.print_header(f"{header_name} ({len(messages)})")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()

    for i, msg in enumerate(messages):
        # Sender
        from_lines = wrap_text(msg['from'], PRINTER_WIDTH)
        printer.print_subheader(from_lines[0] if from_lines else "Unknown")
        
        # Subject in bold
        subj_lines = wrap_text(msg['subject'], PRINTER_WIDTH)
        for line in subj_lines:
            printer.print_bold(line)
            
        printer.print_line()

        # Body in regular text
        body_lines = wrap_text(msg["body"], PRINTER_WIDTH)
        for line in body_lines:
            printer.print_body(line)

        printer.print_line()
