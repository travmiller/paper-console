#!/bin/bash
# WiFi AP Mode Manager using NetworkManager
# Simplified and robust approach for Pi OS Bookworm

# Don't exit on error - we want to continue even if some steps fail
set +e

AP_SSID_PREFIX="PC-1-Setup"
AP_INTERFACE="wlan0"
DEVICE_PASSWORD="${PC1_DEVICE_PASSWORD:-}"
DEVICE_PASSWORD_FILE="${PC1_DEVICE_PASSWORD_FILE:-/etc/pc1/device_password}"
DEVICE_MANAGED_FILE="${PC1_DEVICE_MANAGED_FILE:-/etc/pc1/device_managed}"
DEVICE_CONFIG_DIR="$(dirname "$DEVICE_PASSWORD_FILE")"
NM_DNSMASQ_DIR="${PC1_NM_DNSMASQ_DIR:-/etc/NetworkManager/dnsmasq.d}"
NM_CONF_DIR="${PC1_NM_CONF_DIR:-/etc/NetworkManager/conf.d}"
WIFI_POWERSAVE_CONF_FILE="${PC1_WIFI_POWERSAVE_CONF_FILE:-$NM_CONF_DIR/10-wifi-powersave-off.conf}"
CPUINFO_FILE="${PC1_CPUINFO_FILE:-/proc/cpuinfo}"
BOOT_CONFIG_FILE="${PC1_BOOT_CONFIG_FILE:-}"
BOOT_CMDLINE_FILE="${PC1_BOOT_CMDLINE_FILE:-}"
PRINTER_UART_BACKUP_DIR="${PC1_PRINTER_UART_BACKUP_DIR:-/etc/pc1/backups}"
PRINTER_UART_STATE_FILE="${PC1_PRINTER_UART_STATE_FILE:-/etc/pc1/printer-uart-reboot-boot-id}"
PRINTER_UART_SETUP_MARKER="${PC1_PRINTER_UART_SETUP_MARKER:-/run/pc1-setup-in-progress}"
SERIAL0_PATH="${PC1_SERIAL0_PATH:-/dev/serial0}"
BOOT_ID_FILE="${PC1_BOOT_ID_FILE:-/proc/sys/kernel/random/boot_id}"
SYSTEMCTL_BIN="${PC1_SYSTEMCTL_BIN:-/usr/bin/systemctl}"
SYSTEMD_RUN_BIN="${PC1_SYSTEMD_RUN_BIN:-/usr/bin/systemd-run}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"

PRINTER_UART_CHANGED=0
PRINTER_UART_REBOOT_REQUIRED=0
PRINTER_UART_REBOOT_PENDING=0

# Generate unique SSID suffix from CPU serial.
get_device_id_from_file() {
    local cpuinfo_file="$1"
    if [ -f "$cpuinfo_file" ]; then
        # Return the last 4 hex chars of the CPU serial (no newline).
        # Match app.wifi_manager.get_device_suffix(), which uppercases the
        # printed setup SSID and QR payload.
        # Important: avoid trailing newlines/whitespace in SSID which can make it "disappear" on clients.
        awk -F': ' '/^[Ss]erial[[:space:]]*:/ {s=$2} END { if (length(s) >= 4) print substr(s, length(s)-3); else print "XXXX" }' "$cpuinfo_file" | tr -d '\r\n' | tr '[:lower:]' '[:upper:]'
    else
        echo "XXXX"
    fi
}

get_device_id() {
    get_device_id_from_file "$CPUINFO_FILE"
}

get_invoking_user() {
    local username="${SUDO_USER:-${USER:-}}"
    if [ -n "$username" ]; then
        echo "$username"
        return
    fi
    id -un
}

get_ap_ip() {
    # Get the actual IP assigned to wlan0
    ip -4 addr show "$AP_INTERFACE" 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1
}

get_password_seed() {
    if [ -f /etc/machine-id ]; then
        tr -d '\r\n' < /etc/machine-id
        return
    fi
    if [ -f /var/lib/dbus/machine-id ]; then
        tr -d '\r\n' < /var/lib/dbus/machine-id
        return
    fi
    if [ -f /proc/cpuinfo ]; then
        local serial
        serial=$(awk -F': ' '/^[Ss]erial[[:space:]]*:/ {s=$2} END {print s}' /proc/cpuinfo | tr -d '\r\n')
        if [ -n "$serial" ]; then
            echo "$serial"
            return
        fi
    fi
    hostname
}

