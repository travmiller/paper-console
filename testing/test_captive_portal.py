"""Regression tests for captive portal probe handling."""

import asyncio

import app.main as main_module


def test_captive_apple_redirects_to_setup_when_ap_mode_active(monkeypatch):
    monkeypatch.setattr(main_module, "_captive_portal_is_active", lambda: True)

    response = asyncio.run(main_module.captive_apple())

    assert response.status_code == 302
    assert response.headers["location"] == main_module.CAPTIVE_PORTAL_REDIRECT_URL
    assert response.headers["cache-control"].startswith("no-store")


def test_captive_android_returns_204_when_not_in_ap_mode(monkeypatch):
    monkeypatch.setattr(main_module, "_captive_portal_is_active", lambda: False)

    response = asyncio.run(main_module.captive_android())

    assert response.status_code == 204
    assert response.body == b""


def test_captive_windows_probe_payloads_match_expected_strings(monkeypatch):
    monkeypatch.setattr(main_module, "_captive_portal_is_active", lambda: False)

    connecttest = asyncio.run(main_module.captive_windows_connect_test())
    ncsi = asyncio.run(main_module.captive_windows_ncsi())

    assert connecttest.body == b"Microsoft Connect Test"
    assert ncsi.body == b"Microsoft NCSI"


def test_captive_networkmanager_probe_returns_expected_success_text(monkeypatch):
    monkeypatch.setattr(main_module, "_captive_portal_is_active", lambda: False)

    response = asyncio.run(main_module.captive_networkmanager())

    assert response.body == b"NetworkManager is online\n"
