#!/usr/bin/env python3
"""One-command print feedback loop for agents.

Renders a full receipt bitmap for a module/channel, then previews that exact
bitmap in the terminal as a monochrome dot-map.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RENDER_SCRIPT = PROJECT_ROOT / "testing" / "render_full_print.py"
PREVIEW_SCRIPT = PROJECT_ROOT / "testing" / "console_raster_preview.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render full print(s) and preview them in console dot-map form."
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--module-id", help="Module instance ID from config.")
    target.add_argument("--module-type", help="Module type (e.g., astronomy).")
    target.add_argument("--channel", type=int, help="Channel position (1-8).")

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("testing/tmp/feedback_full_print.png"),
        help="Base output PNG path (default: testing/tmp/feedback_full_print.png).",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=None,
        help="Override max print lines for this job.",
    )
    parser.add_argument(
        "--include-interactive",
        action="store_true",
        help="Attempt to render interactive modules.",
    )
    parser.add_argument(
        "--raw-orientation",
        action="store_true",
        help="Keep printer-native orientation instead of rotating for human reading.",
    )

    parser.add_argument(
        "--cols",
        type=int,
        default=96,
        help="Console preview columns (default: 96).",
    )
    parser.add_argument(
        "--density-threshold",
        type=float,
        default=0.12,
        help="Black density threshold for preview cells (default: 0.12).",
    )
    parser.add_argument(
        "--cell-aspect",
        type=float,
        default=2.0,
        help="Terminal character aspect ratio hint (default: 2.0).",
    )
    parser.add_argument("--on", default="#", help="Character for black dots.")
    parser.add_argument("--off", default=".", help="Character for white dots.")
    return parser.parse_args()


def _build_render_cmd(args: argparse.Namespace) -> list[str]:
    cmd = [sys.executable, str(RENDER_SCRIPT)]
    if args.module_id:
        cmd.extend(["--module-id", args.module_id])
    elif args.module_type:
        cmd.extend(["--module-type", args.module_type])
    elif args.channel is not None:
        cmd.extend(["--channel", str(args.channel)])

    cmd.extend(["--output", str(args.output)])

    if args.max_lines is not None:
        cmd.extend(["--max-lines", str(args.max_lines)])
    if args.include_interactive:
        cmd.append("--include-interactive")
    if args.raw_orientation:
        cmd.append("--raw-orientation")
    return cmd


def _collect_saved_paths(render_stdout: str) -> list[Path]:
    saved = []
    for line in render_stdout.splitlines():
        if line.startswith("[full-print] saved="):
            saved.append(Path(line.split("=", 1)[1].strip()))
    return saved


def _run_preview(path: Path, args: argparse.Namespace) -> None:
    if not path.exists():
        print(f"[feedback] missing file: {path}", file=sys.stderr)
        return

    with Image.open(path) as img:
        dots_width = img.width

    preview_cmd = [
        sys.executable,
        str(PREVIEW_SCRIPT),
        "--image",
        str(path),
        "--dots-width",
        str(dots_width),
        "--cols",
        str(args.cols),
        "--density-threshold",
        str(args.density_threshold),
        "--cell-aspect",
        str(args.cell_aspect),
        "--on",
        args.on[:1],
        "--off",
        args.off[:1],
    ]

    print(f"[feedback] preview={path}")
    proc = subprocess.run(
        preview_cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)


def main() -> int:
    args = parse_args()

    render_cmd = _build_render_cmd(args)
    render_proc = subprocess.run(
        render_cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )

    if render_proc.stdout:
        print(render_proc.stdout, end="")
    if render_proc.stderr:
        print(render_proc.stderr, end="", file=sys.stderr)

    saved_paths = _collect_saved_paths(render_proc.stdout)
    if not saved_paths:
        print(
            "[feedback] No saved bitmap paths found in render output.",
            file=sys.stderr,
        )
        return 2

    for saved_path in saved_paths:
        _run_preview(saved_path, args)

    print(f"[feedback] complete bitmaps={len(saved_paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
