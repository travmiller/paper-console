# Documentation Directory

This directory contains reference documentation for the Paper Console project.

## Raspberry Pi Configuration Documentation

### Quick Reference
- **Reference File**: `raspberry-pi-config-reference.md` - Quick reference with project-specific notes
- **Full Documentation**: Run `scripts/fetch_rpi_docs.py` to download the complete documentation

### Updating Documentation

To fetch the latest Raspberry Pi configuration documentation:

```bash
python scripts/fetch_rpi_docs.py
```

This will create `raspberry-pi-config-full.md` with the complete documentation from the official Raspberry Pi website.

### Using in Cursor

Cursor will automatically index files in this directory. You can:
1. Reference these files in your questions
2. Ask Cursor to check the documentation when working on Raspberry Pi configuration
3. The `.cursorrules` file in the project root also references this documentation

## Adding More Documentation

To add other documentation references:
1. Create a new `.md` file in this directory
2. Add a reference in `.cursorrules` if needed
3. Cursor will automatically index it
