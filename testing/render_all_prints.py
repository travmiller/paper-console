#!/usr/bin/env python3
"""Render a full snapshot set of printable receipts to PNG files.

This script overwrites a target folder on each run so snapshots stay current.
It captures:
1) Every configured channel (1-8)
2) Every configured module instance
3) Key system receipts (setup instructions, first boot welcome, system ready)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app.modules  # noqa: F401
import app.selection_mode as selection_mode
from app.config import (
    PRINTER_WIDTH,
    settings,
    WebhookConfig,
    TextConfig,
    CalendarConfig,
)
from app.module_registry import get_all_modules, get_module
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

    # Ensure interactive state from prior modules does not leak into this render.
    selection_mode.exit_selection_mode()

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
                "Use --exclude-interactive to skip this warning path.",
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
    finally:
        # Some modules (e.g., adventure) enter selection mode; clear it so
        # subsequent snapshots do not inherit the left-edge indicator.
        selection_mode.exit_selection_mode()


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


def _load_dotenv(dotenv_path: Path) -> None:
    """Minimal .env loader (KEY=VALUE) without external dependencies."""
    if not dotenv_path.exists():
        return
    for raw in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _csv_env_list(name: str) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _overlay_env_test_config(type_id: str, config: dict) -> dict:
    """Overlay module config from PC1_TEST_* env vars for richer snapshots."""
    out = dict(config or {})

    if type_id == "news":
        key = os.getenv("PC1_TEST_NEWS_API_KEY", "").strip()
        if key:
            out["news_api_key"] = key

    elif type_id == "email":
        user = os.getenv("PC1_TEST_EMAIL_USER", "").strip()
        password = os.getenv("PC1_TEST_EMAIL_APP_PASSWORD", "").strip()
        host = os.getenv("PC1_TEST_EMAIL_HOST", "").strip()
        if user:
            out["email_user"] = user
        if password:
            out["email_password"] = password
        if host:
            out["email_host"] = host

    elif type_id == "rss":
        feeds = _csv_env_list("PC1_TEST_RSS_FEEDS")
        if feeds:
            out["rss_feeds"] = feeds

    elif type_id == "calendar":
        ics_url = os.getenv("PC1_TEST_CALENDAR_ICS_URL", "").strip()
        if ics_url:
            out["ical_sources"] = [{"label": "Test Calendar", "url": ics_url}]

    elif type_id == "webhook":
        webhook_url = os.getenv("PC1_TEST_WEBHOOK_URL", "").strip()
        webhook_method = os.getenv("PC1_TEST_WEBHOOK_METHOD", "").strip()
        webhook_json_path = os.getenv("PC1_TEST_WEBHOOK_JSON_PATH", "").strip()
        if webhook_url:
            out["url"] = webhook_url
            out["method"] = webhook_method or "GET"
            if webhook_json_path:
                out["json_path"] = webhook_json_path
            # Ensure JSON response for endpoints like icanhazdadjoke.
            headers = dict(out.get("headers", {}))
            headers.setdefault("Accept", "application/json")
            out["headers"] = headers

    return out


def _save_single_bitmap(printer: CapturePrinter, out_path: Path) -> Path:
    if not printer.captured_bitmaps:
        raise RuntimeError("No bitmap captured.")
    img = printer.captured_bitmaps[-1].rotate(180)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path


def _render_channel(
    position: int,
    out_dir: Path,
    include_interactive: bool,
    max_lines: int,
    out_path: Optional[Path] = None,
) -> Path:
    selection_mode.exit_selection_mode()
    modules = _modules_for_channel(position)
    printer = CapturePrinter(width=PRINTER_WIDTH)
    printer.reset_buffer(max_lines=max_lines)
    for module in modules:
        _execute_module(module, printer, include_interactive=include_interactive)
    printer.flush_buffer()
    final_out = out_path or (out_dir / f"channel_{position}.png")
    return _save_single_bitmap(printer, final_out)


def _render_module(
    module_id: str,
    out_dir: Path,
    include_interactive: bool,
    max_lines: int,
    out_path: Optional[Path] = None,
) -> Path:
    selection_mode.exit_selection_mode()
    module = settings.modules[module_id]
    printer = CapturePrinter(width=PRINTER_WIDTH)
    printer.reset_buffer(max_lines=max_lines)
    _execute_module(module, printer, include_interactive=include_interactive)
    printer.flush_buffer()
    safe_module_id = module_id.replace("/", "_")
    final_out = out_path or (out_dir / f"module_{safe_module_id}.png")
    return _save_single_bitmap(printer, final_out)


def _default_config_for_module_type(type_id: str, defn) -> dict:
    # Prefer an existing configured instance to get realistic defaults.
    for module in settings.modules.values():
        if module.type == type_id:
            return _overlay_env_test_config(type_id, dict(module.config or {}))

    # Fall back to config class defaults when available.
    config_class = getattr(defn, "config_class", None)
    if config_class:
        try:
            cfg = config_class()
            if hasattr(cfg, "model_dump"):
                return _overlay_env_test_config(type_id, cfg.model_dump())
            if hasattr(cfg, "dict"):
                return _overlay_env_test_config(type_id, cfg.dict())
        except Exception:
            pass

    return _overlay_env_test_config(type_id, {})


def _render_module_type(
    type_id: str,
    out_dir: Path,
    include_interactive: bool,
    max_lines: int,
    out_path: Optional[Path] = None,
) -> Path:
    selection_mode.exit_selection_mode()
    module_defs = get_all_modules()
    defn = module_defs[type_id]
    config = _default_config_for_module_type(type_id, defn)
    module = SimpleNamespace(
        id=f"type-{type_id}",
        type=type_id,
        name=defn.label,
        config=config,
    )

    printer = CapturePrinter(width=PRINTER_WIDTH)
    printer.reset_buffer(max_lines=max_lines)
    _execute_module(module, printer, include_interactive=include_interactive)
    printer.flush_buffer()
    final_out = out_path or (out_dir / f"module_type_{type_id}.png")
    return _save_single_bitmap(printer, final_out)


def _render_setup_instructions(out_dir: Path, out_path: Optional[Path] = None) -> Path:
    selection_mode.exit_selection_mode()
    import app.utils as utils

    original_printer = utils.printer
    printer = CapturePrinter(width=PRINTER_WIDTH)
    try:
        utils.printer = printer
        utils.print_setup_instructions_sync()
    finally:
        utils.printer = original_printer
    final_out = out_path or (out_dir / "system_setup_instructions.png")
    return _save_single_bitmap(printer, final_out)


def _render_first_boot(out_dir: Path, out_path: Optional[Path] = None) -> Path:
    selection_mode.exit_selection_mode()
    import app.main as main

    original_printer = main.printer
    original_marker_getter = main._get_welcome_marker_path
    printer = CapturePrinter(width=PRINTER_WIDTH)
    marker = out_dir / f"__first_boot_missing_{uuid4().hex}.marker"
    try:
        main.printer = printer
        main._get_welcome_marker_path = lambda: str(marker)
        asyncio.run(main.check_first_boot())
    finally:
        main.printer = original_printer
        main._get_welcome_marker_path = original_marker_getter
        try:
            marker.unlink(missing_ok=True)
        except Exception:
            pass
    final_out = out_path or (out_dir / "system_first_boot_welcome.png")
    return _save_single_bitmap(printer, final_out)


def _render_system_ready(out_dir: Path, out_path: Optional[Path] = None) -> Path:
    selection_mode.exit_selection_mode()
    import app.main as main

    original_printer = main.printer
    original_marker_getter = main._get_welcome_marker_path
    printer = CapturePrinter(width=PRINTER_WIDTH)
    marker = out_dir / "__system_ready_exists.marker"
    marker.write_text("1", encoding="utf-8")
    try:
        main.printer = printer
        main._get_welcome_marker_path = lambda: str(marker)
        asyncio.run(main.check_first_boot())
    finally:
        main.printer = original_printer
        main._get_welcome_marker_path = original_marker_getter
        try:
            marker.unlink(missing_ok=True)
        except Exception:
            pass
    final_out = out_path or (out_dir / "system_ready.png")
    return _save_single_bitmap(printer, final_out)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Unified debug renderer for full or targeted print snapshots."
    )
    target = parser.add_mutually_exclusive_group()
    target.add_argument(
        "--all",
        action="store_true",
        help="Render full snapshot gallery (default when no target is provided).",
    )
    target.add_argument("--channel", type=int, help="Render one channel position (1-8).")
    target.add_argument("--module-id", help="Render one configured module instance by id.")
    target.add_argument("--module-type", help="Render one module type snapshot by type id.")
    target.add_argument(
        "--system",
        choices=["setup", "first_boot", "ready"],
        help="Render one system receipt variant.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("testing/print_gallery"),
        help="Output folder for full sweep mode.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output PNG path for targeted mode (defaults to testing/tmp/<target>.png).",
    )
    parser.add_argument(
        "--exclude-interactive",
        action="store_true",
        help="Skip interactive module types (included by default in all-prints mode).",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=getattr(settings, "max_print_lines", 200),
        help="Max lines per rendered job (default: current settings).",
    )
    return parser.parse_args()


def _default_target_output(args: argparse.Namespace) -> Path:
    if args.output:
        return args.output
    tmp_dir = Path("testing/tmp")
    if args.channel is not None:
        return tmp_dir / f"channel_{args.channel}.png"
    if args.module_id:
        safe = args.module_id.replace("/", "_")
        return tmp_dir / f"module_{safe}.png"
    if args.module_type:
        return tmp_dir / f"module_type_{args.module_type}.png"
    if args.system:
        mapping = {
            "setup": "system_setup_instructions.png",
            "first_boot": "system_first_boot_welcome.png",
            "ready": "system_ready.png",
        }
        return tmp_dir / mapping[args.system]
    return tmp_dir / "single_render.png"


def _run_targeted_render(args: argparse.Namespace, include_interactive: bool) -> int:
    out_path = _default_target_output(args)
    out_dir = out_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.channel is not None:
        saved = _render_channel(
            position=args.channel,
            out_dir=out_dir,
            include_interactive=include_interactive,
            max_lines=args.max_lines,
            out_path=out_path,
        )
        print(f"[render-one] target=channel:{args.channel} saved={saved}")
        return 0

    if args.module_id:
        if args.module_id not in settings.modules:
            print(f"[error] module id not found: {args.module_id}", file=sys.stderr)
            return 2
        saved = _render_module(
            module_id=args.module_id,
            out_dir=out_dir,
            include_interactive=include_interactive,
            max_lines=args.max_lines,
            out_path=out_path,
        )
        print(f"[render-one] target=module:{args.module_id} saved={saved}")
        return 0

    if args.module_type:
        module_defs = get_all_modules()
        if args.module_type not in module_defs:
            print(f"[error] module type not found: {args.module_type}", file=sys.stderr)
            return 2
        saved = _render_module_type(
            type_id=args.module_type,
            out_dir=out_dir,
            include_interactive=include_interactive,
            max_lines=args.max_lines,
            out_path=out_path,
        )
        print(f"[render-one] target=module-type:{args.module_type} saved={saved}")
        return 0

    if args.system:
        if args.system == "setup":
            saved = _render_setup_instructions(out_dir, out_path=out_path)
        elif args.system == "first_boot":
            saved = _render_first_boot(out_dir, out_path=out_path)
        else:
            saved = _render_system_ready(out_dir, out_path=out_path)
        print(f"[render-one] target=system:{args.system} saved={saved}")
        return 0

    return 1


def main() -> int:
    args = parse_args()
    _load_dotenv(PROJECT_ROOT / ".env")
    selection_mode.exit_selection_mode()
    include_interactive = not args.exclude_interactive
    target_mode = any(
        [
            args.channel is not None,
            bool(args.module_id),
            bool(args.module_type),
            bool(args.system),
        ]
    )

    if target_mode:
        return _run_targeted_render(args, include_interactive)

    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # Clear previous snapshots/artifacts so the folder always reflects current outputs.
    for old_png in out_dir.glob("*.png"):
        old_png.unlink()
    for old_marker in out_dir.glob("*.marker"):
        old_marker.unlink()

    generated: list[Path] = []
    failures: list[str] = []

    # Channels
    for position in range(1, 9):
        try:
            generated.append(
                _render_channel(
                    position=position,
                    out_dir=out_dir,
                    include_interactive=include_interactive,
                    max_lines=args.max_lines,
                )
            )
        except Exception as exc:
            msg = f"channel:{position} failed: {exc}"
            failures.append(msg)
            print(f"[warn] {msg}", file=sys.stderr)

    # Modules
    for module_id in sorted(settings.modules.keys()):
        try:
            generated.append(
                _render_module(
                    module_id=module_id,
                    out_dir=out_dir,
                    include_interactive=include_interactive,
                    max_lines=args.max_lines,
                )
            )
        except Exception as exc:
            msg = f"module-instance:{module_id} failed: {exc}"
            failures.append(msg)
            print(f"[warn] {msg}", file=sys.stderr)

    # All registered module types (covers unassigned types).
    module_defs = get_all_modules()
    for type_id in sorted(module_defs.keys()):
        try:
            generated.append(
                _render_module_type(
                    type_id=type_id,
                    out_dir=out_dir,
                    include_interactive=include_interactive,
                    max_lines=args.max_lines,
                )
            )
        except Exception as exc:
            msg = f"module-type:{type_id} failed: {exc}"
            failures.append(msg)
            print(f"[warn] {msg}", file=sys.stderr)

    # System prints
    for renderer in (_render_setup_instructions, _render_first_boot, _render_system_ready):
        try:
            generated.append(renderer(out_dir))
        except Exception as exc:
            print(f"[warn] system render failed ({renderer.__name__}): {exc}", file=sys.stderr)

    # Write a simple manifest for quick diffs/review.
    manifest = out_dir / "manifest.txt"
    with manifest.open("w", encoding="utf-8") as f:
        for path in sorted(generated):
            f.write(f"{path.name}\n")

    failures_report = out_dir / "failures.txt"
    with failures_report.open("w", encoding="utf-8") as f:
        for failure in failures:
            f.write(f"{failure}\n")

    print(f"[all-prints] output_dir={out_dir}")
    print(f"[all-prints] generated_pngs={len(generated)}")
    print(f"[all-prints] manifest={manifest}")
    print(f"[all-prints] failures={len(failures)} report={failures_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
