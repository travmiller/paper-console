import json
import threading

import pytest
from PIL import Image

from app.drivers.printer_serial import PrinterDriver, PrinterTransportError


class _FakeSerial:
    def __init__(self, *, max_write=None, fail_after=None, zero_progress=False):
        self.is_open = True
        self.max_write = max_write
        self.fail_after = fail_after
        self.zero_progress = zero_progress
        self.written = bytearray()
        self.write_calls = 0
        self.flush_calls = 0

    def write(self, data):
        self.write_calls += 1
        if self.zero_progress:
            return 0
        if self.fail_after is not None and len(self.written) >= self.fail_after:
            raise OSError("injected serial failure")

        raw = bytes(data)
        limit = len(raw)
        if self.max_write is not None:
            limit = min(limit, self.max_write)
        if self.fail_after is not None:
            limit = min(limit, self.fail_after - len(self.written))
        self.written.extend(raw[:limit])
        return limit

    def flush(self):
        self.flush_calls += 1


class _FakeBusyHandle:
    def __init__(self, values):
        self.values = list(values)
        self.index = 0

    def get_values(self):
        value = self.values[min(self.index, len(self.values) - 1)]
        self.index += 1
        return [value]


def _make_driver(fake_serial):
    driver = PrinterDriver.__new__(PrinterDriver)
    driver.ser = fake_serial
    driver.port = "/dev/fake-printer"
    driver.baudrate = 9600
    driver._io_lock = threading.RLock()
    driver._incident_lock = threading.Lock()
    driver._busy_chip = None
    driver._busy_handle = None
    driver.last_transport_stats = {}
    return driver


def test_send_bitmap_uses_guarded_24_row_strips():
    fake_serial = _FakeSerial()
    driver = _make_driver(fake_serial)
    image = Image.new("1", (384, 50), 1)

    stats = driver._send_bitmap(image)

    expected_heights = [24, 24, 2]
    cursor = 0
    for height in expected_heights:
        payload_size = 48 * height
        assert fake_serial.written[cursor : cursor + 8] == (
            b"\x1d\x76\x30\x00" + bytes((48, 0, height, 0))
        )
        cursor += 8
        assert fake_serial.written[cursor : cursor + payload_size] == b"\x00" * payload_size
        cursor += payload_size
        assert fake_serial.written[cursor : cursor + 4] == b"\x00" * 4
        cursor += 4

    assert cursor == len(fake_serial.written)
    assert fake_serial.flush_calls == 3
    assert stats["strips"] == 3
    assert stats["bytes_sent"] == len(fake_serial.written)
    assert stats["busy_wait_events"] == 0


def test_write_retries_partial_writes_until_every_byte_is_sent():
    fake_serial = _FakeSerial(max_write=7)
    driver = _make_driver(fake_serial)
    payload = bytes(range(100))

    assert driver._write(payload) == len(payload)
    assert bytes(fake_serial.written) == payload
    assert fake_serial.write_calls > 1


def test_write_raises_when_serial_makes_no_progress():
    driver = _make_driver(_FakeSerial(zero_progress=True))

    with pytest.raises(PrinterTransportError, match="no progress"):
        driver._write(b"receipt")


def test_busy_pin_timeout_is_bounded_and_persisted(monkeypatch, tmp_path):
    incident_path = tmp_path / "printer-incidents.log"
    monkeypatch.setenv("PC1_PRINTER_INCIDENT_LOG", str(incident_path))
    monkeypatch.setattr(PrinterDriver, "BUSY_PIN_DEBOUNCE_SECONDS", 0)
    monkeypatch.setattr(PrinterDriver, "BUSY_PIN_POLL_SECONDS", 0)
    monkeypatch.setattr(PrinterDriver, "BUSY_PIN_WAIT_TIMEOUT", 0)

    driver = _make_driver(_FakeSerial())
    driver._busy_handle = _FakeBusyHandle([1])

    stats = driver._send_bitmap(Image.new("1", (384, 1), 1))

    assert stats["busy_pin_timed_out"] is True
    assert stats["busy_wait_events"] == 1
    records = [json.loads(line) for line in incident_path.read_text().splitlines()]
    assert records[0]["event"] == "busy_pin_timeout"


def test_bitmap_failure_is_raised_and_persisted(monkeypatch, tmp_path):
    incident_path = tmp_path / "printer-incidents.log"
    monkeypatch.setenv("PC1_PRINTER_INCIDENT_LOG", str(incident_path))
    driver = _make_driver(_FakeSerial(fail_after=100))

    with pytest.raises(PrinterTransportError, match="Serial write failed"):
        driver._send_bitmap(Image.new("1", (384, 24), 0))

    records = [json.loads(line) for line in incident_path.read_text().splitlines()]
    assert records[-1]["event"] == "bitmap_send_failed"
    assert records[-1]["strip"] == 1
    assert records[-1]["bytes_sent"] == 100
    assert driver.last_transport_stats["failed_strip"] == 1
