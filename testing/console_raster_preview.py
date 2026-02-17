#!/usr/bin/env python3
"""Render monochrome printer test patterns as terminal text.

This is a lightweight way to inspect black/white dot layouts without hardware.
It can generate a synthetic test pattern or load a PNG/JPG and render it as
ASCII blocks that preserve the printer's fixed dot width.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def _build_test_pattern(width: int, height: int, pattern: str) -> Image.Image:
    """Create a deterministic 1-bit pattern image."""
    img = Image.new("1", (width, height), 1)  # 1=white, 0=black
    draw = ImageDraw.Draw(img)

    if pattern == "grid":
        # Fine + coarse guides for alignment
        for x in range(0, width, 8):
            draw.line((x, 0, x, height - 1), fill=0)
        for y in range(0, height, 8):
            draw.line((0, y, width - 1, y), fill=0)
        for x in range(0, width, 32):
            draw.line((x, 0, x, height - 1), fill=0, width=2)
        for y in range(0, height, 32):
            draw.line((0, y, width - 1, y), fill=0, width=2)
    elif pattern == "checker":
        cell = 16
        for y in range(0, height, cell):
            for x in range(0, width, cell):
                if ((x // cell) + (y // cell)) % 2 == 0:
                    draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=0)
    elif pattern == "bars":
        # Vertical density bands from 0% to 100%
        bands = 10
        band_w = max(1, width // bands)
        for i in range(bands):
            x0 = i * band_w
            x1 = width - 1 if i == bands - 1 else (x0 + band_w - 1)
            density = i / (bands - 1)
            if density <= 0:
                continue
            if density >= 1:
                draw.rectangle((x0, 0, x1, height - 1), fill=0)
                continue
            stride = max(1, round(1 / density))
            for y in range(height):
                for x in range(x0, x1 + 1):
                    if ((x + y) % stride) == 0:
                        draw.point((x, y), fill=0)
    elif pattern == "targets":
        # Bounding box + center marker + diagonals
        draw.rectangle((0, 0, width - 1, height - 1), outline=0, width=2)
        cx, cy = width // 2, height // 2
        draw.line((0, cy, width - 1, cy), fill=0, width=1)
        draw.line((cx, 0, cx, height - 1), fill=0, width=1)
        draw.line((0, 0, width - 1, height - 1), fill=0, width=1)
        draw.line((width - 1, 0, 0, height - 1), fill=0, width=1)
        for r in (24, 48, 72):
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=0, width=1)
    else:
        raise ValueError(f"Unsupported pattern: {pattern}")

    return img


def _load_image(path: Path, width: int, threshold: int) -> Image.Image:
    """Load and normalize input image to printer width, preserving aspect ratio."""
    img = Image.open(path).convert("L")
    if img.width != width:
        scale = width / img.width
        new_height = max(1, int(round(img.height * scale)))
        img = img.resize((width, new_height), Image.Resampling.LANCZOS)
    return img.point(lambda p: 0 if p < threshold else 255, mode="1")


def _image_to_ascii(
    img: Image.Image,
    cols: int,
    on: str,
    off: str,
    density_threshold: float,
    cell_aspect: float,
) -> list[str]:
    """Downsample a 1-bit image into console-friendly character rows."""
    if img.mode != "1":
        img = img.convert("1")

    width, height = img.size
    block_w = max(1, width // cols)
    block_h = max(1, int(round(block_w * cell_aspect)))
    out_cols = max(1, width // block_w)
    out_rows = max(1, height // block_h)
    pixels = img.load()
    rows: list[str] = []

    for row in range(out_rows):
        y0 = row * block_h
        y1 = min(height, y0 + block_h)
        line_chars: list[str] = []
        for col in range(out_cols):
            x0 = col * block_w
            x1 = min(width, x0 + block_w)
            total = (x1 - x0) * (y1 - y0)
            black = 0
            for y in range(y0, y1):
                for x in range(x0, x1):
                    # In mode "1": 0=black, 255=white
                    if pixels[x, y] == 0:
                        black += 1
            black_ratio = black / total if total else 0.0
            line_chars.append(on if black_ratio >= density_threshold else off)
        rows.append("".join(line_chars))

    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render thermal-printer-style monochrome dots to terminal text."
    )
    parser.add_argument(
        "--dots-width",
        type=int,
        default=384,
        help="Printer dot width (default: 384 for 58mm @ 203dpi).",
    )
    parser.add_argument(
        "--dots-height",
        type=int,
        default=220,
        help="Pattern height in dots (only used with --pattern).",
    )
    parser.add_argument(
        "--pattern",
        choices=["grid", "checker", "bars", "targets"],
        default="targets",
        help="Built-in test pattern to render (default: targets).",
    )
    parser.add_argument(
        "--image",
        type=Path,
        help="Optional image path; if provided, uses this instead of --pattern.",
    )
    parser.add_argument(
        "--cols",
        type=int,
        default=96,
        help="Console output columns (default: 96).",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=128,
        help="Threshold 0-255 when converting source image to B/W (default: 128).",
    )
    parser.add_argument(
        "--density-threshold",
        type=float,
        default=0.30,
        help="Black-pixel ratio per output cell required to mark as 'on' (default: 0.30).",
    )
    parser.add_argument(
        "--cell-aspect",
        type=float,
        default=2.0,
        help="Approx terminal char height/width ratio for vertical scaling (default: 2.0).",
    )
    parser.add_argument(
        "--on",
        default="#",
        help="Character used for black dots (default: #).",
    )
    parser.add_argument(
        "--off",
        default=".",
        help="Character used for white dots (default: .).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    width = max(8, args.dots_width)
    if args.image:
        img = _load_image(args.image, width=width, threshold=args.threshold)
        source = f"image:{args.image}"
    else:
        height = max(8, args.dots_height)
        img = _build_test_pattern(width=width, height=height, pattern=args.pattern)
        source = f"pattern:{args.pattern}"

    rows = _image_to_ascii(
        img=img,
        cols=max(8, args.cols),
        on=args.on[:1],
        off=args.off[:1],
        density_threshold=max(0.0, min(1.0, args.density_threshold)),
        cell_aspect=max(0.1, args.cell_aspect),
    )

    print(
        f"[preview] source={source} dots={img.width}x{img.height} "
        f"cols={len(rows[0]) if rows else 0} rows={len(rows)} on={args.on[:1]} off={args.off[:1]}"
    )
    for line in rows:
        print(line)


if __name__ == "__main__":
    main()
