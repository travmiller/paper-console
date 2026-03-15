"""Regression tests for hardware/network failure paths."""

import asyncio
import importlib.util
import subprocess
import sys
import time
import imaplib
import types
from pathlib import Path

import app.main as main_module
import app.wifi_manager as wifi_manager
from app.drivers.printer_serial import PrinterDriver
from app.modules import email_client
from app.modules import quotes as quotes_module
from app.modules import news as news_module
from app.modules import calendar as calendar_module
from app.modules import history as history_module
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


def test_install_update_dependencies_recreates_missing_repo_venv(
    monkeypatch, tmp_path
):
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
    (project_root / "requirements-pi.txt").write_text(
        "-r requirements.txt\nRPi.GPIO\n",
        encoding="utf-8",
    )

    commands = []

    def fake_run(
        cmd, cwd=None, capture_output=False, text=False, timeout=None, check=False
    ):  # noqa: ARG001
        commands.append(cmd)
        if cmd[1:3] == ["-m", "venv"]:
            venv_python = project_root / ".venv" / "bin" / "python"
            venv_python.parent.mkdir(parents=True, exist_ok=True)
            venv_python.write_text("#!/bin/sh\n", encoding="utf-8")
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="", stderr=""
            )
        if cmd[1:4] == ["-m", "pip", "install"]:
            assert cmd[-1] == str(project_root / "requirements-pi.txt")
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="ok", stderr=""
            )
        raise AssertionError(f"Unexpected subprocess command: {cmd}")

    monkeypatch.setattr(
        main_module.shutil,
        "which",
        lambda name: "/usr/bin/python3" if name == "python3" else None,
    )
    monkeypatch.setattr(main_module.subprocess, "run", fake_run)

    result = main_module._install_update_dependencies(project_root, is_dev=False)

    assert result.returncode == 0
    assert any(cmd[1:3] == ["-m", "venv"] for cmd in commands)
    assert any(
        cmd[0] == str(project_root / ".venv" / "bin" / "python")
        and cmd[1:4] == ["-m", "pip", "install"]
        for cmd in commands
    )


def test_install_updates_does_not_restart_service_when_dependency_install_fails(
    monkeypatch, tmp_path
):
    project_root = tmp_path / "project"
    (project_root / "app").mkdir(parents=True)
    (project_root / ".git").mkdir()
    fake_main_path = project_root / "app" / "main.py"
    fake_main_path.write_text("# test stub\n", encoding="utf-8")

    commands = []

    def fake_run(
        cmd, cwd=None, capture_output=False, text=False, timeout=None, check=False
    ):  # noqa: ARG001
        commands.append(cmd)
        if cmd[:3] == ["git", "rev-parse", "--abbrev-ref"]:
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="main\n", stderr=""
            )
        if cmd[:3] == ["git", "pull", "origin"]:
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="Already up to date.\n", stderr=""
            )
        raise AssertionError(f"Unexpected subprocess command: {cmd}")

    monkeypatch.setattr(main_module, "__file__", str(fake_main_path))
    monkeypatch.setattr(main_module.subprocess, "run", fake_run)
    monkeypatch.setattr(
        main_module,
        "_install_update_dependencies",
        lambda project_root, is_dev: subprocess.CompletedProcess(
            args=["python", "-m", "pip"], returncode=1, stdout="", stderr="pip failed"
        ),
    )
    monkeypatch.setattr(main_module.time, "sleep", lambda *_: None)

    result = asyncio.run(main_module.install_updates())

    assert result["success"] is False
    assert "Dependency installation failed" in result["error"]
    assert not any(cmd[:3] == ["sudo", "systemctl", "restart"] for cmd in commands)


def test_validate_production_update_bundle_rejects_missing_web_dist(tmp_path):
    source_dir = tmp_path / "bundle"
    (source_dir / "app").mkdir(parents=True)
    (source_dir / "run.sh").write_text("#!/bin/bash\n", encoding="utf-8")

    try:
        main_module._validate_production_update_bundle(source_dir)
        raise AssertionError("Expected production bundle validation to fail")
    except RuntimeError as exc:
        assert "web/dist/index.html" in str(exc)


def test_install_updates_requires_explicit_production_release_asset(
    monkeypatch, tmp_path
):
    project_root = tmp_path / "project"
    (project_root / "app").mkdir(parents=True)
    fake_main_path = project_root / "app" / "main.py"
    fake_main_path.write_text("# test stub\n", encoding="utf-8")

    class DummyResponse:
        def __init__(self, status_code=200, payload=None):
            self.status_code = status_code
            self._payload = payload or {}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError("http error")

        def json(self):
            return self._payload

    release_payload = {
        "tag_name": "v9.9.9",
        "assets": [{"name": "SHA256SUMS", "browser_download_url": "https://example.test/SHA256SUMS"}],
        "tarball_url": "https://example.test/source.tar.gz",
    }

    def fake_requests_get(url, headers=None, timeout=None, stream=False):  # noqa: ARG001
        assert stream is False
        return DummyResponse(payload=release_payload)

    monkeypatch.setattr(main_module, "__file__", str(fake_main_path))
    monkeypatch.setitem(
        sys.modules,
        "requests",
        types.SimpleNamespace(get=fake_requests_get),
    )

    result = asyncio.run(main_module.install_updates())

    assert result["success"] is False
    assert "required production bundle asset" in result["error"]


def test_quotes_module_does_not_download_when_local_db_is_missing(monkeypatch):
    missing_path = Path("/tmp/pc1-missing-quotes.json")
    monkeypatch.setattr(quotes_module, "_get_quotes_db_path", lambda: missing_path)

    quote = quotes_module.get_random_quote()

    assert quote["quoteText"] == "Offline quotes database is missing."
    assert quote["quoteAuthor"] == "System"


def test_history_module_does_not_download_when_local_db_is_missing(monkeypatch):
    monkeypatch.setattr(history_module, "LOCAL_DB_PATH", Path("/tmp/pc1-missing-history.json"))

    events = history_module.get_events_for_today()

    assert events == ["Offline history database is missing."]


def test_release_build_validates_required_runtime_assets(monkeypatch):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "release_build.py"
    spec = importlib.util.spec_from_file_location("release_build_test_module", script_path)
    release_build = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(release_build)

    monkeypatch.setattr(release_build, "REQUIRED_RUNTIME_PATHS", ["missing/offline.json"])

    try:
        release_build.validate_runtime_assets()
        raise AssertionError("Expected runtime asset validation to fail")
    except FileNotFoundError as exc:
        assert "missing/offline.json" in str(exc)
