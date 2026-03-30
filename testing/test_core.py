"""Pytest suite for PC-1 core behaviors."""

import hashlib

import app.device_password as device_password
import app.modules  # noqa: F401 - triggers module auto-registration
import app.wifi_manager as wifi_manager
from app.config import Settings
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
    expected = "pc1-" + hashlib.sha256(b"seed-value").hexdigest()[:10]
    assert wifi_manager.get_ap_password() == expected
