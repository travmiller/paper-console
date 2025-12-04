"""
WiFi API Router
Provides endpoints for WiFi management.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import app.wifi_manager as wifi_manager
import asyncio

router = APIRouter(prefix="/api/wifi", tags=["wifi"])


class WiFiConnectRequest(BaseModel):
    ssid: str
    password: Optional[str] = None


def do_wifi_connect(ssid: str, password: Optional[str]):
    """Background task to connect to WiFi."""
    import time

    print(f"[WIFI] Background: Starting connection to {ssid}")

    # Stop AP mode first
    if wifi_manager.is_ap_mode_active():
        print("[WIFI] Background: Stopping AP mode...")
        wifi_manager.stop_ap_mode()
        # Wait for WiFi adapter to switch back to client mode
        print("[WIFI] Background: Waiting for adapter to reset...")
        time.sleep(5)

    # Connect to the new network
    print(f"[WIFI] Background: Connecting to {ssid}...")
    success = wifi_manager.connect_to_wifi(ssid, password)

    if success:
        print(f"[WIFI] Background: Successfully connected to {ssid}")
    else:
        print(f"[WIFI] Background: Failed to connect to {ssid}")
        # If connection failed, restart AP mode so user can try again
        print("[WIFI] Background: Restarting AP mode for retry...")
        time.sleep(2)
        wifi_manager.start_ap_mode()


@router.get("/status")
async def wifi_status():
    """Get current WiFi connection status."""
    return wifi_manager.get_wifi_status()


@router.get("/networks")
async def scan_wifi_networks():
    """Scan for available WiFi networks."""
    networks = wifi_manager.scan_networks()
    return {"networks": networks}


@router.post("/connect")
async def connect_wifi(request: WiFiConnectRequest, background_tasks: BackgroundTasks):
    """
    Connect to a WiFi network.
    This returns immediately and does the connection in the background,
    because the AP mode will be stopped and the client will lose connection.
    """
    # Schedule the connection in the background
    background_tasks.add_task(do_wifi_connect, request.ssid, request.password)

    # Return immediately - the client will lose connection anyway
    return {
        "success": True,
        "message": f"Connecting to {request.ssid}... Device will be available at http://pc-1.local in ~30 seconds",
        "connecting": True,
    }


@router.post("/ap-mode")
async def trigger_ap_mode(background_tasks: BackgroundTasks):
    """Manually trigger AP mode for reconfiguration."""

    def delayed_ap_start():
        import time
        import qrcode
        from app.hardware import printer, _is_raspberry_pi
        from app.config import PRINTER_WIDTH

        print(
            "[WIFI] Waiting 2 seconds before starting AP mode (to allow response to send)..."
        )
        time.sleep(2)

        success = wifi_manager.start_ap_mode()

        if success:
            print("[WIFI] AP mode started. Waiting for stabilization...")
            time.sleep(5)  # Wait for AP to stabilize

            # Print instructions directly here to avoid import loops
            try:
                print("[SYSTEM] Printing Setup Instructions (from wifi module)...")

                # Helper for centering text
                def center(text):
                    padding = max(0, (PRINTER_WIDTH - len(text)) // 2)
                    return " " * padding + text

                printer.print_text(center("PC-1 SETUP MODE"))
                printer.print_text(center("=" * 20))
                printer.feed(1)
                printer.print_text(center("Connect to WiFi:"))

                # Get device ID for SSID
                ssid_suffix = "XXXX"
                try:
                    if _is_raspberry_pi:
                        with open("/proc/cpuinfo", "r") as f:
                            for line in f:
                                if line.startswith("Serial"):
                                    ssid_suffix = line.split(":")[1].strip()[-4:]
                                    break
                except:
                    pass

                ssid = f"PC-1-Setup-{ssid_suffix}"

                printer.print_text(center(ssid))
                printer.print_text(center("Password: setup1234"))
                printer.feed(1)
                printer.print_text(center("Then visit:"))
                printer.print_text(center("http://pc-1.local"))
                printer.print_text(center("OR"))
                printer.print_text(center("http://10.42.0.1"))
                printer.feed(2)

                # Generate QR Code for WiFi
                try:
                    qr_data = f"WIFI:T:WPA;S:{ssid};P:setup1234;H:false;;"
                    qr = qrcode.QRCode(version=1, box_size=1, border=1)
                    qr.add_data(qr_data)
                    qr.make(fit=True)

                    printer.print_text(center("Scan to Connect:"))
                    printer.feed(1)

                    matrix = qr.get_matrix()
                    for row in matrix:
                        line = "".join(["█" if cell else " " for cell in row])
                        printer.print_text(center(line))

                    printer.feed(1)
                    printer.print_text(center("(If QR fails, use manual)"))

                except Exception as qr_e:
                    print(f"[ERROR] QR Generation failed: {qr_e}")

                printer.feed(3)

            except Exception as e:
                print(f"[ERROR] Failed to print instructions: {e}")
        else:
            print("[ERROR] Failed to start AP mode from background task")

    # Add to background tasks so we can return response immediately
    background_tasks.add_task(delayed_ap_start)

    return {"success": True, "message": "AP mode activating in 2 seconds..."}


@router.post("/forget")
async def forget_network(request: WiFiConnectRequest):
    """Forget a saved WiFi network."""
    success = wifi_manager.forget_wifi(request.ssid)

    if success:
        return {"success": True, "message": f"Forgot {request.ssid}"}
    else:
        raise HTTPException(status_code=500, detail="Failed to forget network")
