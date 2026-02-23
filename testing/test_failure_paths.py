"""Regression tests for hardware/network failure paths."""

import subprocess
import time
import imaplib

import app.wifi_manager as wifi_manager
from app.drivers.printer_serial import PrinterDriver
from app.modules import email_client
from app.modules import news as news_module
from app.modules import calendar as calendar_module
from app import factory_reset as factory_reset_module
from datetime import datetime, timedelta, timezone


def _completed(returncode: int = 0, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(
        args=["nmcli"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_connect_to_wifi_returns_false_when_profile_creation_fails(monkeypatch):
    def fake_run_command(cmd, check=False):  # noqa: ARG001
        if "add" in cmd:
            return _completed(returncode=1, stderr="failed to create profile")
        return _completed(returncode=0)

    monkeypatch.setattr(wifi_manager, "run_command", fake_run_command)

    assert wifi_manager.connect_to_wifi("TestSSID", "password123") is False


def test_start_ap_mode_retries_then_succeeds(monkeypatch):
    start_attempts = {"count": 0}

    def fake_run_command(cmd, check=False):  # noqa: ARG001
        if cmd[-1] == "start":
            start_attempts["count"] += 1
            if start_attempts["count"] < 2:
                return _completed(returncode=1, stderr="first start failed")
        return _completed(returncode=0)

    monkeypatch.setattr(wifi_manager, "run_command", fake_run_command)
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    assert wifi_manager.start_ap_mode(retries=3, retry_delay=0) is True
    assert start_attempts["count"] == 2


def test_start_ap_mode_returns_false_after_all_retries(monkeypatch):
    def fake_run_command(cmd, check=False):  # noqa: ARG001
        if cmd[-1] == "start":
            return _completed(returncode=1, stderr="all starts failed")
        return _completed(returncode=0)

    monkeypatch.setattr(wifi_manager, "run_command", fake_run_command)
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    assert wifi_manager.start_ap_mode(retries=2, retry_delay=0) is False


def test_printer_driver_handles_serial_init_failure(monkeypatch):
    import serial

    monkeypatch.setattr(
        PrinterDriver,
        "_load_font_family",
        lambda self: {"regular": None, "bold": None},
    )
    monkeypatch.setattr(
        serial,
        "Serial",
        lambda *args, **kwargs: (_ for _ in ()).throw(serial.SerialException("no port")),
    )

    driver = PrinterDriver(port="COM99")
    assert driver.ser is None


def test_fetch_emails_sets_auth_failed_on_imap_auth_error(monkeypatch):
    config = {
        "email_service": "Custom",
        "email_user": "user@example.com",
        "email_password": "bad-password",
        "email_host": "imap.example.com",
        "email_port": 993,
        "email_use_ssl": True,
    }

    def fake_imap4_ssl(*args, **kwargs):  # noqa: ARG001
        raise imaplib.IMAP4.error("AUTHENTICATIONFAILED")

    monkeypatch.setattr(imaplib, "IMAP4_SSL", fake_imap4_ssl)

    messages = email_client.fetch_emails(config)
    assert messages == []
    assert email_client._LAST_FETCH_ERROR == "auth_failed"


def test_news_module_uses_configurable_country_and_page_size(monkeypatch):
    captured = {}

    class DummyResponse:
        def json(self):
            return {"status": "ok", "articles": []}

    def fake_get(url, params=None, timeout=0):  # noqa: ARG001
        captured["params"] = params or {}
        return DummyResponse()

    monkeypatch.setattr(news_module.requests, "get", fake_get)
    news_module.get_newsapi_articles(
        {
            "news_api_key": "abc123",
            "country": "ca",
            "page_size": 7,
        }
    )

    assert captured["params"]["country"] == "ca"
    assert captured["params"]["pageSize"] == 7


def test_calendar_rrule_respects_exdate_in_window():
    now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = now + timedelta(hours=9)
    skip = start + timedelta(days=1)

    dt_fmt = "%Y%m%dT%H%M%SZ"
    ics = "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "BEGIN:VEVENT",
            f"DTSTART:{start.strftime(dt_fmt)}",
            "RRULE:FREQ=DAILY;COUNT=3",
            f"EXDATE:{skip.strftime(dt_fmt)}",
            "SUMMARY:Recurring test event",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )

    events = calendar_module.parse_events(ics, days_to_show=4, timezone_str="UTC")
    event_days = set(events.keys())

    assert start.date() in event_days
    assert skip.date() not in event_days
    assert (start + timedelta(days=2)).date() in event_days


def test_factory_reset_reports_reboot_failure(monkeypatch):
    deleted = []

    monkeypatch.setattr(factory_reset_module.os.path, "exists", lambda _p: True)
    monkeypatch.setattr(factory_reset_module.os, "remove", lambda p: deleted.append(p))
    monkeypatch.setattr(
        factory_reset_module.wifi_manager, "forget_all_wifi", lambda: True
    )
    monkeypatch.setattr(
        factory_reset_module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=["sudo", "reboot"], returncode=1, stdout="", stderr="sudo denied"
        ),
    )

    result = factory_reset_module.perform_factory_reset()

    assert result["config_cleared"] is True
    assert result["wifi_cleared"] is True
    assert result["reboot_requested"] is False
    assert any("Reboot command failed" in e for e in result["errors"])
    assert len(deleted) == 3


def test_factory_reset_success_path(monkeypatch):
    monkeypatch.setattr(factory_reset_module.os.path, "exists", lambda _p: False)
    monkeypatch.setattr(
        factory_reset_module.wifi_manager, "forget_all_wifi", lambda: True
    )
    monkeypatch.setattr(
        factory_reset_module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=["sudo", "reboot"], returncode=0, stdout="", stderr=""
        ),
    )

    result = factory_reset_module.perform_factory_reset()

    assert result["config_cleared"] is True
    assert result["wifi_cleared"] is True
    assert result["reboot_requested"] is True
    assert result["errors"] == []
