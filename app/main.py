from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, Response
from contextlib import asynccontextmanager
import asyncio
import uuid
import os
import hmac
from typing import Dict, Optional, List
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel
import subprocess
import platform
import pytz
import logging
import re
import shutil
import sys
import time

# Configure logging
LOG_LEVEL_NAME = os.environ.get("PC1_LOG_LEVEL", "WARNING").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_NAME, logging.WARNING)

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # Console output
    ],
    force=True,
)

# Keep noisy dependency logs quiet on embedded deployments.
for noisy_logger in ("uvicorn.access", "httpx", "urllib3", "asyncio"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

SEMVER_TAG_RE = re.compile(
    r"^v(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?"
    r"(?:\+[0-9A-Za-z.-]+)?$"
)


def _parse_cors_origins() -> List[str]:
    """
    Parse allowed CORS origins from env.
    Defaults to local/dev origins rather than wildcard.
    """
    raw = os.environ.get("PC1_CORS_ORIGINS", "").strip()
    if raw:
        origins = [o.strip() for o in raw.split(",") if o.strip()]
        if "*" in origins:
            return ["*"]
        return origins
    return [
        "http://localhost",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
        "http://pc-1.local",
    ]


from app.auth import (
    require_admin_access,
    get_admin_auth_status,
    verify_admin_password,
    set_admin_session_cookie,
    clear_admin_session_cookie,
)


from app.config import (
    settings,
    Settings,
    save_config,
    load_config,
    WebhookConfig,
    TextConfig,
    CalendarConfig,
    EmailConfig,
    ModuleInstance,
    ChannelModuleAssignment,
    ChannelConfig,
    PRINTER_WIDTH,
)

# Import modules package to trigger auto-discovery and registration
import app.modules  # noqa: F401

# Import module registry for dynamic dispatch
from app.module_registry import (
    get_module as get_module_def,
    get_all_modules,
    list_module_types,
    is_registered,
    validate_module_config,
)

# Legacy imports for modules with special handling (can be removed after full migration)
from app.modules import email_client, webhook, text, calendar

from app.routers import wifi
import app.device_password as device_password
import app.wifi_manager as wifi_manager
import app.hardware as hardware
from app.hardware import printer, dial, button, _is_raspberry_pi
import app.location_lookup as location_lookup

# --- BACKGROUND TASKS ---

config_lock = asyncio.Lock()


async def save_settings_background(settings_snapshot: Settings):
    """Save settings to disk in background with a lock to prevent race conditions."""
    async with config_lock:
        await asyncio.to_thread(save_config, settings_snapshot)


email_polling_task = None
scheduler_task = None
task_monitor_task = None


def _printer_is_available() -> bool:
    """Best-effort hardware printer availability check."""
    if not printer:
        return False
    checker = getattr(printer, "is_available", None)
    if callable(checker):
        try:
            return bool(checker())
        except Exception:
            logger.debug("Printer availability probe failed", exc_info=True)
            return False
    # Mock drivers generally have no explicit availability method.
    return True


async def task_watchdog():
    """Monitor background tasks and restart them if they die unexpectedly."""
    global email_polling_task, scheduler_task

    while True:
        await asyncio.sleep(60)  # Check every minute

        # Silently restart any dead tasks
        if email_polling_task is not None and email_polling_task.done():
            email_polling_task = asyncio.create_task(email_polling_loop())

        if scheduler_task is not None and scheduler_task.done():
            scheduler_task = asyncio.create_task(scheduler_loop())


async def email_polling_loop():
    """
    Polls for new emails from all email modules at their configured intervals.
    Uses the shortest polling interval among all active email modules.
    """
    while True:
        try:
            # Find all active email modules
            email_modules = []
            min_interval = None

            for module in settings.modules.values():
                if module.type == "email":
                    email_config = EmailConfig(**(module.config or {}))
                    if email_config.auto_print_new:
                        email_modules.append(module)
                        if min_interval is None or email_config.polling_interval < min_interval:
                            min_interval = email_config.polling_interval

            if not email_modules:
                await asyncio.sleep(60)
                continue

            await asyncio.sleep(max(1, min_interval or 60))

            # Check each email module silently
            for module in email_modules:
                try:
                    if not _try_begin_print_job(debounce=False):
                        logger.info(
                            "Skipping auto-print email poll for module_id=%s because printer is busy or reserved.",
                            getattr(module, "id", "unknown"),
                        )
                        continue

                    # Run email fetching and printing in thread pool to avoid blocking event loop
                    from concurrent.futures import ThreadPoolExecutor

                    def _fetch_and_print_email():
                        # Fetch emails (blocking IMAP operation)
                        emails = email_client.fetch_emails(module.config)
                        if emails:
                            # Prepare printer for new job
                            if hasattr(printer, "reset_buffer"):
                                max_lines = getattr(settings, "max_print_lines", 200)
                                printer.reset_buffer(max_lines)

                            email_client.format_email_receipt(
                                printer,
                                messages=emails,
                                config=module.config,
                                module_name=module.name,
                            )

                            # Flush to hardware (spacing is built into bitmap)
                            if hasattr(printer, "flush_buffer"):
                                printer.flush_buffer()

                    loop = asyncio.get_event_loop()
                    with ThreadPoolExecutor() as executor:
                        await loop.run_in_executor(executor, _fetch_and_print_email)

                except Exception:
                    logger.exception(
                        "Email polling iteration failed for module_id=%s",
                        getattr(module, "id", "unknown"),
                    )
                finally:
                    _clear_print_reservation(clear_hold=False)

        except Exception:
            logger.exception("Email polling loop encountered an unexpected error")
            await asyncio.sleep(60)  # Wait before retrying on error


async def scheduler_loop():
    """
    Checks every minute if any channel is scheduled to run at the current time.
    """
    last_run_minute = ""

    while True:
        try:
            await asyncio.sleep(10)

            now = datetime.now()
            current_time = now.strftime("%H:%M")

            # Prevent running multiple times in the same minute
            if current_time == last_run_minute:
                continue

            last_run_minute = current_time

            # Check all channels for matching schedule
            for pos, channel in settings.channels.items():
                if channel.schedule and current_time in channel.schedule:
                    if not _try_begin_print_job(debounce=False):
                        logger.info(
                            "Skipping scheduled print for channel %s because printer is busy or reserved.",
                            pos,
                        )
                        continue
                    await trigger_channel(pos)

        except Exception:
            await asyncio.sleep(60)


# --- HARDWARE CALLBACKS ---

# Print state tracking with proper thread synchronization
import threading

print_lock = threading.Lock()
print_in_progress = False
hold_action_in_progress = False
hold_action_started_at = 0.0
last_print_time = 0.0
PRINT_DEBOUNCE_SECONDS = 3.0  # Minimum time between print jobs
HOLD_ACTION_TIMEOUT_SECONDS = 20.0


global_loop = None


def _printer_reserved_locked() -> bool:
    """Return True when the printer is reserved for a print or hold action."""
    return print_in_progress or hold_action_in_progress


def _expire_stale_hold_action_locked(current_time: float):
    """Release a long-hold reservation if its matching release event was lost."""
    global hold_action_in_progress, hold_action_started_at

    if not hold_action_in_progress:
        return
    if (current_time - hold_action_started_at) < HOLD_ACTION_TIMEOUT_SECONDS:
        return

    hold_action_in_progress = False
    hold_action_started_at = 0.0
    logger.warning(
        "Cleared stale hold reservation after %.1fs without a matching release.",
        HOLD_ACTION_TIMEOUT_SECONDS,
    )


def _try_begin_print_job(*, debounce: bool = False) -> bool:
    """Reserve the printer for a new print job."""
    global print_in_progress, last_print_time
    import time

    with print_lock:
        current_time = time.time()
        _expire_stale_hold_action_locked(current_time)

        if _printer_reserved_locked():
            return False

        if debounce and (current_time - last_print_time) < PRINT_DEBOUNCE_SECONDS:
            return False

        print_in_progress = True
        last_print_time = current_time
        return True


def _reserve_hold_action() -> bool:
    """Reserve the printer once the user crosses a long-hold threshold."""
    global hold_action_in_progress, hold_action_started_at, last_print_time
    import time

    with print_lock:
        current_time = time.time()
        _expire_stale_hold_action_locked(current_time)

        if print_in_progress:
            return False

        hold_action_in_progress = True
        hold_action_started_at = current_time
        last_print_time = current_time
        return True


def _promote_hold_to_print_job() -> bool:
    """Convert a hold reservation into an active print job."""
    global print_in_progress, hold_action_in_progress, hold_action_started_at, last_print_time
    import time

    with print_lock:
        current_time = time.time()
        _expire_stale_hold_action_locked(current_time)

        if print_in_progress:
            return False

        hold_action_in_progress = False
        hold_action_started_at = 0.0
        print_in_progress = True
        last_print_time = current_time
        return True


def _clear_print_reservation(*, clear_hold: bool = True):
    """Release active print/hold reservations."""
    global print_in_progress, hold_action_in_progress, hold_action_started_at, last_print_time
    import time

    with print_lock:
        if print_in_progress:
            # Start debounce from the end of the physical print window, not the start.
            last_print_time = time.time()
        print_in_progress = False
        if clear_hold:
            hold_action_in_progress = False
            hold_action_started_at = 0.0

    if hasattr(button, "drain_pending_events"):
        try:
            button.drain_pending_events()
        except Exception:
            logger.debug("Failed to drain button events after print completion", exc_info=True)


def on_button_press_threadsafe():
    """Callback that schedules the trigger on the main event loop."""
    global global_loop

    if not _try_begin_print_job(debounce=True):
        return

    try:
        if global_loop and global_loop.is_running():
            # Check for selection mode (adventure game, settings menu, etc.)
            from app.selection_mode import is_selection_mode_active

            if is_selection_mode_active():
                # In selection mode: use dial position as choice input
                position = dial.read_position()
                asyncio.run_coroutine_threadsafe(
                    handle_selection_async(position), global_loop
                )
            else:
                # Normal mode: trigger the current channel
                asyncio.run_coroutine_threadsafe(trigger_current_channel(), global_loop)
        else:
            # Loop not running, reset flag
            _clear_print_reservation(clear_hold=False)
    except Exception:
        # Failed to schedule, reset flag
        _clear_print_reservation(clear_hold=False)


async def handle_selection_async(dial_position: int):
    """
    Async wrapper to handle selection mode input.
    Runs blocking operations in a thread pool.
    """
    from concurrent.futures import ThreadPoolExecutor
    from app.selection_mode import handle_selection

    def _do_selection():
        # Tactile feedback - blip on button press
        if hasattr(printer, "blip"):
            printer.blip()
        handle_selection(dial_position)

    try:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            await loop.run_in_executor(executor, _do_selection)
    finally:
        # Always mark print as complete
        _clear_print_reservation(clear_hold=False)


def on_button_long_press_threadsafe():
    """Callback for long press (5 seconds) - opens quick actions menu."""
    global global_loop

    if not _promote_hold_to_print_job() and not _try_begin_print_job(debounce=False):
        return

    try:
        if global_loop and global_loop.is_running():
            asyncio.run_coroutine_threadsafe(long_press_menu_trigger(), global_loop)
        else:
            _clear_print_reservation()
    except Exception:
        _clear_print_reservation()


def on_button_long_press_ready_threadsafe():
    """Callback fired at 5s hold threshold to signal 'you can release now'."""
    try:
        _reserve_hold_action()
        # Half-line tactile feed cue.
        if hasattr(printer, "feed_dots"):
            printer.feed_dots(12)
        elif hasattr(printer, "blip"):
            printer.blip()
    except Exception:
        logger.debug("Long-press ready tactile cue failed", exc_info=True)


def _print_channel_config_summary(position: int):
    """Print a summary of the currently selected channel configuration."""
    if hasattr(printer, "reset_buffer"):
        max_lines = getattr(settings, "max_print_lines", 200)
        printer.reset_buffer(max_lines)

    printer.print_header(f"CHANNEL {position}", icon="list")
    printer.print_line()

    channel = settings.channels.get(position)
    if not channel or not channel.modules:
        printer.print_body("This channel is empty.")
        printer.print_caption("Use web settings to add modules.")
    else:
        sorted_assignments = sorted(channel.modules, key=lambda m: m.order)
        printer.print_caption("Assigned modules:")
        for idx, assignment in enumerate(sorted_assignments, start=1):
            module = settings.modules.get(assignment.module_id)
            module_name = module.name if module else "(missing module)"
            printer.print_body(f"  {idx}. {module_name}")

        if channel.schedule:
            printer.feed(1)
            printer.print_caption("Schedule:")
            for schedule_time in channel.schedule[:8]:
                printer.print_body(f"  - {schedule_time}")
            if len(channel.schedule) > 8:
                printer.print_caption(f"  +{len(channel.schedule) - 8} more")
        else:
            printer.feed(1)
            printer.print_caption("Schedule: none")

    printer.print_line()
    printer.print_caption("Visit http://pc-1.local")
    printer.print_caption("to edit this channel.")
    printer.feed(1)

    if hasattr(printer, "flush_buffer"):
        printer.flush_buffer()


def _write_channel_overview_compact():
    """Write all channel assignments in a compact format (no reset/flush)."""
    printer.print_header("CHANNELS", icon="list")
    for channel_num in range(1, 9):
        channel = settings.channels.get(channel_num)
        if channel and channel.modules:
            names = []
            for assignment in sorted(channel.modules, key=lambda m: m.order):
                module = settings.modules.get(assignment.module_id)
                if module:
                    names.append(module.name)
            if names:
                printer.print_body(f"{channel_num}: {' + '.join(names)}")
            else:
                printer.print_caption(f"{channel_num}: (empty)")
        else:
            printer.print_caption(f"{channel_num}: (empty)")


def _write_long_press_menu_compact(position: int):
    """Write long-press quick action menu in compact format (no reset/flush)."""
    printer.print_header("QUICK ACTIONS", icon="settings")
    printer.print_caption(f"Dial: {position}")
    printer.print_body("[1] Table of contents")
    printer.print_body("[2] System monitor")
    printer.print_body("[3] Reprint setup instructions")
    printer.print_body("[4] Reset WiFi")
    printer.print_body("[5] Reset Factory Settings")
    printer.print_caption("[8] Cancel")
    printer.print_caption("Turn dial, press button")


def _print_system_monitor():
    """Print system monitor receipt (single-shot)."""
    if hasattr(printer, "reset_buffer"):
        max_lines = getattr(settings, "max_print_lines", 200)
        printer.reset_buffer(max_lines)
    from app.modules.system_monitor import format_system_monitor_receipt

    format_system_monitor_receipt(printer, {}, "SYSTEM MONITOR")
    if hasattr(printer, "flush_buffer"):
        printer.flush_buffer()


def _print_current_channel_and_menu(position: int):
    """Print current channel details + quick menu in one print job."""
    if hasattr(printer, "reset_buffer"):
        max_lines = getattr(settings, "max_print_lines", 200)
        printer.reset_buffer(max_lines)
    channel = settings.channels.get(position)

    printer.print_header(f"CHANNEL {position}", icon="list")
    if not channel or not channel.modules:
        printer.print_body("This channel is empty.")
        printer.print_caption("Use web settings to add modules.")
    else:
        sorted_assignments = sorted(channel.modules, key=lambda m: m.order)
        for idx, assignment in enumerate(sorted_assignments, start=1):
            module = settings.modules.get(assignment.module_id)
            module_name = module.name if module else "(missing module)"
            printer.print_body(f"{idx}. {module_name}")
        if channel.schedule:
            printer.print_caption("Schedule: " + ", ".join(channel.schedule[:4]))
            if len(channel.schedule) > 4:
                printer.print_caption(f"+{len(channel.schedule) - 4} more times")
        else:
            printer.print_caption("Schedule: none")

    _write_long_press_menu_compact(position)
    if hasattr(printer, "flush_buffer"):
        printer.flush_buffer()


def _print_channel_overview():
    """Print all channel assignments (compact view)."""
    if hasattr(printer, "reset_buffer"):
        max_lines = getattr(settings, "max_print_lines", 200)
        printer.reset_buffer(max_lines)
    _write_channel_overview_compact()

    if hasattr(printer, "flush_buffer"):
        printer.flush_buffer()


def _print_long_press_menu(position: int):
    """Print long-press quick action menu."""
    if hasattr(printer, "reset_buffer"):
        max_lines = getattr(settings, "max_print_lines", 200)
        printer.reset_buffer(max_lines)
    _write_long_press_menu_compact(position)

    if hasattr(printer, "flush_buffer"):
        printer.flush_buffer()


async def long_press_menu_trigger():
    """Long-press flow: open quick action menu and enter selection mode."""
    from concurrent.futures import ThreadPoolExecutor
    from app.selection_mode import enter_selection_mode, exit_selection_mode

    # Cancel any existing interactive mode before opening quick actions
    exit_selection_mode()

    position = dial.read_position()

    def _initial_print():
        # Print quick actions menu only (no auto-TOC print).
        _print_long_press_menu(position)

    try:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            await loop.run_in_executor(executor, _initial_print)
    except Exception:
        logger.exception("Failed to render long-press menu")
        _clear_print_reservation(clear_hold=False)
        return

    def _handle_quick_action(dial_position: int):
        from app.selection_mode import exit_selection_mode
        from app.hardware import printer as hw_printer

        if dial_position == 8:
            exit_selection_mode()
            if hasattr(hw_printer, "reset_buffer"):
                hw_printer.reset_buffer()
            hw_printer.print_header("CANCELLED", icon="x")
            hw_printer.print_line()
            hw_printer.feed(1)
            if hasattr(hw_printer, "flush_buffer"):
                hw_printer.flush_buffer()
            return

        if dial_position == 1:
            exit_selection_mode()
            _print_channel_overview()
            return

        if dial_position == 2:
            exit_selection_mode()
            _print_system_monitor()
            return

        if dial_position == 3:
            exit_selection_mode()
            from app.utils import print_setup_instructions_sync

            print_setup_instructions_sync()
            return

        if dial_position == 4:
            exit_selection_mode()
            if global_loop and global_loop.is_running():
                asyncio.run_coroutine_threadsafe(manual_ap_mode_trigger(), global_loop)
            return

        if dial_position == 5:
            exit_selection_mode()
            try:
                from app.modules.settings_menu import _confirm_factory_reset

                _confirm_factory_reset(hw_printer, "quick-factory-reset")
            except Exception:
                logger.exception("Failed to open factory reset confirmation")
            return

        # Invalid selection: exit quick actions without side effects.
        exit_selection_mode()
        if hasattr(hw_printer, "reset_buffer"):
            hw_printer.reset_buffer()
        hw_printer.print_header("QUICK ACTIONS", icon="settings")
        hw_printer.print_caption("No action selected.")
        hw_printer.print_caption("Hold button 5s to open menu.")
        hw_printer.feed(1)
        if hasattr(hw_printer, "flush_buffer"):
            hw_printer.flush_buffer()

    quick_actions_id = f"quick-actions-{position}"
    if hasattr(button, "drain_pending_events"):
        button.drain_pending_events()
    enter_selection_mode(_handle_quick_action, quick_actions_id)
    # Release lock only after quick-actions selection mode is fully active.
    _clear_print_reservation(clear_hold=False)

    async def _auto_exit_quick_actions_after_timeout(module_id: str):
        """Auto-exit quick actions if no selection is made within timeout."""
        from app.selection_mode import is_selection_mode_active, get_current_module_id

        await asyncio.sleep(120)

        if not is_selection_mode_active():
            return
        if get_current_module_id() != module_id:
            return

        # Still in this quick-actions session after timeout: exit with a brief hint.
        exit_selection_mode()
        from app.hardware import printer as hw_printer

        if hasattr(hw_printer, "reset_buffer"):
            max_lines = getattr(settings, "max_print_lines", 200)
            hw_printer.reset_buffer(max_lines)
        hw_printer.print_header("QUICK ACTIONS", icon="settings")
        hw_printer.print_caption("No action selected.")
        hw_printer.print_caption("Menu timed out after 2 min.")
        hw_printer.feed(1)
        if hasattr(hw_printer, "flush_buffer"):
            hw_printer.flush_buffer()

    asyncio.create_task(_auto_exit_quick_actions_after_timeout(quick_actions_id))


from app.utils import print_setup_instructions_sync, print_setup_wifi_access_details


async def print_setup_instructions():
    """Prints the WiFi setup instructions.
    Runs blocking printer operations in a thread pool to avoid blocking the event loop.
    """
    from concurrent.futures import ThreadPoolExecutor
    from app.selection_mode import exit_selection_mode

    # Cancel any active interactive mode
    exit_selection_mode()

    try:
        # Run blocking printer operations in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            await loop.run_in_executor(executor, print_setup_instructions_sync)
    except Exception as e:
        logger.error(f"Error in print_setup_instructions: {e}", exc_info=True)


def _get_welcome_marker_path() -> str:
    """Get path to the welcome message marker file."""
    import app.config as config_module

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(config_module.__file__)))
    return os.path.join(base_dir, ".welcome_printed")


