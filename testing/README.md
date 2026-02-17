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

Render full module/channel print jobs to receipt bitmap PNGs:

```bash
./.venv/bin/python testing/render_full_print.py --module-type astronomy --output testing/tmp/astronomy_full_module.png
./.venv/bin/python testing/render_full_print.py --channel 3 --output testing/tmp/channel3_full.png
./.venv/bin/python testing/console_raster_preview.py --image testing/tmp/channel3_full.png --cols 96
```

Discover targets:

```bash
./.venv/bin/python testing/render_full_print.py --list-modules
./.venv/bin/python testing/render_full_print.py --list-channels
```

Close the loop (render full print + immediate console dot-map preview):

```bash
./.venv/bin/python testing/print_feedback_loop.py --module-type astronomy
./.venv/bin/python testing/print_feedback_loop.py --channel 3
./.venv/bin/python testing/print_feedback_loop.py --channel 3 --cols 120 --density-threshold 0.10
```
