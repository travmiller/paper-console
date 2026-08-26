#!/usr/bin/env python3
"""Bounded, labeled hardware burn-in for the PC-1 printer UART."""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
from pathlib import Path
import sys
import time

from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.drivers.printer_serial import PrinterDriver


def _cpu_worker(stop_event: multiprocessing.synchronize.Event) -> None:
    payload = b"pc1-pl011-burnin" * 4096
    digest = payload
    while not stop_event.is_set():
        digest = hashlib.sha256(digest + payload).digest()


def _temperature_celsius() -> float | None:
    thermal_path = Path("/sys/class/thermal/thermal_zone0/temp")
    try:
        return int(thermal_path.read_text(encoding="utf-8").strip()) / 1000
    except (OSError, ValueError):
        return None


def _wait_for_safe_temperature(limit_celsius: float = 75.0) -> float | None:
    temperature = _temperature_celsius()
    while temperature is not None and temperature >= limit_celsius:
        print(f"Cooling at {temperature:.1f}C before next receipt", flush=True)
        time.sleep(5)
        temperature = _temperature_celsius()
    return temperature


def _pattern(index: int) -> Image.Image:
    image = Image.new("1", (320, 56), 1)
    draw = ImageDraw.Draw(image)
    pattern = index % 3
    if pattern == 0:
        for x in range(0, image.width, 16):
            draw.rectangle((x, 0, x + 3, image.height - 1), fill=0)
    elif pattern == 1:
        for y in range(0, image.height, 12):
            offset = 0 if (y // 12) % 2 == 0 else 8
            for x in range(-offset, image.width, 24):
                draw.rectangle((x, y, x + 7, min(y + 5, image.height - 1)), fill=0)
    else:
        for offset in range(-image.height, image.width, 20):
            draw.line((offset, image.height - 1, offset + image.height, 0), fill=0, width=2)
    return image


def _queue_receipt(
    printer: PrinterDriver,
    index: int,
    total: int,
    cpu_workers: int,
) -> None:
    printer.reset_buffer()
    printer.print_header(f"PL011 BURN {index:02d}/{total:02d}")
    printer.print_subheader("HARDWARE UART STRESS")
    printer.print_body(
        "Guarded raster strips are printing while the Pi is under bounded CPU load."
    )
    printer.print_image(_pattern(index))
    printer.print_body(
        "Pack my box with five dozen liquor jugs. 0123456789 ABCDEF abcdef."
    )
    printer.print_caption(f"CPU workers: {cpu_workers} | pattern: {(index - 1) % 3 + 1}")
    printer.print_bold("PASS MARKER: END OF RECEIPT")


def _preview(path: Path, cpu_workers: int) -> int:
    printer = PrinterDriver(init_serial=False)
    _queue_receipt(printer, 1, 12, cpu_workers)
    image = printer._render_unified_bitmap(list(printer.print_buffer))
    if image is None:
        raise RuntimeError("Burn-in receipt rendered no image")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    print(path)
    return 0


def _run(count: int, cpu_workers: int) -> int:
    stop_event = multiprocessing.Event()
    workers = [
        multiprocessing.Process(target=_cpu_worker, args=(stop_event,), daemon=True)
        for _ in range(cpu_workers)
    ]
    for worker in workers:
        worker.start()

    printer = PrinterDriver()
    results = []
    try:
        if not printer.is_available():
            raise RuntimeError("Printer serial interface is unavailable")

        for index in range(1, count + 1):
            temperature = _wait_for_safe_temperature()
            _queue_receipt(printer, index, count, cpu_workers)
            stats = printer.flush_buffer() or printer.last_transport_stats
            result = {
                "receipt": index,
                "temperature_celsius": temperature,
                **(stats or {}),
            }
            results.append(result)
            print(json.dumps(result, sort_keys=True), flush=True)
    finally:
        printer.close()
        stop_event.set()
        for worker in workers:
            worker.join(timeout=5)
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=2)

    print(json.dumps({"completed": len(results), "results": results}, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--cpu-workers", type=int, default=2)
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()

    if args.count < 1 or args.count > 50:
        parser.error("--count must be between 1 and 50")
    if args.cpu_workers < 0 or args.cpu_workers > 4:
        parser.error("--cpu-workers must be between 0 and 4")
    if args.preview:
        return _preview(args.preview, args.cpu_workers)
    return _run(args.count, args.cpu_workers)


if __name__ == "__main__":
    raise SystemExit(main())
