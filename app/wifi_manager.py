"""
WiFi Manager for PC-1
Handles WiFi scanning, connection, and AP mode management.
"""

import subprocess
import os
from typing import List, Dict, Optional


def run_command(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=check
        )
        return result
    except subprocess.CalledProcessError:
        raise


def is_ap_mode_active() -> bool:
    """Check if AP mode is currently active."""
    try:
        result = run_command(["nmcli", "connection", "show", "--active"], check=False)
        return "PC-1-Hotspot" in result.stdout
    except Exception:
        return False


def has_wifi_connection() -> bool:
    """Check if we have an active WiFi connection (not AP mode)."""
    try:
        result = run_command(
            ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device"], check=False
        )

        for line in result.stdout.splitlines():
            parts = line.split(":")
            if len(parts) >= 3:
                device, dev_type, state = parts[0], parts[1], parts[2]
                if device == "wlan0" and dev_type == "wifi" and state == "connected":
                    if not is_ap_mode_active():
                        return True
        return False
    except Exception:
        return False


def get_wifi_status() -> Dict:
    """Get current WiFi connection status."""
    try:
        if is_ap_mode_active():
            return {"connected": False, "mode": "ap", "ssid": None, "ip": "10.42.0.1"}

        result = run_command(
            ["nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active"],
            check=False,
        )

        for line in result.stdout.splitlines():
            parts = line.split(":")
            if len(parts) >= 3:
                name, conn_type, device = parts[0], parts[1], parts[2]
                if conn_type == "802-11-wireless" and device == "wlan0":
                    ip_result = run_command(["hostname", "-I"], check=False)
                    ip = (
                        ip_result.stdout.strip().split()[0]
                        if ip_result.stdout.strip()
                        else None
                    )
                    return {"connected": True, "mode": "client", "ssid": name, "ip": ip}

        return {"connected": False, "mode": "none", "ssid": None, "ip": None}
    except Exception:
        return {"connected": False, "mode": "error", "ssid": None, "ip": None}


def scan_networks() -> List[Dict]:
    """Scan for available WiFi networks."""
    try:
        run_command(["sudo", "nmcli", "device", "wifi", "rescan"], check=False)

        import time

        time.sleep(2)

        result = run_command(
            ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list"],
            check=False,
        )

        networks = []
        seen_ssids = set()

        for line in result.stdout.splitlines():
            parts = line.split(":")
            if len(parts) >= 3:
                ssid = parts[0]
                signal = parts[1]
                security = parts[2]

                if ssid and ssid not in seen_ssids:
                    networks.append(
                        {
                            "ssid": ssid,
                            "signal": int(signal) if signal.isdigit() else 0,
                            "secure": security != "" and security != "--",
                        }
                    )
                    seen_ssids.add(ssid)

        networks.sort(key=lambda x: x["signal"], reverse=True)
        return networks

    except Exception:
        return []


def connect_to_wifi(ssid: str, password: Optional[str] = None) -> bool:
    """Connect to a WiFi network and save it for auto-connect on boot."""
    try:
        # Delete existing connection with same SSID if it exists
        run_command(["sudo", "nmcli", "connection", "delete", ssid], check=False)

        # Create a saved connection profile (this persists across reboots)
        if password:
            result = run_command(
                [
                    "sudo",
                    "nmcli",
                    "connection",
                    "add",
                    "type",
                    "wifi",
                    "con-name",
                    ssid,
                    "ifname",
                    "wlan0",
                    "ssid",
                    ssid,
                    "wifi-sec.key-mgmt",
                    "wpa-psk",
                    "wifi-sec.psk",
                    password,
                ],
                check=False,
            )
        else:
            result = run_command(
                [
                    "sudo",
                    "nmcli",
                    "connection",
                    "add",
                    "type",
                    "wifi",
                    "con-name",
                    ssid,
                    "ifname",
                    "wlan0",
                    "ssid",
                    ssid,
                ],
                check=False,
            )

        if result.returncode != 0:
            return False

        # Set connection to auto-connect
        run_command(
            [
                "sudo",
                "nmcli",
                "connection",
                "modify",
                ssid,
                "connection.autoconnect",
                "yes",
            ],
            check=False,
        )

        # Activate the connection
        result = run_command(["sudo", "nmcli", "connection", "up", ssid], check=False)
        return result.returncode == 0

    except Exception:
        return False


def start_ap_mode(retries: int = 3, retry_delay: float = 5.0) -> bool:
    """Start AP mode using the shell script with retry logic."""
    script_path = os.path.join(
        os.path.dirname(__file__), "..", "scripts", "wifi_ap_nmcli.sh"
    )
    script_path = os.path.abspath(script_path)

    for attempt in range(1, retries + 1):
        try:
            # Clean state before retry
            if attempt > 1:
                run_command(["sudo", script_path, "stop"], check=False)
                import time

                time.sleep(2)

            result = run_command(["sudo", script_path, "start"], check=False)

            if result.returncode == 0:
                return True

        except Exception:
            pass

        if attempt < retries:
            import time

            time.sleep(retry_delay)

    return False


def stop_ap_mode() -> bool:
    """Stop AP mode."""
    try:
        script_path = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "wifi_ap_nmcli.sh"
        )
        script_path = os.path.abspath(script_path)
        run_command(["sudo", script_path, "stop"], check=False)
        return True
    except Exception:
        return False


def forget_wifi(ssid: str) -> bool:
    """Forget a saved WiFi network."""
    try:
        result = run_command(
            ["sudo", "nmcli", "connection", "delete", ssid], check=False
        )
        return result.returncode == 0
    except Exception:
        return False


def forget_all_wifi() -> bool:
    """Forget all saved WiFi networks (for factory reset)."""
    try:
        # Get all saved connections
        result = run_command(
            ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"], check=False
        )

        for line in result.stdout.splitlines():
            parts = line.split(":")
            if len(parts) >= 2:
                name, conn_type = parts[0], parts[1]
                # Delete WiFi connections (but not the AP hotspot)
                if conn_type == "802-11-wireless" and name != "PC-1-Hotspot":
                    run_command(
                        ["sudo", "nmcli", "connection", "delete", name], check=False
                    )

        return True
    except Exception:
        return False
