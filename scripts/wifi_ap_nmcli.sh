#!/bin/bash
# WiFi AP Mode Manager using NetworkManager (stable approach for Bookworm)

set -e

AP_SSID_PREFIX="PC-1-Setup"
AP_PASSWORD="setup1234"
AP_INTERFACE="wlan0"
AP_IP="192.168.4.1"
AP_GATEWAY="192.168.4.1"

# Generate unique SSID suffix from CPU serial
get_device_id() {
    if [ -f /proc/cpuinfo ]; then
        grep -i serial /proc/cpuinfo | awk '{print $3}' | tail -c 5
    else
        echo "XXXX"
    fi
}

start_ap() {
    echo "Starting AP Mode..."
    
    DEVICE_ID=$(get_device_id)
    SSID="${AP_SSID_PREFIX}-${DEVICE_ID}"
    
    # Check if hotspot already exists
    if nmcli connection show "PC-1-Hotspot" &>/dev/null; then
        echo "Hotspot profile exists, deleting and recreating..."
        nmcli connection delete "PC-1-Hotspot"
    fi
    
    echo "Creating new hotspot profile..."
    # Create AP using NetworkManager with specific IP
    nmcli connection add type wifi ifname "$AP_INTERFACE" \
        con-name "PC-1-Hotspot" \
        autoconnect no \
        ssid "$SSID" \
        mode ap \
        ipv4.method shared \
        ipv4.addresses "$AP_IP/24" \
        ipv6.method ignore \
        wifi-sec.key-mgmt wpa-psk \
        wifi-sec.psk "$AP_PASSWORD"
    
    # Activate the hotspot
    nmcli connection up "PC-1-Hotspot"
    
    # Wait for AP to be ready
    sleep 3
    
    # Start captive portal (redirect all DNS to ourselves)
    start_captive_portal
    
    echo "AP Mode Active: $SSID"
    echo "Password: $AP_PASSWORD"
    echo "Portal: http://$AP_IP"
}

stop_ap() {
    echo "Stopping AP Mode..."
    
    # Stop captive portal
    stop_captive_portal
    
    # Deactivate hotspot
    if nmcli connection show "PC-1-Hotspot" &>/dev/null; then
        nmcli connection down "PC-1-Hotspot" 2>/dev/null || true
    fi
    
    echo "AP Mode Stopped"
}

start_captive_portal() {
    # Get the actual IP of wlan0 (in case it differs)
    ACTUAL_IP=$(ip -4 addr show "$AP_INTERFACE" | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1)
    PORTAL_IP="${ACTUAL_IP:-$AP_IP}"
    
    # Create dnsmasq config for captive portal
    # This makes ANY domain resolve to our IP
    cat > /tmp/dnsmasq-captive.conf <<EOF
interface=$AP_INTERFACE
bind-interfaces
address=/#/$PORTAL_IP
EOF
    
    # Start dnsmasq for captive portal DNS
    dnsmasq -C /tmp/dnsmasq-captive.conf -k &
    echo $! > /tmp/dnsmasq-captive.pid
    
    echo "Captive portal started (redirecting to $PORTAL_IP)"
}

stop_captive_portal() {
    if [ -f /tmp/dnsmasq-captive.pid ]; then
        kill $(cat /tmp/dnsmasq-captive.pid) 2>/dev/null || true
        rm -f /tmp/dnsmasq-captive.pid
    fi
    rm -f /tmp/dnsmasq-captive.conf
    echo "Captive portal stopped"
}

status() {
    if nmcli connection show --active | grep -q "PC-1-Hotspot"; then
        echo "AP Mode: ACTIVE"
        DEVICE_ID=$(get_device_id)
        echo "SSID: ${AP_SSID_PREFIX}-${DEVICE_ID}"
        echo "Password: $AP_PASSWORD"
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

