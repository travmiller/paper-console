#!/usr/bin/env bash

set -euo pipefail

PORT="${PORT:-18000}"
BUILD_WEB=0
CHECK_WEB=1
CHECK_PRINT=1
FORCE_NPM_CI=0

usage() {
  cat <<'EOF'
PC-1 smoke test (WSL/Linux)

Usage:
  scripts/smoke_test.sh [--build-web] [--force-npm-ci] [--port PORT] [--no-web] [--no-print]

Examples:
  scripts/smoke_test.sh
  scripts/smoke_test.sh --build-web
  scripts/smoke_test.sh --build-web --force-npm-ci
  PORT=8000 scripts/smoke_test.sh --no-web
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build-web) BUILD_WEB=1; shift ;;
    --force-npm-ci) FORCE_NPM_CI=1; shift ;;
    --port) PORT="${2:?Missing port}"; shift 2 ;;
    --no-web) CHECK_WEB=0; shift ;;
    --no-print) CHECK_PRINT=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
cd "$ROOT_DIR"

# Prefer a local venv if present.
if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
elif [[ -f "venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "venv/bin/activate"
fi

PYTHON_BIN="python3"
if command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

for cmd in curl "$PYTHON_BIN"; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing dependency: $cmd" >&2
    exit 1
  fi
done

BASE_URL="http://127.0.0.1:${PORT}"
LOG_FILE="$(mktemp -t pc1-smoke.XXXXXX.log)"

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]] && kill -0 "$SERVER_PID" >/dev/null 2>&1; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
    wait "$SERVER_PID" >/dev/null 2>&1 || true
  fi
  echo "Log: ${LOG_FILE}"
}
trap cleanup EXIT

if [[ "$BUILD_WEB" -eq 1 ]]; then
  if ! command -v npm >/dev/null 2>&1; then
    echo "Missing dependency: npm (needed for --build-web)" >&2
    exit 1
  fi
  echo "[0/4] Building web UI..."
  if [[ "$FORCE_NPM_CI" -eq 1 || ! -d "web/node_modules" ]]; then
    (cd web && npm ci)
  fi
  (cd web && npm run build)
fi

echo "[1/4] Starting backend on ${BASE_URL}..."
PYTHONUNBUFFERED=1 "$PYTHON_BIN" -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT}" >"$LOG_FILE" 2>&1 &
SERVER_PID=$!

echo "[2/4] Waiting for /api/health..."
READY=0
for _ in $(seq 1 80); do
  if curl -fsS "${BASE_URL}/api/health" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 0.25
done
if [[ "$READY" -ne 1 ]]; then
  echo "Backend did not become ready." >&2
  tail -n 200 "$LOG_FILE" >&2 || true
  exit 1
fi

echo "[3/4] Verifying API health JSON..."
HEALTH_BODY="$(curl -fsS -H "Accept: application/json" "${BASE_URL}/api/health" || true)"
if [[ -z "$HEALTH_BODY" ]]; then
  echo "Empty /api/health response. Dumping headers for diagnostics..." >&2
  curl -sS -i "${BASE_URL}/api/health" >&2 || true
  exit 1
fi
HEALTH_BODY="$HEALTH_BODY" "$PYTHON_BIN" - <<'PY'
import json,os,sys
raw = os.environ.get("HEALTH_BODY") or ""
data=json.loads(raw)
if data.get("status") != "healthy":
  raise SystemExit(f"Unexpected health status: {data.get('status')!r}")
print("OK")
PY

if [[ "$CHECK_WEB" -eq 1 ]]; then
  if [[ -f "web/dist/index.html" ]]; then
    echo "[4a/4] Verifying built UI is served..."
    html="$(curl -fsS "${BASE_URL}/")"
    ASSET_PATH="$(
      HTML="$html" "$PYTHON_BIN" - <<'PY'
import os,re
html = os.environ.get("HTML") or ""
if 'id="root"' not in html:
  raise SystemExit("index.html did not contain #root")
m = re.search(r"(/assets/[^\"']+\.(?:js|css))", html)
print(m.group(1) if m else "")
PY
    )"
    if [[ -n "$ASSET_PATH" ]]; then
      curl -fsS "${BASE_URL}${ASSET_PATH}" >/dev/null
    fi
    echo "OK"
  else
    echo "[4a/4] Skipping UI check (missing web/dist). Run with --build-web to include it."
  fi
fi

if [[ "$CHECK_PRINT" -eq 1 ]]; then
  echo "[4b/4] Triggering a mock print and checking console output..."
  MODULES_BODY="$(curl -fsS -H "Accept: application/json" "${BASE_URL}/api/modules" || true)"
  if [[ -z "$MODULES_BODY" ]]; then
    echo "Empty /api/modules response." >&2
    curl -sS -i "${BASE_URL}/api/modules" >&2 || true
    exit 1
  fi

  MODULE_ID="$(
    MODULES_BODY="$MODULES_BODY" "$PYTHON_BIN" - <<'PY'
import json,os,sys
data=json.loads(os.environ.get("MODULES_BODY") or "{}")
mods=(data.get("modules") or {})
offline={"games","maze","quotes","history","text","checklist"}
for mid, m in mods.items():
  if isinstance(m, dict) and m.get("type") in offline:
    print(mid)
    raise SystemExit(0)
raise SystemExit(1)
PY
  )" || true

  CREATED_TEMP=0
  if [[ -z "$MODULE_ID" ]]; then
    echo "No offline module found; creating temporary text module..." >&2
    MODULE_ID="$(
      curl -fsS -H "Content-Type: application/json" -X POST "${BASE_URL}/api/modules" \
        -d '{"type":"text","name":"Smoke Test Note","config":{"content":"SMOKE TEST"}}' \
        | "$PYTHON_BIN" - <<'PY'
import json,sys
data=json.load(sys.stdin)
mod=data.get("module") or {}
print(mod.get("id",""))
PY
    )"
    if [[ -z "$MODULE_ID" ]]; then
      echo "Failed to create temp module." >&2
      exit 1
    fi
    CREATED_TEMP=1
  fi

  curl -fsS -X POST "${BASE_URL}/debug/print-module/${MODULE_ID}" >/dev/null

  PRINTED=0
  for _ in $(seq 1 80); do
    if rg -q "\\[PRINT\\]" "$LOG_FILE" 2>/dev/null || grep -q "\\[PRINT\\]" "$LOG_FILE"; then
      PRINTED=1
      break
    fi
    sleep 0.25
  done
  if [[ "$PRINTED" -ne 1 ]]; then
    echo "Did not detect mock printer output in server log." >&2
    tail -n 200 "$LOG_FILE" >&2 || true
    exit 1
  fi
  echo "OK"

  if [[ "$CREATED_TEMP" -eq 1 ]]; then
    curl -fsS -X DELETE "${BASE_URL}/api/modules/${MODULE_ID}" >/dev/null || true
  fi
fi

echo "Smoke test passed."
