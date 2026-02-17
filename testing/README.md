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
