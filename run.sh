#!/bin/bash

set -euo pipefail

PORT=${PORT:-8000}
SERVICE_NAME="pc-1"
SERVICE_WAS_ACTIVE=0

# Try to activate venv if it exists
if [ -f "venv/Scripts/activate" ]; then
    # shellcheck disable=SC1091
    source venv/Scripts/activate
elif [ -f "venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
fi

cleanup() {
    if [ "$SERVICE_WAS_ACTIVE" -eq 1 ]; then
        echo "Restarting ${SERVICE_NAME}.service..."
        sudo systemctl start "${SERVICE_NAME}" || echo "Failed to restart ${SERVICE_NAME}.service"
    fi
}
trap cleanup EXIT

# If the systemd service is running, stop it so that --reload can bind to the port cleanly.
if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files | grep -q "^${SERVICE_NAME}.service"; then
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        echo "Stopping ${SERVICE_NAME}.service so run.sh can own port ${PORT}..."
        sudo systemctl stop "${SERVICE_NAME}"
        SERVICE_WAS_ACTIVE=1
    fi
fi

# Guard against any other lingering uvicorn process on the same port.
# Force kill anything on the port before starting
if lsof -ti tcp:"${PORT}" >/dev/null 2>&1; then
    echo "Port ${PORT} is in use. Force killing..."
    lsof -ti tcp:"${PORT}" | xargs kill -9 || true
    sleep 2
fi

# Also kill any lingering python processes for this app specifically (if run.sh is used)
# Be careful not to kill system python, but this is usually safe in this context
pkill -f "uvicorn app.main:app" || true

echo "Starting PC-1 Server on port ${PORT}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"

