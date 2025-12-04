#!/bin/bash
# WiFi AP Mode Manager using NetworkManager
# Simplified and robust approach for Pi OS Bookworm

set -e

AP_SSID_PREFIX="PC-1-Setup"
AP_PASSWORD="setup1234"
AP_INTERFACE="wlan0"

# Generate unique SSID suffix from CPU serial
get_device_id() {
    if [ -f /proc/cpuinfo ]; then
        grep -i serial /proc/cpuinfo | awk '{print $3}' | tail -c 5
    else
        echo "XXXX"
    fi
}

get_ap_ip() {
    # Get the actual IP assigned to wlan0
    ip -4 addr show "$AP_INTERFACE" 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1
}

start_ap() {
    echo "Starting AP Mode..."
    
    DEVICE_ID=$(get_device_id)
    SSID="${AP_SSID_PREFIX}-${DEVICE_ID}"
    
    # Delete any existing hotspot profile
    nmcli connection delete "PC-1-Hotspot" 2>/dev/null || true
    
    # Disconnect from any current WiFi
    nmcli device disconnect "$AP_INTERFACE" 2>/dev/null || true
    
    sleep 2
    
    echo "Creating hotspot: $SSID"
    
    # Use the simple hotspot command - NetworkManager handles DHCP automatically
    nmcli device wifi hotspot \
        ifname "$AP_INTERFACE" \
        con-name "PC-1-Hotspot" \
        ssid "$SSID" \
        password "$AP_PASSWORD"
    
    # Wait for AP to be ready
    sleep 3
    
    # Get the IP that was assigned
    AP_IP=$(get_ap_ip)
    
    echo ""
    echo "========================================"
    echo "AP Mode Active!"
    echo "SSID: $SSID"
    echo "Password: $AP_PASSWORD"
    echo "IP: ${AP_IP:-unknown}"
    echo "Portal: http://${AP_IP:-10.42.0.1}"
    echo "========================================"
}

stop_ap() {
    echo "Stopping AP Mode..."
    
    # Deactivate hotspot
    nmcli connection down "PC-1-Hotspot" 2>/dev/null || true
    nmcli connection delete "PC-1-Hotspot" 2>/dev/null || true
    
    echo "AP Mode Stopped"
}

status() {
    if nmcli connection show --active 2>/dev/null | grep -q "PC-1-Hotspot"; then
        echo "AP Mode: ACTIVE"
        DEVICE_ID=$(get_device_id)
        AP_IP=$(get_ap_ip)
        echo "SSID: ${AP_SSID_PREFIX}-${DEVICE_ID}"
        echo "Password: $AP_PASSWORD"
        echo "IP: ${AP_IP:-unknown}"
    else
        echo "AP Mode: INACTIVE"
    fi
}

case "$1" in
    start)
        start_ap
        ;;
    stop)
        stop_ap
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 {start|stop|status}"
        exit 1
        ;;
esac
