"""
WiFi API Router
Provides endpoints for WiFi management.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import app.wifi_manager as wifi_manager

router = APIRouter(prefix="/api/wifi", tags=["wifi"])


class WiFiConnectRequest(BaseModel):
    ssid: str
    password: Optional[str] = None


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
async def connect_wifi(request: WiFiConnectRequest):
    """Connect to a WiFi network."""
    success = wifi_manager.connect_to_wifi(request.ssid, request.password)
    
    if success:
        return {"success": True, "message": f"Connected to {request.ssid}"}
    else:
        raise HTTPException(status_code=500, detail="Failed to connect to WiFi")


@router.post("/ap-mode")
async def trigger_ap_mode():
    """Manually trigger AP mode for reconfiguration."""
    success = wifi_manager.start_ap_mode()
    
    if success:
        return {"success": True, "message": "AP mode activated"}
    else:
        raise HTTPException(status_code=500, detail="Failed to start AP mode")


@router.post("/forget")
async def forget_network(request: WiFiConnectRequest):
    """Forget a saved WiFi network."""
    success = wifi_manager.forget_wifi(request.ssid)
    
    if success:
        return {"success": True, "message": f"Forgot {request.ssid}"}
    else:
        raise HTTPException(status_code=500, detail="Failed to forget network")

