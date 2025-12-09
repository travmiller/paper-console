#!/bin/bash
# prepare_golden_image.sh
# Run this on a fully-configured Pi BEFORE creating the golden image
# This cleans user-specific data so each flashed unit starts fresh

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║       PC-1 Golden Image Preparation Script                     ║"
echo "║  Run this BEFORE creating your master SD card image            ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Get project directory (script is in manufacturing/, project is parent)
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_DIR=$(dirname "$SCRIPT_DIR")

echo "Project directory: $PROJECT_DIR"
echo ""

# Confirm
read -p "This will reset config and clean logs. Continue? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "1. Resetting config.json to factory defaults..."
if [ -f "$SCRIPT_DIR/config.default.json" ]; then
    cp "$SCRIPT_DIR/config.default.json" "$PROJECT_DIR/config.json"
else
    cat > "$PROJECT_DIR/config.json" << 'EOF'
{
    "timezone": "America/New_York",
    "latitude": 40.7128,
    "longitude": -74.006,
    "city_name": "New York",
    "time_format": "12h",
    "openweather_api_key": null,
    "modules": {},
    "channels": {
        "1": {"modules": [], "schedule": []},
        "2": {"modules": [], "schedule": []},
        "3": {"modules": [], "schedule": []},
        "4": {"modules": [], "schedule": []},
        "5": {"modules": [], "schedule": []},
        "6": {"modules": [], "schedule": []},
        "7": {"modules": [], "schedule": []},
        "8": {"modules": [], "schedule": []}
    }
}
EOF
fi
echo "   ✓ config.json reset"

echo ""
echo "2. Clearing system logs and caches..."
sudo journalctl --vacuum-time=1s 2>/dev/null || true
sudo rm -rf /var/log/*.gz /var/log/*.1 /var/log/*.old 2>/dev/null || true
sudo truncate -s 0 /var/log/syslog 2>/dev/null || true
sudo truncate -s 0 /var/log/messages 2>/dev/null || true
echo "   ✓ Logs cleared"

echo ""
echo "3. Clearing bash history..."
history -c
rm -f ~/.bash_history
echo "   ✓ History cleared"

echo ""
echo "4. Clearing WiFi saved networks (except hotspot config)..."
# Keep the hotspot capability but remove any connected networks
sudo nmcli connection delete id "$(nmcli -t -f NAME connection show | grep -v 'PC-1-Hotspot' | grep -v 'lo')" 2>/dev/null || true
echo "   ✓ WiFi networks cleared"

echo ""
echo "5. Resetting machine-id for unique identity per device..."
sudo rm -f /etc/machine-id
sudo rm -f /var/lib/dbus/machine-id
# Don't regenerate - systemd will do it on first boot
echo "   ✓ Machine ID will regenerate on first boot"

echo ""
echo "6. Enabling SSH (for headless setup if needed)..."
sudo systemctl enable ssh
echo "   ✓ SSH enabled"

echo ""
echo "7. Removing unnecessary default folders..."
rm -rf ~/Desktop ~/Documents ~/Downloads ~/Music ~/Pictures ~/Public ~/Templates ~/Videos 2>/dev/null || true
# Prevent them from being recreated on login
mkdir -p ~/.config
cat > ~/.config/user-dirs.dirs << 'XDGEOF'
XDG_DESKTOP_DIR="$HOME"
XDG_DOWNLOAD_DIR="$HOME"
XDG_DOCUMENTS_DIR="$HOME"
XDG_MUSIC_DIR="$HOME"
XDG_PICTURES_DIR="$HOME"
XDG_VIDEOS_DIR="$HOME"
XDG_TEMPLATES_DIR="$HOME"
XDG_PUBLICSHARE_DIR="$HOME"
XDGEOF
echo "enabled=False" > ~/.config/user-dirs.conf
echo "   ✓ Junk folders removed"

echo ""
echo "8. Clearing apt cache to reduce image size..."
sudo apt-get clean
sudo apt-get autoclean
echo "   ✓ Apt cache cleared"

echo ""
echo "9. Zeroing free space for better compression (optional but recommended)..."
read -p "   Zero free space? This takes a few minutes but makes smaller images. [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "   Zeroing... (this will take a while)"
    sudo dd if=/dev/zero of=/zero.fill bs=1M 2>/dev/null || true
    sudo rm -f /zero.fill
    echo "   ✓ Free space zeroed"
else
    echo "   Skipped zeroing"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  ✓ Golden Image Preparation Complete!                          ║"
echo "╠════════════════════════════════════════════════════════════════╣"
echo "║  Next steps:                                                   ║"
echo "║  1. Shut down the Pi: sudo shutdown -h now                     ║"
echo "║  2. Remove SD card and insert into your computer               ║"
echo "║  3. Create image using one of these methods:                   ║"
echo "║                                                                ║"
echo "║  Windows (Win32DiskImager or similar):                         ║"
echo "║    - Read from SD card to create .img file                     ║"
echo "║                                                                ║"
echo "║  Linux/Mac:                                                    ║"
echo "║    sudo dd if=/dev/sdX of=pc1-golden.img bs=4M status=progress ║"
echo "║                                                                ║"
echo "║  Then compress: gzip pc1-golden.img                            ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

