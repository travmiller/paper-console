"""
WiFi Manager for PC-1
Handles WiFi scanning, connection, and AP mode management.
"""

import subprocess
import json
import re
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
        print(f"[WIFI] Error: {e.stderr}")
        raise


def is_ap_mode_active() -> bool:
    """Check if AP mode is currently active."""
    try:
        result = run_command(['nmcli', 'connection', 'show', '--active'], check=False)
        return 'PC-1-Hotspot' in result.stdout
    except Exception as e:
        print(f"[WIFI] Error checking AP mode: {e}")
        return False


def get_wifi_status() -> Dict:
    """Get current WiFi connection status."""
    try:
        # Check if in AP mode
        if is_ap_mode_active():
            return {
                "connected": False,
                "mode": "ap",
                "ssid": None,
                "ip": "192.168.4.1"
            }
        
        # Check regular WiFi connection
        result = run_command(['nmcli', '-t', '-f', 'ACTIVE,SSID,IP4.ADDRESS', 'connection', 'show', '--active'], check=False)
        
        for line in result.stdout.splitlines():
            if line.startswith('yes:'):
                parts = line.split(':')
                if len(parts) >= 3:
                    ssid = parts[1]
                    ip = parts[2].split('/')[0] if parts[2] else None
                    return {
                        "connected": True,
                        "mode": "client",
                        "ssid": ssid,
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
        
        # Get scan results
        result = run_command(['nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY', 'device', 'wifi', 'list'])
        
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
                        "secure": security != ""
                    })
                    seen_ssids.add(ssid)
        
        # Sort by signal strength
        networks.sort(key=lambda x: x['signal'], reverse=True)
        return networks
        
    except Exception as e:
        print(f"[WIFI] Error scanning networks: {e}")
        return []


def connect_to_wifi(ssid: str, password: Optional[str] = None) -> bool:
    """
    Connect to a WiFi network.
    Creates a new connection profile and activates it.
    """
    try:
        # Delete existing connection with same SSID if it exists
        run_command(['sudo', 'nmcli', 'connection', 'delete', ssid], check=False)
        
        # Stop AP mode if active
        if is_ap_mode_active():
            stop_ap_mode()
        
        # Create and activate new connection
        cmd = [
            'sudo', 'nmcli', 'device', 'wifi', 'connect',
            ssid
        ]
        
        if password:
            cmd.extend(['password', password])
        
        result = run_command(cmd)
        
        print(f"[WIFI] Connected to {ssid}")
        return True
        
    except Exception as e:
        print(f"[WIFI] Failed to connect to {ssid}: {e}")
        return False


def start_ap_mode() -> bool:
    """Start AP mode using the shell script."""
    try:
        script_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'wifi_ap_nmcli.sh')
        result = run_command(['sudo', script_path, 'start'])
        print("[WIFI] AP mode started")
        return True
    except Exception as e:
        print(f"[WIFI] Failed to start AP mode: {e}")
        return False


def stop_ap_mode() -> bool:
    """Stop AP mode."""
    try:
        script_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'wifi_ap_nmcli.sh')
        result = run_command(['sudo', script_path, 'stop'])
        print("[WIFI] AP mode stopped")
        return True
    except Exception as e:
        print(f"[WIFI] Failed to stop AP mode: {e}")
        return False


def forget_wifi(ssid: str) -> bool:
    """Forget a saved WiFi network."""
    try:
        result = run_command(['sudo', 'nmcli', 'connection', 'delete', ssid])
        print(f"[WIFI] Forgot network: {ssid}")
        return True
    except Exception as e:
        print(f"[WIFI] Failed to forget {ssid}: {e}")
        return False

