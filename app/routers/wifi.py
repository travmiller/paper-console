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
    from app.hardware import printer
    from app.config import settings

    # Stop AP mode first
    if wifi_manager.is_ap_mode_active():
        wifi_manager.stop_ap_mode()
        # Wait for WiFi adapter to switch back to client mode
        time.sleep(5)

    # Always clean up DNS hijacking before connecting (in case AP mode wasn't detected)
    wifi_manager.cleanup_dns_hijacking()

    # Connect to the new network
    success = wifi_manager.connect_to_wifi(ssid, password)
    feed_lines = getattr(settings, "cutter_feed_lines", 7)

    if success:
        # Wait for IP address
        time.sleep(3)
        # Clean up DNS hijacking again after connection (ensure it's gone)
        wifi_manager.cleanup_dns_hijacking()
        status = wifi_manager.get_wifi_status()
        ip_address = status.get("ip", "unknown")

        printer.feed(1)
        printer.print_text("=" * 32)
        printer.print_text("      WIFI CONNECTED!")
        printer.print_text("=" * 32)
        printer.feed(1)
        printer.print_text(f"Network: {ssid}")
        printer.print_text(f"IP Addr: {ip_address}")
        printer.print_text("")
        printer.print_text("Manage device at:")
        printer.print_text("  http://pc-1.local")
        printer.feed(2)

        if hasattr(printer, "flush_buffer"):
            printer.flush_buffer()

    else:
        # If connection failed, restart AP mode so user can try again
        printer.feed(1)
        printer.print_text("=" * 32)
        printer.print_text("   CONNECTION FAILED")
        printer.print_text("=" * 32)
        printer.feed(1)
        printer.print_text(f"Could not join:")
        printer.print_text(f"{ssid}")
        printer.print_text("")
        printer.print_text("Restoring Setup Mode...")
        printer.feed(2)

        if hasattr(printer, "flush_buffer"):
            printer.flush_buffer()

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
        from app.utils import print_setup_instructions_sync

        # PRINT FIRST to ensure instructions are out before network disruption
        print_setup_instructions_sync()

        # Wait for HTTP response to send before disrupting network
        time.sleep(2)

        wifi_manager.start_ap_mode()

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
