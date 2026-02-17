"""Shared authentication helpers for privileged API endpoints."""

import ipaddress
import os
from typing import Dict, Optional
from urllib.parse import urlparse

from fastapi import HTTPException, Request


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


def require_admin_access(request: Request):
    """
    Protect privileged endpoints.
    - If PC1_ADMIN_TOKEN is set, require X-PC1-Admin-Token.
    - Otherwise, allow only local/private network requests.
    """
    configured_token = os.environ.get("PC1_ADMIN_TOKEN", "").strip()
    provided_token = request.headers.get("X-PC1-Admin-Token", "").strip()

    if configured_token:
        if provided_token != configured_token:
            raise HTTPException(
                status_code=401,
                detail="Admin token required or invalid.",
                headers={"X-PC1-Auth-Required": "true"},
            )
        return

    client_host = request.client.host if request.client else None
    origin = request.headers.get("origin")
    if not (_host_is_private_or_local(client_host) or _origin_is_local(origin)):
        raise HTTPException(
            status_code=403,
            detail="Privileged endpoint is restricted to local/private networks.",
        )


def get_admin_auth_status() -> Dict[str, object]:
    """Return privileged endpoint auth mode (without exposing secrets)."""
    token_set = bool(os.environ.get("PC1_ADMIN_TOKEN", "").strip())
    return {
        "token_required": token_set,
        "auth_mode": "token" if token_set else "local_network",
        "message": (
            "Admin token required for privileged actions."
            if token_set
            else "Privileged actions are limited to local/private network clients."
        ),
    }