async def check_first_boot():
    """Check if this is first boot and print welcome message.
    Runs blocking printer operations in a thread pool to avoid blocking the event loop.
    """
    marker_path = _get_welcome_marker_path()
    from concurrent.futures import ThreadPoolExecutor
    from app.selection_mode import exit_selection_mode

    # Cancel any active interactive mode
    exit_selection_mode()

    # Wait for printer to be ready (applies to all boots)
    await asyncio.sleep(2)

    # Check if marker exists first (this is fast, doesn't need thread pool)
    is_first_boot = not os.path.exists(marker_path)

    def _do_print():
        """Synchronous function that does the actual printing work."""
        try:
            # Force hardware printer into a clean baseline before startup receipts.
            if hasattr(printer, "clear_hardware_buffer"):
                printer.clear_hardware_buffer()
            if hasattr(printer, "reset_buffer"):
                printer.reset_buffer()

            # If marker exists, just print ready message
            if not is_first_boot:
                # Visual header with inline icon (no feed before - content starts immediately)
                printer.print_header("SYSTEM READY", icon="check", icon_size=28)

                from app.config import format_print_datetime

                printer.print_bold(format_print_datetime())

                printer.print_line()

                # Show channel assignments
                printer.print_subheader("CHANNELS")

                import app.config as config_module

                configured_settings = config_module.settings

                # Show all 8 channels
                for channel_num in range(1, 9):
                    channel = configured_settings.channels.get(channel_num)
                    if channel and channel.modules:
                        # Get module names
                        module_names = []
                        for mod_assignment in sorted(
                            channel.modules, key=lambda m: m.order
                        ):
                            module_id = mod_assignment.module_id
                            if module_id in configured_settings.modules:
                                module = configured_settings.modules[module_id]
                                module_names.append(module.name)

                        if module_names:
                            modules_str = " + ".join(module_names)
                            printer.print_body(f"  {channel_num}. {modules_str}")
                    else:
                        printer.print_caption(f"  {channel_num}. (empty)")

                # Flush buffer (spacing is built into bitmap)
                if hasattr(printer, "flush_buffer"):
                    printer.flush_buffer()
                return
            else:
                # First boot! Print welcome message
                ssid = wifi_manager.get_ap_ssid()
                ap_password = wifi_manager.get_ap_password()

                # Welcome header with icon (no feed before - content starts immediately)
                printer.print_header("WELCOME")
                printer.print_icon("home", size=56)

                printer.print_bold("PC-1 Paper Console")
                printer.print_body("Your personal printer for")
                printer.print_body("weather, news, puzzles,")
                printer.print_body("and more.")
                printer.print_line()

                # Setup instructions
                printer.print_subheader("SETUP INSTRUCTIONS")
                printer.print_line()

                # Step 1
                printer.print_bold("STEP 1: CONNECT TO WIFI")
                printer.print_icon("wifi", size=32)
                printer.print_body("On your phone or computer,")
                printer.print_body("connect to WiFi network:")
                printer.print_line()
                print_setup_wifi_access_details(
                    printer,
                    ssid=ssid,
                    password=ap_password,
                )
                printer.print_line()

                # Step 2
                printer.print_bold("STEP 2: OPEN SETUP PAGE")
                printer.print_icon("arrow_right", size=32)
                printer.print_body("Visit in your browser:")
                printer.print_line()
                printer.print_bold("  http://10.42.0.1")
                printer.print_caption("  (or http://pc-1.local)")
                printer.print_line()

                # Step 3
                printer.print_bold("STEP 3: CONFIGURE WIFI")
                printer.print_icon("settings", size=32)
                printer.print_body("Select your home WiFi and")
                printer.print_body("enter the password.")
                printer.print_caption("PC-1 will remember it.")
                printer.print_line()

                # After setup section
                printer.print_subheader("AFTER SETUP")
                printer.print_line()
                printer.print_body("Turn the dial to select a")
                printer.print_body("channel, then press the")
                printer.print_body("button to print!")
                printer.print_line()

                printer.print_bold("Default Channels:")
                for channel_num in range(1, 9):
                    channel = settings.channels.get(channel_num)
                    if channel and channel.modules:
                        module_names = []
                        for mod_assignment in sorted(
                            channel.modules, key=lambda m: m.order
                        ):
                            module_id = mod_assignment.module_id
                            if module_id in settings.modules:
                                module = settings.modules[module_id]
                                module_names.append(module.name)

                        if module_names:
                            modules_str = " + ".join(module_names)
                            printer.print_body(f"  {channel_num}. {modules_str}")
                        else:
                            printer.print_caption(f"  {channel_num}. (empty)")
                    else:
                        printer.print_caption(f"  {channel_num}. (empty)")
                printer.print_line()

                printer.print_caption("Customize channels at:")
                printer.print_bold("  http://pc-1.local")
                printer.print_line()

                printer.print_subheader("QUICK HELP")
                printer.print_body("Button 5s = Quick actions")
                printer.print_body("Button 15s = Reset all")
                printer.feed(1)

                # Flush buffer to print (spacing is built into bitmap)
                if hasattr(printer, "flush_buffer"):
                    printer.flush_buffer()

                # Create marker file so we don't print again
                try:
                    with open(marker_path, "w") as f:
                        f.write("1")
                except Exception:
                    logger.warning(
                        "Could not write first-boot marker file at %s",
                        marker_path,
                        exc_info=True,
                    )
        except Exception as e:
            logger.error(f"System Ready print error: {e}", exc_info=True)

    try:
        # Run blocking printer operations in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            await loop.run_in_executor(executor, _do_print)
    except Exception as e:
        logger.error(f"Error in check_first_boot: {e}", exc_info=True)


async def check_wifi_startup():
    """Check WiFi status on startup and enter AP mode if needed."""
    startup_was_first_boot = not os.path.exists(_get_welcome_marker_path())

    # Give system time to connect to saved WiFi
    await asyncio.sleep(10)

    status = wifi_manager.get_wifi_status()

    if not status["connected"] and status["mode"] != "ap":
        success = wifi_manager.start_ap_mode(retries=3)

        if success:
            await asyncio.sleep(5)
            if startup_was_first_boot:
                logger.info(
                    "Skipping duplicate startup setup receipt because first-boot receipt already includes setup instructions."
                )
                return
            await print_setup_instructions()
        else:
            # Schedule periodic retry in the background
            asyncio.create_task(periodic_wifi_recovery())


async def periodic_wifi_recovery():
    """Periodically check if we need to recover WiFi/AP mode. Runs forever until success."""
    retry_interval = 300  # 5 minutes

    while True:
        await asyncio.sleep(retry_interval)

        status = wifi_manager.get_wifi_status()

        # Exit if we have connectivity
        if status["connected"] or status["mode"] == "ap":
            return

        # Try to start AP mode
        success = wifi_manager.start_ap_mode(retries=2)
        if success:
            await asyncio.sleep(5)
            await print_setup_instructions()
            return


async def manual_ap_mode_trigger():
    """Manually trigger AP mode."""
    logger.info("Manual AP mode trigger initiated")

    from app.selection_mode import exit_selection_mode

    exit_selection_mode()

    # Print instructions BEFORE switching network mode
    await print_setup_instructions()

    # Give a small delay for the printer buffer to flush/finish
    await asyncio.sleep(2)

    logger.info("Starting AP mode...")
    success = wifi_manager.start_ap_mode()

    if success:
        logger.info("AP mode started successfully")
    else:
        logger.error("AP mode failed to start - check wifi_ap_nmcli.sh script")


async def factory_reset_trigger():
    """Factory reset (button hold 15+ seconds) - deletes config and reboots.
    Runs blocking printer operations in a thread pool to avoid blocking the event loop.
    """
    from concurrent.futures import ThreadPoolExecutor
    from app.selection_mode import exit_selection_mode
    from app.factory_reset import perform_factory_reset

    exit_selection_mode()

    def _print_reset_message():
        # Start from a clean transport state before sending reset notice.
        if hasattr(printer, "clear_hardware_buffer"):
            printer.clear_hardware_buffer()
        # Reset printer buffer
        if hasattr(printer, "reset_buffer"):
            printer.reset_buffer()

        # Print factory reset message
        printer.feed(1)
        printer.print_text("=" * 32)
        printer.print_text("")
        printer.print_text("     FACTORY RESET")
        printer.print_text("")
        printer.print_text("  All settings will be")
        printer.print_text("  cleared. Device will")
        printer.print_text("  reboot in setup mode.")
        printer.print_text("")
        printer.print_text("=" * 32)
        printer.feed(2)

        # Flush buffer to print (spacing is built into bitmap)
        if hasattr(printer, "flush_buffer"):
            printer.flush_buffer()

    try:
        # Run blocking printer operations in thread pool to avoid blocking event loop
        try:
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                await loop.run_in_executor(executor, _print_reset_message)
        except Exception:
            logger.warning(
                "Factory reset pre-reboot receipt failed to print",
                exc_info=True,
            )  # Continue reset flow even if print fails

        # Wait for print to complete
        await asyncio.sleep(3)

        reset_result = perform_factory_reset()
        if not reset_result.get("reboot_requested", False):
            logger.error(
                "Factory reset finished but reboot could not be requested: %s",
                "; ".join(reset_result.get("errors", [])),
            )
            # Fallback: try to make the device recoverable without reboot.
            try:
                if wifi_manager.start_ap_mode(retries=2):
                    await asyncio.sleep(1)
                    await print_setup_instructions()
            except Exception:
                logger.exception("Factory reset fallback AP-mode recovery failed")
    finally:
        _clear_print_reservation()


