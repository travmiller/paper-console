#!/usr/bin/env python3
"""Render full module/channel print jobs to receipt bitmap PNG files.

This uses the real bitmap print pipeline (serial driver renderer) but captures
the final raster image instead of sending bytes to hardware.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

# Ensure project root is importable when running as `python testing/render_full_print.py`.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app.modules  # noqa: F401  # Ensure module registration side effects.
from app.config import (
    settings,
    WebhookConfig,
    TextConfig,
    CalendarConfig,
    PRINTER_WIDTH,
)
from app.module_registry import get_module
from app.drivers.printer_serial import PrinterDriver as SerialPrinterDriver
from app.modules import webhook, text, calendar, email_client


class CapturePrinter(SerialPrinterDriver):
    """Serial printer driver that captures raster bitmaps instead of sending."""

    def __init__(self, width: int = PRINTER_WIDTH):
        # Force a non-existent serial port to avoid touching real hardware.
        super().__init__(width=width, port="/dev/pc1-mock-serial")
        self.captured_bitmaps = []

    def _send_bitmap(self, img):  # type: ignore[override]
        if img is not None:
            self.captured_bitmaps.append(img.copy())

    def blip(self):
        # Skip tactile feedback in offline render mode.
        return

    def feed_direct(self, lines: int = 3):
        # No hardware feed in offline render mode.
        return

    def clear_hardware_buffer(self):
        # Keep software state reset behavior only.
        self.print_buffer.clear()
        self.lines_printed = 0
        self.max_lines = 0
        self._max_lines_hit = False


def _execute_module(module, printer: CapturePrinter, include_interactive: bool) -> bool:
    module_type = module.type
    config = module.config or {}
    module_name = module.name or module_type.upper()

    if module_type == "off":
        return True

    try:
        if module_type == "webhook":
            action_config = WebhookConfig(**config)
            webhook.run_webhook(action_config, printer, module_name)
            return True

        if module_type == "text":
            text_config = TextConfig(**config)
            text.format_text_receipt(printer, text_config, module_name)
            return True

        if module_type == "calendar":
            cal_config = CalendarConfig(**config)
            calendar.format_calendar_receipt(printer, cal_config, module_name)
            return True

        if module_type == "email":
            emails = email_client.fetch_emails(config)
            email_client.format_email_receipt(
                printer, messages=emails, config=config, module_name=module_name
            )
            return True

        module_def = get_module(module_type)
        if not module_def:
            print(
                f"[warn] Unknown module type '{module_type}' (id={module.id}); skipped.",
                file=sys.stderr,
            )
            return False

        if module_def.interactive and not include_interactive:
            print(
                f"[warn] Interactive module '{module_name}' (type={module_type}) skipped. "
                "Use --include-interactive to attempt rendering.",
                file=sys.stderr,
            )
            return False

        module_def.execute_fn(printer, config, module_name)
        return True

    except Exception as exc:  # pragma: no cover - debug utility path
        print(
            f"[warn] Module '{module_name}' (type={module_type}) failed: {exc}",
            file=sys.stderr,
        )
        printer.print_text(f"{module_name}")
        printer.print_line()
        printer.print_text("Could not load this content.")
        printer.print_text("Please check your settings")
        printer.print_text("or try again later.")
        return False


def _modules_for_channel(position: int):
    channel = settings.channels.get(position)
    if not channel:
        raise ValueError(f"Channel {position} is not configured.")
    assignments = sorted(channel.modules or [], key=lambda a: a.order)
    modules = []
    for assignment in assignments:
        module = settings.modules.get(assignment.module_id)
        if module is None:
            print(
                f"[warn] Channel {position} references missing module id "
                f"'{assignment.module_id}'; skipped.",
                file=sys.stderr,
            )
            continue
        modules.append(module)
    if not modules:
        raise ValueError(f"Channel {position} has no renderable modules.")
    return modules


def _find_first_module_id_by_type(module_type: str) -> str:
    for module_id, module in settings.modules.items():
        if module.type == module_type:
            return module_id
    raise ValueError(f"No module instance found for type '{module_type}'.")


def _save_bitmaps(
    bitmaps: List,
    output: Path,
    rotate_for_human_view: bool,
) -> List[Path]:
    if not bitmaps:
        raise ValueError("No bitmaps were captured.")

    if output.suffix.lower() != ".png":
        output = output.with_suffix(".png")
    output.parent.mkdir(parents=True, exist_ok=True)

    out_paths: List[Path] = []
    many = len(bitmaps) > 1
    for idx, img in enumerate(bitmaps, start=1):
        final_img = img.rotate(180) if rotate_for_human_view else img
        if many:
            out_path = output.with_name(f"{output.stem}_{idx:02d}{output.suffix}")
        else:
            out_path = output
        final_img.save(out_path)
        out_paths.append(out_path)
    return out_paths


def _print_modules_list() -> None:
    print("module_id\ttype\tname")
    for module_id, module in sorted(settings.modules.items()):
        print(f"{module_id}\t{module.type}\t{module.name}")


def _print_channels_list() -> None:
    print("channel\torder\tmodule_id\ttype\tname")
    for position in sorted(settings.channels.keys()):
        channel = settings.channels.get(position)
        assignments = sorted(channel.modules or [], key=lambda a: a.order) if channel else []
        if not assignments:
            print(f"{position}\t-\t-\t-\t(empty)")
            continue
        for assignment in assignments:
            module = settings.modules.get(assignment.module_id)
            if module:
                print(
                    f"{position}\t{assignment.order}\t{assignment.module_id}\t"
                    f"{module.type}\t{module.name}"
                )
            else:
                print(f"{position}\t{assignment.order}\t{assignment.module_id}\t-\t(missing)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture full print bitmap(s) for a module or channel."
    )
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--module-id", help="Module instance ID from config.json.")
    target.add_argument(
        "--module-type",
        help="Module type (e.g., astronomy); renders first matching instance.",
    )
    target.add_argument(
        "--channel",
        type=int,
        help="Channel position (1-8) to render in configured module order.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("testing/tmp/full_print.png"),
        help="Output PNG path (default: testing/tmp/full_print.png).",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=None,
        help="Override max line limit for this render job.",
    )
    parser.add_argument(
        "--include-interactive",
        action="store_true",
        help="Attempt to run interactive modules (off by default).",
    )
    parser.add_argument(
        "--raw-orientation",
        action="store_true",
        help="Save bitmap as sent to printer (default rotates for human reading).",
    )
    parser.add_argument(
        "--list-modules",
        action="store_true",
        help="List available module IDs/types/names and exit.",
    )
    parser.add_argument(
        "--list-channels",
        action="store_true",
        help="List channels and assigned modules and exit.",
    )
    return parser.parse_args()


def _select_modules(args: argparse.Namespace):
    if args.module_id:
        module = settings.modules.get(args.module_id)
        if module is None:
            raise ValueError(f"Module id '{args.module_id}' not found.")
        return [module], f"module:{args.module_id}"

    if args.module_type:
        module_id = _find_first_module_id_by_type(args.module_type)
        module = settings.modules[module_id]
        return [module], f"module-type:{args.module_type} ({module_id})"

    if args.channel is not None:
        return _modules_for_channel(args.channel), f"channel:{args.channel}"

    raise ValueError("Provide one of --module-id, --module-type, or --channel.")


def main() -> int:
    args = parse_args()

    if args.list_modules:
        _print_modules_list()
    if args.list_channels:
        _print_channels_list()
    if args.list_modules or args.list_channels:
        return 0

    modules, target_label = _select_modules(args)

    printer = CapturePrinter(width=PRINTER_WIDTH)
    max_lines = args.max_lines if args.max_lines is not None else getattr(settings, "max_print_lines", 200)
    if hasattr(printer, "reset_buffer"):
        printer.reset_buffer(max_lines=max_lines)

    success_count = 0
    for module in modules:
        ok = _execute_module(module, printer, include_interactive=args.include_interactive)
        success_count += 1 if ok else 0

    printer.flush_buffer()

    out_paths = _save_bitmaps(
        printer.captured_bitmaps,
        output=args.output,
        rotate_for_human_view=not args.raw_orientation,
    )

    print(
        f"[full-print] target={target_label} modules={len(modules)} "
        f"success={success_count} bitmaps={len(out_paths)}"
    )
    for path in out_paths:
        print(f"[full-print] saved={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
