"""Canonical Device Password helpers for auth, AP setup, and SSH sync."""

from __future__ import annotations

import hashlib
import os
import platform
from pathlib import Path

DEVICE_PASSWORD_ENV = "PC1_DEVICE_PASSWORD"
DEVICE_PASSWORD_FILE_ENV = "PC1_DEVICE_PASSWORD_FILE"
DEVICE_PASSWORD_FILE_DEFAULT = "/etc/pc1/device_password"
DEVICE_MANAGED_ENV = "PC1_DEVICE_MANAGED"
DEVICE_MANAGED_FILE_ENV = "PC1_DEVICE_MANAGED_FILE"
DEVICE_MANAGED_FILE_DEFAULT = "/etc/pc1/device_managed"
MIN_DEVICE_PASSWORD_LENGTH = 8
DEFAULT_DEVICE_PASSWORD_LENGTH = 8
DEFAULT_DEVICE_PASSWORD_ALPHABET = "abcdefghijklmnopqrstuvwxyz"
TRUTHY_VALUES = {"1", "true", "yes", "on"}


def _env_or_default(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def get_device_password_file_path() -> Path:
    return Path(_env_or_default(DEVICE_PASSWORD_FILE_ENV, DEVICE_PASSWORD_FILE_DEFAULT))


def get_device_managed_marker_path() -> Path:
    return Path(_env_or_default(DEVICE_MANAGED_FILE_ENV, DEVICE_MANAGED_FILE_DEFAULT))


def _read_password_file(path: Path) -> str:
    try:
        if not path.exists() or not path.is_file():
            return ""
        return path.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception:
        return ""


def _read_text_file(path: Path) -> str:
    try:
        if not path.exists() or not path.is_file():
            return ""
        return path.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception:
        return ""


def _looks_like_raspberry_pi() -> bool:
    for path_str in (
        "/proc/device-tree/model",
        "/sys/firmware/devicetree/base/model",
    ):
        model = _read_text_file(Path(path_str)).lower()
        if "raspberry pi" in model:
            return True
    return False


def _looks_like_pc1_host() -> bool:
    if platform.system() != "Linux":
        return False
    if not _looks_like_raspberry_pi():
        return False
    return Path("/etc/systemd/system/pc-1.service").exists()


def _device_password_store_writable() -> bool:
    path = get_device_password_file_path()
    try:
        if path.exists():
            return os.access(path, os.W_OK)
        parent = path.parent
        return parent.exists() and os.access(parent, os.W_OK)
    except Exception:
        return False


def _format_default_device_password(source_bytes: bytes) -> str:
    alphabet = DEFAULT_DEVICE_PASSWORD_ALPHABET
    return "".join(
        alphabet[byte % len(alphabet)]
        for byte in source_bytes[:DEFAULT_DEVICE_PASSWORD_LENGTH]
    )


def _fallback_device_password() -> str:
    digest = hashlib.sha256(
        get_device_password_seed().encode("utf-8", errors="ignore")
    ).digest()
    # Keep the fallback deterministic, lowercase, and letters-only.
    return _format_default_device_password(digest)


def get_device_password_seed() -> str:
    """Return a stable per-device secret seed for fallback password derivation."""
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                    value = handle.read().strip()
                    if value:
                        return value
        except Exception:
            pass

    try:
        if os.path.exists("/proc/cpuinfo"):
            with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    if line.lower().startswith("serial"):
                        serial = line.split(":", 1)[1].strip()
                        if serial:
                            return serial
    except Exception:
        pass

    return os.uname().nodename if hasattr(os, "uname") else "pc1"


def is_device_managed() -> bool:
    explicit = os.environ.get(DEVICE_MANAGED_ENV, "").strip().lower()
    if explicit:
        return explicit in TRUTHY_VALUES
    try:
        if get_device_managed_marker_path().exists():
            return True
    except Exception:
        pass
    return _looks_like_pc1_host()


def get_device_password_source() -> str:
    env_password = os.environ.get(DEVICE_PASSWORD_ENV, "").strip()
    if len(env_password) >= MIN_DEVICE_PASSWORD_LENGTH:
        return "env"

    stored_password = _read_password_file(get_device_password_file_path())
    managed = is_device_managed()
    if len(stored_password) >= MIN_DEVICE_PASSWORD_LENGTH:
        return "managed_file" if managed else "file"

    if managed:
        return "managed_fallback"

    return "fallback"


def get_device_password() -> str:
    env_password = os.environ.get(DEVICE_PASSWORD_ENV, "").strip()
    if len(env_password) >= MIN_DEVICE_PASSWORD_LENGTH:
        return env_password

    stored_password = _read_password_file(get_device_password_file_path())
    if len(stored_password) >= MIN_DEVICE_PASSWORD_LENGTH:
        return stored_password

    return _fallback_device_password()


def can_change_device_password() -> bool:
    return is_device_managed() and _device_password_store_writable()


def set_device_password(new_password: str) -> None:
    normalized = (new_password or "").strip()
    if len(normalized) < MIN_DEVICE_PASSWORD_LENGTH:
        raise ValueError(
            f"Device Password must be at least {MIN_DEVICE_PASSWORD_LENGTH} characters long"
        )
    if not can_change_device_password():
        raise PermissionError(
            "Device Password changes are only available on managed PC-1 devices"
        )

    path = get_device_password_file_path()

    try:
        if path.exists():
            with open(path, "r+", encoding="utf-8") as handle:
                handle.seek(0)
                handle.write(f"{normalized}\n")
                handle.truncate()
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(f"{normalized}\n")
    except Exception as exc:
        raise RuntimeError(f"Failed to persist Device Password: {exc}") from exc
