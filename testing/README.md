# Testing (WSL/Linux)

Run the automated suite from WSL/Linux:

```bash
./testing/run_tests.sh
```

This script will:
1. Create `.venv` if missing
2. Install `requirements-dev.txt`
3. Run `pytest` against `testing/`
