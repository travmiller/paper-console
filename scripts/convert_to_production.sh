#!/usr/bin/env bash
#
# Convert a git-clone PC-1 install into a production-style release install.
#
# What this script does:
# - Downloads a release artifact tarball from GitHub
# - Verifies it against the matching .sha256 asset
# - Backs up the current project state outside the repo
# - Preserves config.json and .env
# - Installs the release contents in-place
# - Reinstalls requirements-pi.txt into .venv
# - Removes .git so the app switches to production OTA behavior
# - Restarts pc-1.service
#
# Important:
# - Run this as the project owner user (for example: admin), not via sudo.
# - The script will prompt for sudo when stopping/restarting the service.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
DEFAULT_REPO="${PC1_UPDATE_GITHUB_REPO:-travmiller/paper-console}"
SERVICE_NAME="pc-1.service"
RELEASE_REPO="$DEFAULT_REPO"
RELEASE_TAG=""
ASSUME_YES=0
SKIP_PROJECT_BACKUP=0
BACKUP_ROOT="${HOME}/pc1-conversion-backups"

usage() {
    cat <<'EOF'
Usage:
  bash scripts/convert_to_production.sh [options]

Options:
  --repo <owner/name>     GitHub repo slug. Default: PC1_UPDATE_GITHUB_REPO or travmiller/paper-console
  --tag <vX.Y.Z>          Specific release tag to install. Default: latest release
  --service <name>        Systemd service name. Default: pc-1.service
  --backup-root <path>    Backup directory root. Default: ~/pc1-conversion-backups
  --skip-project-backup   Skip the full project tar backup (faster, less safe)
  -y, --yes               Run non-interactively
  -h, --help              Show this help text

Examples:
  bash scripts/convert_to_production.sh
  bash scripts/convert_to_production.sh --tag v1.2.3
  bash scripts/convert_to_production.sh --repo travmiller/paper-console --tag v1.2.3

After success:
  - .git is removed
  - .version is present
  - Settings-page updates use production OTA instead of git pull
EOF
}

log() {
    printf '[*] %s\n' "$1"
}

warn() {
    printf '[!] %s\n' "$1"
}

die() {
    printf '[x] %s\n' "$1" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

confirm() {
    local prompt="$1"
    if [[ "$ASSUME_YES" -eq 1 ]]; then
        return 0
    fi
    read -r -p "$prompt [y/N] " reply
    [[ "$reply" =~ ^[Yy]$ ]]
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo)
            RELEASE_REPO="${2:?Missing value for --repo}"
            shift 2
            ;;
        --tag)
            RELEASE_TAG="${2:?Missing value for --tag}"
            shift 2
            ;;
        --service)
            SERVICE_NAME="${2:?Missing value for --service}"
            shift 2
            ;;
        --backup-root)
            BACKUP_ROOT="${2:?Missing value for --backup-root}"
            shift 2
            ;;
        --skip-project-backup)
            SKIP_PROJECT_BACKUP=1
            shift
            ;;
        -y|--yes)
            ASSUME_YES=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "Unknown option: $1"
            ;;
    esac
done

if [[ "$(id -u)" -eq 0 ]]; then
    die "Run this as the project owner user, not with sudo. The script will call sudo only when needed."
fi

require_command python3
require_command tar
require_command sha256sum
require_command sudo

if [[ ! -d "$PROJECT_DIR" ]]; then
    die "Project directory not found: $PROJECT_DIR"
fi

if [[ ! -d "$PROJECT_DIR/.git" ]]; then
    if [[ -f "$PROJECT_DIR/.version" ]]; then
        die "This install already looks production-like (.git is absent and .version exists)."
    fi
    die "No .git directory found at $PROJECT_DIR. Refusing to run on a non-git install."
fi

PROJECT_OWNER="$(stat -c '%U' "$PROJECT_DIR")"
CURRENT_USER="$(id -un)"
if [[ "$PROJECT_OWNER" != "$CURRENT_USER" ]]; then
    die "Run this as '$PROJECT_OWNER' so the updated files and .venv remain user-owned."
