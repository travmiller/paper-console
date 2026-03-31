"""Regression tests for snapshot gallery fixture data."""

from datetime import date
import importlib.util
from pathlib import Path

from app.config import CalendarConfig
from app.drivers.printer_mock import PrinterDriver
from app.modules import calendar as calendar_module
from app.modules import email_client
from app.modules import history as history_module
from PIL import Image


def _load_render_all_prints_module():
    script_path = Path(__file__).resolve().parent / "render_all_prints.py"
    spec = importlib.util.spec_from_file_location(
        "render_all_prints_test_module", script_path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_snapshot_defaults_fill_blank_modules():
    render_all_prints = _load_render_all_prints_module()

    history_config = render_all_prints._apply_snapshot_defaults("history", {})
    text_config = render_all_prints._apply_snapshot_defaults(
        "text",
        {"content_doc": {"type": "doc", "content": [{"type": "paragraph"}]}},
    )
    calendar_config = render_all_prints._apply_snapshot_defaults("calendar", {})
    email_config = render_all_prints._apply_snapshot_defaults("email", {})

    assert history_config["reference_date"] == render_all_prints.SNAPSHOT_HISTORY_DATE
    assert render_all_prints.text._doc_has_visible_content(text_config["content_doc"])
    assert "BEGIN:VCALENDAR" in calendar_config["mock_ics_content"]
    assert email_config["mock_messages"][0]["subject"] == "Hi Grandma"


def test_snapshot_email_defaults_override_live_credentials_with_mock():
    render_all_prints = _load_render_all_prints_module()

    email_config = render_all_prints._apply_snapshot_defaults(
        "email",
        {
            "email_user": "real@example.com",
            "email_password": "secret",
            "email_host": "imap.example.com",
        },
    )

    assert email_config["mock_messages"][0]["subject"] == "Hi Grandma"


def test_calendar_receipt_accepts_mock_ics_content(capsys):
    today = date.today()
    ics = "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "BEGIN:VEVENT",
            f"DTSTART:{today.strftime('%Y%m%d')}T103000",
            "SUMMARY:Mock calendar event",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )
    printer = PrinterDriver()

    calendar_module.format_calendar_receipt(
        printer,
        CalendarConfig(mock_ics_content=ics, view_mode="month"),
        "Calendar",
    )

    output = capsys.readouterr().out
    assert "Mock calendar event" in output


def test_fetch_emails_returns_mock_messages_without_imap(monkeypatch):
    called = {"imap": False}

    def _unexpected_imap(*args, **kwargs):  # noqa: ARG001
        called["imap"] = True
        raise AssertionError("IMAP should not be used for mock gallery messages")

    monkeypatch.setattr(email_client.imaplib, "IMAP4_SSL", _unexpected_imap)

    messages = email_client.fetch_emails(
        {
            "mock_messages": [
                {
                    "from": "Mom <mom@example.com>",
                    "subject": "Bring tea to Grandma",
                    "body": "Can you drop off the chamomile tea tonight?",
                }
            ]
        }
    )

    assert called["imap"] is False
    assert messages == [
        {
            "from": "Mom <mom@example.com>",
            "subject": "Bring tea to Grandma",
            "body": "Can you drop off the chamomile tea tonight?",
        }
    ]


def test_history_reference_date_uses_target_day(monkeypatch, capsys):
    captured = {}

    def _fake_events(target_date):
        captured["target_date"] = target_date
        return [
            "1969: First event",
            "1970: Second event",
            "1971: Third event",
        ]

    def _fake_timeline(width, items, item_height, font):  # noqa: ARG001
        captured["items"] = items
        return Image.new("1", (32, 32), 1)

    monkeypatch.setattr(history_module, "get_events_for_date", _fake_events)
    monkeypatch.setattr(history_module, "draw_timeline_image", _fake_timeline)

    history_module.format_history_receipt(
        PrinterDriver(),
        {"reference_date": "1969-07-20", "count": 2},
        "On This Day",
    )

    output = capsys.readouterr().out
    assert captured["target_date"] == date(1969, 7, 20)
    assert captured["items"] == [
        {"year": 1969, "text": "First event"},
        {"year": 1970, "text": "Second event"},
    ]
    assert "July 20, 1969" in output
