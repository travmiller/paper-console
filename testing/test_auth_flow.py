"""Tests for settings authentication and session handling."""

from http.cookies import SimpleCookie

from fastapi import Response
from starlette.requests import Request

import app.auth as auth


def _request_with_cookie(cookie_name: str, cookie_value: str, *, origin: str | None = None):
    headers = []
    if cookie_name and cookie_value:
        headers.append((b"cookie", f"{cookie_name}={cookie_value}".encode("utf-8")))
    if origin:
        headers.append((b"origin", origin.encode("utf-8")))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "headers": headers,
            "client": ("127.0.0.1", 12345),
        }
    )


def _extract_cookie_value(set_cookie_header: str, cookie_name: str) -> str:
    jar = SimpleCookie()
    jar.load(set_cookie_header)
    return jar[cookie_name].value


def test_verify_admin_password_uses_device_password_when_no_env_token(monkeypatch):
    monkeypatch.delenv("PC1_ADMIN_TOKEN", raising=False)
    monkeypatch.setattr(auth.wifi_manager, "get_ap_password", lambda: "pc1-test-password")

    assert auth.verify_admin_password("pc1-test-password") is True
    assert auth.verify_admin_password("wrong-password") is False


def test_signed_session_cookie_authenticates_request(monkeypatch):
    monkeypatch.delenv("PC1_ADMIN_TOKEN", raising=False)
    monkeypatch.setattr(auth.wifi_manager, "get_ap_password", lambda: "pc1-test-password")
    monkeypatch.setattr(auth.wifi_manager, "get_device_password_seed", lambda: "seed-1")

    response = Response()
    auth.set_admin_session_cookie(response, remember=True, secure=False)
    cookie_value = _extract_cookie_value(
        response.headers["set-cookie"],
        auth.SESSION_COOKIE_NAME,
    )

    request = _request_with_cookie(auth.SESSION_COOKIE_NAME, cookie_value)
    assert auth.is_admin_authenticated(request) is True


def test_signed_session_cookie_invalidates_when_password_changes(monkeypatch):
    monkeypatch.delenv("PC1_ADMIN_TOKEN", raising=False)
    monkeypatch.setattr(auth.wifi_manager, "get_ap_password", lambda: "pc1-test-password")
    monkeypatch.setattr(auth.wifi_manager, "get_device_password_seed", lambda: "seed-1")

    response = Response()
    auth.set_admin_session_cookie(response, remember=True, secure=False)
    cookie_value = _extract_cookie_value(
        response.headers["set-cookie"],
        auth.SESSION_COOKIE_NAME,
    )

    monkeypatch.setattr(auth.wifi_manager, "get_ap_password", lambda: "pc1-other-password")
    request = _request_with_cookie(auth.SESSION_COOKIE_NAME, cookie_value)
    assert auth.is_admin_authenticated(request) is False


def test_require_admin_access_allows_setup_mode_without_login(monkeypatch):
    monkeypatch.setattr(auth.wifi_manager, "is_ap_mode_active", lambda: True)
    request = _request_with_cookie("", "", origin="http://pc-1.local")

    assert auth.require_admin_access(request) is None


def test_auth_status_reports_device_password_mode(monkeypatch):
    monkeypatch.delenv("PC1_ADMIN_TOKEN", raising=False)
    monkeypatch.setattr(auth.wifi_manager, "is_ap_mode_active", lambda: False)
    monkeypatch.setattr(auth.wifi_manager, "get_ap_password", lambda: "pc1-test-password")

    status = auth.get_admin_auth_status()

    assert status["auth_mode"] == "device_password"
    assert status["login_required"] is True
    assert status["token_required"] is True


def test_auth_status_reports_setup_network_bypass(monkeypatch):
    monkeypatch.setattr(auth.wifi_manager, "is_ap_mode_active", lambda: True)

    status = auth.get_admin_auth_status()

    assert status["auth_mode"] == "setup_network"
    assert status["login_required"] is False
