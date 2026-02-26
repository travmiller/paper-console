#!/usr/bin/env bash
#
# Prepare a PC-1 device for golden image capture.
# This script is intended to run on a release-artifact install (no .git).

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"

ASSUME_YES=0
ZERO_FREE_SPACE=0
ALLOW_GIT_TREE=0
PROJECT_DIR="$DEFAULT_PROJECT_DIR"

usage() {
    cat <<'EOF'
Usage:
  scripts/prepare_golden_image.sh [options]

Options:
  -y, --yes             Run non-interactively (no confirmation prompt)
  --zero-free-space     Zero free space before finishing (slower, smaller image)
  --project-dir <path>  Explicit project directory (default: script parent)
  --allow-git-tree      Allow running inside a git checkout (testing only)
  -h, --help            Show this help text

Notes:
  - Production use should run from release artifacts (no .git directory).
  - This script scrubs local state, removes SSH host keys, and removes .env.
EOF
}

log() {
    printf '[*] %s\n' "$1"
}

warn() {
    printf '[!] %s\n' "$1"
}

die() {
    printf '[ERROR] %s\n' "$1" >&2
    exit 1
}

run_as_root() {
    if [[ "$EUID" -eq 0 ]]; then
        "$@"
    else
        sudo "$@"
    fi
}

PROJECT_OWNER_USER=""
run_as_project_owner() {
    if [[ "$EUID" -eq 0 && -n "$PROJECT_OWNER_USER" && "$PROJECT_OWNER_USER" != "root" ]]; then
        sudo -u "$PROJECT_OWNER_USER" "$@"
    else
        "$@"
    fi
}

