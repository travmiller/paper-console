"""Pytest suite for PC-1 core behaviors."""

import hashlib
import shlex
import subprocess
from datetime import datetime
from pathlib import Path

import app.device_password as device_password
import app.modules  # noqa: F401 - triggers module auto-registration
import app.utils as utils
import app.wifi_manager as wifi_manager
from app.config import Settings, format_print_datetime
from app.module_registry import get_all_modules, validate_module_config


def test_default_settings_have_eight_channels():
    settings = Settings()
    assert sorted(settings.channels.keys()) == [1, 2, 3, 4, 5, 6, 7, 8]


def test_default_settings_exclude_removed_module_types():
    settings = Settings()
    assert all(
        module.type not in {"ai", "settings_menu"}
        for module in settings.modules.values()
    )


def test_default_settings_use_stable_release_channel():
    settings = Settings()
    assert settings.release_channel == "stable"


def test_print_datetime_includes_configured_time_format():
    dt = datetime(2026, 4, 21, 16, 5)

    assert (
        format_print_datetime(dt, time_format="12h")
        == "Tuesday, April 21, 2026 4:05 PM"
    )
    assert (
        format_print_datetime(dt, time_format="24h")
        == "Tuesday, April 21, 2026 16:05"
    )


def test_default_module_configs_are_registered_and_valid():
    settings = Settings()
    registry = get_all_modules()

    for module in settings.modules.values():
        assert module.type in registry
        validate_module_config(module.type, module.config or {})


def test_registry_excludes_removed_modules():
    registry = get_all_modules()
    assert "settings_menu" not in registry
    assert "ai" not in registry


def test_ap_password_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("PC1_DEVICE_PASSWORD_FILE", str(tmp_path / "device_password"))
    monkeypatch.setenv("PC1_DEVICE_PASSWORD", "my-strong-password")
    assert wifi_manager.get_ap_password() == "my-strong-password"


def test_ap_password_fallback_uses_device_hash(monkeypatch, tmp_path):
    monkeypatch.delenv("PC1_DEVICE_PASSWORD", raising=False)
    monkeypatch.setenv("PC1_DEVICE_PASSWORD_FILE", str(tmp_path / "device_password"))
    monkeypatch.setattr(device_password, "get_device_password_seed", lambda: "seed-value")
    digest = hashlib.sha256(b"seed-value").digest()
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    expected = "".join(alphabet[byte % len(alphabet)] for byte in digest[:8])
    assert wifi_manager.get_ap_password() == expected


def test_wifi_qr_payload_escapes_reserved_characters():
    payload = wifi_manager.generate_wifi_qr_payload(
        ssid='PC-1;Setup:AB"CD',
        password='pa:ss;wo\\rd,1"',
    )

    assert payload == r'WIFI:S:PC-1\;Setup\:AB\"CD;T:WPA;P:pa\:ss\;wo\\rd\,1\";;'


def test_wifi_qr_payload_marks_hidden_networks_only_when_needed():
    visible_payload = wifi_manager.generate_wifi_qr_payload("PC-1-Setup-ABCD", "pass1234")
    hidden_payload = wifi_manager.generate_wifi_qr_payload(
        "PC-1-Setup-ABCD",
        "pass1234",
        hidden=True,
    )

    assert visible_payload == "WIFI:S:PC-1-Setup-ABCD;T:WPA;P:pass1234;;"
    assert hidden_payload == "WIFI:S:PC-1-Setup-ABCD;T:WPA;P:pass1234;H:true;;"


def test_ap_script_device_id_matches_printed_uppercase_suffix(tmp_path):
    cpuinfo = tmp_path / "cpuinfo"
    cpuinfo.write_text("Serial\t\t: 10000000abcd\n", encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "scripts" / "wifi_ap_nmcli.sh"

    result = subprocess.run(
        [
            "bash",
            "-c",
            (
                f"source {shlex.quote(str(script))}; "
                f"get_device_id_from_file {shlex.quote(str(cpuinfo))}"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "ABCD"


class _RecordingPrinter:
    def __init__(self):
        self.captions = []
        self.qr_calls = []

    def clear_hardware_buffer(self):
        return None

    def reset_buffer(self, max_lines: int = 0):  # noqa: ARG002
        return None

    def print_header(self, *args, **kwargs):  # noqa: ARG002
        return None

    def print_line(self):
        return None

    def print_body(self, *args, **kwargs):  # noqa: ARG002
        return None

    def print_bold(self, *args, **kwargs):  # noqa: ARG002
        return None

    def print_caption(self, text: str):
        self.captions.append(text)

    def print_qr(self, **kwargs):
        self.qr_calls.append(kwargs)

    def feed(self, lines: int = 1):  # noqa: ARG002
        return None

    def flush_buffer(self):
        return None


def test_setup_instructions_include_wifi_qr(monkeypatch):
    printer = _RecordingPrinter()

    monkeypatch.setattr(utils, "printer", printer)
    monkeypatch.setattr(utils.wifi_manager, "get_ap_ssid", lambda: "PC-1-Setup-ABCD")
    monkeypatch.setattr(utils.wifi_manager, "get_ap_password", lambda: "pass1234")

    utils.print_setup_instructions_sync()

    assert "  Password: pass1234" in printer.captions
    assert "  Scan to join automatically" in printer.captions
    assert printer.qr_calls == [
        {
            "data": "WIFI:S:PC-1-Setup-ABCD;T:WPA;P:pass1234;;",
            "size": utils.SETUP_WIFI_QR_SIZE,
            "error_correction": utils.SETUP_WIFI_QR_ERROR_CORRECTION,
        }
    ]
