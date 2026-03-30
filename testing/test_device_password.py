"""Tests for unified Device Password storage and fallback behavior."""

from pathlib import Path

import app.device_password as device_password


def test_device_password_reads_managed_file(monkeypatch, tmp_path: Path):
    password_file = tmp_path / "device_password"
    password_file.write_text("managed-pass-123\n", encoding="utf-8")

    monkeypatch.delenv("PC1_DEVICE_PASSWORD", raising=False)
    monkeypatch.setenv("PC1_DEVICE_PASSWORD_FILE", str(password_file))

    assert device_password.get_device_password() == "managed-pass-123"
    assert device_password.get_device_password_source() == "file"


def test_device_password_reports_managed_file_source(monkeypatch, tmp_path: Path):
    password_file = tmp_path / "device_password"
    managed_file = tmp_path / "device_managed"
    password_file.write_text("managed-pass-123\n", encoding="utf-8")
    managed_file.write_text("1\n", encoding="utf-8")

    monkeypatch.delenv("PC1_DEVICE_PASSWORD", raising=False)
    monkeypatch.setenv("PC1_DEVICE_PASSWORD_FILE", str(password_file))
    monkeypatch.setenv("PC1_DEVICE_MANAGED_FILE", str(managed_file))

    assert device_password.is_device_managed() is True
    assert device_password.get_device_password_source() == "managed_file"


def test_set_device_password_updates_managed_file(monkeypatch, tmp_path: Path):
    password_file = tmp_path / "device_password"
    managed_file = tmp_path / "device_managed"
    password_file.write_text("old-password\n", encoding="utf-8")
    managed_file.write_text("1\n", encoding="utf-8")

    monkeypatch.setenv("PC1_DEVICE_PASSWORD_FILE", str(password_file))
    monkeypatch.setenv("PC1_DEVICE_MANAGED_FILE", str(managed_file))
    monkeypatch.delenv("PC1_DEVICE_PASSWORD", raising=False)

    device_password.set_device_password("new-password-456")

    assert password_file.read_text(encoding="utf-8").strip() == "new-password-456"
    assert device_password.get_device_password() == "new-password-456"
