#!/bin/bash

# Setup script for PC-1 on Raspberry Pi
# Run this with sudo: sudo ./setup_pi.sh

set -e

if [ "$EUID" -ne 0 ]; then 
  echo "Please run as root (sudo ./setup_pi.sh)"
  exit 1
fi

echo "--- PC-1 Setup ---"

# 1. Set Hostname
CURRENT_HOSTNAME=$(hostname)
DESIRED_HOSTNAME="pc-1"

read -p "Enter desired hostname [default: $DESIRED_HOSTNAME]: " INPUT_HOSTNAME
HOSTNAME=${INPUT_HOSTNAME:-$DESIRED_HOSTNAME}

if [ "$CURRENT_HOSTNAME" != "$HOSTNAME" ]; then
    echo "Setting hostname to $HOSTNAME..."
    hostnamectl set-hostname "$HOSTNAME"
    sed -i "s/127.0.1.1.*$/127.0.1.1\t$HOSTNAME/g" /etc/hosts
    echo "Hostname set. You may need to reboot for it to fully take effect on the network."
else
    echo "Hostname is already $HOSTNAME."
fi

# 2. Install dependencies
echo "Installing dependencies..."
apt-get update
apt-get install -y nginx avahi-daemon python3-venv python3-pip dnsmasq network-manager

# Add user to groups for printer access
echo "Adding $SUDO_USER to 'lp' and 'dialout' groups for printer access..."
usermod -a -G lp,dialout "$SUDO_USER"

# 3. Configure Nginx Reverse Proxy
echo "Configuring Nginx..."
cat > /etc/nginx/sites-available/paper-console <<EOL
server {
    listen 80;
    server_name $HOSTNAME.local;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOL

# Link and reload
ln -sf /etc/nginx/sites-available/paper-console /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

# 4. Create Systemd Service
# Attempt to locate the project directory based on script location
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_DIR=$(dirname "$SCRIPT_DIR")
USER_NAME=${SUDO_USER:-$USER}

echo "Configuring Systemd Service..."
echo "Project Directory: $PROJECT_DIR"
echo "User: $USER_NAME"

# Create/Update virtual environment
echo "Checking virtual environment..."
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo "Creating new virtual environment..."
    sudo -u "$USER_NAME" python3 -m venv "$PROJECT_DIR/venv"
fi

# Install/Upgrade dependencies
echo "Installing Python dependencies..."
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    sudo -u "$USER_NAME" "$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
else
    echo "Warning: requirements.txt not found!"
fi

# Check for venv (now guaranteed to exist)
PYTHON_EXEC="python3"
if [ -d "$PROJECT_DIR/venv" ]; then
    PYTHON_EXEC="$PROJECT_DIR/venv/bin/python"
    echo "Using venv at $PROJECT_DIR/venv"
else
    echo "Warning: No venv found. Using system python3."
fi

# Make WiFi script executable
echo "Setting up WiFi AP script..."
chmod +x "$PROJECT_DIR/scripts/wifi_ap_nmcli.sh"

# Give sudo access for WiFi management (no password required for specific scripts)
echo "Configuring sudo permissions for WiFi management..."
cat > /etc/sudoers.d/pc-1-wifi <<EOL
$USER_NAME ALL=(ALL) NOPASSWD: $PROJECT_DIR/scripts/wifi_ap_nmcli.sh
$USER_NAME ALL=(ALL) NOPASSWD: /usr/bin/nmcli
EOL
chmod 0440 /etc/sudoers.d/pc-1-wifi

cat > /etc/systemd/system/pc-1.service <<EOL
[Unit]
Description=PC-1 Paper Console
After=network.target

[Service]
User=$USER_NAME
WorkingDirectory=$PROJECT_DIR
ExecStart=/bin/bash $PROJECT_DIR/run.sh
Restart=always
RestartSec=5
KillSignal=SIGINT
TimeoutStopSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOL

systemctl daemon-reload
systemctl enable pc-1.service
systemctl restart pc-1.service

echo "--- Setup Complete ---"
echo "1. Your device is now accessible at http://$HOSTNAME.local"
echo "2. The application is running as a background service (pc-1.service)"
echo "3. Nginx is proxying port 80 to 8000"
echo ""
echo "To check status: sudo systemctl status pc-1.service"

