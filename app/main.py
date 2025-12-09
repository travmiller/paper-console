from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, Response
from contextlib import asynccontextmanager
import asyncio
import uuid
import os
from typing import Dict, Optional, List
from datetime import datetime
from pydantic import BaseModel
import subprocess
import platform
import pytz
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
from app.modules import (
    astronomy,
    sudoku,
    news,
    rss,
    email_client,
    webhook,
    text,
    calendar,
    weather,
    maze,
    quotes,
    history,
    checklist,
    crossword,
)
from app.routers import wifi
import app.wifi_manager as wifi_manager
import app.hardware as hardware
from app.hardware import printer, dial, button, power_button, _is_raspberry_pi
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
            min_interval = 30  # Default polling interval

            for module in settings.modules.values():
                if module.type == "email":
                    email_config = EmailConfig(**(module.config or {}))
                    if email_config.auto_print_new:
                        email_modules.append(module)
                        if email_config.polling_interval < min_interval:
                            min_interval = email_config.polling_interval

            await asyncio.sleep(min_interval)

            if not email_modules:
                continue

            # Check each email module silently
            for module in email_modules:
                try:
                    emails = email_client.fetch_emails(module.config)
                    if emails:
                        email_client.format_email_receipt(
                            printer,
                            messages=emails,
                            config=module.config,
                            module_name=module.name,
                        )
                except Exception:
                    pass  # Silently skip failed email checks

        except Exception:
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
                    await trigger_channel(pos)

        except Exception:
            await asyncio.sleep(60)


# --- HARDWARE CALLBACKS ---

# Print state tracking
print_in_progress = False


