"""Printer status must remain a passive snapshot during physical printing."""

import asyncio
import json
import threading
import time

import pytest
from PIL import Image

import app.hardware as hardware
import app.main as main
from testing.test_printer_transport import _FakeSerial, _make_driver


@pytest.fixture(autouse=True)
def idle_printer(monkeypatch):
    monkeypatch.setattr(hardware, "print_in_progress", False)
    monkeypatch.setattr(hardware, "hold_action_in_progress", False)
    monkeypatch.setattr(hardware, "hold_action_started_at", 0.0)
    monkeypatch.setattr(hardware, "printer_uart_reboot_pending", False)


@pytest.mark.parametrize(
    "printing,holding,available,reason",
    [
        (False, False, True, "idle"),
        (True, False, True, "printing"),
        (False, True, True, "hold"),
        (True, True, True, "printing"),
        (False, False, False, "unavailable"),
        (True, False, False, "unavailable"),
    ],
)
def test_status_uses_shared_reservation_state(
    monkeypatch, printing, holding, available, reason
):
    monkeypatch.setattr(main, "_printer_is_available", lambda: available)
    monkeypatch.setattr(hardware, "print_in_progress", printing)
    monkeypatch.setattr(hardware, "hold_action_in_progress", holding)
    monkeypatch.setattr(hardware, "hold_action_started_at", time.time())
    assert main._read_printer_status() == {"ready": reason == "idle", "reason": reason}


def test_stale_hold_expires_using_job_reservation_rules(monkeypatch):
    monkeypatch.setattr(main, "_printer_is_available", lambda: True)
    monkeypatch.setattr(hardware, "hold_action_in_progress", True)
    monkeypatch.setattr(
        hardware, "hold_action_started_at",
        time.time() - hardware.HOLD_ACTION_TIMEOUT_SECONDS - 1,
    )
    assert main._read_printer_status() == {"ready": True, "reason": "idle"}
    assert hardware.hold_action_in_progress is False


def test_uart_reboot_pending_is_unavailable_even_with_mock_fallback(monkeypatch):
    monkeypatch.setattr(main, "_printer_is_available", lambda: True)
    monkeypatch.setattr(hardware, "printer_uart_reboot_pending", True)
    assert main._read_printer_status() == {"ready": False, "reason": "unavailable"}


def test_driver_availability_failure_is_unavailable(monkeypatch):
    class BrokenPrinter:
        def is_available(self):
            raise OSError("serial disconnected")

    monkeypatch.setattr(main, "printer", BrokenPrinter())
    assert main._read_printer_status() == {"ready": False, "reason": "unavailable"}


def test_status_is_public_and_sends_no_serial_commands(monkeypatch):
    serial = _FakeSerial()
    driver = _make_driver(serial)
    monkeypatch.setattr(main, "printer", driver)

    async def scenario():
        messages = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        await main.app(
            {
                "type": "http", "asgi": {"version": "3.0"},
                "http_version": "1.1", "method": "GET", "scheme": "http",
                "path": "/api/printer/status", "query_string": b"", "headers": [],
                "client": ("127.0.0.1", 12345), "server": ("pc-1.local", 80),
            },
            receive, send,
        )
        assert messages[0]["status"] == 200
        body = b"".join(m.get("body", b"") for m in messages[1:])
        assert json.loads(body) == {"ready": True, "reason": "idle"}

    asyncio.run(scenario())
    assert serial.written == b""


def test_status_during_flush_does_not_prevent_remote_cancellation(monkeypatch):
    serial = _FakeSerial()
    driver = _make_driver(serial)
    driver.print_buffer = [("text", "status regression receipt")]
    driver.max_lines = 0
    driver._max_lines_hit = False
    driver.cutter_feed_dots = 0
    driver._render_unified_bitmap = lambda ops: Image.new("1", (384, 24), 1)
    driver.wait_for_idle = lambda: None
    transmitting = threading.Event()
    cancelled_during_transport = []

    def transport(image):
        transmitting.set()
        # The real flush_buffer holds its I/O lock until transport returns.
        cancelled = driver._cancel_event.wait(timeout=2)
        cancelled_during_transport.append(cancelled)
        return {"cancelled": cancelled}

    driver._send_bitmap = transport
    monkeypatch.setattr(main, "printer", driver)
    monkeypatch.setattr(hardware, "printer", driver)
    monkeypatch.setattr(hardware, "print_in_progress", True)

    async def scenario():
        worker = threading.Thread(target=driver.flush_buffer)
        worker.start()
        try:
            assert transmitting.wait(timeout=2)
            assert await main.get_printer_status() == {"ready": False, "reason": "printing"}
            await main.debug_cancel_print()
            # Cancellation is a request; the job stays reserved until cleanup.
            assert await main.get_printer_status() == {"ready": False, "reason": "printing"}
        finally:
            driver.request_cancel()
            worker.join(timeout=3)
        assert not worker.is_alive()
        assert cancelled_during_transport == [True]
        hardware.clear_print_reservation(clear_hold=False)
        assert await main.get_printer_status() == {"ready": True, "reason": "idle"}

    asyncio.run(scenario())
    assert serial.written == b""
