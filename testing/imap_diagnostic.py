#!/usr/bin/env python3
"""Safe IMAP login diagnostic for PC-1 test email config."""

from __future__ import annotations

import argparse
import imaplib
import os
import socket
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for raw in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def mask_email(addr: str) -> str:
    if "@" not in addr:
        return "(invalid-email)"
    name, domain = addr.split("@", 1)
    if len(name) <= 2:
        masked_name = "*" * len(name)
    else:
        masked_name = name[0] + ("*" * (len(name) - 2)) + name[-1]
    return f"{masked_name}@{domain}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose IMAP auth for PC-1 test email.")
    parser.add_argument("--dotenv", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    load_dotenv(args.dotenv)

    user = os.getenv("PC1_TEST_EMAIL_USER", "").strip()
    password = os.getenv("PC1_TEST_EMAIL_APP_PASSWORD", "").strip()
    host = os.getenv("PC1_TEST_EMAIL_HOST", "imap.gmail.com").strip() or "imap.gmail.com"

    print(f"[imap] dotenv={args.dotenv} exists={args.dotenv.exists()}")
    print(f"[imap] host={host}")
    print(f"[imap] user={mask_email(user) if user else '(missing)'}")
    print(f"[imap] app_password_set={'yes' if bool(password) else 'no'}")
    print(f"[imap] app_password_length={len(password)}")

    if not user or not password:
        print("[imap] result=missing_config")
        print("[imap] hint=Set PC1_TEST_EMAIL_USER and PC1_TEST_EMAIL_APP_PASSWORD.")
        return 2

    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(args.timeout)
    mail = None
    try:
        mail = imaplib.IMAP4_SSL(host)
        mail.login(user, password)
        status, _ = mail.select("inbox")
        print(f"[imap] login=ok inbox_select={status}")
        return 0
    except imaplib.IMAP4.error as exc:
        text = str(exc)
        upper = text.upper()
        if "AUTHENTICATIONFAILED" in upper or "AUTH FAILED" in upper:
            reason = "auth_failed"
        else:
            reason = "imap_error"
        print(f"[imap] login=fail reason={reason}")
        print(f"[imap] server_message={text}")
        return 1
    except Exception as exc:
        print("[imap] login=fail reason=network_or_ssl_error")
        print(f"[imap] error={exc}")
        return 1
    finally:
        socket.setdefaulttimeout(old_timeout)
        if mail:
            try:
                mail.close()
            except Exception:
                pass
            try:
                mail.logout()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
