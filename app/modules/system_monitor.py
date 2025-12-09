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
    printer.print_header((module_name or "SYSTEM MONITOR").upper())
    printer.print_text(datetime.now().strftime("%A, %b %d"))
    printer.print_line()

    # Network Info
    try:
        hostname = socket.gethostname()
    except Exception:
        hostname = "unknown"

    # Get WiFi info
    wifi_status = get_wifi_status()
    ip_address = wifi_status.get("ip") or "No IP"
    ssid = wifi_status.get("ssid") or "Disconnected"

    # Wrap potentially long strings (hostname, IP, SSID can be long)
    hostname_text = f"Host: {hostname}"
    wrapped_hostname = wrap_text(hostname_text, width=printer.width, indent=0)
    for line in wrapped_hostname:
        printer.print_text(line)

    ip_text = f"IP:   {ip_address}"
    wrapped_ip = wrap_text(ip_text, width=printer.width, indent=0)
    for line in wrapped_ip:
        printer.print_text(line)

    ssid_text = f"WiFi: {ssid}"
    wrapped_ssid = wrap_text(ssid_text, width=printer.width, indent=0)
    for line in wrapped_ssid:
        printer.print_text(line)

    printer.print_line()

    # Disk Usage
    try:
        total, used, free = shutil.disk_usage("/")
        # Convert to GB
        total_gb = total // (2**30)
        used_gb = used // (2**30)
        free_gb = free // (2**30)
        percent = (used / total) * 100 if total > 0 else 0

        printer.print_text("DISK USAGE:")
        disk_text = f"Used: {used_gb}GB / {total_gb}GB ({percent:.1f}%)"
        wrapped_disk = wrap_text(disk_text, width=printer.width, indent=0)
        for line in wrapped_disk:
            printer.print_text(line)

        printer.print_text(f"Free: {free_gb}GB")
    except Exception:
        printer.print_text("Disk usage unavailable")

    printer.print_line()

    # Memory & Uptime
    try:
        # Memory from /proc/meminfo (Linux only)
        with open("/proc/meminfo", "r") as f:
            meminfo = f.read()

        # Parse MemTotal and MemAvailable
        mem_total = 0
        mem_available = 0
        for line in meminfo.splitlines():
            if line.startswith("MemTotal:"):
                mem_total = int(line.split()[1]) // 1024  # MB
            elif line.startswith("MemAvailable:"):
                mem_available = int(line.split()[1]) // 1024  # MB

        if mem_total > 0:
            mem_used = mem_total - mem_available
            mem_percent = (mem_used / mem_total) * 100

            printer.print_text("MEMORY:")
            printer.print_text(f"{mem_used}MB / {mem_total}MB ({mem_percent:.1f}%)")
    except Exception:
        pass

    try:
        # Uptime
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.readline().split()[0])
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            printer.print_text(f"Uptime: {hours}h {minutes}m")
    except Exception:
        pass

    # Load Average
    try:
        with open("/proc/loadavg", "r") as f:
            loadavg = f.read().split()
            load_1min = loadavg[0]
            printer.print_text(f"Load: {load_1min}")
    except Exception:
        pass

    # CPU Temp (Raspberry Pi specific)
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp_millidegrees = int(f.read())
            temp_c = temp_millidegrees / 1000
            printer.print_text(f"CPU Temp: {temp_c:.1f}C")
    except Exception:
        pass

    # Raspberry Pi Throttle Status
    try:
        with open("/proc/cpuinfo", "r") as f:
            cpuinfo = f.read()
            # Check for throttling flags
            throttled = None
            for line in cpuinfo.splitlines():
                if line.startswith("Throttled"):
                    # Format: "Throttled: 0x50000" or "Throttled: 0x0"
                    parts = line.split(":")
                    if len(parts) == 2:
                        throttled_hex = parts[1].strip()
                        if throttled_hex and throttled_hex != "0x0":
                            # Parse hex flags
                            flags = int(throttled_hex, 16)
                            warnings = []
                            if flags & 0x1:
                                warnings.append("Undervoltage")
                            if flags & 0x2:
                                warnings.append("Freq capped")
                            if flags & 0x4:
                                warnings.append("Throttled")
                            if flags & 0x80000:
                                warnings.append("Soft temp")

                            if warnings:
                                printer.print_text(f"WARNING: {', '.join(warnings)}")
                            else:
                                # Unknown flags, show hex
                                printer.print_text(f"Throttle: {throttled_hex}")
                        break
    except Exception:
        pass

    # Last Boot Time
    try:
        with open("/proc/stat", "r") as f:
            for line in f:
                if line.startswith("btime"):
                    boot_timestamp = int(line.split()[1])
                    boot_time = datetime.fromtimestamp(boot_timestamp)
                    boot_str = boot_time.strftime("%b %d %H:%M")
                    printer.print_text(f"Boot: {boot_str}")
                    break
    except Exception:
        pass

    printer.print_line()
    printer.feed(1)
