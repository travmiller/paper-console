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
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=check
        )
        return result
    except subprocess.CalledProcessError as e:
        print(f"[WIFI] Command failed: {' '.join(cmd)}")
        print(f"[WIFI] stderr: {e.stderr}")
        raise


def is_ap_mode_active() -> bool:
    """Check if AP mode is currently active."""
    try:
        result = run_command(['nmcli', 'connection', 'show', '--active'], check=False)
        return 'PC-1-Hotspot' in result.stdout
    except Exception as e:
        print(f"[WIFI] Error checking AP mode: {e}")
        return False


def has_wifi_connection() -> bool:
    """Check if we have an active WiFi connection (not AP mode)."""
    try:
        # Check if wlan0 has an IP address from a WiFi connection
        result = run_command(['nmcli', '-t', '-f', 'DEVICE,TYPE,STATE', 'device'], check=False)
        
        for line in result.stdout.splitlines():
            parts = line.split(':')
            if len(parts) >= 3:
                device, dev_type, state = parts[0], parts[1], parts[2]
                if device == 'wlan0' and dev_type == 'wifi' and state == 'connected':
                    # Check it's not AP mode
                    if not is_ap_mode_active():
                        return True
        return False
    except Exception as e:
        print(f"[WIFI] Error checking WiFi connection: {e}")
        return False


def get_wifi_status() -> Dict:
    """Get current WiFi connection status."""
    try:
        # Check if in AP mode first
        if is_ap_mode_active():
            return {
                "connected": False,
                "mode": "ap",
                "ssid": None,
                "ip": "10.42.0.1"
            }
        
        # Check for active WiFi connection
        result = run_command(['nmcli', '-t', '-f', 'NAME,TYPE,DEVICE', 'connection', 'show', '--active'], check=False)
        
        for line in result.stdout.splitlines():
            parts = line.split(':')
            if len(parts) >= 3:
                name, conn_type, device = parts[0], parts[1], parts[2]
                # Look for WiFi connection on wlan0
                if conn_type == '802-11-wireless' and device == 'wlan0':
                    # Get IP address
                    ip_result = run_command(['hostname', '-I'], check=False)
                    ip = ip_result.stdout.strip().split()[0] if ip_result.stdout.strip() else None
                    
                    return {
                        "connected": True,
                        "mode": "client",
                        "ssid": name,
                        "ip": ip
                    }
        
        return {
            "connected": False,
            "mode": "none",
            "ssid": None,
            "ip": None
        }
    except Exception as e:
        print(f"[WIFI] Error getting status: {e}")
        return {
            "connected": False,
            "mode": "error",
            "ssid": None,
            "ip": None,
            "error": str(e)
        }


def scan_networks() -> List[Dict]:
    """Scan for available WiFi networks."""
    try:
        # Request fresh scan
        run_command(['sudo', 'nmcli', 'device', 'wifi', 'rescan'], check=False)
        
        # Wait a moment for scan to complete
        import time
        time.sleep(2)
        
        # Get scan results
        result = run_command(['nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY', 'device', 'wifi', 'list'], check=False)
        
        networks = []
        seen_ssids = set()
        
        for line in result.stdout.splitlines():
            parts = line.split(':')
            if len(parts) >= 3:
                ssid = parts[0]
                signal = parts[1]
                security = parts[2]
                
                # Skip empty SSIDs and duplicates
                if ssid and ssid not in seen_ssids:
                    networks.append({
                        "ssid": ssid,
                        "signal": int(signal) if signal.isdigit() else 0,
                        "secure": security != "" and security != "--"
                    })
                    seen_ssids.add(ssid)
        
        # Sort by signal strength
        networks.sort(key=lambda x: x['signal'], reverse=True)
        return networks
        
    except Exception as e:
        print(f"[WIFI] Error scanning networks: {e}")
        return []


def connect_to_wifi(ssid: str, password: Optional[str] = None) -> bool:
    """Connect to a WiFi network and save it for auto-connect on boot."""
    try:
        # Delete existing connection with same SSID if it exists
        run_command(['sudo', 'nmcli', 'connection', 'delete', ssid], check=False)
        
        # Create a saved connection profile (this persists across reboots)
        if password:
            # Create WiFi connection with password
            result = run_command([
                'sudo', 'nmcli', 'connection', 'add',
                'type', 'wifi',
                'con-name', ssid,
                'ifname', 'wlan0',
                'ssid', ssid,
                'wifi-sec.key-mgmt', 'wpa-psk',
                'wifi-sec.psk', password
            ], check=False)
        else:
            # Create open WiFi connection
            result = run_command([
                'sudo', 'nmcli', 'connection', 'add',
                'type', 'wifi',
                'con-name', ssid,
                'ifname', 'wlan0',
                'ssid', ssid
            ], check=False)
        
        if result.returncode != 0:
            print(f"[WIFI] Failed to create connection profile: {result.stderr}")
            return False
        
        # Set connection to auto-connect (critical for persistence)
        result = run_command([
            'sudo', 'nmcli', 'connection', 'modify', ssid,
            'connection.autoconnect', 'yes'
        ], check=False)
        
        if result.returncode != 0:
            print(f"[WIFI] Warning: Failed to set autoconnect: {result.stderr}")
        
        # Activate the connection
        result = run_command([
            'sudo', 'nmcli', 'connection', 'up', ssid
        ], check=False)
        
        if result.returncode == 0:
            print(f"[WIFI] Connected to {ssid} (saved for auto-connect)")
            return True
        else:
            print(f"[WIFI] Failed to activate connection: {result.stderr}")
            return False
        
    except Exception as e:
        print(f"[WIFI] Failed to connect to {ssid}: {e}")
        return False


def start_ap_mode() -> bool:
    """Start AP mode using the shell script."""
    try:
        script_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'wifi_ap_nmcli.sh')
        print(f"[WIFI] Starting AP mode with script: {script_path}")
        result = run_command(['sudo', script_path, 'start'], check=False)
        print(f"[WIFI] AP script output: {result.stdout}")
        if result.stderr:
            print(f"[WIFI] AP script stderr: {result.stderr}")
        
        if result.returncode == 0:
            print("[WIFI] AP mode started successfully")
            return True
        else:
            print(f"[WIFI] AP mode failed with code {result.returncode}")
            return False
    except Exception as e:
        print(f"[WIFI] Failed to start AP mode: {e}")
        return False


def stop_ap_mode() -> bool:
    """Stop AP mode."""
    try:
        script_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'wifi_ap_nmcli.sh')
        result = run_command(['sudo', script_path, 'stop'], check=False)
        print("[WIFI] AP mode stopped")
        return True
    except Exception as e:
        print(f"[WIFI] Failed to stop AP mode: {e}")
        return False


def forget_wifi(ssid: str) -> bool:
    """Forget a saved WiFi network."""
    try:
        result = run_command(['sudo', 'nmcli', 'connection', 'delete', ssid], check=False)
        if result.returncode == 0:
            print(f"[WIFI] Forgot network: {ssid}")
            return True
        return False
    except Exception as e:
        print(f"[WIFI] Failed to forget {ssid}: {e}")
        return False
