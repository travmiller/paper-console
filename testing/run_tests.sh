#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
VENV_PY="$PROJECT_DIR/.venv/bin/python"

cd "$PROJECT_DIR"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

if [ ! -x "$VENV_PY" ]; then
  echo ".venv/bin/python was not created successfully."
  echo "Delete .venv and recreate it from your current Unix-like shell."
  exit 1
fi

"$VENV_PY" -m pip install --upgrade pip >/dev/null
"$VENV_PY" -m pip install -r requirements-dev.txt >/dev/null

"$VENV_PY" -m pytest -q -s ./testing "$@"