get_device_password() {
    local seed
    if [ -n "$DEVICE_PASSWORD" ] && [ "${#DEVICE_PASSWORD}" -ge 8 ]; then
        echo "$DEVICE_PASSWORD"
        return
    fi
    if [ -f "$DEVICE_PASSWORD_FILE" ]; then
        local stored_password
        stored_password=$(tr -d '\r\n' < "$DEVICE_PASSWORD_FILE")
        if [ "${#stored_password}" -ge 8 ]; then
            echo "$stored_password"
            return
        fi
    fi
    seed=$(get_password_seed)
    PYTHONPATH="$PROJECT_DIR" python3 - "$seed" <<'PY'
import sys

from app.device_password import derive_device_password_from_seed

print(derive_device_password_from_seed(sys.argv[1]))
PY
}

start_ap() {
    echo "Starting AP Mode..."
    
    DEVICE_ID=$(get_device_id)
    SSID="${AP_SSID_PREFIX}-${DEVICE_ID}"
    AP_PASS=$(get_device_password)
    
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
        
        # Configure DNS hijacking for captive portal detection.
        # The explicit listen/interface binding helps ensure NM's dnsmasq
        # actually answers on the hotspot network for portal probe domains.
        mkdir -p "$NM_DNSMASQ_DIR"
        cat > "$NM_DNSMASQ_DIR/captive-portal.conf" <<EOF
address=/#/${AP_IP:-10.42.0.1}
listen-address=${AP_IP:-10.42.0.1}
interface=${AP_INTERFACE}
bind-interfaces
EOF
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
    rm -f "$NM_DNSMASQ_DIR/captive-portal.conf" 2>/dev/null || true
    
    # Deactivate hotspot
    nmcli connection down "PC-1-Hotspot" 2>/dev/null || true
    nmcli connection delete "PC-1-Hotspot" 2>/dev/null || true
    
    # Reload NM to clear DNS cache
    pkill -HUP -f "dnsmasq.*NetworkManager" 2>/dev/null || true
    
    echo "AP Mode Stopped"
}

ensure_password_store() {
    local owner_user
    owner_user=$(get_invoking_user)

    mkdir -p "$DEVICE_CONFIG_DIR" || return 1
    chown "root:${owner_user}" "$DEVICE_CONFIG_DIR" || return 1
    chmod 0770 "$DEVICE_CONFIG_DIR" || return 1

    touch "$DEVICE_PASSWORD_FILE" "$DEVICE_MANAGED_FILE" || return 1
    chown "root:${owner_user}" "$DEVICE_PASSWORD_FILE" "$DEVICE_MANAGED_FILE" || return 1
    chmod 0660 "$DEVICE_PASSWORD_FILE" || return 1
    chmod 0640 "$DEVICE_MANAGED_FILE" || return 1
}

resolve_boot_config_file() {
    if [ -n "$BOOT_CONFIG_FILE" ]; then
        echo "$BOOT_CONFIG_FILE"
        return
    fi
    if [ -f /boot/firmware/config.txt ]; then
        echo "/boot/firmware/config.txt"
        return
    fi
    echo "/boot/config.txt"
}

resolve_boot_cmdline_file() {
    local config_file="$1"
    if [ -n "$BOOT_CMDLINE_FILE" ]; then
        echo "$BOOT_CMDLINE_FILE"
        return
    fi

    local sibling_cmdline
    sibling_cmdline="$(dirname "$config_file")/cmdline.txt"
    if [ -f "$sibling_cmdline" ]; then
        echo "$sibling_cmdline"
        return
    fi
    if [ -f /boot/firmware/cmdline.txt ]; then
        echo "/boot/firmware/cmdline.txt"
        return
    fi
    echo "/boot/cmdline.txt"
}

config_has_active_line() {
    local config_file="$1"
    local wanted="$2"
    awk -v wanted="$wanted" '
        {
            line = $0
            sub(/[[:space:]]*#.*/, "", line)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", line)
            if (line == wanted) found = 1
        }
        END { exit(found ? 0 : 1) }
    ' "$config_file"
}

backup_boot_file_once() {
    local source_file="$1"
    local backup_name="$2"
    mkdir -p "$PRINTER_UART_BACKUP_DIR" || return 1
    if [ ! -f "$PRINTER_UART_BACKUP_DIR/$backup_name" ]; then
        cp -p "$source_file" "$PRINTER_UART_BACKUP_DIR/$backup_name" || return 1
    fi
}

write_printer_uart_config() {
    local config_file="$1"
    local config_tmp
    config_tmp="$(mktemp "${config_file}.pc1-uart.XXXXXX")" || return 1

    awk '
        /^# BEGIN PC-1 PRINTER UART$/ { managed = 1; next }
        /^# END PC-1 PRINTER UART$/ { managed = 0; next }
        !managed { print }
    ' "$config_file" > "$config_tmp" || {
        rm -f "$config_tmp"
        return 1
    }

    cat >> "$config_tmp" <<'EOF'

# BEGIN PC-1 PRINTER UART
[all]
enable_uart=1
dtoverlay=disable-bt
# END PC-1 PRINTER UART
EOF

    backup_boot_file_once "$config_file" "config.txt.before-printer-uart" || {
        rm -f "$config_tmp"
        return 1
    }
    chmod --reference="$config_file" "$config_tmp" 2>/dev/null || true
    mv "$config_tmp" "$config_file" || return 1
}

