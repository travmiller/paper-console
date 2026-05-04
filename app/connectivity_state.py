"""Small persisted connectivity state for diagnostics and System Monitor."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _state_path() -> Path:
    override = os.environ.get("PC1_CONNECTIVITY_STATE_PATH", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1] / ".connectivity_state.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_connectivity_state() -> Dict[str, Any]:
    path = _state_path()
    try:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_connectivity_state(update: Dict[str, Any]) -> Dict[str, Any]:
    path = _state_path()
    state = read_connectivity_state()
    state.update(update)
    state["version"] = 1
    state["updated_at"] = utc_now_iso()

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(temp_path, path)
    return state


def summarize_diagnostics(diagnostics: Dict[str, Any]) -> Dict[str, Any]:
    status = diagnostics.get("status") or {}
    wlan0 = diagnostics.get("wlan0") or {}
    ip4 = diagnostics.get("ip4") or {}
    wifi_link = diagnostics.get("wifi_link") or {}
    power_save = diagnostics.get("power_save") or {}
    internet = diagnostics.get("internet") or {}
    return {
        "mode": status.get("mode"),
        "connected": status.get("connected"),
        "ssid": status.get("ssid"),
        "ip": status.get("ip"),
        "wlan0_state": wlan0.get("state"),
        "wlan0_connection": wlan0.get("connection"),
        "gateway": ip4.get("gateway"),
        "dns": ip4.get("dns") or [],
        "signal_dbm": wifi_link.get("signal_dbm"),
        "freq_mhz": wifi_link.get("freq_mhz"),
        "kernel_powersave": power_save.get("kernel"),
        "nm_powersave": power_save.get("networkmanager_profile"),
        "internet_dns_ok": internet.get("dns_ok"),
        "internet_tcp_ok": internet.get("tcp_ok"),
        "probe_error": internet.get("error"),
    }
