import imaplib
import email
from email.header import decode_header
from bs4 import BeautifulSoup
from typing import Dict, Any
from app.config import settings, EmailConfig


def clean_text(text):
    """Decodes headers/body to a printable string."""
    if not text:
        return ""
    decoded_list = decode_header(text)
    decoded_str = ""
    for chunk, charset in decoded_list:
        if isinstance(chunk, bytes):
            try:
                decoded_str += chunk.decode(charset or "utf-8")
            except:
                decoded_str += chunk.decode("utf-8", errors="ignore")
        else:
            decoded_str += str(chunk)
    return decoded_str


def strip_html(html_content):
    """Removes HTML tags to return clean text."""
    soup = BeautifulSoup(html_content, "html.parser")
    return soup.get_text(separator=" ", strip=True)


# --- REAL IMAP LOGIC ---
def fetch_emails(config: Dict[str, Any] = None):
    """
    Fetches unread emails from the 'pc-1' folder.
    Returns a list of dicts: {'from', 'subject', 'body'}
    """

    # Backwards compatibility / Direct Call support
    if config is None:
        # Try to find email config from channels (legacy support)
        for _, chan in settings.channels.items():
            if chan.type == "email":
                config = chan.config
                break
        if config is None:
            # No config found, return empty
            print("[EMAIL] No email configuration found.")
            return []

    try:
        # Validate config has required fields
        if not config.get("email_user") or not config.get("email_password"):
            print("[EMAIL] Missing email credentials in config.")
            return []

        email_config = EmailConfig(**config)
    except Exception as e:
        print(f"Invalid Email Config: {e}")
        return []

    if not email_config.email_user or not email_config.email_password:
        print("No email credentials found.")
        return []

    mail = None
    try:
        mail = imaplib.IMAP4_SSL(email_config.email_host)
        mail.login(email_config.email_user, email_config.email_password)

        # Select Inbox (Dedicated Account Mode)
        status, _ = mail.select("inbox")
        if status != "OK":
            print(f"[EMAIL] Failed to select inbox. Status: {status}")
            return []

        # Search for all Unread emails
        status, messages = mail.search(None, "UNSEEN")
        if status != "OK":
            print(f"[EMAIL] Failed to search for emails. Status: {status}")
            return []
        
        if not messages[0]:
            # No unread emails
            return []
        
        msg_ids = messages[0].split()
        if not msg_ids:
            return []

        results = []
        fetched_msg_ids = []  # Track which messages we fetched
        
        # Limit to last 5
        for num in msg_ids[-5:]:
            try:
                status, msg_data = mail.fetch(num, "(RFC822)")
                if status != "OK":
                    continue
                    
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])

                        subject = clean_text(msg["Subject"])
                        sender = clean_text(msg["From"])

                        # Get Body
                        body = "No content."
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disposition = str(part.get("Content-Disposition"))

                                if "attachment" not in content_type:
                                    try:
                                        payload = part.get_payload(decode=True).decode()
                                        if content_type == "text/plain":
                                            body = payload
                                            break  # Prefer plain text
                                        elif content_type == "text/html":
                                            body = strip_html(
                                                payload
                                            )  # Fallback to stripped HTML
                                    except:
                                        pass
                        else:
                            try:
                                payload = msg.get_payload(decode=True).decode()
                                if msg.get_content_type() == "text/html":
                                    body = strip_html(payload)
                                else:
                                    body = payload
                            except:
                                pass

                        # Clean up body (remove excessive whitespace)
                        body = " ".join(body.split())

                        results.append(
                            {
                                "from": sender,
                                "subject": subject,
                                "body": body[:500],  # Truncate
                            }
                        )
                        fetched_msg_ids.append(num)
            except Exception as e:
                print(f"[EMAIL] Error fetching message {num}: {e}")
                continue

        # Mark fetched emails as read
        if fetched_msg_ids:
            try:
                for msg_id in fetched_msg_ids:
                    mail.store(msg_id, "+FLAGS", "\\Seen")
            except Exception as e:
                print(f"[EMAIL] Warning: Failed to mark emails as read: {e}")

        return results
    except Exception as e:
        print(f"[EMAIL] IMAP Error: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        # Close connection
        if mail:
            try:
                mail.close()
                mail.logout()
            except:
                pass


# --- FORMATTER ---
def format_email_receipt(printer, messages=None, config: Dict[str, Any] = None, module_name: str = None):
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
    
    header_name = (module_name or "EMAIL INBOX").upper()

    if not messages:
        printer.print_header(header_name)
        printer.print_text(datetime.now().strftime("%A, %b %d"))
        printer.print_line()
        printer.print_text("No new messages.")
        return

    printer.print_header(f"{header_name} ({len(messages)})")
    printer.print_text(datetime.now().strftime("%A, %b %d"))
    printer.print_line()

    for i, msg in enumerate(messages):
        # Header: FROM
        printer.print_text(f"FROM: {msg['from']}")

        # Header: SUBJECT
        # Wrap subject if needed
        printer.print_text(f"SUBJ: {msg['subject']}")
        printer.print_line()

        # Body
        # Simple wrapping
        words = msg["body"].split()
        line = ""
        for word in words:
            if len(line) + len(word) + 1 <= 32:  # PRINTER_WIDTH
                line += word + " "
            else:
                printer.print_text(line)
                line = word + " "
        if line:
            printer.print_text(line)

        printer.print_line()  # Separator between emails
