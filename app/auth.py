"""Shared authentication helpers for privileged API endpoints."""

import base64
import hashlib
import hmac
import ipaddress
import json
import os
import time
from typing import Dict, Optional
from urllib.parse import urlparse

from fastapi import HTTPException, Request, Response

import app.wifi_manager as wifi_manager

AUTH_REQUIRED_HEADER = "X-PC1-Auth-Required"
TOKEN_HEADER = "X-PC1-Admin-Token"
SESSION_COOKIE_NAME = "pc1_admin_session"
REMEMBER_DURATION_SECONDS = 30 * 24 * 60 * 60
SESSION_DURATION_SECONDS = 12 * 60 * 60


def _host_is_private_or_local(host: Optional[str]) -> bool:
    if not host:
        return False

    # Handle values like "127.0.0.1:12345".
    if ":" in host and host.count(":") == 1:
        host = host.split(":")[0]

    lowered = host.lower()
    if lowered in {"localhost", "pc-1.local"}:
        return True

    try:
        addr = ipaddress.ip_address(host)
        return addr.is_loopback or addr.is_private or addr.is_link_local
    except ValueError:
        return False


def _origin_is_local(origin: Optional[str]) -> bool:
    if not origin:
        return False
    try:
        parsed = urlparse(origin)
        return _host_is_private_or_local(parsed.hostname)
    except Exception:
        return False


def _urlsafe_b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _urlsafe_b64decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(f"{raw}{padding}".encode("ascii"))


def _current_admin_password() -> str:
    configured_token = os.environ.get("PC1_ADMIN_TOKEN", "").strip()
    if configured_token:
        return configured_token
    return wifi_manager.get_ap_password()


def _session_secret() -> bytes:
    explicit_secret = os.environ.get("PC1_SESSION_SECRET", "").strip()
    if explicit_secret:
        seed = explicit_secret
    else:
        seed = wifi_manager.get_device_password_seed()
    return hashlib.sha256(f"pc1-session::{seed}".encode("utf-8")).digest()


def _password_fingerprint() -> str:
    return hashlib.sha256(_current_admin_password().encode("utf-8")).hexdigest()


def _sign_session_payload(payload_segment: str) -> str:
    signature = hmac.new(
        _session_secret(),
        payload_segment.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _urlsafe_b64encode(signature)


def _build_session_cookie_value(remember: bool) -> str:
    now = int(time.time())
    lifetime = REMEMBER_DURATION_SECONDS if remember else SESSION_DURATION_SECONDS
    payload = {
        "v": 1,
        "iat": now,
        "exp": now + lifetime,
        "pwd": _password_fingerprint(),
    }
    payload_segment = _urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signature_segment = _sign_session_payload(payload_segment)
    return f"{payload_segment}.{signature_segment}"


def _read_session_payload(cookie_value: str) -> Optional[Dict[str, object]]:
    try:
        payload_segment, signature_segment = cookie_value.split(".", 1)
    except ValueError:
        return None

    expected_signature = _sign_session_payload(payload_segment)
    if not hmac.compare_digest(signature_segment, expected_signature):
        return None

    try:
        payload = json.loads(_urlsafe_b64decode(payload_segment).decode("utf-8"))
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    expires_at = int(payload.get("exp", 0))
    if expires_at <= int(time.time()):
        return None

    if payload.get("pwd") != _password_fingerprint():
        return None

    return payload


def is_admin_authenticated(request: Request) -> bool:
    provided_token = request.headers.get(TOKEN_HEADER, "").strip()
    if provided_token and hmac.compare_digest(provided_token, _current_admin_password()):
        return True

    session_cookie = request.cookies.get(SESSION_COOKIE_NAME, "").strip()
    if session_cookie and _read_session_payload(session_cookie):
        return True

    return False


def verify_admin_password(password: str) -> bool:
    candidate = (password or "").strip()
    if not candidate:
        return False
    return hmac.compare_digest(candidate, _current_admin_password())


def set_admin_session_cookie(
    response: Response,
    remember: bool,
    *,
    secure: bool = False,
) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=_build_session_cookie_value(remember=remember),
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=REMEMBER_DURATION_SECONDS if remember else None,
    )


def clear_admin_session_cookie(response: Response, *, secure: bool = False) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=secure,
        samesite="lax",
    )


def _allow_setup_mode_without_auth(request: Request) -> bool:
    if not wifi_manager.is_ap_mode_active():
        return False
    client_host = request.client.host if request.client else None
    origin = request.headers.get("origin")
    return _host_is_private_or_local(client_host) or _origin_is_local(origin)


def require_admin_access(request: Request):
    """Protect privileged endpoints with header or signed-session auth."""
    if is_admin_authenticated(request):
        return

    if _allow_setup_mode_without_auth(request):
        return

    raise HTTPException(
        status_code=401,
        detail="Settings password required or invalid.",
        headers={AUTH_REQUIRED_HEADER: "true"},
    )


def get_admin_auth_status(request: Optional[Request] = None) -> Dict[str, object]:
    """Return privileged endpoint auth mode without exposing secrets."""
    if wifi_manager.is_ap_mode_active():
        return {
            "token_required": False,
            "login_required": False,
            "authenticated": True,
            "auth_mode": "setup_network",
            "password_label": "Device password",
            "message": "Setup mode is active. Settings login is bypassed on the local setup network.",
            "password_help": "Connect to the printed setup WiFi to continue onboarding.",
            "session_supported": False,
            "remember_supported": False,
        }

    token_set = bool(os.environ.get("PC1_ADMIN_TOKEN", "").strip())
    return {
        "token_required": True,
        "login_required": True,
        "authenticated": is_admin_authenticated(request) if request else False,
        "auth_mode": "admin_token" if token_set else "device_password",
        "password_label": "Admin token" if token_set else "Device password",
        "message": (
            "Enter the configured admin token to access settings."
            if token_set
            else "Enter the device password from the printed setup instructions to access settings."
        ),
        "password_help": (
            "This browser can remember your login with a signed secure session cookie."
        ),
        "session_supported": True,
        "remember_supported": True,
    }
