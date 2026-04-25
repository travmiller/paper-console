import types

from app.drivers.printer_serial import PrinterDriver


class _FakeBusyHandle:
    def __init__(self, values):
        self.values = list(values)
        self.index = 0

    def get_values(self):
        value = self.values[min(self.index, len(self.values) - 1)]
        self.index += 1
        return [value]

    def close(self):
        return None


def _make_driver():
    driver = PrinterDriver.__new__(PrinterDriver)
    driver.ser = types.SimpleNamespace(is_open=True)
    driver._busy_chip = None
    driver._busy_handle = None
    driver._io_lock = None
    return driver


def test_read_busy_pin_returns_gpio_level():
    driver = _make_driver()
    driver._busy_handle = _FakeBusyHandle([1])
    assert driver._read_busy_pin() == 1

    driver._busy_handle = _FakeBusyHandle([0])
    assert driver._read_busy_pin() == 0


def test_wait_for_idle_prefers_busy_pin(monkeypatch):
    driver = _make_driver()
    driver._busy_handle = _FakeBusyHandle([1, 1, 0, 0])
    driver.is_printer_busy = lambda: True

    current = {"t": 0.0}

    def fake_time():
        return current["t"]

    def fake_sleep(seconds):
        current["t"] += seconds

    monkeypatch.setattr("app.drivers.printer_serial.time.time", fake_time)
    monkeypatch.setattr("app.drivers.printer_serial.time.sleep", fake_sleep)

    driver.wait_for_idle(timeout=2.0, quiet_period=0.2)

    assert current["t"] >= 0.4