remove_serial_console_from_cmdline() {
    local cmdline_file="$1"
    [ -f "$cmdline_file" ] || return 0
    if ! grep -Eq '(^|[[:space:]])console=(serial0|ttyAMA[0-9]*|ttyS[0-9]*)(,[^[:space:]]*)?([[:space:]]|$)' "$cmdline_file"; then
        return 0
    fi

    local cmdline_tmp
    cmdline_tmp="$(mktemp "${cmdline_file}.pc1-uart.XXXXXX")" || return 1
    awk '
        {
            output = ""
            for (i = 1; i <= NF; i++) {
                if ($i ~ /^console=(serial0|ttyAMA[0-9]*|ttyS[0-9]*)(,.*)?$/) continue
                output = output (output ? " " : "") $i
            }
            print output
        }
    ' "$cmdline_file" > "$cmdline_tmp" || {
        rm -f "$cmdline_tmp"
        return 1
    }

    if cmp -s "$cmdline_file" "$cmdline_tmp"; then
        rm -f "$cmdline_tmp"
        return 0
    fi

    backup_boot_file_once "$cmdline_file" "cmdline.txt.before-printer-uart" || {
        rm -f "$cmdline_tmp"
        return 1
    }
    chmod --reference="$cmdline_file" "$cmdline_tmp" 2>/dev/null || true
    mv "$cmdline_tmp" "$cmdline_file" || return 1
    PRINTER_UART_CHANGED=1
}

current_boot_id() {
    if [ -f "$BOOT_ID_FILE" ]; then
        tr -d '\r\n' < "$BOOT_ID_FILE"
        return
    fi
    echo "unknown"
}

current_serial_target() {
    local target
    target="$(readlink "$SERIAL0_PATH" 2>/dev/null)"
    if [ -n "$target" ]; then
        basename "$target"
        return
    fi
    if [ -e "$SERIAL0_PATH" ]; then
        basename "$SERIAL0_PATH"
        return
    fi
    echo "missing"
}

disable_uart_conflicts() {
    local unit_state uart_name
    unit_state="$("$SYSTEMCTL_BIN" is-enabled hciuart.service 2>/dev/null)"
    case "$unit_state" in
        disabled|masked|not-found|"")
            ;;
        *)
            "$SYSTEMCTL_BIN" disable --now hciuart.service >/dev/null 2>&1 || true
            ;;
    esac

    for uart_name in serial0 ttyS0 ttyAMA0; do
        unit_state="$("$SYSTEMCTL_BIN" is-enabled "serial-getty@${uart_name}.service" 2>/dev/null)"
        if [ "$unit_state" != "masked" ]; then
            "$SYSTEMCTL_BIN" disable --now "serial-getty@${uart_name}.service" >/dev/null 2>&1 || true
            "$SYSTEMCTL_BIN" mask "serial-getty@${uart_name}.service" >/dev/null 2>&1 || true
        fi
    done
}