def on_button_press():
    """
    Callback for when the physical button is pressed.
    Calls the async trigger_current_channel function.
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(trigger_current_channel())
    except RuntimeError:
        pass


global_loop = None


def on_button_press_threadsafe():
    """Callback that schedules the trigger on the main event loop."""
    global global_loop, print_in_progress

    # Simple check to prevent double prints
    if print_in_progress:
        return

    if global_loop and global_loop.is_running():
        asyncio.run_coroutine_threadsafe(trigger_current_channel(), global_loop)


def on_button_long_press_threadsafe():
    """Callback for long press (5 seconds) - triggers AP mode."""
    global global_loop
    if global_loop and global_loop.is_running():
        asyncio.run_coroutine_threadsafe(manual_ap_mode_trigger(), global_loop)


from app.utils import print_setup_instructions_sync


async def print_setup_instructions():
    """Prints the WiFi setup instructions."""
    print_setup_instructions_sync()


def _get_welcome_marker_path() -> str:
    """Get path to the welcome message marker file."""
    import app.config as config_module

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(config_module.__file__)))
    return os.path.join(base_dir, ".welcome_printed")


async def check_first_boot():
    """Check if this is first boot and print welcome message."""
    marker_path = _get_welcome_marker_path()

    # Wait for printer to be ready (applies to all boots)
    await asyncio.sleep(2)

    if hasattr(printer, "reset_buffer"):
        printer.reset_buffer()

    # If marker exists, just print ready message
    if os.path.exists(marker_path):
        printer.feed(1)
        printer.print_text("=" * 32)
        printer.print_text("       SYSTEM READY")
        printer.print_text("=" * 32)
        printer.feed(1)

        # Flush buffer
        if hasattr(printer, "flush_buffer"):
            printer.flush_buffer()
        if hasattr(printer, "feed_direct"):
            printer.feed_direct(3)
        return

    # First boot! Print welcome message (if marker doesn't exist)
    # Get device ID for SSID
    ssid_suffix = "XXXX"
    try:
        if _is_raspberry_pi:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if line.startswith("Serial"):
                        ssid_suffix = line.split(":")[1].strip()[-4:]
                        break
    except Exception:
        pass

    ssid = f"PC-1-Setup-{ssid_suffix}"

    printer.feed(1)
    printer.print_text("================================")
    printer.print_text("")
    printer.print_text("    Welcome to PC-1!")
    printer.print_text("    Your Paper Console")
    printer.print_text("")
    printer.print_text("================================")
    printer.feed(1)
    printer.print_text("PC-1 prints weather, news,")
    printer.print_text("puzzles, and more on paper.")
    printer.print_text("")
    printer.print_text("First, let's connect it to")
    printer.print_text("your home WiFi so it can")
    printer.print_text("fetch content from the internet.")
    printer.feed(1)
    printer.print_text("--------------------------------")
    printer.print_text("STEP 1: CONNECT TO PC-1")
    printer.print_text("--------------------------------")
    printer.print_text("")
    printer.print_text("On your phone or computer,")
    printer.print_text("look for this WiFi network:")
    printer.print_text("")
    printer.print_text(f"  {ssid}")
    printer.print_text("  Password: setup1234")
    printer.feed(1)
    printer.print_text("--------------------------------")
    printer.print_text("STEP 2: OPEN SETUP PAGE")
    printer.print_text("--------------------------------")
    printer.print_text("")
    printer.print_text("Your phone may open it")
    printer.print_text("automatically. If not, visit:")
    printer.print_text("")
    printer.print_text("  http://10.42.0.1")
    printer.feed(1)
    printer.print_text("--------------------------------")
    printer.print_text("STEP 3: CHOOSE YOUR WIFI")
    printer.print_text("--------------------------------")
    printer.print_text("")
    printer.print_text("Select your home WiFi and")
    printer.print_text("enter its password. PC-1 will")
    printer.print_text("remember it and connect")
    printer.print_text("automatically from now on.")
    printer.feed(1)
    printer.print_text("================================")
    printer.print_text("AFTER SETUP")
    printer.print_text("================================")
    printer.print_text("")
    printer.print_text("Turn the dial to choose:")
    printer.print_text("  1 = Weather forecast")
    printer.print_text("  2 = Moon & sunrise times")
    printer.print_text("  3 = Sudoku puzzle")
    printer.print_text("")
    printer.print_text("Press the button to print!")
    printer.print_text("")
    printer.print_text("Customize channels anytime at:")
    printer.print_text("  http://pc-1.local")
    printer.feed(1)
    printer.print_text("--------------------------------")
    printer.print_text("NEED HELP LATER?")
    printer.print_text("--------------------------------")
    printer.print_text("Power Btn 5s = WiFi setup")
    printer.print_text("Power Btn 15s = Reset all")
    printer.print_text("================================")
    printer.feed(2)

    # Flush buffer to print (prints are reversed for tear-off orientation)
    if hasattr(printer, "flush_buffer"):
        printer.flush_buffer()
    if hasattr(printer, "feed_direct"):
        printer.feed_direct(3)

    # Create marker file so we don't print again
    try:
        with open(marker_path, "w") as f:
            f.write("1")
    except Exception:
        pass


async def check_wifi_startup():
    """Check WiFi status on startup and enter AP mode if needed."""
    # Give system time to connect to saved WiFi
    await asyncio.sleep(10)

    status = wifi_manager.get_wifi_status()

    if not status["connected"] and status["mode"] != "ap":
        success = wifi_manager.start_ap_mode(retries=3)

        if success:
            await asyncio.sleep(5)
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
    """Manually trigger AP mode (e.g. via button hold 5-15 seconds)."""
    # Print instructions BEFORE switching network mode
    await print_setup_instructions()

    # Give a small delay for the printer buffer to flush/finish
    await asyncio.sleep(2)

    wifi_manager.start_ap_mode()


async def factory_reset_trigger():
    """Factory reset (button hold 15+ seconds) - deletes config and reboots."""
    import subprocess

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

    # Flush buffer to print
    if hasattr(printer, "flush_buffer"):
        printer.flush_buffer()
    if hasattr(printer, "feed_direct"):
        printer.feed_direct(3)

    # Wait for print to complete
    await asyncio.sleep(3)

    # Delete config file and welcome marker
    try:
        import app.config as config_module

        base_dir = os.path.dirname(
            os.path.dirname(os.path.abspath(config_module.__file__))
        )
        config_path = os.path.join(base_dir, "config.json")
        backup_path = os.path.join(base_dir, "config.json.bak")
        welcome_marker = os.path.join(base_dir, ".welcome_printed")

        if os.path.exists(config_path):
            os.remove(config_path)
        if os.path.exists(backup_path):
            os.remove(backup_path)
        if os.path.exists(welcome_marker):
            os.remove(welcome_marker)
    except Exception:
        pass

    # Forget all saved WiFi networks
    try:
        wifi_manager.forget_all_wifi()
    except Exception:
        pass

    # Reboot the device
    await asyncio.sleep(1)
    try:
        subprocess.run(["sudo", "reboot"], check=False)
    except Exception:
        pass


def on_factory_reset_threadsafe():
    """Callback for factory reset press (15+ seconds)."""
    global global_loop
    if global_loop and global_loop.is_running():
        asyncio.run_coroutine_threadsafe(factory_reset_trigger(), global_loop)


async def shutdown_trigger():
    """Shutdown the device safely."""
    import subprocess

    # Print shutdown message
    printer.feed(1)
    printer.print_text("=" * 32)
    printer.print_text("       SHUTTING DOWN")
    printer.print_text("=" * 32)
    printer.feed(1)

    # Flush buffer
    if hasattr(printer, "flush_buffer"):
        printer.flush_buffer()
    if hasattr(printer, "feed_direct"):
        printer.feed_direct(3)

    await asyncio.sleep(2)

    try:
        subprocess.run(["sudo", "shutdown", "-h", "now"], check=False)
    except Exception:
        pass


def on_power_button_callback_threadsafe():
    """Callback for power button short press (shutdown)."""
    global global_loop
    if global_loop and global_loop.is_running():
        asyncio.run_coroutine_threadsafe(shutdown_trigger(), global_loop)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global email_polling_task, scheduler_task, task_monitor_task, global_loop

    # Capture the running loop
    global_loop = asyncio.get_running_loop()

    # Clear printer hardware buffer first to prevent startup garbage
    if hasattr(printer, "clear_hardware_buffer"):
        printer.clear_hardware_buffer()

    # Check for first boot and print welcome message
    asyncio.create_task(check_first_boot())

    # Check WiFi and start AP mode if needed
    asyncio.create_task(check_wifi_startup())

    # Start background tasks
    email_polling_task = asyncio.create_task(email_polling_loop())
    scheduler_task = asyncio.create_task(scheduler_loop())
    task_monitor_task = asyncio.create_task(task_watchdog())

    # Initialize Main Button Callbacks (Printing Only)
    button.set_callback(on_button_press_threadsafe)

    # Initialize Power Button Callbacks (Shutdown, AP Mode, Factory Reset)
    power_button.set_callback(
        on_power_button_callback_threadsafe
    )  # Short press = Shutdown
    power_button.set_long_press_callback(
        on_button_long_press_threadsafe
    )  # 5s = AP Mode (reusing function name)
    power_button.set_factory_reset_callback(
        on_factory_reset_threadsafe
    )  # 15s = Factory Reset

    yield

    # Shutdown - cancel all background tasks
    for task in [email_polling_task, scheduler_task, task_monitor_task]:
        if task:
            task.cancel()
            try:
                await task
            except Exception:
                pass

    # Cleanup hardware drivers
    if hasattr(printer, "close"):
        printer.close()
    if hasattr(dial, "cleanup"):
        dial.cleanup()
    if hasattr(button, "cleanup"):
        button.cleanup()
    if hasattr(power_button, "cleanup"):
        power_button.cleanup()


app = FastAPI(
    title="PC-1 (Paper Console 1)",
    description="Backend API for the PC-1 offline news printer.",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow Frontend (React) to talk to Backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to localhost
    allow_credentials=True,
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
    health["components"]["printer"] = "available" if printer else "unavailable"
    health["components"]["dial"] = "available" if dial else "unavailable"
    health["components"]["button"] = "available" if button else "unavailable"
    health["components"]["power_button"] = (
        "available" if power_button else "unavailable"
    )
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


@app.get("/api/settings", response_model=Settings)
async def get_settings():
    return settings


@app.post("/api/settings")
async def update_settings(new_settings: Settings, background_tasks: BackgroundTasks):
    """Updates the configuration and saves it to disk."""
    global settings
    import app.config as config_module

    # Update in-memory - create new settings object
    settings = new_settings
    # Update module-level reference so modules that access app.config.settings will see the update
    config_module.settings = settings

    # Save to disk
    background_tasks.add_task(save_settings_background, settings.model_copy(deep=True))

    return {"message": "Settings saved", "config": settings}


@app.post("/api/settings/reset")
async def reset_settings(background_tasks: BackgroundTasks):
    """Resets all settings to their default values."""
    global settings

    # Create fresh settings instance (uses defaults from config.py)
    settings = Settings()

    # Save to disk (overwriting existing config.json)
    background_tasks.add_task(save_settings_background, settings.model_copy(deep=True))

    return {"message": "Settings reset to defaults", "config": settings}


@app.post("/api/settings/reload")
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
                pass

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
                pass

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


@app.post("/api/system/timezone")
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


@app.post("/api/system/time")
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
                pass  # Ignore hwclock errors

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


@app.post("/api/system/time/sync/disable")
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


@app.post("/api/system/time/sync")
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
                    pass

                return {
                    "success": False,
                    "error": result.stderr or "Failed to sync time with NTP",
                    "message": "Could not synchronize time. Ensure NTP is configured or try manual time setting.",
                }

            # Sync hardware clock
            try:
                subprocess.run(["sudo", "hwclock", "--systohc"], timeout=5, check=False)
            except Exception:
                pass

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
                pass

            # Fallback to /etc/timezone
            if not system_timezone:
                try:
                    with open("/etc/timezone", "r") as f:
                        system_timezone = f.read().strip()
                except Exception:
                    pass

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

            response = requests.get(
                nominatim_url, params=params, headers=headers, timeout=3
            )
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


@app.get("/api/modules")
async def list_modules():
    """List all module instances."""
    return {"modules": settings.modules}


@app.post("/api/modules")
async def create_module(module: ModuleInstance, background_tasks: BackgroundTasks):
    """Create a new module instance."""
    global settings

    # If no ID provided, generate one
    if not module.id:
        module.id = str(uuid.uuid4())

    settings.modules[module.id] = module
    background_tasks.add_task(save_settings_background, settings.model_copy(deep=True))

    return {"message": "Module created", "module": module}


@app.get("/api/modules/{module_id}")
async def get_module(module_id: str):
    """Get a specific module instance."""
    module = settings.modules.get(module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    return module


@app.put("/api/modules/{module_id}")
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
    settings.modules[module_id] = module
    background_tasks.add_task(save_settings_background, settings.model_copy(deep=True))

    # Update module-level reference so modules that access app.config.settings will see the update
    config_module.settings = settings

    return {"message": "Module updated", "module": module}


@app.delete("/api/modules/{module_id}")
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


@app.post("/api/channels/{position}/modules")
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


@app.delete("/api/channels/{position}/modules/{module_id}")
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


@app.post("/api/channels/{position}/modules/reorder")
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


@app.post("/api/channels/{position}/schedule")
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
    """Execute a single module instance. Returns True if successful, False if failed."""
    module_type = module.type
    config = module.config or {}
    module_name = module.name or module_type.upper()

    try:
        # Dispatch Logic
        if module_type == "webhook":
            action_config = WebhookConfig(**config)
            webhook.run_webhook(action_config, printer, module_name)

        elif module_type == "text":
            text_config = TextConfig(**config)
            text.format_text_receipt(printer, text_config, module_name)

        elif module_type == "calendar":
            cal_config = CalendarConfig(**config)
            calendar.format_calendar_receipt(printer, cal_config, module_name)

        elif module_type == "news":
            news.format_news_receipt(printer, config, module_name)

        elif module_type == "rss":
            rss.format_rss_receipt(printer, config, module_name)

        elif module_type == "email":
            emails = email_client.fetch_emails(config)
            email_client.format_email_receipt(
                printer, messages=emails, config=config, module_name=module_name
            )

        elif module_type == "games":
            sudoku.format_sudoku_receipt(printer, config, module_name)

        elif module_type == "maze":
            maze.format_maze_receipt(printer, config, module_name)

        elif module_type == "quotes":
            quotes.format_quotes_receipt(printer, config, module_name)

        elif module_type == "history":
            history.format_history_receipt(printer, config, module_name)

        elif module_type == "checklist":
            checklist.format_checklist_receipt(printer, config, module_name)

        elif module_type == "crossword":
            crossword.format_crossword_receipt(printer, config, module_name)

        elif module_type == "astronomy":
            astronomy.format_astronomy_receipt(printer, module_name=module_name)

        elif module_type == "weather":
            weather.format_weather_receipt(printer, config, module_name)

        elif module_type == "off":
            return True  # Disabled modules are "successful" (intentionally empty)

        else:
            # Unknown module type
            printer.print_text(f"{module_name}")
            printer.print_line()
            printer.print_text("This module type is not")
            printer.print_text("recognized. Please check")
            printer.print_text("your settings.")
            return False

        return True

    except Exception:
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
    """
    global print_in_progress

    # Mark print as in progress
    print_in_progress = True

    try:
        # Instant tactile feedback - tiny paper blip
        if hasattr(printer, "blip"):
            printer.blip()

        # Clear hardware buffer (reset) before starting new job to kill any ghosts
        if hasattr(printer, "clear_hardware_buffer"):
            printer.clear_hardware_buffer()

        # Reset printer buffer at start of print job (for invert mode)
        # Also set max lines limit
        max_lines = getattr(settings, "max_print_lines", 200)
        if hasattr(printer, "reset_buffer"):
            printer.reset_buffer(max_lines)

        # Check paper status before printing
        if hasattr(printer, "check_paper_status"):
            paper_status = printer.check_paper_status()
            if paper_status.get("paper_near_end"):
                printer.print_text("")
                printer.print_text("*** PAPER LOW ***")
                printer.print_text("")
                printer.feed(1)

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

            feed_lines = getattr(settings, "cutter_feed_lines", 3)
            if feed_lines > 0:
                printer.feed_direct(feed_lines)
            return

        # Sort modules by order and execute each
        sorted_modules = sorted(channel.modules, key=lambda m: m.order)

        for assignment in sorted_modules:
            module = settings.modules.get(assignment.module_id)
            if module:
                execute_module(module)

                # Check for max lines exceeded after each module
                if (
                    hasattr(printer, "is_max_lines_exceeded")
                    and printer.is_max_lines_exceeded()
                ):
                    # Flush buffer first so content prints
                    if hasattr(printer, "flush_buffer"):
                        printer.flush_buffer()

                    # Print message AFTER flush so it appears at the end
                    printer.print_text("")
                    printer.print_text("--- MAX LENGTH REACHED ---")
                    printer.feed(1)

                    # Flush again for the message, then feed for cutter
                    if hasattr(printer, "flush_buffer"):
                        printer.flush_buffer()
                    feed_lines = getattr(settings, "cutter_feed_lines", 3)
                    if feed_lines > 0:
                        printer.feed_direct(feed_lines)
                    return

                # Add a separator between modules
                if assignment != sorted_modules[-1]:
                    printer.feed(1)

        # Flush buffer to actually print (in reverse order for tear-off orientation)
        if hasattr(printer, "flush_buffer"):
            printer.flush_buffer()

        # Add cutter feed lines at the end of the print job
        feed_lines = getattr(settings, "cutter_feed_lines", 3)
        if feed_lines > 0:
            printer.feed_direct(feed_lines)

    finally:
        # Always mark print as complete
        print_in_progress = False


