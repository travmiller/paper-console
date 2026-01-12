import shutil
import socket
import os
from datetime import datetime
from typing import Dict, Any
from app.wifi_manager import get_wifi_status
from app.utils import wrap_text


def format_system_monitor_receipt(
    printer, config: Dict[str, Any] = None, module_name: str = None
):
    """Prints system status information."""

    # Header
    printer.print_header(module_name or "SYSTEM")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()

    # Network Info
    try:
        hostname = socket.gethostname()
    except Exception:
        hostname = "unknown"

    wifi_status = get_wifi_status()
    ip_address = wifi_status.get("ip") or "No IP"
    ssid = wifi_status.get("ssid") or "Disconnected"

    printer.print_subheader("NETWORK")
    printer.print_body(f"Host: {hostname}")
    printer.print_body(f"IP:   {ip_address}")
    printer.print_body(f"WiFi: {ssid}")
    printer.print_line()

    # Disk Usage
    try:
        total, used, free = shutil.disk_usage("/")
        total_gb = total // (2**30)
        used_gb = used // (2**30)
        free_gb = free // (2**30)
        percent = (used / total) * 100 if total > 0 else 0

        printer.print_subheader("STORAGE")
        printer.print_body(f"{used_gb}GB / {total_gb}GB ({percent:.1f}%)")
        printer.print_caption(f"{free_gb}GB free")
    except Exception:
        printer.print_caption("Disk info unavailable")

    printer.print_line()

    # Memory & System (Linux only)
    has_system_info = False
    
    try:
        with open("/proc/meminfo", "r") as f:
            meminfo = f.read()

        mem_total = 0
        mem_available = 0
        for line in meminfo.splitlines():
            if line.startswith("MemTotal:"):
                mem_total = int(line.split()[1]) // 1024
            elif line.startswith("MemAvailable:"):
                mem_available = int(line.split()[1]) // 1024

        if mem_total > 0:
            mem_used = mem_total - mem_available
            mem_percent = (mem_used / mem_total) * 100
            printer.print_subheader("MEMORY")
            printer.print_body(f"{mem_used}MB / {mem_total}MB ({mem_percent:.1f}%)")
            has_system_info = True
    except Exception:
        pass

    try:
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.readline().split()[0])
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            printer.print_body(f"Uptime: {hours}h {minutes}m")
            has_system_info = True
    except Exception:
        pass

    try:
        with open("/proc/loadavg", "r") as f:
            loadavg = f.read().split()
            load_1min = loadavg[0]
            printer.print_body(f"Load: {load_1min}")
            has_system_info = True
    except Exception:
        pass

    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp_millidegrees = int(f.read())
            temp_c = temp_millidegrees / 1000
            printer.print_body(f"CPU: {temp_c:.1f}°C")
            has_system_info = True
    except Exception:
        pass

    # Throttle warnings
    try:
        with open("/proc/cpuinfo", "r") as f:
            cpuinfo = f.read()
            for line in cpuinfo.splitlines():
                if line.startswith("Throttled"):
                    parts = line.split(":")
                    if len(parts) == 2:
                        throttled_hex = parts[1].strip()
                        if throttled_hex and throttled_hex != "0x0":
                            flags = int(throttled_hex, 16)
                            warnings = []
                            if flags & 0x1:
                                warnings.append("Undervolt")
                            if flags & 0x2:
                                warnings.append("Capped")
                            if flags & 0x4:
                                warnings.append("Throttled")
                            if warnings:
                                printer.print_bold(f"⚠ {', '.join(warnings)}")
                        break
    except Exception:
        pass

    try:
        with open("/proc/stat", "r") as f:
            for line in f:
                if line.startswith("btime"):
                    boot_timestamp = int(line.split()[1])
                    boot_time = datetime.fromtimestamp(boot_timestamp)
                    boot_str = boot_time.strftime("%b %d %H:%M")
                    printer.print_caption(f"Boot: {boot_str}")
                    break
    except Exception:
        pass

    printer.print_line()
