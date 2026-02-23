# Testing (WSL/Linux)

Run the automated suite from WSL/Linux:

```bash
./testing/run_tests.sh
```

This script will:
1. Create `.venv` if missing
2. Install `requirements-dev.txt`
3. Run `pytest` against `testing/`

Generate console dot-map previews (useful for printer layout debugging):

```bash
python testing/console_raster_preview.py --pattern targets
python testing/console_raster_preview.py --pattern bars --dots-height 300 --cols 120
python testing/console_raster_preview.py --image ./some_print_bitmap.png --cols 100
```

Unified print snapshot renderer:

```bash
# Full sweep (overwrites output-dir PNGs)
./.venv/bin/python testing/render_all_prints.py
./.venv/bin/python testing/render_all_prints.py --output-dir testing/print_gallery

# Targeted renders (single PNG)
./.venv/bin/python testing/render_all_prints.py --channel 3
./.venv/bin/python testing/render_all_prints.py --module-id default-weather-001
./.venv/bin/python testing/render_all_prints.py --module-type astronomy
./.venv/bin/python testing/render_all_prints.py --system setup
./.venv/bin/python testing/render_all_prints.py --module-type astronomy --output testing/tmp/astronomy_debug.png

# Optional
./.venv/bin/python testing/render_all_prints.py --exclude-interactive
```

Notes:
- Full sweep mode clears existing `*.png` files in the target folder and rewrites them.
- Targeted mode writes a single image (default path under `testing/tmp/` unless `--output` is provided).
- Full sweep also renders all registered module types (including unassigned ones) and writes `failures.txt`.

Settings UI snapshot renderer:

```bash
# Full UI sweep (starts backend + frontend, rewrites gallery)
./.venv/bin/python testing/render_settings_ui.py

# Reuse already-running servers
./.venv/bin/python testing/render_settings_ui.py --reuse-servers

# Optional output folder (still rewritten each run)
./.venv/bin/python testing/render_settings_ui.py --output-dir testing/ui_gallery

# First run: install Playwright Chromium
./.venv/bin/python testing/render_settings_ui.py --install-browser
```

Notes:
- This workflow captures key UI states (tabs, modals) and module edit screens.
- It creates temporary `UI TEST :: ...` modules to capture every module-type editor, then cleans them up.
- Output includes `manifest.txt`, `failures.txt`, `notes.txt`, and optional `runtime_warnings.txt`.
- If Linux runtime libraries are missing (e.g. `libnspr4.so`), run `npx --yes -p playwright playwright install-deps chromium` with sudo.