async def trigger_current_channel():
    """
    The Core Logic:
    Reads the dial position and executes all modules assigned to that channel.
    """
    position = dial.read_position()
    await trigger_channel(position)


@app.post("/action/trigger")
async def manual_trigger():
    """Simulates pressing the big brass button."""
    global print_in_progress

    if print_in_progress:
        raise HTTPException(status_code=409, detail="Print already in progress")

    await trigger_current_channel()
    return {"message": "Triggered"}


@app.post("/action/dial/{position}")
async def set_dial(position: int):
    """Simulates turning the physical rotary switch."""
    if position < 1 or position > 8:
        raise HTTPException(status_code=400, detail="Position must be 1-8")

    dial.set_position(position)
    return {"message": f"Dial turned to {position}"}


@app.post("/action/print-channel/{position}")
async def print_channel(position: int):
    """Set dial position and trigger print atomically."""
    global print_in_progress

    if position < 1 or position > 8:
        raise HTTPException(status_code=400, detail="Position must be 1-8")

    if print_in_progress:
        raise HTTPException(status_code=409, detail="Print already in progress")

    # Don't need to set dial.set_position since we're passing position directly
    await trigger_channel(position)
    return {"message": f"Printing channel {position}"}


# --- DEBUG / VIRTUAL HARDWARE CONTROLS ---


