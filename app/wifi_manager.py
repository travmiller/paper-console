"""
WiFi Manager for PC-1
Handles WiFi scanning, connection, and AP mode management.
"""

import subprocess
import os
import logging
import shutil
import socket
import time
from typing import List, Dict, Optional

import app.device_password as device_password

AP_SSID_PREFIX = "PC-1-Setup"


def get_device_suffix() -> str:
    """Return a stable 4-char device suffix from CPU serial when available."""
    try:
        if os.path.exists("/proc/cpuinfo"):
            with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.lower().startswith("serial"):
                        serial = line.split(":", 1)[1].strip()
                        if serial:
                            return serial[-4:].upper()
    except Exception:
        pass
    return "XXXX"


def get_device_password_seed() -> str:
    """Return a stable per-device secret seed for fallback password derivation."""
    return device_password.get_device_password_seed()


def get_ap_ssid() -> str:
    """Get setup AP SSID."""
    return f"{AP_SSID_PREFIX}-{get_device_suffix()}"


def get_ap_password() -> str:
    """Get setup AP password, which now matches the unified Device Password."""
    return device_password.get_device_password()


def generate_wifi_qr_payload(
    ssid: str,
    password: str,
    security: str = "WPA",
    hidden: bool = False,
) -> str:
    """Generate a WiFi QR payload compatible with phone camera scanners."""

    def _escape(value: str) -> str:
        return (
            value.replace("\\", "\\\\")
            .replace(";", "\\;")
            .replace(",", "\\,")
            .replace(":", "\\:")
            .replace('"', '\\"')
        )

    escaped_ssid = _escape(ssid)
    hidden_field = ";H:true" if hidden else ""

    if security.upper() == "NOPASS":
        return f"WIFI:S:{escaped_ssid};T:nopass{hidden_field};;"

    escaped_password = _escape(password)
    return f"WIFI:S:{escaped_ssid};T:{security};P:{escaped_password}{hidden_field};;"


def get_ap_wifi_qr_payload() -> str:
    """Return the QR payload for the setup AP credentials."""
    return generate_wifi_qr_payload(get_ap_ssid(), get_ap_password())


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
            return {
                "connected": False,
                "mode": "ap",
                "ssid": None,
                "ip": "10.42.0.1",
                "ap_ssid": get_ap_ssid(),
                "ap_password": get_ap_password(),
            }

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


def _optional_command(name: str, fallback_paths: List[str]) -> Optional[str]:
    found = shutil.which(name)
    if found:
        return found
    for path in fallback_paths:
        if os.path.exists(path):
            return path
    return None


def check_internet_reachability(
    host: str = "api.open-meteo.com",
    port: int = 443,
    timeout: float = 5.0,
) -> Dict:
    """Best-effort DNS/TCP probe for online modules without making API requests."""
    started_at = time.monotonic()
    result = {
        "host": host,
        "port": port,
        "dns_ok": False,
        "tcp_ok": False,
        "ip": None,
        "latency_ms": None,
        "error": None,
    }

    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        if not addresses:
            result["error"] = "dns returned no addresses"
            return result

        result["dns_ok"] = True
        result["ip"] = addresses[0][4][0]

        with socket.create_connection((host, port), timeout=timeout):
            result["tcp_ok"] = True
            result["latency_ms"] = int((time.monotonic() - started_at) * 1000)
            return result
    except Exception as exc:
        result["latency_ms"] = int((time.monotonic() - started_at) * 1000)
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result