ensure_printer_uart() {
    PRINTER_UART_CHANGED=0
    PRINTER_UART_REBOOT_REQUIRED=0
    PRINTER_UART_REBOOT_PENDING=0

    local config_file cmdline_file serial_target boot_id previous_boot_id
    config_file="$(resolve_boot_config_file)"
    if [ ! -f "$config_file" ]; then
        echo "status=unavailable"
        echo "error=boot_config_missing"
        echo "config_file=$config_file"
        return 1
    fi
    cmdline_file="$(resolve_boot_cmdline_file "$config_file")"

    if ! config_has_active_line "$config_file" "enable_uart=1" ||
       { ! config_has_active_line "$config_file" "dtoverlay=disable-bt" &&
         ! config_has_active_line "$config_file" "dtoverlay=miniuart-bt"; }; then
        write_printer_uart_config "$config_file" || {
            echo "status=failed"
            echo "error=boot_config_write_failed"
            return 1
        }
        PRINTER_UART_CHANGED=1
    fi

    remove_serial_console_from_cmdline "$cmdline_file" || {
        echo "status=failed"
        echo "error=boot_cmdline_write_failed"
        return 1
    }
    disable_uart_conflicts

    serial_target="$(current_serial_target)"
    boot_id="$(current_boot_id)"
    previous_boot_id=""
    if [ -f "$PRINTER_UART_STATE_FILE" ]; then
        previous_boot_id="$(tr -d '\r\n' < "$PRINTER_UART_STATE_FILE")"
    fi

    if [ "$PRINTER_UART_CHANGED" -eq 1 ]; then
        PRINTER_UART_REBOOT_REQUIRED=1
        echo "status=reboot_required"
    elif [[ "$serial_target" == ttyAMA* ]]; then
        rm -f "$PRINTER_UART_STATE_FILE"
        echo "status=ready"
    elif [ -n "$previous_boot_id" ] && [ "$previous_boot_id" = "$boot_id" ]; then
        PRINTER_UART_REBOOT_PENDING=1
        echo "status=reboot_pending"
    elif [ -n "$previous_boot_id" ] && [ "$previous_boot_id" != "$boot_id" ]; then
        echo "status=failed"
        echo "error=pl011_not_active_after_reboot"
        echo "serial_target=$serial_target"
        return 2
    else
        PRINTER_UART_REBOOT_REQUIRED=1
        echo "status=reboot_required"
    fi

    echo "changed=$PRINTER_UART_CHANGED"
    echo "reboot_required=$PRINTER_UART_REBOOT_REQUIRED"
    echo "reboot_pending=$PRINTER_UART_REBOOT_PENDING"
    echo "serial_target=$serial_target"
    echo "config_file=$config_file"
    return 0
}

schedule_printer_uart_reboot() {
    if [ -f "$PRINTER_UART_SETUP_MARKER" ]; then
        echo "reboot_scheduled=false"
        echo "error=setup_in_progress"
        return 3
    fi

    local boot_id
    boot_id="$(current_boot_id)"
    mkdir -p "$(dirname "$PRINTER_UART_STATE_FILE")" || return 1
    printf '%s\n' "$boot_id" > "$PRINTER_UART_STATE_FILE" || return 1

    "$SYSTEMD_RUN_BIN" \
        --unit=pc1-printer-uart-reboot \
        --on-active=2s \
        --timer-property=AccuracySec=1s \
        "$SYSTEMCTL_BIN" reboot >/dev/null 2>&1
    if [ $? -ne 0 ]; then
        rm -f "$PRINTER_UART_STATE_FILE"
        echo "reboot_scheduled=false"
        echo "error=reboot_schedule_failed"
        return 1
    fi

    echo "reboot_scheduled=true"
    return 0
}

ensure_wifi_powersave_off() {
    mkdir -p "$NM_CONF_DIR" || return 1
    cat > "$WIFI_POWERSAVE_CONF_FILE" <<EOF
[connection]
wifi.powersave=2
EOF
    chmod 0644 "$WIFI_POWERSAVE_CONF_FILE" || return 1
    systemctl restart NetworkManager || return 1

    # OTA compatibility bridge: the updater that installs a new release is
    # still running the previous Python code, but it invokes this newly copied
    # helper before restarting. Apply and schedule the one-time UART migration
    # here so deployed units can move to PL011 in the same OTA transaction.
    ensure_printer_uart
    local uart_result=$?
    if [ "$uart_result" -eq 0 ] && [ "$PRINTER_UART_REBOOT_REQUIRED" -eq 1 ]; then
        schedule_printer_uart_reboot || true
    fi
    return 0
}

status() {
    if nmcli connection show --active 2>/dev/null | grep -q "PC-1-Hotspot"; then
        echo "AP Mode: ACTIVE"
        DEVICE_ID=$(get_device_id)
        AP_PASS=$(get_device_password)
        AP_IP=$(get_ap_ip)
        echo "SSID: ${AP_SSID_PREFIX}-${DEVICE_ID}"
        echo "Password: $AP_PASS"
        echo "IP: ${AP_IP:-unknown}"
    else
        echo "AP Mode: INACTIVE"
    fi
}

main() {
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
        ensure-password-store)
            ensure_password_store
            exit $?
            ;;
        ensure-wifi-powersave-off)
            ensure_wifi_powersave_off
            exit $?
            ;;
        ensure-printer-uart)
            ensure_printer_uart
            exit $?
            ;;
        schedule-printer-uart-reboot)
            schedule_printer_uart_reboot
            exit $?
            ;;
        *)
            echo "Usage: $0 {start|stop|status|ensure-password-store|ensure-wifi-powersave-off|ensure-printer-uart|schedule-printer-uart-reboot}"
            exit 1
            ;;
    esac
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    main "$@"
fi
