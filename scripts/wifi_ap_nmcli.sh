#!/bin/bash
# WiFi AP Mode Manager using NetworkManager
# Simplified and robust approach for Pi OS Bookworm

# Don't exit on error - we want to continue even if some steps fail
set +e

AP_SSID_PREFIX="PC-1-Setup"
AP_INTERFACE="wlan0"
AP_PASSWORD="${PC1_SETUP_PASSWORD:-}"

# Generate unique SSID suffix from CPU serial
get_device_id() {
    if [ -f /proc/cpuinfo ]; then
        # Return the last 4 hex chars of the CPU serial (no newline).
        # Important: avoid trailing newlines/whitespace in SSID which can make it "disappear" on clients.
        awk -F': ' '/^[Ss]erial[[:space:]]*:/ {s=$2} END { if (length(s) >= 4) print substr(s, length(s)-3); else print "XXXX" }' /proc/cpuinfo | tr -d '\r\n'
    else
        echo "XXXX"
    fi
}

get_ap_ip() {
    # Get the actual IP assigned to wlan0
    ip -4 addr show "$AP_INTERFACE" 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1
}

get_ap_password() {
    local device_id="$1"
    if [ -n "$AP_PASSWORD" ] && [ "${#AP_PASSWORD}" -ge 8 ]; then
        echo "$AP_PASSWORD"
    else
        echo "pc1-${device_id,,}-setup"
    fi
}

start_ap() {
    echo "Starting AP Mode..."
    
    DEVICE_ID=$(get_device_id)
    SSID="${AP_SSID_PREFIX}-${DEVICE_ID}"
    AP_PASS=$(get_ap_password "$DEVICE_ID")
    
    # 1. CLEANUP: Delete any existing hotspot connection to avoid conflicts
    nmcli connection delete "PC-1-Hotspot" 2>/dev/null || true
    
    # Ensure WiFi is actually on and unblocked
    nmcli radio wifi on
    rfkill unblock wifi
    sleep 2
    
    echo "Creating hotspot: $SSID"
    
    # 2. CREATE & START: Force 2.4GHz (band bg) since Pi Zero 2 W doesn't support 5GHz
    # We use exactly what worked in manual testing
    nmcli device wifi hotspot \
        ifname "$AP_INTERFACE" \
        con-name "PC-1-Hotspot" \
        ssid "$SSID" \
        password "$AP_PASS" \
        band bg \
        channel 1
    
    HOTSPOT_RESULT=$?
    
    # Wait for AP to be ready
    sleep 3
    
    # 4. VERIFY & RECOVER
    if [ $HOTSPOT_RESULT -ne 0 ]; then
        echo "Hotspot creation failed, attempting manual activation..."
        # Sometimes creation succeeds but activation fails. Try bringing it up explicitly.
        nmcli connection up "PC-1-Hotspot" 2>/dev/null || true
        sleep 3
    fi
    
    # 5. FINAL CHECK
    if nmcli connection show --active 2>/dev/null | grep -q "PC-1-Hotspot"; then
        AP_IP=$(get_ap_ip)
        echo ""
        echo "========================================"
        echo "AP Mode Active!"
        echo "SSID: $SSID"
        echo "Password: $AP_PASS"
        echo "IP: ${AP_IP:-10.42.0.1}"
        echo "========================================"
        
        # Configure DNS hijacking (Safe version: just address mapping)
        NM_DNSMASQ_DIR="/etc/NetworkManager/dnsmasq.d"
        mkdir -p "$NM_DNSMASQ_DIR"
        echo "address=/#/${AP_IP:-10.42.0.1}" > "$NM_DNSMASQ_DIR/captive-portal.conf"
        # Try to reload DNS, but don't worry if it fails - WiFi is the priority
        pkill -HUP -f "dnsmasq.*NetworkManager" 2>/dev/null || true
        
        return 0
    else
        echo "ERROR: AP Mode failed to start. Current status:"
        nmcli device status
        return 1
    fi
}

stop_ap() {
    echo "Stopping AP Mode..."
    
    # Remove dnsmasq config
    rm -f /etc/NetworkManager/dnsmasq.d/captive-portal.conf 2>/dev/null || true
    
    # Deactivate hotspot
    nmcli connection down "PC-1-Hotspot" 2>/dev/null || true
    nmcli connection delete "PC-1-Hotspot" 2>/dev/null || true
    
    # Reload NM to clear DNS cache
    pkill -HUP -f "dnsmasq.*NetworkManager" 2>/dev/null || true
    
    echo "AP Mode Stopped"
}

status() {
    if nmcli connection show --active 2>/dev/null | grep -q "PC-1-Hotspot"; then
        echo "AP Mode: ACTIVE"
        DEVICE_ID=$(get_device_id)
        AP_PASS=$(get_ap_password "$DEVICE_ID")
        AP_IP=$(get_ap_ip)
        echo "SSID: ${AP_SSID_PREFIX}-${DEVICE_ID}"
        echo "Password: $AP_PASS"
        echo "IP: ${AP_IP:-unknown}"
    else
        echo "AP Mode: INACTIVE"
    fi
}

case "$1" in
    start)
        start_ap
        exit $?
        ;;
    stop)
        stop_ap
        exit $?
        ;;
    status)
        status
        exit 0
        ;;
    *)
        echo "Usage: $0 {start|stop|status}"
        exit 1
        ;;
esac