@app.post("/debug/print-module/{module_id}")
async def print_module(module_id: str):
    """Forces a specific module instance to print (for testing)."""
    module = settings.modules.get(module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")

    execute_module(module)
    return {"message": f"Module '{module.name}' printed to console"}


@app.post("/debug/test-webhook")
async def test_webhook(action: WebhookConfig):
    """
    Executes a custom webhook immediately for testing.
    Pass the webhook configuration in the body.
    """
    webhook.run_webhook(action, printer, module_name=None)
    return {"message": "Webhook executed"}


# --- CAPTIVE PORTAL (Auto-launch setup page) ---


@app.get("/hotspot-detect.html")
@app.get("/library/test/success.html")
async def captive_apple():
    """iOS/macOS captive portal detection - redirect to setup page."""
    # Check if we're in AP mode
    status = wifi_manager.get_wifi_status()
    if status.get("mode") == "ap":
        return RedirectResponse(url="/", status_code=302)
    # If not in AP mode, return success (device has internet)
    return {"status": "success"}


@app.get("/generate_204")
@app.get("/gen_204")
async def captive_android():
    """Android captive portal detection - redirect to setup page."""
    status = wifi_manager.get_wifi_status()
    if status.get("mode") == "ap":
        return RedirectResponse(url="/", status_code=302)
    # Return 204 No Content if not in AP mode (device has internet)
    return Response(status_code=204)


@app.get("/connecttest.txt")
@app.get("/ncsi.txt")
async def captive_windows():
    """Windows captive portal detection - redirect to setup page."""
    status = wifi_manager.get_wifi_status()
    if status.get("mode") == "ap":
        return RedirectResponse(url="/", status_code=302)
    # Return success text if not in AP mode
    return Response(content="Microsoft Connect Test", media_type="text/plain")


@app.get("/success.txt")
async def captive_other():
    """Generic captive portal detection."""
    status = wifi_manager.get_wifi_status()
    if status.get("mode") == "ap":
        return RedirectResponse(url="/", status_code=302)
    return {"status": "success"}


# --- STATIC FILES (FRONTEND) ---

# Mount the built React app
# Ensure 'web/dist' exists (run 'npm run build' in web/ directory first)
if os.path.exists("web/dist"):
    app.mount("/assets", StaticFiles(directory="web/dist/assets"), name="assets")

    # Serve favicon explicitly
    @app.get("/favicon.svg")
    async def serve_favicon():
        return FileResponse("web/dist/favicon.svg", media_type="image/svg+xml")

    # Serve index.html for the root and any client-side routes
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # If path starts with api/, let it fall through to API routes
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