def get_network_diagnostics(probe_internet: bool = True) -> Dict:
    """Collect compact WiFi diagnostics for state-change logging and receipts."""
    diagnostics = {
        "status": get_wifi_status(),
        "wlan0": {},
        "active_wifi": {},
        "ip4": {},
        "wifi_link": {},
        "power_save": {},
        "wifi_radio": None,
        "default_route": None,
        "internet": None,
    }

    try:
        result = run_command(
            ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"],
            check=False,
        )
        for line in result.stdout.splitlines():
            parts = line.split(":")
            if len(parts) >= 4 and parts[0] == "wlan0":
                diagnostics["wlan0"] = {
                    "device": parts[0],
                    "type": parts[1],
                    "state": parts[2],
                    "connection": ":".join(parts[3:]) or None,
                }
                break
    except Exception as exc:
        diagnostics["wlan0"] = {"error": f"{type(exc).__name__}: {exc}"}

    try:
        result = run_command(
            ["nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active"],
            check=False,
        )
        for line in result.stdout.splitlines():
            parts = line.split(":")
            if len(parts) >= 3 and parts[1] == "802-11-wireless" and parts[2] == "wlan0":
                diagnostics["active_wifi"] = {
                    "name": parts[0],
                    "type": parts[1],
                    "device": parts[2],
                }
                break
    except Exception as exc:
        diagnostics["active_wifi"] = {"error": f"{type(exc).__name__}: {exc}"}

    active_wifi_name = (diagnostics.get("active_wifi") or {}).get("name")
    if active_wifi_name:
        try:
            result = run_command(
                [
                    "nmcli",
                    "-g",
                    "802-11-wireless.powersave",
                    "connection",
                    "show",
                    active_wifi_name,
                ],
                check=False,
            )
            diagnostics["power_save"]["networkmanager_profile"] = (
                result.stdout.strip() or None
            )
        except Exception as exc:
            diagnostics["power_save"]["networkmanager_profile"] = (
                f"error: {type(exc).__name__}: {exc}"
            )

    try:
        result = run_command(
            [
                "nmcli",
                "-t",
                "-f",
                "IP4.ADDRESS,IP4.GATEWAY,IP4.DNS",
                "device",
                "show",
                "wlan0",
            ],
            check=False,
        )
        ip4 = {}
        dns = []
        for line in result.stdout.splitlines():
            key, _, value = line.partition(":")
            if key.startswith("IP4.ADDRESS"):
                ip4.setdefault("addresses", []).append(value)
            elif key == "IP4.GATEWAY":
                ip4["gateway"] = value or None
            elif key.startswith("IP4.DNS"):
                dns.append(value)
        if dns:
            ip4["dns"] = dns
        diagnostics["ip4"] = ip4
    except Exception as exc:
        diagnostics["ip4"] = {"error": f"{type(exc).__name__}: {exc}"}

    iw_cmd = _optional_command("iw", ["/usr/sbin/iw", "/sbin/iw"])
    if iw_cmd:
        try:
            result = run_command([iw_cmd, "dev", "wlan0", "link"], check=False)
            link = {}
            for raw_line in result.stdout.splitlines():
                line = raw_line.strip()
                if line.startswith("Connected to "):
                    link["connected_to"] = line.removeprefix("Connected to ").strip()
                elif line.startswith("SSID:"):
                    link["ssid"] = line.split(":", 1)[1].strip()
                elif line.startswith("freq:"):
                    link["freq_mhz"] = line.split(":", 1)[1].strip()
                elif line.startswith("signal:"):
                    link["signal_dbm"] = line.split(":", 1)[1].strip()
                elif line.startswith("tx bitrate:"):
                    link["tx_bitrate"] = line.split(":", 1)[1].strip()
            diagnostics["wifi_link"] = link or {"raw": result.stdout.strip() or None}
        except Exception as exc:
            diagnostics["wifi_link"] = {"error": f"{type(exc).__name__}: {exc}"}

        try:
            result = run_command([iw_cmd, "dev", "wlan0", "get", "power_save"], check=False)
            diagnostics["power_save"]["kernel"] = result.stdout.strip() or None
        except Exception as exc:
            diagnostics["power_save"]["kernel"] = f"error: {type(exc).__name__}: {exc}"
    else:
        diagnostics["wifi_link"] = {"error": "iw unavailable"}
        diagnostics["power_save"]["kernel"] = "iw unavailable"

    try:
        result = run_command(["nmcli", "radio", "wifi"], check=False)
        diagnostics["wifi_radio"] = result.stdout.strip() or None
    except Exception as exc:
        diagnostics["wifi_radio"] = f"error: {type(exc).__name__}: {exc}"

    ip_cmd = _optional_command("ip", ["/usr/sbin/ip", "/sbin/ip"])
    if ip_cmd:
        try:
            result = run_command([ip_cmd, "route", "show", "default"], check=False)
            diagnostics["default_route"] = (
                result.stdout.strip().splitlines()[0] if result.stdout.strip() else None
            )
        except Exception as exc:
            diagnostics["default_route"] = f"error: {type(exc).__name__}: {exc}"
    else:
        diagnostics["default_route"] = "ip command unavailable"

    if probe_internet:
        diagnostics["internet"] = check_internet_reachability()

    return diagnostics


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

        # Disable WiFi power saving on this profile so newly-configured
        # networks don't drop off the LAN after idle. NM values: 2 = disable.
        run_command(
            [
                "sudo",
                "nmcli",
                "connection",
                "modify",
                ssid,
                "802-11-wireless.powersave",
                "2",
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
    logger = logging.getLogger(__name__)
    script_path = os.path.join(
        os.path.dirname(__file__), "..", "scripts", "wifi_ap_nmcli.sh"
    )
    script_path = os.path.abspath(script_path)

    for attempt in range(1, retries + 1):
        try:
            logger.info(
                "Starting AP mode (attempt %s/%s) via %s", attempt, retries, script_path
            )
            # Clean state before retry
            if attempt > 1:
                # Run via /bin/bash to avoid shebang/exec-bit/CRLF issues.
                # Use -n (non-interactive) so we fail fast if sudoers isn't configured.
                run_command(["sudo", "-n", "/bin/bash", script_path, "stop"], check=False)
                import time

                time.sleep(2)

            # Run via /bin/bash to avoid shebang/exec-bit/CRLF issues.
            # Use -n (non-interactive) so we fail fast if sudoers isn't configured.
            result = run_command(
                ["sudo", "-n", "/bin/bash", script_path, "start"], check=False
            )

            # Keep journald quiet in normal operation; details are available when debugging.
            if result.stdout and result.stdout.strip():
                logger.debug("AP script stdout:\n%s", result.stdout.strip())
            if result.stderr and result.stderr.strip():
                logger.debug("AP script stderr:\n%s", result.stderr.strip())
            logger.debug("AP script exit code: %s", result.returncode)

            if result.returncode != 0:
                # Surface only a compact hint at INFO/WARN level.
                stderr_first_line = (result.stderr or "").strip().splitlines()[:1]
                hint = stderr_first_line[0] if stderr_first_line else "(no stderr)"
                logger.warning("AP mode attempt %s failed (exit %s): %s", attempt, result.returncode, hint)

            if result.returncode == 0:
                return True

        except Exception:
            logger.exception("AP mode start attempt failed")

        if attempt < retries:
            import time

            time.sleep(retry_delay)

    return False


def ensure_managed_device_password_store() -> bool:
    """Recreate managed device password storage through the privileged WiFi helper."""
    script_path = os.path.join(
        os.path.dirname(__file__), "..", "scripts", "wifi_ap_nmcli.sh"
    )
    script_path = os.path.abspath(script_path)
    try:
        result = run_command(
            ["sudo", "-n", "/bin/bash", script_path, "ensure-password-store"],
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def ensure_wifi_powersave_disabled() -> bool:
    """Recreate the persistent NetworkManager powersave override via the privileged WiFi helper."""
    script_path = os.path.join(
        os.path.dirname(__file__), "..", "scripts", "wifi_ap_nmcli.sh"
    )
    script_path = os.path.abspath(script_path)
    try:
        result = run_command(
            ["sudo", "-n", "/bin/bash", script_path, "ensure-wifi-powersave-off"],
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def cleanup_dns_hijacking() -> bool:
    """Remove DNS hijacking configuration (captive portal DNS)."""
    try:
        # Remove DNS hijacking config file
        run_command(
            [
                "sudo",
                "-n",
                "/usr/bin/rm",
                "-f",
                "/etc/NetworkManager/dnsmasq.d/captive-portal.conf",
            ],
            check=False,
        )
        # Reload dnsmasq to apply changes
        run_command(
            ["sudo", "-n", "/usr/bin/pkill", "-HUP", "-f", "dnsmasq.*NetworkManager"],
            check=False,
        )
        return True
    except Exception:
        return False


def stop_ap_mode() -> bool:
    """Stop AP mode."""
    try:
        script_path = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "wifi_ap_nmcli.sh"
        )
        script_path = os.path.abspath(script_path)
        # Run via /bin/bash to avoid shebang/exec-bit/CRLF issues.
        # Use -n (non-interactive) so we fail fast if sudoers isn't configured.
        run_command(["sudo", "-n", "/bin/bash", script_path, "stop"], check=False)
        # Also explicitly clean up DNS hijacking in case the script didn't
        cleanup_dns_hijacking()
        return True
    except Exception:
        return False


def get_saved_wifi_profiles() -> List[Dict]:
    """Return saved client WiFi profiles, excluding the setup hotspot profile."""
    profiles = []
    try:
        result = run_command(
            ["nmcli", "-t", "-f", "NAME,UUID,TYPE,AUTOCONNECT", "connection", "show"],
            check=False,
        )
        for line in result.stdout.splitlines():
            parts = line.split(":")
            if len(parts) < 4:
                continue
            name, uuid, conn_type, autoconnect = parts[0], parts[1], parts[2], parts[3]
            if conn_type != "802-11-wireless" or name == "PC-1-Hotspot":
                continue
            profiles.append(
                {
                    "name": name,
                    "uuid": uuid,
                    "autoconnect": autoconnect.lower() in {"yes", "true"},
                }
            )
    except Exception:
        return []

    profiles.sort(key=lambda p: (not p.get("autoconnect", False), p.get("name") or ""))
    return profiles


def _select_saved_wifi_profile(preferred_ssid: Optional[str] = None) -> Optional[Dict]:
    profiles = get_saved_wifi_profiles()
    if not profiles:
        return None

    if preferred_ssid:
        for profile in profiles:
            if profile.get("name") == preferred_ssid:
                return profile

    for profile in profiles:
        if profile.get("autoconnect"):
            return profile

    return profiles[0]


def recover_saved_wifi(action: str, preferred_ssid: Optional[str] = None) -> Dict:
    """
    Nudge NetworkManager toward saved client WiFi without starting setup AP mode.

    action:
      - connection_up: bring up the selected saved profile
      - reapply: reapply wlan0 settings, then bring up the saved profile if needed
      - cycle: disconnect wlan0 briefly, then bring up the saved profile
    """
    profile = _select_saved_wifi_profile(preferred_ssid)
    if not profile:
        return {
            "success": False,
            "action": action,
            "target": None,
            "error": "no saved wifi profiles",
        }

    target = profile["name"]
    commands = []

    def _run(cmd: List[str]) -> subprocess.CompletedProcess:
        commands.append(cmd)
        return run_command(cmd, check=False)

    try:
        _run(["sudo", "nmcli", "radio", "wifi", "on"])

        if action == "connection_up":
            result = _run(["sudo", "nmcli", "connection", "up", target])
        elif action == "reapply":
            result = _run(["sudo", "nmcli", "device", "reapply", "wlan0"])
            status = get_wifi_status()
            if not status.get("connected"):
                result = _run(["sudo", "nmcli", "connection", "up", target])
        elif action == "cycle":
            _run(["sudo", "nmcli", "device", "disconnect", "wlan0"])
            time.sleep(5)
            _run(["sudo", "nmcli", "radio", "wifi", "on"])
            result = _run(["sudo", "nmcli", "connection", "up", target])
        else:
            return {
                "success": False,
                "action": action,
                "target": target,
                "error": f"unknown recovery action: {action}",
            }

        return {
            "success": result.returncode == 0,
            "action": action,
            "target": target,
            "returncode": result.returncode,
            "stdout": (result.stdout or "").strip()[:300],
            "stderr": (result.stderr or "").strip()[:300],
            "commands": [" ".join(cmd) for cmd in commands],
        }
    except Exception as exc:
        return {
            "success": False,
            "action": action,
            "target": target,
            "error": f"{type(exc).__name__}: {exc}",
            "commands": [" ".join(cmd) for cmd in commands],
        }


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
