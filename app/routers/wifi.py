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
        "connecting": True
    }


@router.post("/ap-mode")
async def trigger_ap_mode(background_tasks: BackgroundTasks):
    """Manually trigger AP mode for reconfiguration."""
    
    def delayed_ap_start():
        import time
        print("[WIFI] Waiting 2 seconds before starting AP mode (to allow response to send)...")
        time.sleep(2)
        
        success = wifi_manager.start_ap_mode()
        
        if success:
            print("[WIFI] AP mode started. Waiting for stabilization...")
            time.sleep(5)  # Wait for AP to stabilize
            
            # Print instructions
            try:
                # Import here to avoid circular import
                from app.main import print_setup_instructions_sync
                print_setup_instructions_sync()
            except ImportError:
                print("[ERROR] Could not import print_setup_instructions_sync")
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