confirm_or_exit() {
    if [[ "$ASSUME_YES" -eq 1 ]]; then
        return
    fi

    echo ""
    echo "This will scrub this device for golden image capture:"
    echo "- reset config.json and config.json.bak to defaults"
    echo "- remove .env and local runtime markers"
    echo "- clear WiFi profiles, logs, and shell histories"
    echo "- disable SSH and remove SSH host keys"
    echo "- clear machine identity (/etc/machine-id)"
    echo ""
    read -r -p "Continue? [y/N] " reply
    if [[ ! "$reply" =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -y|--yes)
            ASSUME_YES=1
            shift
            ;;
        --zero-free-space)
            ZERO_FREE_SPACE=1
            shift
            ;;
        --project-dir)
            [[ $# -ge 2 ]] || die "--project-dir requires a value"
            PROJECT_DIR="$2"
            shift 2
            ;;
        --allow-git-tree)
            ALLOW_GIT_TREE=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "Unknown argument: $1"
            ;;
    esac
done

PROJECT_DIR="$(cd -- "$PROJECT_DIR" && pwd)"
[[ -d "$PROJECT_DIR" ]] || die "Project directory does not exist: $PROJECT_DIR"

if [[ "$EUID" -ne 0 ]] && ! command -v sudo >/dev/null 2>&1; then
    die "sudo is required when not running as root"
fi

if [[ "$EUID" -ne 0 ]]; then
    # Validate sudo access early to fail fast.
    sudo -v
fi

[[ -f "$PROJECT_DIR/run.sh" ]] || die "Missing run.sh in project directory"
[[ -f "$PROJECT_DIR/scripts/setup_pi.sh" ]] || die "Missing scripts/setup_pi.sh"
[[ -f "$PROJECT_DIR/web/dist/index.html" ]] || die "Missing web/dist/index.html (build frontend first)"
[[ -f "$PROJECT_DIR/.version" ]] || die "Missing .version (install from release artifacts first)"

RELEASE_VERSION="$(tr -d '\r\n' < "$PROJECT_DIR/.version")"
[[ -n "$RELEASE_VERSION" ]] || die ".version exists but is empty"

if [[ -d "$PROJECT_DIR/.git" && "$ALLOW_GIT_TREE" -ne 1 ]]; then
    die "Git checkout detected. Production golden images must be prepared from release artifacts. Use --allow-git-tree only for local testing."
fi

if [[ -n "${SUDO_USER:-}" ]]; then
    PROJECT_OWNER_USER="$SUDO_USER"
else
    PROJECT_OWNER_USER="$(stat -c '%U' "$PROJECT_DIR" 2>/dev/null || true)"
    if [[ -z "$PROJECT_OWNER_USER" || "$PROJECT_OWNER_USER" == "UNKNOWN" ]]; then
        PROJECT_OWNER_USER="$(id -un)"
    fi
fi

PYTHON_BIN="python3"
if [[ -x "$PROJECT_DIR/venv/bin/python" ]]; then
    PYTHON_BIN="$PROJECT_DIR/venv/bin/python"
elif [[ -x "$PROJECT_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
fi

log "Project directory: $PROJECT_DIR"
log "Release version: $RELEASE_VERSION"
log "Python binary: $PYTHON_BIN"
echo ""

confirm_or_exit

log "Stopping pc-1.service"
run_as_root systemctl stop pc-1.service >/dev/null 2>&1 || true

log "Resetting config.json and config.json.bak to factory defaults"
run_as_project_owner bash -lc "cd '$PROJECT_DIR' && '$PYTHON_BIN' - <<'PY'
import json
from app.config import Settings

settings = Settings()
payload = json.dumps(settings.model_dump(), indent=4) + '\\n'

with open('config.json', 'w', encoding='utf-8') as f:
    f.write(payload)
with open('config.json.bak', 'w', encoding='utf-8') as f:
    f.write(payload)

# Validate serialized payload
Settings(**settings.model_dump())
PY"

log "Removing runtime markers and local secrets"
run_as_root rm -f \
    "$PROJECT_DIR/.welcome_printed" \
    "$PROJECT_DIR/config.json.tmp" \
    "$PROJECT_DIR/config.json.bak.tmp" \
    "$PROJECT_DIR/.env" \
    "$PROJECT_DIR/.env.bak" \
    "$PROJECT_DIR/.deploy_config"

log "Clearing cached artifacts and Python bytecode"
run_as_root find "$PROJECT_DIR" -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
run_as_root find "$PROJECT_DIR" -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete 2>/dev/null || true
run_as_root find "$PROJECT_DIR" -type d -name "*.egg-info" -prune -exec rm -rf {} + 2>/dev/null || true
run_as_root rm -rf \
    "$PROJECT_DIR/.pytest_cache" \
    "$PROJECT_DIR/testing/tmp" \
    "$PROJECT_DIR/testing/print_gallery" \
    "$PROJECT_DIR/testing/ui_gallery"

log "Disabling SSH and removing SSH identity"
run_as_root systemctl stop ssh >/dev/null 2>&1 || true
run_as_root systemctl disable ssh >/dev/null 2>&1 || true
if command -v raspi-config >/dev/null 2>&1; then
    run_as_root raspi-config nonint do_ssh 1 >/dev/null 2>&1 || true
fi
run_as_root rm -f /etc/ssh/ssh_host_*
run_as_root rm -rf /root/.ssh
if [[ -d /home ]]; then
    while IFS= read -r home_dir; do
        run_as_root rm -rf "$home_dir/.ssh" "$home_dir/.bash_history"
    done < <(find /home -mindepth 1 -maxdepth 1 -type d)
fi

log "Clearing machine identity and random seed"
run_as_root rm -f /etc/machine-id /var/lib/dbus/machine-id /var/lib/systemd/random-seed

log "Clearing logs and package caches"
run_as_root journalctl --rotate >/dev/null 2>&1 || true
run_as_root journalctl --vacuum-time=1s >/dev/null 2>&1 || true
run_as_root find /var/log -type f -exec truncate -s 0 {} \; 2>/dev/null || true
run_as_root rm -f /var/log/*.gz /var/log/*.old /var/log/*.[0-9] 2>/dev/null || true
run_as_root apt-get clean >/dev/null 2>&1 || true
run_as_root apt-get autoclean >/dev/null 2>&1 || true

log "Removing saved WiFi profiles"
if command -v nmcli >/dev/null 2>&1; then
    while IFS=: read -r uuid conn_type; do
        [[ -z "$uuid" ]] && continue
        if [[ "$conn_type" == "802-11-wireless" ]]; then
            run_as_root nmcli connection delete uuid "$uuid" >/dev/null 2>&1 || true
        fi
    done < <(run_as_root nmcli -t -f UUID,TYPE connection show 2>/dev/null || true)
fi
run_as_root rm -f /etc/NetworkManager/dnsmasq.d/captive-portal.conf
run_as_root pkill -HUP -f "dnsmasq.*NetworkManager" >/dev/null 2>&1 || true

if [[ "$ZERO_FREE_SPACE" -eq 1 ]]; then
    log "Zeroing free space (this may take several minutes)"
    run_as_root dd if=/dev/zero of=/zero.fill bs=1M status=progress >/dev/null 2>&1 || true
    run_as_root sync
    run_as_root rm -f /zero.fill
fi

run_as_root sync

echo ""
echo "Golden image preparation completed."
echo ""
echo "Next steps:"
echo "1. Shut down the Pi: sudo shutdown -h now"
echo "2. Capture the SD card image on your host machine"
echo "3. Flash that image to production cards"
echo ""
warn "WiFi profiles were removed. Remote SSH sessions may disconnect after this run."

