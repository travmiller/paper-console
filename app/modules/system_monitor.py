import shutil
import socket
import os
from datetime import datetime
from typing import Dict, Any
from app.wifi_manager import get_wifi_status
from app.utils import wrap_text
from app.module_registry import register_module
from PIL import Image, ImageDraw


@register_module(
    type_id="system_monitor",
    label="System Monitor",
    description="System status: IP address, disk usage, memory, uptime, CPU temperature",
    icon="desktop",
    offline=True,
    category="utilities",
    config_schema={
        "type": "object",
        "properties": {}
    }
)
def format_system_monitor_receipt(
    printer, config: Dict[str, Any] = None, module_name: str = None
):
    """Prints system status information."""

    # Header
    printer.print_header(module_name or "SYSTEM", icon="desktop")
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
        printer.print_subheader("STORAGE")
        
        width = getattr(printer, "PRINTER_WIDTH_DOTS", 384)
        font = getattr(printer, "_get_font", lambda s: None)("regular")
        img = draw_progress_bar_image(
            width, 
            height=12, 
            value=percent, 
            max_value=100, 
            label=f"{percent:.0f}%", 
            font=font
        )
        printer.print_image(img)
        
        printer.print_body(f"{used_gb}GB / {total_gb}GB")
        printer.print_body(f"{used_gb}GB / {total_gb}GB")
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
            printer.print_subheader("MEMORY")
            
            width = getattr(printer, "PRINTER_WIDTH_DOTS", 384)
            font = getattr(printer, "_get_font", lambda s: None)("regular")
            img = draw_progress_bar_image(
                width, 
                height=12, 
                value=mem_percent, 
                max_value=100, 
                label=f"{mem_percent:.0f}%", 
                font=font
            )
            printer.print_image(img)
            
            printer.print_body(f"{mem_used}MB / {mem_total}MB")
            printer.print_body(f"{mem_used}MB / {mem_total}MB")
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


def draw_progress_bar_image(
    width: int,
    height: int,
    value: float,
    max_value: float,
    label: str,
    font,
) -> Image.Image:
    """Draw a progress bar to an image."""
    
    # Create image
    # Add extra width for label if needed?
    # Original _draw_progress_bar drew label to the right of the bar.
    # It seems it expected 'width' to be just the bar width?
    # Let's check: "label_x = x + width + 4"
    # So if we pass full printer width, the label would be off-screen.
    # We need to calculate bar width to fit label.
    
    label_width = 0
    if label and font:
        try:
            bbox = font.getbbox(label)
            label_width = bbox[2] - bbox[0] if bbox else 0
        except:
             label_width = len(label) * 8
        label_width += 4  # Spacing
        
    bar_width = width - label_width
    
    img = Image.new("1", (width, height), 1)  # White background
    draw = ImageDraw.Draw(img)
    x, y = 0, 0
    
    # Draw border
    draw.rectangle([x, y, x + bar_width - 1, y + height - 1], outline=0, width=2)

    # Calculate fill width
    if max_value > 0:
        fill_width = int((value / max_value) * (bar_width - 4))  # -4 for border
        fill_width = max(0, min(fill_width, bar_width - 4))
    else:
        fill_width = 0

    # Draw filled portion (checkerboard pattern for visual interest)
    if fill_width > 0:
        for px in range(x + 2, x + 2 + fill_width):
            for py in range(y + 2, y + height - 2):
                # Checkerboard pattern
                if ((px - x) + (py - y)) % 4 < 2:
                    draw.point((px, py), fill=0)

    # Draw label if provided
    if label and font:
        # Position label to the right of bar
        label_x = x + bar_width + 4
        # Center vertically
        text_height = getattr(font, "size", 12)
        label_y = y + (height - text_height) // 2
        draw.text((label_x, label_y), label, font=font, fill=0)
        
    return img