fi

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="${BACKUP_ROOT}/${TIMESTAMP}"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/pc1-prod-convert.XXXXXX")"
PYTHON_BIN="python3"
if [[ -x "$PROJECT_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
fi

cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

log "Project directory: $PROJECT_DIR"
log "Release repo: $RELEASE_REPO"
if [[ -n "$RELEASE_TAG" ]]; then
    log "Requested release tag: $RELEASE_TAG"
else
    log "Requested release tag: latest"
fi
log "Service: $SERVICE_NAME"
log "Backups: $BACKUP_DIR"

if ! confirm "Convert this git checkout into a production-style release install?"; then
    die "Cancelled."
fi

log "Fetching release metadata from GitHub"
readarray -t RELEASE_INFO < <("$PYTHON_BIN" - "$RELEASE_REPO" "$RELEASE_TAG" <<'PY'
import json
import sys
import urllib.error
import urllib.request

repo = sys.argv[1]
tag = sys.argv[2].strip()
if tag:
    api_url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
else:
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"

req = urllib.request.Request(api_url, headers={"User-Agent": "PC-1-Production-Converter"})
try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.load(resp)
except urllib.error.HTTPError as exc:
    body = exc.read().decode("utf-8", errors="ignore")
    raise SystemExit(f"GitHub API request failed: HTTP {exc.code}: {body[:400]}")

tag_name = (data.get("tag_name") or "").strip()
if not tag_name:
    raise SystemExit("Release metadata did not include tag_name")

assets = data.get("assets") or []
asset_map = {str(asset.get("name") or "").strip(): asset for asset in assets}
tar_name = f"pc1-{tag_name}.tar.gz"
sha_name = f"pc1-{tag_name}.sha256"

tar_asset = asset_map.get(tar_name)
sha_asset = asset_map.get(sha_name)
if not tar_asset:
    raise SystemExit(f"Release is missing required asset: {tar_name}")
if not sha_asset:
    raise SystemExit(f"Release is missing required asset: {sha_name}")

tar_url = (tar_asset.get("browser_download_url") or "").strip()
sha_url = (sha_asset.get("browser_download_url") or "").strip()
if not tar_url or not sha_url:
    raise SystemExit("Release asset metadata did not include browser_download_url")

print(tag_name)
print(tar_name)
print(tar_url)
print(sha_url)
PY
)

[[ "${#RELEASE_INFO[@]}" -eq 4 ]] || die "Could not parse release metadata"
RESOLVED_TAG="${RELEASE_INFO[0]}"
TARBALL_NAME="${RELEASE_INFO[1]}"
TARBALL_URL="${RELEASE_INFO[2]}"
SHA_URL="${RELEASE_INFO[3]}"

log "Resolved release tag: $RESOLVED_TAG"

TARBALL_PATH="$TMP_DIR/$TARBALL_NAME"
SHA_PATH="$TMP_DIR/${TARBALL_NAME%.tar.gz}.sha256"

download_file() {
    local url="$1"
    local dest="$2"
    "$PYTHON_BIN" - "$url" "$dest" <<'PY'
import shutil
import sys
import urllib.request

url = sys.argv[1]
dest = sys.argv[2]
req = urllib.request.Request(url, headers={"User-Agent": "PC-1-Production-Converter"})
with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as out:
    shutil.copyfileobj(resp, out)
PY
}

log "Downloading release tarball"
download_file "$TARBALL_URL" "$TARBALL_PATH"

log "Downloading release checksum"
download_file "$SHA_URL" "$SHA_PATH"

EXPECTED_SHA="$(awk '{print $1}' "$SHA_PATH" | tr -d '\r\n')"
[[ -n "$EXPECTED_SHA" ]] || die "Could not read expected SHA256 from $SHA_PATH"
ACTUAL_SHA="$(sha256sum "$TARBALL_PATH" | awk '{print $1}')"
if [[ "$EXPECTED_SHA" != "$ACTUAL_SHA" ]]; then
    die "Release tarball checksum mismatch. Expected $EXPECTED_SHA but got $ACTUAL_SHA"
fi
log "Checksum verified"

EXTRACT_DIR="$TMP_DIR/extract"
mkdir -p "$EXTRACT_DIR"
tar -xzf "$TARBALL_PATH" -C "$EXTRACT_DIR"

SOURCE_DIR="$EXTRACT_DIR"
ITEM_COUNT="$(find "$EXTRACT_DIR" -mindepth 1 -maxdepth 1 | wc -l | tr -d ' ')"
if [[ "$ITEM_COUNT" == "1" ]]; then
    FIRST_ITEM="$(find "$EXTRACT_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1 || true)"
    if [[ -n "$FIRST_ITEM" ]]; then
        SOURCE_DIR="$FIRST_ITEM"
    fi
fi

[[ -f "$SOURCE_DIR/.version" ]] || die "Release bundle is missing .version"
[[ -f "$SOURCE_DIR/run.sh" ]] || die "Release bundle is missing run.sh"
[[ -d "$SOURCE_DIR/app" ]] || die "Release bundle is missing app/"
[[ -f "$SOURCE_DIR/web/dist/index.html" ]] || die "Release bundle is missing web/dist/index.html"

mkdir -p "$BACKUP_DIR"
printf '%s\n' "$RESOLVED_TAG" > "$BACKUP_DIR/target-release.txt"

log "Saving git state metadata"
git -C "$PROJECT_DIR" status --short > "$BACKUP_DIR/git-status.txt" || true
git -C "$PROJECT_DIR" rev-parse HEAD > "$BACKUP_DIR/git-head.txt" || true
git -C "$PROJECT_DIR" diff --binary > "$BACKUP_DIR/git-diff.patch" || true
git -C "$PROJECT_DIR" diff --cached --binary > "$BACKUP_DIR/git-diff-cached.patch" || true

if [[ "$SKIP_PROJECT_BACKUP" -eq 0 ]]; then
    log "Creating full project backup (excluding .venv)"
    tar \
        --exclude='.venv' \
        --exclude='testing/tmp' \
        --exclude='testing/print_gallery' \
        --exclude='testing/ui_gallery' \
        -czf "$BACKUP_DIR/project-pre-conversion.tgz" \
        -C "$PROJECT_DIR" \
        .
else
    warn "Skipping full project backup (--skip-project-backup)"
fi

CONFIG_BACKUP="$TMP_DIR/config.json.backup"
ENV_BACKUP="$TMP_DIR/env.backup"

if [[ -f "$PROJECT_DIR/config.json" ]]; then
    cp -a "$PROJECT_DIR/config.json" "$CONFIG_BACKUP"
    log "Backed up config.json"
fi

if [[ -f "$PROJECT_DIR/.env" ]]; then
    cp -a "$PROJECT_DIR/.env" "$ENV_BACKUP"
    log "Backed up .env"
fi

log "Stopping $SERVICE_NAME"
sudo systemctl stop "$SERVICE_NAME"

log "Installing release contents into $PROJECT_DIR"
while IFS= read -r item; do
    name="$(basename "$item")"
    dest="$PROJECT_DIR/$name"
    rm -rf "$dest"
    cp -a "$item" "$dest"
done < <(find "$SOURCE_DIR" -mindepth 1 -maxdepth 1 | sort)

if [[ -f "$CONFIG_BACKUP" ]]; then
    cp -a "$CONFIG_BACKUP" "$PROJECT_DIR/config.json"
    log "Restored config.json"
fi

if [[ -f "$ENV_BACKUP" ]]; then
    cp -a "$ENV_BACKUP" "$PROJECT_DIR/.env"
    log "Restored .env"
fi

VENV_DIR="$PROJECT_DIR/.venv"
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    log "Creating virtual environment"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

log "Installing production dependencies from requirements-pi.txt"
"$VENV_DIR/bin/python" -m pip install -r "$PROJECT_DIR/requirements-pi.txt"

if [[ -d "$PROJECT_DIR/.git" ]]; then
    log "Removing .git so the updater switches to production OTA mode"
    rm -rf "$PROJECT_DIR/.git"
fi

if [[ -f "$PROJECT_DIR/.version" ]]; then
    log "Installed version: $(tr -d '\r\n' < "$PROJECT_DIR/.version")"
fi

log "Restarting $SERVICE_NAME"
sudo systemctl reset-failed "$SERVICE_NAME" >/dev/null 2>&1 || true
sudo systemctl restart "$SERVICE_NAME"
sleep 2

if ! systemctl is-active --quiet "$SERVICE_NAME"; then
    die "Conversion completed, but $SERVICE_NAME is not active. Check: sudo journalctl -u $SERVICE_NAME -n 100"
fi

cat <<EOF

[OK] Conversion complete.

Backups:
  $BACKUP_DIR

What changed:
  - Installed release: $RESOLVED_TAG
  - Preserved config.json and .env
  - Removed .git
  - Restarted $SERVICE_NAME

Sanity checks:
  cd "$PROJECT_DIR"
  test -d .git && echo "still git" || echo "non-git install"
  test -f .version && { echo -n ".version="; cat .version; }
  sudo systemctl status "$SERVICE_NAME" --no-pager

EOF