def on_factory_reset_threadsafe():
    """Callback for factory reset press (15+ seconds)."""
    global global_loop
    if not _promote_hold_to_print_job() and not _try_begin_print_job(debounce=False):
        logger.info("Ignoring factory reset hold because printer is already busy.")
        return

    if global_loop and global_loop.is_running():
        asyncio.run_coroutine_threadsafe(factory_reset_trigger(), global_loop)
    else:
        _clear_print_reservation()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global email_polling_task, scheduler_task, task_monitor_task, global_loop
    from concurrent.futures import ThreadPoolExecutor

    # Capture the running loop
    global_loop = asyncio.get_running_loop()

    admin_auth = get_admin_auth_status()
    logger.info("Settings auth mode: %s", admin_auth["auth_mode"])

    # Clear printer hardware buffer first to prevent startup garbage
    # Run in thread pool to avoid blocking event loop
    def _init_printer():
        if hasattr(printer, "clear_hardware_buffer"):
            printer.clear_hardware_buffer()

    try:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            await loop.run_in_executor(executor, _init_printer)
    except Exception:
        logger.exception(
            "Printer startup initialization failed (continuing without blocking startup)"
        )
    if _is_raspberry_pi and not _printer_is_available():
        logger.warning(
            "Printer driver is unavailable at startup; hardware printing may fail until serial is restored."
        )

    # Check for first boot and print welcome message
    asyncio.create_task(check_first_boot())

    # Check WiFi and start AP mode if needed
    asyncio.create_task(check_wifi_startup())

    # Start background tasks
    email_polling_task = asyncio.create_task(email_polling_loop())
    scheduler_task = asyncio.create_task(scheduler_loop())
    task_monitor_task = asyncio.create_task(task_watchdog())

    # Initialize Main Button Callbacks
    # Short press = Print
    button.set_callback(on_button_press_threadsafe)
    # Long press (5s) = Quick actions menu
    button.set_long_press_callback(on_button_long_press_threadsafe)
    # Long-press threshold reached (5s) = tactile cue
    if hasattr(button, "set_long_press_ready_callback"):
        button.set_long_press_ready_callback(on_button_long_press_ready_threadsafe)
    # Factory reset (15s) = Factory Reset
    button.set_factory_reset_callback(on_factory_reset_threadsafe)

    yield

    # Shutdown - cancel all background tasks
    for task in [email_polling_task, scheduler_task, task_monitor_task]:
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Background task shutdown failed")

    # Cleanup hardware drivers
    if hasattr(printer, "close"):
        printer.close()
    if hasattr(dial, "cleanup"):
        dial.cleanup()
    if hasattr(button, "cleanup"):
        button.cleanup()


app = FastAPI(
    title="PC-1 (Paper Console 1)",
    description="Backend API for the PC-1 offline news printer.",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow Frontend (React) to talk to Backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include WiFi router
app.include_router(wifi.router)


# --- CORE API ---


@app.get("/api/system/status")
async def read_root():
    pos = dial.read_position()
    channel = settings.channels.get(pos)
    module_info = "unknown"
    if channel:
        if channel.modules:
            module_info = f"{len(channel.modules)} module(s)"
        elif channel.type:
            module_info = channel.type

    return {
        "status": "online",
        "app": "PC-1",
        "version": "v1.0",
        "configured_timezone": settings.timezone,
        "current_channel": pos,
        "current_module": module_info,
    }


class AuthLoginRequest(BaseModel):
    password: str
    remember: bool = False


@app.get("/api/system/auth/status")
async def get_auth_status(request: Request):
    """Return privileged endpoint auth mode for UI guidance."""
    return get_admin_auth_status(request)


@app.post("/api/system/auth/login")
async def login_auth(request: Request, payload: AuthLoginRequest, response: Response):
    """Authenticate a settings session and set a signed cookie."""
    if not verify_admin_password(payload.password):
        raise HTTPException(
            status_code=401,
            detail="Invalid Device Password.",
            headers={"X-PC1-Auth-Required": "true"},
        )

    set_admin_session_cookie(
        response,
        remember=bool(payload.remember),
        secure=request.url.scheme == "https",
    )
    auth_status = get_admin_auth_status()
    auth_status["authenticated"] = True
    return {
        "message": "Authenticated",
        "auth": auth_status,
    }


@app.post("/api/system/auth/logout")
async def logout_auth(request: Request, response: Response):
    """Clear any saved settings session cookie."""
    clear_admin_session_cookie(response, secure=request.url.scheme == "https")
    return {"message": "Logged out"}


@app.get("/api/health")
async def health_check():
    """
    Health check endpoint for monitoring.
    Returns detailed status of all system components.
    """
    import os

    health = {"status": "healthy", "components": {}}

    # Check background tasks
    health["components"]["email_polling"] = (
        "running" if email_polling_task and not email_polling_task.done() else "stopped"
    )
    health["components"]["scheduler"] = (
        "running" if scheduler_task and not scheduler_task.done() else "stopped"
    )
    health["components"]["task_monitor"] = (
        "running" if task_monitor_task and not task_monitor_task.done() else "stopped"
    )

    # Check WiFi status
    try:
        wifi_status = wifi_manager.get_wifi_status()
        health["components"]["wifi"] = wifi_status.get("mode", "unknown")
        health["wifi_connected"] = wifi_status.get("connected", False)
    except Exception as e:
        health["components"]["wifi"] = f"error: {e}"

    # Check hardware drivers
    health["components"]["printer"] = (
        "available" if _printer_is_available() else "unavailable"
    )
    health["components"]["dial"] = "available" if dial else "unavailable"
    health["components"]["button"] = "available" if button else "unavailable"
    health["components"]["gpio"] = "available" if _is_raspberry_pi else "mock"

    # Check config file
    import app.config as config_module

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(config_module.__file__)))
    config_path = os.path.join(base_dir, "config.json")
    health["components"]["config"] = (
        "exists" if os.path.exists(config_path) else "missing"
    )

    # Overall status
    critical_issues = []
    if health["components"]["email_polling"] == "stopped":
        critical_issues.append("email_polling stopped")
    if health["components"]["scheduler"] == "stopped":
        critical_issues.append("scheduler stopped")
    if _is_raspberry_pi and health["components"]["printer"] == "unavailable":
        critical_issues.append("printer unavailable")

    if critical_issues:
        health["status"] = "degraded"
        health["issues"] = critical_issues

    return health


@app.get("/status")
async def get_status():
    """Returns the current state of the device."""
    pos = dial.read_position()
    channel = settings.channels.get(pos)
    module_info = "unknown"
    if channel:
        if channel.modules:
            module_info = f"{len(channel.modules)} module(s)"
        elif channel.type:
            module_info = channel.type

    return {"state": "idle", "current_channel": pos, "current_module": module_info}


# --- SETTINGS API ---


@app.get(
    "/api/settings",
    response_model=Settings,
    dependencies=[Depends(require_admin_access)],
)
async def get_settings():
    return settings


@app.post("/api/settings", dependencies=[Depends(require_admin_access)])
async def update_settings(new_settings: Settings, background_tasks: BackgroundTasks):
    """Updates the configuration and saves it to disk."""
    global settings
    import app.config as config_module
    validation_warnings: List[str] = []

    # Update in-memory - create new settings object
    settings = new_settings

    # VALIDATE MODULE CONFIGS
    # Ensure all modules have valid configuration before saving
    for module_id, module in settings.modules.items():
        if module_id == "unassigned":
            continue

        try:
            # We don't validate unassigned explicitly here since they are just copies
            # but we definitely validate the configured ones.
            # Note: module.type is reliable, module.config is what we check.
            validate_module_config(module.type, module.config or {})
        except ValueError as e:
            # Revert in-memory settings on failure
            # config_module.settings = load_config()  # Reload old config
            # raise HTTPException(status_code=400, detail=str(e))

            # Log warning but allow save to proceed
            # This prevents unrelated module validation errors from blocking global settings updates
            warning = f"{module_id} ({module.type}): {e}"
            validation_warnings.append(warning)
            logging.warning("Validation warning: %s", warning)

    # Update module-level reference so modules that access app.config.settings will see the update
    config_module.settings = settings

    # Save to disk
    background_tasks.add_task(save_settings_background, settings.model_copy(deep=True))

    response = {"message": "Settings saved", "config": settings}
    if validation_warnings:
        response["validation_warnings"] = validation_warnings
    return response


@app.post("/api/settings/reset", dependencies=[Depends(require_admin_access)])
async def reset_settings(background_tasks: BackgroundTasks):
    """Resets all settings to their default values."""
    global settings

    # Create fresh settings instance (uses defaults from config.py)
    settings = Settings()

    # Save to disk (overwriting existing config.json)
    background_tasks.add_task(save_settings_background, settings.model_copy(deep=True))

    return {"message": "Settings reset to defaults", "config": settings}


@app.post("/api/settings/reload", dependencies=[Depends(require_admin_access)])
async def reload_settings():
    """Reloads settings from config.json on disk."""
    global settings
    import app.config as config_module

    new_settings = load_config()

    # Update in-memory globals
    settings = new_settings
    config_module.settings = settings

    return {"message": "Settings reloaded from disk", "config": settings}


# --- SYSTEM TIME API ---


