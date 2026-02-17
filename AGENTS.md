# Agent Instructions

Use WSL for local development commands.

## Project Context

Use `readme.md` as canonical project context for setup, architecture, and expected behavior.

Rules:
- Check `readme.md` before making architecture, workflow, or UX assumptions.
- If instructions conflict, prefer: explicit user chat instructions, then `AGENTS.md`, then `readme.md`.
- Do not copy large sections of `readme.md` into responses unless explicitly requested; summarize relevant parts.

## Console Raster Preview for Print Debugging

When validating printer output (layout, clipping, alignment, density, or black/white dot rendering), run the full feedback loop command:

```bash
./.venv/bin/python testing/print_feedback_loop.py --module-type astronomy
./.venv/bin/python testing/print_feedback_loop.py --channel 3
```

This command:
- Renders the full receipt bitmap through the real print pipeline (`testing/render_full_print.py`)
- Saves PNG output under `testing/tmp/`
- Prints a console dot-map preview from that exact full receipt image

Use this fallback command only for synthetic calibration patterns:

```bash
./.venv/bin/python testing/console_raster_preview.py --pattern targets --dots-width 384 --cols 96
```

Rules:
- Prefer `./.venv/bin/python` in this repo (do not assume `python` is on `PATH`).
- Prefer full-print feedback loop previews over synthetic patterns when evaluating actual print changes.
- Use `--dots-width 384` by default for the 58mm printer path unless a different width is explicitly provided.
- Use built-in patterns (`grid`, `checker`, `bars`, `targets`) for deterministic diagnostics.
- Use `--image <path>` to inspect an actual bitmap that would be printed.
- Share/paste generated dot-map output in agent responses when requesting print QA feedback.