@app.get("/api/system/timezone")
async def get_system_timezone():
    """
    Get the current system timezone.
    """
    try:
        if platform.system() == "Linux":
            # Try timedatectl first
            try:
                result = subprocess.run(
                    ["timedatectl", "show", "-p", "Timezone", "--value"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return {
                        "timezone": result.stdout.strip(),
                        "found": True,
                    }
            except Exception:
                logger.debug("timedatectl timezone lookup failed", exc_info=True)

            # Fallback to /etc/timezone
            try:
                with open("/etc/timezone", "r") as f:
                    timezone = f.read().strip()
                    if timezone:
                        return {
                            "timezone": timezone,
                            "found": True,
                        }
            except Exception:
                logger.debug("/etc/timezone fallback lookup failed", exc_info=True)

        # Fallback to environment variable
        timezone = os.environ.get("TZ")
        if timezone:
            return {
                "timezone": timezone,
                "found": True,
            }

        return {
            "timezone": None,
            "found": False,
            "message": "Could not detect system timezone",
        }

    except Exception as e:
        return {
            "timezone": None,
            "found": False,
            "error": str(e),
        }


@app.get("/api/system/timezone/list")
async def list_timezones():
    """
    Get a list of available timezones.
    Returns common US timezones and a few others.
    """
    # Common timezones organized by region
    timezones = {
        "US Eastern": [
            "America/New_York",
            "America/Detroit",
            "America/Indiana/Indianapolis",
            "America/Indiana/Vevay",
            "America/Indiana/Vincennes",
            "America/Indiana/Winamac",
            "America/Kentucky/Louisville",
            "America/Kentucky/Monticello",
        ],
        "US Central": [
            "America/Chicago",
            "America/Indiana/Knox",
            "America/Indiana/Tell_City",
            "America/Menominee",
            "America/North_Dakota/Center",
            "America/North_Dakota/New_Salem",
            "America/North_Dakota/Beulah",
        ],
        "US Mountain": [
            "America/Denver",
            "America/Boise",
        ],
        "US Arizona": [
            "America/Phoenix",
        ],
        "US Pacific": [
            "America/Los_Angeles",
            "America/Anchorage",
            "America/Juneau",
            "America/Sitka",
            "America/Metlakatla",
            "America/Yakutat",
            "America/Nome",
        ],
        "US Territories": [
            "Pacific/Honolulu",
            "America/Puerto_Rico",
            "America/St_Thomas",
            "Pacific/Guam",
            "Pacific/Saipan",
            "Pacific/Pago_Pago",
        ],
        "Other": [
            "UTC",
            "Europe/London",
            "Europe/Paris",
            "Asia/Tokyo",
            "Australia/Sydney",
        ],
    }

    # Flatten into a simple list with labels
    timezone_list = []
    for region, tz_list in timezones.items():
        for tz in tz_list:
            timezone_list.append({"value": tz, "label": tz, "region": region})

    return {"timezones": timezone_list}


class SetTimezoneRequest(BaseModel):
    timezone: str


@app.post("/api/system/timezone", dependencies=[Depends(require_admin_access)])
async def set_system_timezone(request: SetTimezoneRequest):
    """
    Set the system timezone.
    Requires root/admin privileges on Linux.
    """
    timezone = request.timezone
    try:
        # Validate timezone format
        try:
            pytz.timezone(timezone)
        except Exception:
            return {
                "success": False,
                "error": f"Invalid timezone: {timezone}",
                "message": "The specified timezone is not valid.",
            }

        if platform.system() == "Linux":
            # Use timedatectl to set timezone
            result = subprocess.run(
                ["sudo", "timedatectl", "set-timezone", timezone],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": result.stderr or "Failed to set timezone",
                    "message": "Could not set system timezone. Ensure the application has sudo privileges.",
                }

            return {
                "success": True,
                "message": f"System timezone set to {timezone}",
                "timezone": timezone,
            }

        elif platform.system() == "Windows":
            # Windows doesn't easily support timezone changes via command line
            # Would need to use tzutil or registry edits
            return {
                "success": False,
                "error": "Timezone setting not supported on Windows",
                "message": "Please set timezone through Windows settings.",
            }

        else:
            return {
                "success": False,
                "error": f"Timezone setting not supported on {platform.system()}",
                "message": "System timezone setting is only supported on Linux.",
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Command timed out",
            "message": "Setting timezone timed out. Please try again.",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "An error occurred while setting timezone.",
        }


@app.get("/api/system/time")
async def get_system_time():
    """
    Get the current system time and date.
    Returns time in the configured timezone and format.
    """
    try:
        from app.config import format_time

        tz = pytz.timezone(settings.timezone)
        now = datetime.now(tz)

        # Format time according to user's preference
        time_formatted = format_time(now, settings.time_format)
        date_str = now.strftime("%Y-%m-%d")

        # Format full datetime string with date and formatted time
        formatted = f"{date_str} {time_formatted}"

        return {
            "datetime": now.isoformat(),
            "date": date_str,
            "time": now.strftime("%H:%M:%S"),
            "timezone": settings.timezone,
            "formatted": formatted,
            "time_formatted": time_formatted,
        }
    except Exception as e:
        # Fallback to UTC if timezone is invalid
        from app.config import format_time

        now = datetime.now(pytz.UTC)
        time_formatted = format_time(now, settings.time_format)
        date_str = now.strftime("%Y-%m-%d")
        formatted = f"{date_str} {time_formatted}"

        return {
            "datetime": now.isoformat(),
            "date": date_str,
            "time": now.strftime("%H:%M:%S"),
            "timezone": "UTC",
            "formatted": formatted,
            "time_formatted": time_formatted,
            "error": str(e),
        }


class SetTimeRequest(BaseModel):
    date: str
    time: str


@app.post("/api/system/time", dependencies=[Depends(require_admin_access)])
async def set_system_time(request: SetTimeRequest):
    """
    Set the system time and date.

    Args:
        date: Date in YYYY-MM-DD format
        time: Time in HH:MM:SS format
    """
    date = request.date
    time = request.time
    try:
        # Validate date and time format
        datetime.strptime(date, "%Y-%m-%d")
        datetime.strptime(time, "%H:%M:%S")

        # Combine date and time
        datetime_str = f"{date} {time}"

        if platform.system() == "Linux":
            # Disable NTP sync first to prevent it from overriding manual time setting
            # This is critical - NTP will immediately override manual time if enabled
            try:
                ntp_result = subprocess.run(
                    ["sudo", "timedatectl", "set-ntp", "false"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if ntp_result.returncode != 0:
                    print(f"Warning: Failed to disable NTP: {ntp_result.stderr}")
            except Exception as e:
                print(f"Warning: Error disabling NTP: {e}")

            # On Linux/Raspberry Pi, use 'date' command with sudo
            # Format: sudo date -s "YYYY-MM-DD HH:MM:SS"
            # This sets the time in the system's local timezone
            print(f"Setting system time to: {datetime_str}")
            result = subprocess.run(
                ["sudo", "date", "-s", datetime_str],
                capture_output=True,
                text=True,
                timeout=5,
            )

            print(
                f"Date command result: returncode={result.returncode}, stdout={result.stdout}, stderr={result.stderr}"
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": result.stderr
                    or "Failed to set system time. May require root privileges.",
                    "message": "Could not set system time. Ensure the application has sudo privileges or run as root.",
                }

            # Also sync hardware clock if available
            try:
                subprocess.run(["sudo", "hwclock", "--systohc"], timeout=5, check=False)
            except Exception:
                logger.debug("Ignoring hwclock sync failure after manual time set", exc_info=True)

            return {
                "success": True,
                "message": f"System time set to {datetime_str}. NTP sync disabled to preserve manual setting.",
                "datetime": datetime_str,
            }
        elif platform.system() == "Windows":
            # On Windows, use 'date' and 'time' commands
            # Note: This may require admin privileges
            date_cmd = f'date {date.replace("-", "/")}'
            time_cmd = f"time {time}"

            result1 = subprocess.run(
                date_cmd, shell=True, capture_output=True, text=True, timeout=5
            )
            result2 = subprocess.run(
                time_cmd, shell=True, capture_output=True, text=True, timeout=5
            )

            if result1.returncode != 0 or result2.returncode != 0:
                return {
                    "success": False,
                    "error": "Failed to set system time on Windows. May require admin privileges.",
                    "message": "Could not set system time. Run as administrator.",
                }

            return {
                "success": True,
                "message": f"System time set to {datetime_str}",
                "datetime": datetime_str,
            }
        else:
            return {
                "success": False,
                "error": f"Setting system time not supported on {platform.system()}",
                "message": "System time setting is only supported on Linux and Windows.",
            }

    except ValueError as e:
        return {
            "success": False,
            "error": f"Invalid date or time format: {str(e)}",
            "message": "Date must be YYYY-MM-DD and time must be HH:MM:SS",
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Command timed out",
            "message": "Setting system time timed out. Please try again.",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "An error occurred while setting system time.",
        }


@app.post("/api/system/time/sync/disable", dependencies=[Depends(require_admin_access)])
async def disable_ntp_sync():
    """
    Disable NTP synchronization to allow manual time setting.
    """
    try:
        if platform.system() == "Linux":
            result = subprocess.run(
                ["sudo", "timedatectl", "set-ntp", "false"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return {
                    "success": True,
                    "message": "NTP synchronization disabled. Manual time setting is now active.",
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr or "Failed to disable NTP",
                    "message": "Could not disable NTP sync. Manual time may be overridden.",
                }
        return {"success": True, "message": "NTP sync disabled"}
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Error disabling NTP sync",
        }


@app.post("/api/system/time/sync", dependencies=[Depends(require_admin_access)])
async def sync_system_time():
    """
    Automatically synchronize system time using NTP.
    Requires internet connection.
    """
    try:
        if platform.system() == "Linux":
            # Use timedatectl to sync with NTP
            result = subprocess.run(
                ["sudo", "timedatectl", "set-ntp", "true"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                # Try alternative: ntpdate (if available)
                try:
                    result2 = subprocess.run(
                        ["sudo", "ntpdate", "-s", "pool.ntp.org"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result2.returncode == 0:
                        # Sync hardware clock
                        subprocess.run(
                            ["sudo", "hwclock", "--systohc"], timeout=5, check=False
                        )
                        return {
                            "success": True,
                            "message": "Time synchronized with NTP servers",
                        }
                except Exception:
                    logger.debug("ntpdate fallback failed", exc_info=True)

                return {
                    "success": False,
                    "error": result.stderr or "Failed to sync time with NTP",
                    "message": "Could not synchronize time. Ensure NTP is configured or try manual time setting.",
                }

            # Sync hardware clock
            try:
                subprocess.run(["sudo", "hwclock", "--systohc"], timeout=5, check=False)
            except Exception:
                logger.debug("Ignoring hwclock sync failure after NTP enable", exc_info=True)

            return {
                "success": True,
                "message": "Time synchronization enabled. System will sync with NTP servers.",
            }

        elif platform.system() == "Windows":
            # On Windows, use w32tm to sync
            result = subprocess.run(
                ["w32tm", "/resync"],
                shell=True,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": result.stderr or "Failed to sync time",
                    "message": "Could not synchronize time. May require admin privileges.",
                }

            return {
                "success": True,
                "message": "Time synchronized with Windows Time service",
            }

        else:
            return {
                "success": False,
                "error": f"Time sync not supported on {platform.system()}",
                "message": "Automatic time synchronization is only supported on Linux and Windows.",
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Command timed out",
            "message": "Time synchronization timed out. Please try again.",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "An error occurred while synchronizing time.",
        }


# --- SSH MANAGEMENT API ---


@app.get("/api/system/version")
async def get_current_version():
    """
    Get the current version identifier without checking for updates.
    """
    try:
        project_root = _get_project_root()
        install_mode = _get_install_mode(project_root)

        if install_mode == "production":
            version_file = project_root / ".version"
            if version_file.exists():
                version_text = version_file.read_text(encoding="utf-8").strip()
                if version_text:
                    return {
                        "version": version_text,
                        "install_mode": install_mode,
                        "can_convert_to_production": False,
                    }
            return {
                "version": "unknown",
                "install_mode": install_mode,
                "can_convert_to_production": False,
            }

        # Development clones report the current git commit.
        # If a stale .version exists alongside .git, the install still behaves as dev.
        current_commit_result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5,
        )

        current_commit = (
            current_commit_result.stdout.strip()
            if current_commit_result.returncode == 0
            else "unknown"
        )

        return {
            "version": current_commit,
            "install_mode": install_mode,
            "can_convert_to_production": True,
        }

    except Exception as e:
        return {
            "version": "unknown",
            "install_mode": "unknown",
            "can_convert_to_production": False,
            "error": str(e),
        }


def _get_project_root() -> Path:
    """Return the project root directory (parent of app/)."""
    return Path(__file__).parent.parent


def _get_install_mode(project_root: Optional[Path] = None) -> str:
    root = project_root or _get_project_root()
    return "development" if (root / ".git").exists() else "production"


def _get_release_channel() -> str:
    channel = str(getattr(settings, "release_channel", "stable") or "stable").strip().lower()
    return "beta" if channel == "beta" else "stable"


def _should_include_prereleases() -> bool:
    return _get_release_channel() == "beta"


def _parse_semver_tag(tag_name: object) -> Optional[tuple[int, int, int, tuple[str, ...]]]:
    tag = str(tag_name or "").strip()
    match = SEMVER_TAG_RE.match(tag)
    if not match:
        return None

    prerelease = match.group("prerelease")
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        tuple(prerelease.split(".")) if prerelease else (),
    )


def _compare_prerelease_identifiers(left: str, right: str) -> int:
    left_is_numeric = left.isdigit()
    right_is_numeric = right.isdigit()

    if left_is_numeric and right_is_numeric:
        left_num = int(left)
        right_num = int(right)
        return (left_num > right_num) - (left_num < right_num)

    if left_is_numeric != right_is_numeric:
        return -1 if left_is_numeric else 1

    return (left > right) - (left < right)


def _compare_semver_tags(
    left: tuple[int, int, int, tuple[str, ...]],
    right: tuple[int, int, int, tuple[str, ...]],
) -> int:
    left_core = left[:3]
    right_core = right[:3]
    if left_core != right_core:
        return (left_core > right_core) - (left_core < right_core)

    left_prerelease = left[3]
    right_prerelease = right[3]
    if not left_prerelease and not right_prerelease:
        return 0
    if not left_prerelease:
        return 1
    if not right_prerelease:
        return -1

    for left_part, right_part in zip(left_prerelease, right_prerelease):
        comparison = _compare_prerelease_identifiers(left_part, right_part)
        if comparison:
            return comparison

    return (len(left_prerelease) > len(right_prerelease)) - (
        len(left_prerelease) < len(right_prerelease)
    )


def _is_release_newer_than_current(latest_version: str, current_version: str) -> bool:
    latest_semver = _parse_semver_tag(latest_version)
    current_semver = _parse_semver_tag(current_version)
    if latest_semver and current_semver:
        return _compare_semver_tags(latest_semver, current_semver) > 0
    return latest_version != current_version


def _select_release_from_list(
    releases: object,
    *,
    include_prerelease: bool,
) -> Dict[str, object]:
    if not isinstance(releases, list):
        raise RuntimeError("Release server returned an unexpected response.")

    target_lane = "stable or beta" if include_prerelease else "stable"
    best_release: Optional[Dict[str, object]] = None
    best_version: Optional[tuple[int, int, int, tuple[str, ...]]] = None

    for release_data in releases:
        if not isinstance(release_data, dict):
            continue
        if release_data.get("draft"):
            continue

        is_prerelease = bool(release_data.get("prerelease"))
        if is_prerelease and not include_prerelease:
            continue

        version = _parse_semver_tag(release_data.get("tag_name"))
        if not version:
            continue

        if best_version is None or _compare_semver_tags(version, best_version) > 0:
            best_release = release_data
            best_version = version

    if best_release is not None:
        return best_release

    raise RuntimeError(f"No published {target_lane} releases are available.")


def _fetch_release_data(
    release_repo: str,
    *,
    release_tag: str = "",
    include_prerelease: bool = False,
) -> Dict[str, object]:
    import requests

    if release_tag:
        release_path = f"releases/tags/{release_tag}"
        release_resp = requests.get(
            f"https://api.github.com/repos/{release_repo}/{release_path}",
            headers={"User-Agent": "PC-1-OTA-Updater"},
            timeout=10,
        )
        release_resp.raise_for_status()
        return release_resp.json()

    release_resp = requests.get(
        f"https://api.github.com/repos/{release_repo}/releases",
        headers={"User-Agent": "PC-1-OTA-Updater"},
        timeout=10,
    )
    release_resp.raise_for_status()
    return _select_release_from_list(
        release_resp.json(),
        include_prerelease=include_prerelease,
    )


def _get_release_bundle_metadata(
    release_repo: str,
    *,
    release_tag: str = "",
    include_prerelease: bool = False,
) -> Dict[str, str]:
    release_data = _fetch_release_data(
        release_repo,
        release_tag=release_tag,
        include_prerelease=include_prerelease,
    )

    tag_name = (release_data.get("tag_name") or "").strip()
    if not tag_name:
        raise RuntimeError("Release metadata did not include tag_name")

    assets = release_data.get("assets") or []
    preferred_asset_name = f"pc1-{tag_name}.tar.gz"
    checksum_asset_name = f"pc1-{tag_name}.sha256"

    tar_asset = next(
        (asset for asset in assets if asset.get("name") == preferred_asset_name),
        None,
    )
    if not tar_asset:
        raise RuntimeError(
            "Latest release is missing the required production bundle asset "
            f"'{preferred_asset_name}'."
        )

    checksum_asset = next(
        (asset for asset in assets if asset.get("name") == checksum_asset_name),
        None,
    )
    aggregate_checksum_asset = next(
        (
            asset
            for asset in assets
            if str(asset.get("name", "")).lower() in {"sha256sums", "sha256sums.txt"}
        ),
        None,
    )

    tarball_url = (tar_asset.get("browser_download_url") or "").strip()
    tarball_name = str(tar_asset.get("name") or "").strip()
    if not tarball_url:
        raise RuntimeError("Release bundle metadata did not include a download URL")

    checksum_url = (
        (checksum_asset.get("browser_download_url") or "").strip()
        if checksum_asset
        else ""
    )
    aggregate_checksum_url = (
        (aggregate_checksum_asset.get("browser_download_url") or "").strip()
        if aggregate_checksum_asset
        else ""
    )

    return {
        "tag_name": tag_name,
        "tarball_name": tarball_name,
        "tarball_url": tarball_url,
        "checksum_url": checksum_url,
        "aggregate_checksum_url": aggregate_checksum_url,
    }


def _extract_expected_sha_from_checksum_text(
    checksum_text: str, tarball_name: str
) -> str:
    for raw_line in checksum_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) == 1 and len(parts[0]) >= 64:
            return parts[0].strip().lower()
        if len(parts) >= 2 and parts[-1].lstrip("*") == tarball_name:
            return parts[0].strip().lower()
    return ""


def _install_release_bundle(
    project_root: Path,
    release_repo: str,
    *,
    expected_sha: str = "",
    release_tag: str = "",
    include_prerelease: bool = False,
) -> str:
    import hashlib
    import requests
    import tarfile
    import tempfile

    release_meta = _get_release_bundle_metadata(
        release_repo,
        release_tag=release_tag,
        include_prerelease=include_prerelease,
    )
    tag_name = release_meta["tag_name"]
    tarball_name = release_meta["tarball_name"]
    tarball_url = release_meta["tarball_url"]

    with tempfile.TemporaryDirectory(prefix="pc1-update-") as tmp_dir:
        tar_path = Path(tmp_dir) / tarball_name
        sha256 = hashlib.sha256()

        with requests.get(
            tarball_url,
            headers={"User-Agent": "PC-1-OTA-Updater"},
            timeout=20,
            stream=True,
        ) as download_resp:
            download_resp.raise_for_status()
            with open(tar_path, "wb") as tar_file:
                for chunk in download_resp.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    tar_file.write(chunk)
                    sha256.update(chunk)

        resolved_expected_sha = (expected_sha or "").strip().lower()
        if not resolved_expected_sha:
            checksum_candidates = [
                release_meta["checksum_url"],
                release_meta["aggregate_checksum_url"],
            ]
            for checksum_url in checksum_candidates:
                if not checksum_url:
                    continue
                checksum_resp = requests.get(
                    checksum_url,
                    headers={"User-Agent": "PC-1-OTA-Updater"},
                    timeout=10,
                )
                if not checksum_resp.ok:
                    continue
                resolved_expected_sha = _extract_expected_sha_from_checksum_text(
                    checksum_resp.text,
                    tarball_name,
                )
                if resolved_expected_sha:
                    break

        actual_sha = sha256.hexdigest().lower()
        if resolved_expected_sha and actual_sha != resolved_expected_sha:
            raise RuntimeError("SHA256 mismatch for downloaded update package")

        extract_dir = Path(tmp_dir) / "extract"
        extract_dir.mkdir(parents=True, exist_ok=True)

        with tarfile.open(tar_path, "r:gz") as tar:
            def _is_within_directory(directory: Path, target: Path) -> bool:
                abs_directory = directory.resolve()
                abs_target = target.resolve()
                return str(abs_target).startswith(str(abs_directory))

            for member in tar.getmembers():
                member_path = extract_dir / member.name
                if not _is_within_directory(extract_dir, member_path):
                    raise ValueError("Update package contains invalid file paths")
            tar.extractall(extract_dir)

        extracted_items = [p for p in extract_dir.iterdir()]
        source_dir = (
            extracted_items[0]
            if len(extracted_items) == 1 and extracted_items[0].is_dir()
            else extract_dir
        )
        _validate_production_update_bundle(source_dir)

        version_file = project_root / ".version"
        config_backup = Path(tmp_dir) / "config.json.backup"
        env_backup = Path(tmp_dir) / ".env.backup"
        config_path = project_root / "config.json"
        env_path = project_root / ".env"

        if config_path.exists():
            shutil.copy2(config_path, config_backup)
        if env_path.exists():
            shutil.copy2(env_path, env_backup)

        excluded = {".git", ".github", "__pycache__", ".venv"}
        for item in source_dir.iterdir():
            if item.name in excluded:
                continue
            dest = project_root / item.name
            if dest.exists():
                if dest.is_dir() and not dest.is_symlink():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        if config_backup.exists():
            shutil.copy2(config_backup, config_path)
        if env_backup.exists():
            shutil.copy2(env_backup, env_path)

        version_file.write_text(tag_name, encoding="utf-8")

    return tag_name


def _restart_pc1_service() -> None:
    if platform.system() != "Linux":
        return

    subprocess.run(
        ["sudo", "systemctl", "reset-failed", "pc-1.service"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    restart_result = subprocess.run(
        ["sudo", "systemctl", "restart", "pc-1.service"],
        capture_output=True,
        text=True,
        timeout=15,
    )

    # systemctl restart returns 0 on success, but even if it returns non-zero,
    # the service might still restart. Check the actual service status instead.
    if restart_result.returncode != 0:
        time.sleep(3)
        status_result = subprocess.run(
            ["systemctl", "is-active", "pc-1.service"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if (
            status_result.returncode == 0
            and status_result.stdout.strip() == "active"
        ):
            pass

    time.sleep(1)


@app.get("/api/system/updates/check")
async def check_for_updates():
    """
    Check if there are updates available from the remote repository.
    Returns user-friendly status information.
    """
    try:
        import subprocess
        from pathlib import Path

        # Get the project root directory (parent of app/)
        project_root = Path(__file__).parent.parent

        # Development mode: use git-based compare
        if (project_root / ".git").exists():
            # Get current branch
            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if branch_result.returncode != 0:
                return {
                    "available": False,
                    "message": "Could not determine current branch",
                    "error": branch_result.stderr,
                }

            current_branch = branch_result.stdout.strip()

            # Get current commit hash (short)
            current_commit_result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=5,
            )

            current_commit = (
                current_commit_result.stdout.strip()
                if current_commit_result.returncode == 0
                else "unknown"
            )

            # Fetch from origin (without pulling)
            fetch_result = subprocess.run(
                ["git", "fetch", "origin", current_branch],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if fetch_result.returncode != 0:
                return {
                    "available": False,
                    "message": "Could not check for updates",
                    "error": "Unable to connect to the update server. Check your internet connection.",
                    "current_commit": current_commit,
                }

            # Compare local vs remote
            local_commit_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            remote_commit_result = subprocess.run(
                ["git", "rev-parse", f"origin/{current_branch}"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if local_commit_result.returncode != 0 or remote_commit_result.returncode != 0:
                return {
                    "available": False,
                    "message": "Could not compare versions",
                    "error": "Unable to determine version information.",
                }

            local_commit = local_commit_result.stdout.strip()
            remote_commit = remote_commit_result.stdout.strip()

            # Check if there are updates
            if local_commit == remote_commit:
                return {
                    "available": False,
                    "up_to_date": True,
                    "message": "You're on the latest version",
                    "current_version": current_commit,
                }

            # Count commits behind
            behind_result = subprocess.run(
                [
                    "git",
                    "rev-list",
                    "--count",
                    f"{local_commit}..origin/{current_branch}",
                ],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            commits_behind = (
                int(behind_result.stdout.strip())
                if behind_result.returncode == 0
                else 0
            )

            latest_version_result = subprocess.run(
                ["git", "rev-parse", "--short", f"origin/{current_branch}"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            latest_version = (
                latest_version_result.stdout.strip()
                if latest_version_result.returncode == 0
                else "unknown"
            )

            return {
                "available": True,
                "up_to_date": False,
                "message": (
                    "New update available!"
                    if commits_behind > 0
                    else "Update available"
                ),
                "commits_behind": commits_behind,
                "current_version": current_commit,
                "latest_version": latest_version,
            }

        # Production mode: use GitHub releases and .version marker
        release_repo = os.environ.get("PC1_UPDATE_GITHUB_REPO", "travmiller/paper-console")
        release_channel = _get_release_channel()
        current_version = "unknown"
        version_file = project_root / ".version"
        if version_file.exists():
            version_text = version_file.read_text(encoding="utf-8").strip()
            if version_text:
                current_version = version_text

        try:
            release_data = _fetch_release_data(
                release_repo,
                include_prerelease=_should_include_prereleases(),
            )
        except RuntimeError as e:
            return {
                "available": False,
                "message": "Could not check for updates",
                "error": str(e),
                "current_version": current_version,
                "release_channel": release_channel,
            }
        except Exception:
            return {
                "available": False,
                "message": "Could not check for updates",
                "error": "Unable to reach the release server.",
                "current_version": current_version,
                "release_channel": release_channel,
            }

        latest_version = (release_data.get("tag_name") or "").strip() or "unknown"
        if latest_version == "unknown":
            return {
                "available": False,
                "message": "Could not compare versions",
                "error": "Unable to determine version information.",
                "current_version": current_version,
                "release_channel": release_channel,
            }

        if not _is_release_newer_than_current(latest_version, current_version):
            return {
                "available": False,
                "up_to_date": True,
                "message": "You're on the latest version",
                "current_version": current_version,
                "latest_version": latest_version,
                "release_channel": release_channel,
            }

        return {
            "available": True,
            "up_to_date": False,
            "message": "New update available!",
            "commits_behind": 1,
            "current_version": current_version,
            "latest_version": latest_version,
            "release_channel": release_channel,
        }

    except subprocess.TimeoutExpired:
        return {
            "available": False,
            "message": "Update check timed out",
            "error": "The update check took too long. Please try again.",
        }
    except Exception as e:
        return {
            "available": False,
            "message": "Could not check for updates",
            "error": f"Something went wrong: {str(e)}",
        }


def _update_requirements_path(project_root: Path, is_dev: bool) -> Path:
    pi_requirements = project_root / "requirements-pi.txt"
    if not is_dev and pi_requirements.exists():
        return pi_requirements
    return project_root / "requirements.txt"


def _ensure_update_virtualenv(project_root: Path) -> Path:
    venv_dir = project_root / ".venv"
    venv_python = venv_dir / "bin" / "python"
    if venv_python.exists():
        return venv_python

    bootstrap_python = shutil.which("python3") or sys.executable
    logger.warning(
        "Update install missing repo virtualenv; recreating %s using %s",
        venv_dir,
        bootstrap_python,
    )

    create_result = subprocess.run(
        [bootstrap_python, "-m", "venv", str(venv_dir)],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if create_result.returncode != 0 or not venv_python.exists():
        detail = (create_result.stderr or create_result.stdout or "").strip()[:500]
        raise RuntimeError(
            "Could not create application virtual environment"
            + (f": {detail}" if detail else "")
        )

    return venv_python


def _install_update_dependencies(
    project_root: Path, is_dev: bool
) -> subprocess.CompletedProcess:
    requirements_path = _update_requirements_path(project_root, is_dev)
    if not requirements_path.exists():
        raise RuntimeError(f"Missing dependency file: {requirements_path.name}")

    python_exec = _ensure_update_virtualenv(project_root)
    return subprocess.run(
        [str(python_exec), "-m", "pip", "install", "-r", str(requirements_path)],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=300,  # 5 minutes specifically for slow installs on Pi
    )


def _validate_production_update_bundle(source_dir: Path) -> None:
    required_paths = [
        source_dir / "web" / "dist" / "index.html",
        source_dir / "run.sh",
        source_dir / "app",
    ]
    missing = [path for path in required_paths if not path.exists()]
    if missing:
        missing_list = ", ".join(str(path.relative_to(source_dir)) for path in missing)
        raise RuntimeError(
            "Production update bundle is missing required runtime assets: "
            f"{missing_list}"
        )


@app.post("/api/system/updates/install", dependencies=[Depends(require_admin_access)])
async def install_updates():
    """
    Install available updates and restart the service.
    """
    try:
        project_root = _get_project_root()

        # Check if we're running from a git clone (dev mode)
        is_dev = (project_root / ".git").exists()

        # If in dev mode, keep the old git pull logic for convenience
        if is_dev:
            # Get current branch
            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if branch_result.returncode != 0:
                return {
                    "success": False,
                    "message": "Could not determine current branch",
                    "error": branch_result.stderr,
                }

            current_branch = branch_result.stdout.strip()

            # Pull latest changes
            pull_result = subprocess.run(
                ["git", "pull", "origin", current_branch],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if pull_result.returncode != 0:
                return {
                    "success": False,
                    "message": "Update failed",
                    "error": pull_result.stderr or "Could not pull latest changes",
                }
        else:
            # Production OTA flow (release tarball download)
            release_repo = os.environ.get(
                "PC1_UPDATE_GITHUB_REPO", "travmiller/paper-console"
            ).strip()
            expected_sha = os.environ.get("PC1_UPDATE_TARBALL_SHA256", "").strip().lower()

            try:
                _install_release_bundle(
                    project_root,
                    release_repo,
                    expected_sha=expected_sha,
                    include_prerelease=_should_include_prereleases(),
                )
            except Exception as e:
                logger.exception("Production OTA install failed")
                return {
                    "success": False,
                    "message": "OTA Download/Extract failed",
                    "error": str(e),
                }

        # Recreate the repo venv if needed and install dependencies there before restart.
        install_result = _install_update_dependencies(project_root, is_dev=is_dev)

        if install_result.returncode != 0:
            logger.error(
                "Dependency install after update failed: %s",
                (install_result.stderr or install_result.stdout or "").strip()[:500],
            )
            return {
                "success": False,
                "message": "Update failed",
                "error": "Dependency installation failed. The running service was left unchanged.",
            }

        # Dev-mode convenience only: production releases must ship prebuilt web assets.
        web_dir = project_root / "web"
        if is_dev and web_dir.exists() and (web_dir / "package.json").exists():
            npm_exec = shutil.which("npm")
            if not npm_exec:
                logger.info(
                    "Skipping optional dev UI rebuild during update because npm is unavailable"
                )
            else:
                npm_ci_result = subprocess.run(
                    [npm_exec, "ci"],
                    cwd=web_dir,
                    capture_output=True,
                    timeout=120,
                    check=False,
                )
                if npm_ci_result.returncode != 0:
                    logger.warning(
                        "Optional UI npm ci failed during update: %s",
                        (npm_ci_result.stderr or npm_ci_result.stdout or "").strip()[
                            :500
                        ],
                    )
                npm_build_result = subprocess.run(
                    [npm_exec, "run", "build"],
                    cwd=web_dir,
                    capture_output=True,
                    timeout=120,
                    check=False,
                )
                if npm_build_result.returncode != 0:
                    logger.warning(
                        "Optional UI build failed during update: %s",
                        (npm_build_result.stderr or npm_build_result.stdout or "").strip()[
                            :500
                        ],
                    )

        # Restart the service
        _restart_pc1_service()

        return {
            "success": True,
            "message": "Update installed successfully!",
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "Update timed out",
            "error": "The update process took too long. Please try again.",
        }
    except Exception as e:
        return {
            "success": False,
            "message": "Update failed",
            "error": str(e),
        }


@app.post(
    "/api/system/updates/convert-to-production",
    dependencies=[Depends(require_admin_access)],
)
async def convert_to_production_updates():
    """Convert a git-clone install into a production OTA install."""
    try:
        project_root = _get_project_root()
        if not (project_root / ".git").exists():
            return {
                "success": False,
                "message": "This unit already uses production OTA updates.",
            }

        release_repo = os.environ.get(
            "PC1_UPDATE_GITHUB_REPO", "travmiller/paper-console"
        ).strip()
        expected_sha = os.environ.get("PC1_UPDATE_TARBALL_SHA256", "").strip().lower()

        try:
            tag_name = _install_release_bundle(
                project_root,
                release_repo,
                expected_sha=expected_sha,
                include_prerelease=_should_include_prereleases(),
            )
        except Exception as e:
            logger.exception("Production conversion failed")
            return {
                "success": False,
                "message": "Conversion failed",
                "error": str(e),
            }

        install_result = _install_update_dependencies(project_root, is_dev=False)
        if install_result.returncode != 0:
            logger.error(
                "Dependency install after production conversion failed: %s",
                (install_result.stderr or install_result.stdout or "").strip()[:500],
            )
            return {
                "success": False,
                "message": "Conversion failed",
                "error": "Dependency installation failed. The running service was left unchanged.",
            }

        git_dir = project_root / ".git"
        if git_dir.exists():
            shutil.rmtree(git_dir)

        _restart_pc1_service()

        return {
            "success": True,
            "message": f"Converted to production updates using {tag_name}.",
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "Conversion timed out",
            "error": "The conversion process took too long. Please try again.",
        }
    except Exception as e:
        return {
            "success": False,
            "message": "Conversion failed",
            "error": str(e),
        }


@app.get("/api/system/ssh/status")
async def get_ssh_status():
    """
    Get SSH service status and configuration.
    """
    try:
        if platform.system() != "Linux":
            return {
                "enabled": False,
                "available": False,
                "message": "SSH management is only available on Linux systems",
            }

        # Check if SSH service is enabled
        result = subprocess.run(
            ["systemctl", "is-enabled", "ssh"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        service_enabled = result.returncode == 0 and result.stdout.strip() in (
            "enabled",
            "enabled-runtime",
        )

        # Check if SSH service is active
        result_active = subprocess.run(
            ["systemctl", "is-active", "ssh"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        service_active = (
            result_active.returncode == 0 and result_active.stdout.strip() == "active"
        )

        # Get current username
        username = _get_system_username()

        # Get current IP address (useful as a fallback when mDNS is flaky)
        ip_address = wifi_manager.get_wifi_status().get("ip")

        # Check if raspi-config SSH is enabled (if on Raspberry Pi)
        raspi_ssh_enabled = None
        if _is_raspberry_pi:
            try:
                result_raspi = subprocess.run(
                    ["raspi-config", "nonint", "get_ssh"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                # raspi-config returns 0 if enabled, 1 if disabled
                raspi_ssh_enabled = result_raspi.returncode == 0
            except Exception:
                logger.debug("raspi-config SSH status probe failed", exc_info=True)

        return {
            "enabled": service_enabled,
            "active": service_active,
            "available": True,
            "username": username,
            "ip_address": ip_address,
            "raspi_config_enabled": raspi_ssh_enabled,
        }

    except Exception as e:
        return {
            "enabled": False,
            "active": False,
            "available": False,
            "error": str(e),
            "message": "Could not check SSH status",
        }


@app.post("/api/system/ssh/enable", dependencies=[Depends(require_admin_access)])
async def enable_ssh():
    """
    Enable SSH service.
    """
    try:
        if platform.system() != "Linux":
            return {
                "success": False,
                "message": "SSH management is only available on Linux systems",
            }

        # Enable SSH via systemctl
        result = subprocess.run(
            ["sudo", "systemctl", "enable", "ssh"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": result.stderr,
                "message": "Failed to enable SSH service",
            }

        # Start SSH service if not running
        subprocess.run(
            ["sudo", "systemctl", "start", "ssh"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Also enable via raspi-config if on Raspberry Pi
        if _is_raspberry_pi:
            try:
                subprocess.run(
                    ["sudo", "raspi-config", "nonint", "do_ssh", "0"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except Exception:
                logger.debug("raspi-config SSH enable command failed", exc_info=True)

        return {
            "success": True,
            "message": "SSH service enabled successfully",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Error enabling SSH service",
        }


@app.post("/api/system/ssh/disable", dependencies=[Depends(require_admin_access)])
async def disable_ssh():
    """
    Disable SSH service.
    """
    try:
        if platform.system() != "Linux":
            return {
                "success": False,
                "message": "SSH management is only available on Linux systems",
            }

        # Stop SSH service
        subprocess.run(
            ["sudo", "systemctl", "stop", "ssh"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Disable SSH service
        result = subprocess.run(
            ["sudo", "systemctl", "disable", "ssh"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": result.stderr,
                "message": "Failed to disable SSH service",
            }

        # Also disable via raspi-config if on Raspberry Pi
        if _is_raspberry_pi:
            try:
                subprocess.run(
                    ["sudo", "raspi-config", "nonint", "do_ssh", "1"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except Exception:
                logger.debug("raspi-config SSH disable command failed", exc_info=True)

        return {
            "success": True,
            "message": "SSH service disabled successfully",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Error disabling SSH service",
        }


def _get_system_username() -> str:
    return os.environ.get("USER") or os.environ.get("USERNAME") or "admin"


def _sync_device_password_to_system_user(new_password: str) -> Dict[str, object]:
    if platform.system() != "Linux":
        return {
            "synced": False,
            "username": None,
            "message": "System password sync is only available on Linux systems",
        }

    if not device_password.is_device_managed():
        return {
            "synced": False,
            "username": None,
            "message": "System password sync is disabled for unmanaged builds",
        }

    username = _get_system_username()
    password_input = f"{username}:{new_password}\n"
    result = subprocess.run(
        ["sudo", "chpasswd"],
        input=password_input,
        capture_output=True,
        text=True,
        timeout=10,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Failed to sync the Linux login password. Ensure the application has sudo privileges."
        )

    return {
        "synced": True,
        "username": username,
        "message": f"SSH login for '{username}' now uses the Device Password",
    }


def _restart_ap_mode_after_device_password_change() -> None:
    try:
        time.sleep(1)
        wifi_manager.stop_ap_mode()
        time.sleep(1)
        wifi_manager.start_ap_mode(retries=2)
    except Exception:
        logger.exception("Failed to restart AP mode after Device Password change")


class DevicePasswordChange(BaseModel):
    current_password: str
    new_password: str


@app.get("/api/system/device-password/status")
async def get_device_password_status():
    managed = device_password.is_device_managed()
    can_change = device_password.can_change_device_password()
    source = device_password.get_device_password_source()

    if source == "managed_file":
        status_label = "Managed on Device"
        message = (
            "Changing the Device Password updates settings login, setup WiFi, printed setup instructions, and SSH access."
        )
    elif source == "managed_fallback":
        status_label = "Built-in Device Password"
        message = (
            "This PC-1 is using its built-in Device Password. Managed password storage has not been provisioned on this unit yet, "
            "so password changes and SSH sync are not available from settings."
        )
    elif source == "file":
        status_label = "Stored Locally"
        message = (
            "This build is using a locally stored Device Password file outside the managed device provisioning flow."
        )
    elif source == "env":
        status_label = "Development Override"
        message = (
            "This build is using a development Device Password override from the environment."
        )
    else:
        status_label = "Fallback Password"
        message = (
            "This build is using a fallback Device Password derived from the local machine."
        )

    return {
        "managed": managed,
        "can_change": can_change,
        "source": source,
        "status_label": status_label,
        "password_label": "Device Password",
        "ssh_sync_enabled": platform.system() == "Linux" and can_change,
        "ssh_username": _get_system_username() if platform.system() == "Linux" else None,
        "message": message,
    }


@app.post("/api/system/device-password", dependencies=[Depends(require_admin_access)])
async def change_device_password(
    password_data: DevicePasswordChange,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
):
    """Change the canonical Device Password used by settings, setup WiFi, and SSH."""
    try:
        if not device_password.can_change_device_password():
            return {
                "success": False,
                "message": "Device Password changes are only available on managed PC-1 devices",
            }

        current_password = (password_data.current_password or "").strip()
        new_password = (password_data.new_password or "").strip()

        if not current_password or not verify_admin_password(current_password):
            return {
                "success": False,
                "message": "Current Device Password is incorrect",
            }

        if len(new_password) < 8:
            return {
                "success": False,
                "message": "Device Password must be at least 8 characters long",
            }

        if hmac.compare_digest(current_password, new_password):
            return {
                "success": False,
                "message": "New Device Password must be different from the current one",
            }

        previous_password = device_password.get_device_password()
        ap_mode_was_active = wifi_manager.is_ap_mode_active()

        try:
            device_password.set_device_password(new_password)
        except Exception as exc:
            return {
                "success": False,
                "error": str(exc),
                "message": "Failed to persist the new Device Password",
            }

        try:
            sync_result = _sync_device_password_to_system_user(new_password)
        except Exception as exc:
            try:
                device_password.set_device_password(previous_password)
            except Exception:
                logger.exception(
                    "Failed to restore the previous Device Password after SSH sync failure"
                )
                return {
                    "success": False,
                    "error": str(exc),
                    "message": "Failed to sync SSH access and could not restore the previous Device Password",
                }
            return {
                "success": False,
                "error": str(exc),
                "message": str(exc),
            }

        if ap_mode_was_active:
            background_tasks.add_task(_restart_ap_mode_after_device_password_change)

        clear_admin_session_cookie(
            response,
            secure=request.url.scheme == "https",
        )

        message_parts = ["Device Password changed successfully."]
        if sync_result.get("synced") and sync_result.get("message"):
            message_parts.append(sync_result["message"] + ".")
        if ap_mode_was_active:
            message_parts.append(
                "Setup WiFi is restarting. Reconnect using the new Device Password."
            )

        return {
            "success": True,
            "message": " ".join(message_parts),
            "reauth_required": True,
            "ssh_password_synced": bool(sync_result.get("synced")),
            "username": sync_result.get("username"),
            "ap_mode_restarting": ap_mode_was_active,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Error changing Device Password",
        }


# --- LOCATION SEARCH API ---


@app.get("/api/location/system-default")
async def get_system_default_location():
    """
    Get default location based on system timezone.
    Reads the system timezone and suggests a location in that timezone.
    """
    try:
        system_timezone = None

        if platform.system() == "Linux":
            # Try timedatectl first (most reliable)
            try:
                result = subprocess.run(
                    ["timedatectl", "show", "-p", "Timezone", "--value"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    system_timezone = result.stdout.strip()
            except Exception:
                logger.debug("timedatectl system-default lookup failed", exc_info=True)

            # Fallback to /etc/timezone
            if not system_timezone:
                try:
                    with open("/etc/timezone", "r") as f:
                        system_timezone = f.read().strip()
                except Exception:
                    logger.debug("/etc/timezone system-default lookup failed", exc_info=True)

        # Fallback to environment variable
        if not system_timezone:
            system_timezone = os.environ.get("TZ")

        if not system_timezone:
            return {
                "found": False,
                "message": "Could not detect system timezone",
            }

        # Find a default location for this timezone
        # Use major cities in each timezone as defaults
        timezone_to_default_location = {
            "America/New_York": {"city": "New York", "state": "NY", "zipcode": "10001"},
            "America/Chicago": {"city": "Chicago", "state": "IL", "zipcode": "60601"},
            "America/Denver": {"city": "Denver", "state": "CO", "zipcode": "80201"},
            "America/Phoenix": {"city": "Phoenix", "state": "AZ", "zipcode": "85001"},
            "America/Los_Angeles": {
                "city": "Los Angeles",
                "state": "CA",
                "zipcode": "90001",
            },
            "America/Anchorage": {
                "city": "Anchorage",
                "state": "AK",
                "zipcode": "99501",
            },
            "Pacific/Honolulu": {"city": "Honolulu", "state": "HI", "zipcode": "96801"},
            "America/Puerto_Rico": {
                "city": "San Juan",
                "state": "PR",
                "zipcode": "00901",
            },
        }

        # Try exact match first
        default = timezone_to_default_location.get(system_timezone)

        # If no exact match, try to find any location in the timezone
        if not default:
            # Search for locations in the timezone by looking up a common city
            # We'll use the timezone name to infer a location
            timezone_parts = system_timezone.split("/")
            if len(timezone_parts) >= 2:
                location_name = timezone_parts[-1].replace("_", " ")
                # Try searching for the location name
                results = location_lookup.search_locations(location_name, limit=1)
                if results:
                    result = results[0]
                    return {
                        "found": True,
                        "timezone": system_timezone,
                        "location": {
                            "name": result["name"],
                            "city": result["city"],
                            "state": result["state"],
                            "zipcode": result["zipcode"],
                            "latitude": result["latitude"],
                            "longitude": result["longitude"],
                            "timezone": result["timezone"],
                        },
                    }

            return {
                "found": False,
                "timezone": system_timezone,
                "message": f"Found timezone {system_timezone} but no default location available",
            }

        # Get full location details for the default
        location_result = location_lookup.get_location_by_zip(default["zipcode"])
        if location_result:
            return {
                "found": True,
                "timezone": system_timezone,
                "location": {
                    "name": location_result["name"],
                    "city": location_result["city"],
                    "state": location_result["state"],
                    "zipcode": location_result["zipcode"],
                    "latitude": location_result["latitude"],
                    "longitude": location_result["longitude"],
                    "timezone": location_result["timezone"],
                },
            }
        else:
            # Fallback: create location from default data
            state = default["state"]

            # Import the constants from location_lookup
            from app.location_lookup import STATE_TO_TIMEZONE, STATE_COORDINATES

            # Get timezone and coordinates from state
            timezone = STATE_TO_TIMEZONE.get(state, "America/New_York")
            coords = STATE_COORDINATES.get(state, (40.7128, -74.0060))
            lat, lon = coords

            return {
                "found": True,
                "timezone": system_timezone,
                "location": {
                    "name": default["city"],
                    "city": default["city"],
                    "state": state,
                    "zipcode": default["zipcode"],
                    "latitude": lat,
                    "longitude": lon,
                    "timezone": timezone,
                },
            }

    except Exception as e:
        return {
            "found": False,
            "error": str(e),
            "message": "Error detecting system location",
        }


@app.get("/api/location/search")
async def search_location(q: str, limit: int = 20, use_api: Optional[str] = None):
    """
    Search for locations by city name using the local GeoNames database.
    Returns location data with timezone and coordinates.
    """
    if not q or len(q.strip()) < 2:
        return {"results": []}

    query = q.strip()
    results = []

    # Check if API is requested (default to False - always use local database)
    use_api_enabled = False
    if use_api is not None:
        use_api_enabled = (
            use_api.lower() == "true" if isinstance(use_api, str) else bool(use_api)
        )

    # Try API first if explicitly requested (for future use or testing)
    if use_api_enabled:
        try:
            import requests
            import time
            from concurrent.futures import ThreadPoolExecutor

            # Use Nominatim API (free, no API key required)
            # Rate limit: 1 request per second - we'll respect this
            nominatim_url = "https://nominatim.openstreetmap.org/search"
            params = {
                "q": query,
                "format": "json",
                "limit": limit,
                "addressdetails": 1,
                "countrycodes": "us",  # Focus on US locations
            }
            headers = {
                "User-Agent": "Paper-Console/1.0 (PC-1 Thermal Printer)",  # Required by Nominatim
            }

            # Run blocking network request in thread pool to avoid blocking event loop
            def _fetch_location_api():
                return requests.get(
                    nominatim_url, params=params, headers=headers, timeout=3
                )

            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                response = await loop.run_in_executor(executor, _fetch_location_api)

            if response.status_code == 200:
                api_results = response.json()
                if api_results:
                    # Convert Nominatim results to our format
                    for item in api_results:
                        address = item.get("address", {})
                        city = (
                            address.get("city")
                            or address.get("town")
                            or address.get("village")
                            or address.get("municipality")
                            or ""
                        )
                        # Nominatim provides state_code (2-letter) or state (full name)
                        state = address.get("state_code", "") or address.get(
                            "state", ""
                        )
                        zipcode = address.get("postcode", "")

                        # Convert full state name to abbreviation if needed
                        if state and len(state) > 2:
                            # Map common full state names to abbreviations
                            state_name_to_code = {
                                "Alabama": "AL",
                                "Alaska": "AK",
                                "Arizona": "AZ",
                                "Arkansas": "AR",
                                "California": "CA",
                                "Colorado": "CO",
                                "Connecticut": "CT",
                                "Delaware": "DE",
                                "Florida": "FL",
                                "Georgia": "GA",
                                "Hawaii": "HI",
                                "Idaho": "ID",
                                "Illinois": "IL",
                                "Indiana": "IN",
                                "Iowa": "IA",
                                "Kansas": "KS",
                                "Kentucky": "KY",
                                "Louisiana": "LA",
                                "Maine": "ME",
                                "Maryland": "MD",
                                "Massachusetts": "MA",
                                "Michigan": "MI",
                                "Minnesota": "MN",
                                "Mississippi": "MS",
                                "Missouri": "MO",
                                "Montana": "MT",
                                "Nebraska": "NE",
                                "Nevada": "NV",
                                "New Hampshire": "NH",
                                "New Jersey": "NJ",
                                "New Mexico": "NM",
                                "New York": "NY",
                                "North Carolina": "NC",
                                "North Dakota": "ND",
                                "Ohio": "OH",
                                "Oklahoma": "OK",
                                "Oregon": "OR",
                                "Pennsylvania": "PA",
                                "Rhode Island": "RI",
                                "South Carolina": "SC",
                                "South Dakota": "SD",
                                "Tennessee": "TN",
                                "Texas": "TX",
                                "Utah": "UT",
                                "Vermont": "VT",
                                "Virginia": "VA",
                                "Washington": "WA",
                                "West Virginia": "WV",
                                "Wisconsin": "WI",
                                "Wyoming": "WY",
                                "District of Columbia": "DC",
                                "Puerto Rico": "PR",
                                "Virgin Islands": "VI",
                                "Guam": "GU",
                                "American Samoa": "AS",
                                "Northern Mariana Islands": "MP",
                            }
                            state = state_name_to_code.get(
                                state, state[:2].upper() if len(state) >= 2 else ""
                            )

                        # Only include US locations with city and valid 2-letter state code
                        if city and state and len(state) == 2:
                            # Get timezone from state
                            from app.location_lookup import (
                                STATE_TO_TIMEZONE,
                                STATE_COORDINATES,
                            )

                            timezone = STATE_TO_TIMEZONE.get(state, "America/New_York")
                            coords = STATE_COORDINATES.get(state, (40.7128, -74.0060))

                            # Use actual coordinates from API
                            lat = float(item.get("lat", coords[0]))
                            lon = float(item.get("lon", coords[1]))

                            display_name = f"{city}, {state}"
                            if zipcode:
                                display_name = f"{city}, {state} {zipcode}"

                            result = {
                                "id": f"{zipcode}-{city}-{state}-{item.get('place_id', '')}",
                                "name": display_name,
                                "zipcode": zipcode,
                                "city": city,
                                "state": state,
                                "latitude": lat,
                                "longitude": lon,
                                "timezone": timezone,
                            }
                            results.append(result)

                            if len(results) >= limit:
                                break

                    if results:
                        return {"results": results, "source": "api"}
        except Exception as e:
            # API failed, fall back to local database
            print(f"Location API search failed: {e}, falling back to local database")

    # Fall back to local database (works offline)
    local_results = location_lookup.search_locations(query, limit=limit)
    if local_results:
        return {"results": local_results, "source": "local"}

    return {"results": [], "source": "none"}


# --- MODULE MANAGEMENT API ---


@app.get("/api/module-types")
async def get_module_types():
    """
    Returns all available module types from the registry.

    This endpoint enables the frontend to dynamically discover what module
    types are available without hardcoding them. Each module type includes:
    - id: The module type identifier (e.g., "weather", "quotes")
    - label: Human-readable name for the UI
    - description: Brief description of what the module does
    - icon: Icon name for the UI
    - offline: Whether the module works without internet
    - category: Grouping category for UI organization
    - configSchema: JSON schema for config form generation (optional)
    """
    return {"moduleTypes": list_module_types()}


@app.get("/api/modules", dependencies=[Depends(require_admin_access)])
async def list_modules():
    """List all module instances."""
    return {"modules": settings.modules}


def _normalize_text_module_config(module: ModuleInstance) -> None:
    """Ensure text modules use content_doc and strip legacy markdown content."""
    if module.type != "text":
        return

    config = module.config if isinstance(module.config, dict) else {}

    content_doc = config.get("content_doc")
    is_valid_doc = (
        isinstance(content_doc, dict)
        and content_doc.get("type") == "doc"
        and isinstance(content_doc.get("content"), list)
    )

    if not is_valid_doc:
        legacy_content = config.get("content")
        if isinstance(legacy_content, str) and legacy_content:
            lines = legacy_content.split("\n")
            paragraphs = []
            for line in lines:
                if line.strip():
                    paragraphs.append(
                        {"type": "paragraph", "content": [{"type": "text", "text": line}]}
                    )
                else:
                    paragraphs.append({"type": "paragraph"})
            config["content_doc"] = {
                "type": "doc",
                "content": paragraphs or [{"type": "paragraph"}],
            }
        else:
            config["content_doc"] = {"type": "doc", "content": [{"type": "paragraph"}]}

    config.pop("content", None)
    module.config = config


def _convert_and_resize_image_module_config(module: ModuleInstance) -> None:
    """Compact uploaded image data before storing it in config.json."""
    if module.type != "image" or not module.config:
        return

    image_data = module.config.get("image_data")
    if isinstance(image_data, str) and image_data.startswith("data:"):
        from app.modules.print_image import resize_and_convert_image

        module.config["image_data"] = resize_and_convert_image(image_data)


@app.post("/api/modules", dependencies=[Depends(require_admin_access)])
async def create_module(module: ModuleInstance, background_tasks: BackgroundTasks):
    """Create a new module instance."""
    global settings

    # If no ID provided, generate one
    if not module.id:
        module.id = str(uuid.uuid4())

    _normalize_text_module_config(module)
    _convert_and_resize_image_module_config(module)
    settings.modules[module.id] = module
    background_tasks.add_task(save_settings_background, settings.model_copy(deep=True))

    return {"message": "Module created", "module": module}


@app.get("/api/modules/{module_id}", dependencies=[Depends(require_admin_access)])
async def get_module(module_id: str):
    """Get a specific module instance."""
    module = settings.modules.get(module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    return module


@app.put("/api/modules/{module_id}", dependencies=[Depends(require_admin_access)])
async def update_module(
    module_id: str, module: ModuleInstance, background_tasks: BackgroundTasks
):
    """Update a module instance."""
    global settings
    import app.config as config_module

    if module_id not in settings.modules:
        raise HTTPException(status_code=404, detail="Module not found")

    # Ensure ID matches
    module.id = module_id
    _normalize_text_module_config(module)
    _convert_and_resize_image_module_config(module)
    settings.modules[module_id] = module
    background_tasks.add_task(save_settings_background, settings.model_copy(deep=True))

    # Update module-level reference so modules that access app.config.settings will see the update
    config_module.settings = settings

    return {"message": "Module updated", "module": module}


@app.delete("/api/modules/{module_id}", dependencies=[Depends(require_admin_access)])
async def delete_module(module_id: str, background_tasks: BackgroundTasks):
    """Delete a module instance."""
    global settings

    if module_id not in settings.modules:
        raise HTTPException(status_code=404, detail="Module not found")

    # Check if module is assigned to any channels
    assigned_channels = []
    for pos, channel in settings.channels.items():
        if channel.modules:
            for assignment in channel.modules:
                if assignment.module_id == module_id:
                    assigned_channels.append(pos)

    if assigned_channels:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete module: it is assigned to channels {assigned_channels}. Remove it from channels first.",
        )

    del settings.modules[module_id]
    background_tasks.add_task(save_settings_background, settings.model_copy(deep=True))

    return {"message": "Module deleted"}


@app.post(
    "/api/modules/{module_id}/actions/{action}",
    dependencies=[Depends(require_admin_access)],
)
async def execute_module_action(module_id: str, action: str):
    """
    Execute a module-specific action.

    Supported actions depend on the module type.
    """
    if module_id not in settings.modules:
        raise HTTPException(status_code=404, detail="Module not found")

    module = settings.modules[module_id]

    # Add other module actions here as needed

    raise HTTPException(
        status_code=400,
        detail=f"Unknown action '{action}' for module type '{module.type}'",
    )


@app.post("/api/channels/{position}/modules", dependencies=[Depends(require_admin_access)])
async def assign_module_to_channel(
    position: int,
    module_id: str,
    background_tasks: BackgroundTasks,
    order: Optional[int] = None,
):
    """Assign a module to a channel."""
    global settings

    if position < 1 or position > 8:
        raise HTTPException(status_code=400, detail="Position must be 1-8")

    if module_id not in settings.modules:
        raise HTTPException(status_code=404, detail="Module not found")

    # Get or create channel config
    if position not in settings.channels:
        settings.channels[position] = ChannelConfig(modules=[])

    channel = settings.channels[position]

    # Ensure modules list exists
    if not channel.modules:
        channel.modules = []

    # Check if module is already assigned
    if any(a.module_id == module_id for a in channel.modules):
        raise HTTPException(
            status_code=400, detail="Module already assigned to this channel"
        )

    # Determine order (default to end)
    if order is None:
        order = max([a.order for a in channel.modules], default=-1) + 1

    # Add assignment
    channel.modules.append(ChannelModuleAssignment(module_id=module_id, order=order))
    background_tasks.add_task(save_settings_background, settings.model_copy(deep=True))

    return {"message": "Module assigned to channel", "channel": channel}


@app.delete(
    "/api/channels/{position}/modules/{module_id}",
    dependencies=[Depends(require_admin_access)],
)
async def remove_module_from_channel(
    position: int, module_id: str, background_tasks: BackgroundTasks
):
    """Remove a module from a channel."""
    global settings

    if position not in settings.channels:
        raise HTTPException(status_code=404, detail="Channel not found")

    channel = settings.channels[position]

    if not channel.modules:
        raise HTTPException(
            status_code=404, detail="Module not assigned to this channel"
        )

    # Remove assignment
    channel.modules = [a for a in channel.modules if a.module_id != module_id]
    background_tasks.add_task(save_settings_background, settings.model_copy(deep=True))

    return {"message": "Module removed from channel", "channel": channel}


@app.post(
    "/api/channels/{position}/modules/reorder",
    dependencies=[Depends(require_admin_access)],
)
async def reorder_channel_modules(
    position: int, module_orders: Dict[str, int], background_tasks: BackgroundTasks
):
    """Reorder modules within a channel. module_orders is {module_id: new_order}."""
    global settings

    if position not in settings.channels:
        raise HTTPException(status_code=404, detail="Channel not found")

    channel = settings.channels[position]

    if not channel.modules:
        raise HTTPException(status_code=400, detail="Channel has no modules")

    # Update orders
    for assignment in channel.modules:
        if assignment.module_id in module_orders:
            assignment.order = module_orders[assignment.module_id]

    background_tasks.add_task(save_settings_background, settings.model_copy(deep=True))

    return {"message": "Modules reordered", "channel": channel}


@app.post(
    "/api/channels/{position}/schedule",
    dependencies=[Depends(require_admin_access)],
)
async def update_channel_schedule(
    position: int, schedule: List[str], background_tasks: BackgroundTasks
):
    """Update the print schedule for a channel."""
    global settings

    if position not in settings.channels:
        settings.channels[position] = ChannelConfig(modules=[])

    settings.channels[position].schedule = schedule
    background_tasks.add_task(save_settings_background, settings.model_copy(deep=True))

    return {"message": "Schedule updated", "channel": settings.channels[position]}


# --- EVENT ROUTER ---


def execute_module(module: ModuleInstance) -> bool:
    """
    Execute a single module instance using the module registry.

    Returns True if successful, False if failed.
    """
    module_type = module.type
    config = module.config or {}
    module_name = module.name or module_type.upper()

    # Handle disabled modules
    if module_type == "off":
        return True  # Disabled modules are "successful" (intentionally empty)

    try:
        # Special handling for modules with Pydantic config classes
        # These require config to be parsed into specific types before calling
        if module_type == "webhook":
            action_config = WebhookConfig(**config)
            webhook.run_webhook(action_config, printer, module_name)
            return True

        elif module_type == "text":
            text_config = TextConfig(**config)
            text.format_text_receipt(printer, text_config, module_name)
            return True

        elif module_type == "calendar":
            cal_config = CalendarConfig(**config)
            calendar.format_calendar_receipt(printer, cal_config, module_name)
            return True

        elif module_type == "email":
            # Email has special handling - fetch emails first, then format
            emails = email_client.fetch_emails(config)
            email_client.format_email_receipt(
                printer, messages=emails, config=config, module_name=module_name
            )
            return True

        # Use registry for all other modules
        module_def = get_module_def(module_type)
        if module_def:
            # Standard call signature: (printer, config, module_name)
            module_def.execute_fn(printer, config, module_name)
            return True
        else:
            # Unknown module type
            printer.print_text(f"{module_name}")
            printer.print_line()
            printer.print_text("This module type is not")
            printer.print_text("recognized. Please check")
            printer.print_text("your settings.")
            return False

    except Exception as e:
        # Log the error for debugging
        logging.error(f"Error executing module '{module_type}': {e}")
        # Print a friendly error message
        printer.print_text(f"{module_name}")
        printer.print_line()
        printer.print_text("Could not load this content.")
        printer.print_text("Please check your settings")
        printer.print_text("or try again later.")
        return False


async def trigger_channel(position: int):
    """
    Executes all modules assigned to a specific channel position.
    Runs blocking printer operations in a thread pool to avoid blocking the event loop.
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from app.selection_mode import exit_selection_mode

    # Cancel any active interactive mode when a new channel is triggered
    exit_selection_mode()

    def _do_print():
        """Synchronous function that does the actual printing work."""
        # Instant tactile feedback - tiny paper blip (2 dots, ~0.01")
        if hasattr(printer, "blip"):
            printer.blip()

        # Reset printer buffer at start of print job (for invert mode)
        # Also set max lines limit
        max_lines = getattr(settings, "max_print_lines", 200)
        if hasattr(printer, "reset_buffer"):
            printer.reset_buffer(max_lines)

        channel = settings.channels.get(position)

        # Handle empty or unconfigured channels
        if not channel or not channel.modules:
            printer.print_text(f"CHANNEL {position}")
            printer.print_line()
            printer.print_text("This channel is empty.")
            printer.print_text("")
            printer.print_text("Visit http://pc-1.local")
            printer.print_text("to set it up.")
            printer.feed(1)

            # Flush buffer to print
            if hasattr(printer, "flush_buffer"):
                printer.flush_buffer()
            return

        # Sort modules by order
        sorted_modules = sorted(channel.modules, key=lambda m: m.order)

        # Separate standard and interactive modules
        from app.module_registry import get_module

        standard_modules = []
        interactive_modules = []

        for assignment in sorted_modules:
            module = settings.modules.get(assignment.module_id)
            if module:
                module_def = get_module(module.type)
                if module_def and getattr(module_def, "interactive", False):
                    interactive_modules.append(module)
                else:
                    standard_modules.append(module)

        # 1. Execute all standard modules first
        for module in standard_modules:
            execute_module(module)

            # Separator between modules (unless it's the last standard one)
            if module != standard_modules[-1]:
                printer.feed(2)

            # Check for max lines exceeded
            if (
                hasattr(printer, "is_max_lines_exceeded")
                and printer.is_max_lines_exceeded()
            ):
                if hasattr(printer, "flush_buffer"):
                    printer.flush_buffer()
                printer.print_text("")
                printer.print_text("--- MAX LENGTH REACHED ---")
                printer.feed(1)

                # Flush again for the message
                if hasattr(printer, "flush_buffer"):
                    printer.flush_buffer()
                return

        # 2. Handle Interactive Modules
        if not interactive_modules:
            # Done
            pass

        elif len(interactive_modules) == 1:
            # Single interactive module - run it directly
            if standard_modules:
                printer.feed(2)  # Separator from previous content
            execute_module(interactive_modules[0])

        else:
            # Multiple interactive modules - show selection menu
            if standard_modules:
                printer.feed(2)

            printer.print_header("SELECT APP", icon="list")
            printer.print_line()

            # Print menu options
            for i, module in enumerate(interactive_modules, 1):
                # Ensure we don't exceed 7 options (8 is reserved for Exit)
                if i > 7:
                    break
                printer.print_body(f"[{i}] {module.name}")

            printer.feed(1)
            printer.print_caption("[8] Cancel")
            printer.print_line()
            printer.print_caption("Turn dial to select")
            printer.feed(1)

            if hasattr(printer, "flush_buffer"):
                printer.flush_buffer()

            # Enter special selection mode to choose the app
            from app.selection_mode import enter_selection_mode, exit_selection_mode

            def handle_app_selection(dial_position: int):
                # Position 8 = Cancel
                if dial_position == 8:
                    exit_selection_mode()
                    # Print cancellation message
                    from app.hardware import printer as hw_printer

                    if hasattr(hw_printer, "reset_buffer"):
                        hw_printer.reset_buffer()
                    hw_printer.print_header("CANCELLED", icon="x")
                    hw_printer.print_line()
                    hw_printer.feed(1)
                    if hasattr(hw_printer, "flush_buffer"):
                        hw_printer.flush_buffer()
                    return

                # Check valid selection index (1-based)
                idx = dial_position - 1
                if 0 <= idx < len(interactive_modules):
                    # Valid selection - Exit menu selection mode first
                    exit_selection_mode()

                    # Execute the chosen module
                    # This module will then likely enter its OWN selection mode
                    target_module = interactive_modules[idx]

                    # We need to run this on the main thread via execute_module,
                    # but we are currently in the selection callback (potentially thread pool).
                    # Actually, execute_module just queues prints or runs logic.
                    # The tricky part is the adventure module expects to be called to PRINT content
                    # and enters its OWN selection mode.

                    # We can directly call execute_module from here.
                    # IMPORTANT: The printer buffer needs reset? Maybe.
                    from app.hardware import printer as hw_printer

                    if hasattr(hw_printer, "reset_buffer"):
                        hw_printer.reset_buffer()

                    execute_module(target_module)

                    if hasattr(hw_printer, "flush_buffer"):
                        hw_printer.flush_buffer()

                else:
                    # Invalid selection
                    # Ideally we'd re-print or just beep, but for now we do nothing
                    pass

            # Register the callback
            # We use a special ID to indicate this is the channel meta-menu
            enter_selection_mode(handle_app_selection, f"channel-menu-{position}")

            # Return early since we've handled the printing/logic
            return

        if hasattr(printer, "flush_buffer"):
            printer.flush_buffer()

        # Flush buffer to actually print. The printer driver applies a fixed
        # post-print cutter feed after each job.
        if hasattr(printer, "flush_buffer"):
            printer.flush_buffer()

    try:
        # Run blocking printer operations in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            await loop.run_in_executor(executor, _do_print)
    finally:
        # Always mark print as complete (thread-safe)
        _clear_print_reservation(clear_hold=False)


async def trigger_current_channel():
    """
    The Core Logic:
    Reads the dial position and executes all modules assigned to that channel.
    """
    position = dial.read_position()
    await trigger_channel(position)


@app.post("/action/trigger", dependencies=[Depends(require_admin_access)])
async def manual_trigger():
    """Simulates pressing the big brass button."""
    if not _try_begin_print_job(debounce=False):
        raise HTTPException(status_code=409, detail="Print already in progress")

    try:
        await trigger_current_channel()
    finally:
        _clear_print_reservation(clear_hold=False)
    return {"message": "Triggered"}


@app.post("/action/dial/{position}", dependencies=[Depends(require_admin_access)])
async def set_dial(position: int):
    """Simulates turning the physical rotary switch."""
    if position < 1 or position > 8:
        raise HTTPException(status_code=400, detail="Position must be 1-8")

    dial.set_position(position)
    return {"message": f"Dial turned to {position}"}


@app.post(
    "/action/print-channel/{position}",
    dependencies=[Depends(require_admin_access)],
)
async def print_channel(position: int, background_tasks: BackgroundTasks):
    """Set dial position and trigger print atomically. Returns immediately while print runs in background."""
    logger = logging.getLogger(__name__)

    if position < 1 or position > 8:
        raise HTTPException(status_code=400, detail="Position must be 1-8")

    if not _try_begin_print_job(debounce=False):
        raise HTTPException(status_code=409, detail="Print already in progress")

    # Run print in background and return immediately
    # trigger_channel handles errors and clears print_in_progress in its finally block
    background_tasks.add_task(trigger_channel, position)
    return {"message": f"Printing channel {position}"}


# --- DEBUG / VIRTUAL HARDWARE CONTROLS ---


@app.post(
    "/debug/print-module/{module_id}",
    dependencies=[Depends(require_admin_access)],
)
async def print_module(module_id: str, background_tasks: BackgroundTasks):
    """Forces a specific module instance to print (for testing)."""
    module = settings.modules.get(module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")

    if not _try_begin_print_job(debounce=False):
        raise HTTPException(status_code=409, detail="Print already in progress")

    # Run print in background and return immediately
    # print_module_direct handles errors and clears print_in_progress in its finally block
    background_tasks.add_task(print_module_direct, module_id)
    return {"message": f"Printing module '{module.name}'"}


async def print_module_direct(module_id: str):
    """Internal function to print a single module with proper buffer setup.
    Runs blocking printer operations in a thread pool to avoid blocking the event loop.
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from app.selection_mode import exit_selection_mode

    # Cancel any active interactive mode
    exit_selection_mode()

    def _do_print():
        """Synchronous function that does the actual printing work."""
        module = settings.modules.get(module_id)
        if not module:
            return

        # Instant tactile feedback - tiny paper blip (2 dots, ~0.01")
        if hasattr(printer, "blip"):
            printer.blip()

        # Reset printer buffer at start of print job (for invert mode)
        # Also set max lines limit
        max_lines = getattr(settings, "max_print_lines", 200)
        if hasattr(printer, "reset_buffer"):
            printer.reset_buffer(max_lines)

        # Execute the module
        execute_module(module)

        # Flush buffer to actually print. The printer driver applies a fixed
        # post-print cutter feed after each job.
        if hasattr(printer, "flush_buffer"):
            printer.flush_buffer()

    try:
        # Run blocking printer operations in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            await loop.run_in_executor(executor, _do_print)
    finally:
        # Always mark print as complete (thread-safe)
        _clear_print_reservation(clear_hold=False)


@app.post("/debug/test-webhook", dependencies=[Depends(require_admin_access)])
async def test_webhook(action: WebhookConfig):
    """
    Executes a custom webhook immediately for testing.
    Pass the webhook configuration in the body.
    Runs blocking operations in a thread pool to avoid blocking the event loop.
    """
    from concurrent.futures import ThreadPoolExecutor

    def _run_webhook():
        webhook.run_webhook(action, printer, module_name=None)

    try:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            await loop.run_in_executor(executor, _run_webhook)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error in test_webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Webhook execution failed: {str(e)}"
        )

    return {"message": "Webhook executed"}


def _preview_webhook_sync(config: dict):
    import requests
    import json

    action = WebhookConfig(**config)
    url = action.url
    json_path = action.json_path

    if not url:
        return {"success": False, "error": "URL is required"}

    try:
        response = webhook.request_webhook_response(action)

        if response.status_code >= 400:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text[:200]}",
                "status_code": response.status_code,
            }

        content_type = (response.headers.get("content-type") or "").split(";", 1)[
            0
        ].strip().lower()
        if content_type.startswith("image/"):
            try:
                import base64
                import io
                from PIL import Image

                with Image.open(io.BytesIO(response.content)) as image:
                    dimensions = f"{image.width}x{image.height}"
                    preview_image = webhook._prepare_image_for_print(image)
                    preview_buffer = io.BytesIO()
                    preview_image.save(preview_buffer, format="PNG")
                preview_data_url = (
                    "data:image/png;base64,"
                    f"{base64.b64encode(preview_buffer.getvalue()).decode('ascii')}"
                )
            except Exception:
                dimensions = "unknown size"
                preview_data_url = ""
            return {
                "success": True,
                "content": f"Image response: {content_type} ({dimensions})",
                "content_type": "image",
                "preview_data_url": preview_data_url,
                "status_code": response.status_code,
            }

        # Parse response
        try:
            data = response.json()
        except Exception:
            # Not JSON, return as text
            return {
                "success": True,
                "content": response.text[:500],
                "content_type": "text",
                "status_code": response.status_code,
            }

        # Extract value at json_path if specified
        if json_path:
            keys = json_path.split(".")
            value = data
            for k in keys:
                if isinstance(value, dict):
                    value = value.get(k, {})
                elif isinstance(value, list) and k.isdigit():
                    idx = int(k)
                    if 0 <= idx < len(value):
                        value = value[idx]
                    else:
                        value = None
                else:
                    value = None
                    break

            if value and not isinstance(value, (dict, list)):
                return {
                    "success": True,
                    "content": str(value),
                    "content_type": "extracted",
                    "json_path": json_path,
                    "status_code": response.status_code,
                }
            return {
                "success": False,
                "error": f"Path '{json_path}' not found in response",
                "raw_response": json.dumps(data, indent=2)[:500],
                "status_code": response.status_code,
            }

        # Return full JSON response
        return {
            "success": True,
            "content": json.dumps(data, indent=2)[:500],
            "content_type": "json",
            "status_code": response.status_code,
        }

    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timed out (10s limit)"}
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "error": "Could not connect to server. Check the URL.",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/webhook/test", dependencies=[Depends(require_admin_access)])
async def preview_webhook(config: dict):
    """
    Tests a webhook configuration and returns the response without printing.
    Useful for validating webhook setup before actual use.
    """

    try:
        return await asyncio.to_thread(_preview_webhook_sync, config)
    except Exception as e:
        return {"success": False, "error": str(e)}


# --- CAPTIVE PORTAL (Auto-launch setup page) ---


CAPTIVE_PORTAL_REDIRECT_URL = "http://10.42.0.1/"
CAPTIVE_PORTAL_CACHE_BYPASS_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


def _captive_portal_is_active() -> bool:
    """Return True when the local setup AP is active."""
    try:
        return wifi_manager.is_ap_mode_active()
    except Exception:
        return False


def _captive_portal_redirect() -> RedirectResponse:
    """Redirect probe clients to the setup UI with no-cache headers."""
    response = RedirectResponse(url=CAPTIVE_PORTAL_REDIRECT_URL, status_code=302)
    for header_name, header_value in CAPTIVE_PORTAL_CACHE_BYPASS_HEADERS.items():
        response.headers[header_name] = header_value
    return response


def _captive_portal_response(
    *,
    content: str = "",
    status_code: int = 200,
    media_type: str = "text/plain",
) -> Response:
    response = Response(content=content, status_code=status_code, media_type=media_type)
    for header_name, header_value in CAPTIVE_PORTAL_CACHE_BYPASS_HEADERS.items():
        response.headers[header_name] = header_value
    return response


@app.get("/hotspot-detect.html")
@app.get("/library/test/success.html")
@app.get("/success.html")
async def captive_apple():
    """iOS/macOS captive portal detection - redirect to setup page."""
    if _captive_portal_is_active():
        return _captive_portal_redirect()
    return _captive_portal_response(
        content="<!DOCTYPE html><html><head><title>Success</title></head><body>Success</body></html>",
        media_type="text/html",
    )


@app.get("/generate_204")
@app.get("/gen_204")
@app.get("/mobile/status.php")
async def captive_android():
    """Android captive portal detection - redirect to setup page."""
    if _captive_portal_is_active():
        return _captive_portal_redirect()
    return _captive_portal_response(status_code=204)


@app.get("/connecttest.txt")
async def captive_windows_connect_test():
    """Windows 10+ captive portal detection."""
    if _captive_portal_is_active():
        return _captive_portal_redirect()
    return _captive_portal_response(content="Microsoft Connect Test")


@app.get("/ncsi.txt")
async def captive_windows_ncsi():
    """Windows 8.1 and earlier captive portal detection."""
    if _captive_portal_is_active():
        return _captive_portal_redirect()
    return _captive_portal_response(content="Microsoft NCSI")


@app.get("/redirect")
async def captive_windows_redirect():
    """Windows passive connectivity redirect target."""
    if _captive_portal_is_active():
        return _captive_portal_redirect()
    return _captive_portal_response(status_code=204)


@app.get("/success.txt")
@app.get("/canonical.html")
async def captive_other():
    """Generic captive portal detection used by various clients."""
    if _captive_portal_is_active():
        return _captive_portal_redirect()
    return _captive_portal_response(content="success\n")


@app.get("/check_network_status.txt")
async def captive_networkmanager():
    """NetworkManager/Linux captive portal detection."""
    if _captive_portal_is_active():
        return _captive_portal_redirect()
    return _captive_portal_response(content="NetworkManager is online\n")


# --- STATIC FILES (FRONTEND) ---

# Mount the built React app
# Ensure 'web/dist' exists (run 'npm run build' in web/ directory first)
if os.path.exists("web/dist"):
    app.mount("/assets", StaticFiles(directory="web/dist/assets"), name="assets")

    # Serve fonts directory with explicit MIME type
    if os.path.exists("web/dist/fonts"):

        @app.get("/fonts/{font_path:path}")
        async def serve_font(font_path: str):
            font_file_path = os.path.join("web/dist/fonts", font_path)
            if os.path.exists(font_file_path):
                # Determine MIME type based on file extension
                if font_path.endswith(".woff2"):
                    return FileResponse(font_file_path, media_type="font/woff2")
                elif font_path.endswith(".woff"):
                    return FileResponse(font_file_path, media_type="font/woff")
                elif font_path.endswith(".ttf"):
                    return FileResponse(font_file_path, media_type="font/ttf")
                elif font_path.endswith(".otf"):
                    return FileResponse(font_file_path, media_type="font/otf")
            raise HTTPException(status_code=404, detail="Font not found")

    # Serve favicon explicitly
    @app.get("/favicon.svg")
    async def serve_favicon():
        return FileResponse("web/dist/favicon.svg", media_type="image/svg+xml")

    # Serve index.html for the root and any client-side routes
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # If path starts with api/, let it fall through to API routes
        # Fonts are handled by the mount above, so they won't reach here
        if (
            full_path.startswith("api/")
            or full_path.startswith("docs")
            or full_path.startswith("openapi.json")
        ):
            raise HTTPException(status_code=404, detail="Not found")

        # Otherwise serve the React app
        return FileResponse("web/dist/index.html")

else:
    print("[WARNING] web/dist directory not found. Frontend will not be served.")
