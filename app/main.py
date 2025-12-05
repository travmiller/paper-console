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
)
from app.routers import wifi
import app.wifi_manager as wifi_manager
import app.hardware as hardware
from app.hardware import printer, dial, button, _is_raspberry_pi

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

# Print state tracking for cancellation
print_in_progress = False
cancel_print_requested = False


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
    """Callback that schedules the trigger on the main event loop.

    If a print is already in progress, this will cancel it instead.
    """
    global global_loop, print_in_progress, cancel_print_requested

    if print_in_progress:
        # Cancel the current print job
        cancel_print_requested = True
    elif global_loop and global_loop.is_running():
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

    # If marker exists, we've already printed welcome
    if os.path.exists(marker_path):
        return

    # First boot! Print welcome message
    await asyncio.sleep(2)  # Wait for printer to be ready

    if hasattr(printer, "reset_buffer"):
        printer.reset_buffer()

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
    printer.print_text("Hold button 5 sec = WiFi setup")
    printer.print_text("Hold button 15 sec = Reset all")
    printer.print_text("================================")
    printer.feed(2)

    # Flush if invert mode
    if (
        hasattr(printer, "invert")
        and printer.invert
        and hasattr(printer, "flush_buffer")
    ):
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

    # Flush if invert mode
    if (
        hasattr(printer, "invert")
        and printer.invert
        and hasattr(printer, "flush_buffer")
    ):
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global email_polling_task, scheduler_task, task_monitor_task, global_loop

    # Capture the running loop
    global_loop = asyncio.get_running_loop()

    # Check for first boot and print welcome message
    asyncio.create_task(check_first_boot())

    # Check WiFi and start AP mode if needed
    asyncio.create_task(check_wifi_startup())

    # Start background tasks
    email_polling_task = asyncio.create_task(email_polling_loop())
    scheduler_task = asyncio.create_task(scheduler_loop())
    task_monitor_task = asyncio.create_task(task_watchdog())

    # Initialize Button Callbacks
    button.set_callback(on_button_press_threadsafe)
    button.set_long_press_callback(on_button_long_press_threadsafe)
    button.set_factory_reset_callback(on_factory_reset_threadsafe)

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
    global settings, printer
    import app.config as config_module

    # Check if invert_print setting changed
    old_invert = getattr(settings, "invert_print", False)
    new_invert = getattr(new_settings, "invert_print", False)

    # Update in-memory - create new settings object
    settings = new_settings
    # Update module-level reference so modules that access app.config.settings will see the update
    config_module.settings = settings

    # Save to disk
    background_tasks.add_task(save_settings_background, settings.model_copy(deep=True))

    # Reinitialize printer if invert setting changed
    if old_invert != new_invert:
        if hasattr(hardware.printer, "close"):
            hardware.printer.close()

        # Create new instance
        if _is_raspberry_pi:
            from app.drivers.printer_serial import PrinterDriver
        else:
            from app.drivers.printer_mock import PrinterDriver

        hardware.printer = PrinterDriver(width=PRINTER_WIDTH, invert=new_invert)
        # Update local reference if used elsewhere in this file (it is used in background tasks)
        # Note: modules importing 'printer' from hardware will still have the OLD reference!
        # This is a limitation of Python imports.
        # To fix this, we should probably make 'printer' a proxy or always access it via hardware.printer

        # Update global reference for this module
        global printer
        printer = hardware.printer

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
    global settings, printer
    import app.config as config_module

    new_settings = load_config()

    # Check if invert_print setting changed
    old_invert = getattr(settings, "invert_print", False)
    new_invert = getattr(new_settings, "invert_print", False)

    # Update in-memory globals
    settings = new_settings
    config_module.settings = settings

    # Reinitialize printer if invert setting changed
    if old_invert != new_invert:
        if hasattr(printer, "close"):
            printer.close()

        if _is_raspberry_pi:
            from app.drivers.printer_serial import PrinterDriver
        else:
            from app.drivers.printer_mock import PrinterDriver

        printer = PrinterDriver(width=PRINTER_WIDTH, invert=new_invert)

    return {"message": "Settings reloaded from disk", "config": settings}


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
    Can be cancelled by pressing the button again during printing.
    """
    global print_in_progress, cancel_print_requested

    # Mark print as in progress
    print_in_progress = True
    cancel_print_requested = False

    try:
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

            # Flush and feed for invert mode
            if (
                hasattr(printer, "invert")
                and printer.invert
                and hasattr(printer, "flush_buffer")
            ):
                printer.flush_buffer()

            feed_lines = getattr(settings, "cutter_feed_lines", 3)
            if feed_lines > 0:
                printer.feed_direct(feed_lines)
            return

        # Sort modules by order and execute each
        sorted_modules = sorted(channel.modules, key=lambda m: m.order)

        for assignment in sorted_modules:
            # Check for cancellation before each module
            if cancel_print_requested:
                # Clear buffer and print cancellation message
                if hasattr(printer, "reset_buffer"):
                    printer.reset_buffer()
                printer.print_text("--- PRINT CANCELLED ---")
                printer.feed(1)

                # Feed to clear cutter
                feed_lines = getattr(settings, "cutter_feed_lines", 3)
                if feed_lines > 0:
                    printer.feed_direct(feed_lines)
                return

            module = settings.modules.get(assignment.module_id)
            if module:
                execute_module(module)
                
                # Check for max lines exceeded after each module
                if hasattr(printer, "is_max_lines_exceeded") and printer.is_max_lines_exceeded():
                    printer.print_text("")
                    printer.print_text("--- MAX LENGTH REACHED ---")
                    printer.feed(1)
                    
                    # Flush and feed
                    if (
                        hasattr(printer, "invert")
                        and printer.invert
                        and hasattr(printer, "flush_buffer")
                    ):
                        printer.flush_buffer()
                    
                    feed_lines = getattr(settings, "cutter_feed_lines", 3)
                    if feed_lines > 0:
                        printer.feed_direct(feed_lines)
                    return
                
                # Add a separator between modules
                if assignment != sorted_modules[-1]:
                    printer.feed(1)

        # Check for cancellation before final flush
        if cancel_print_requested:
            if hasattr(printer, "reset_buffer"):
                printer.reset_buffer()
            printer.print_text("--- PRINT CANCELLED ---")
            printer.feed(1)
            feed_lines = getattr(settings, "cutter_feed_lines", 3)
            if feed_lines > 0:
                printer.feed_direct(feed_lines)
            return

        # If invert is enabled, flush buffer to actually print (in reverse order)
        if (
            hasattr(printer, "invert")
            and printer.invert
            and hasattr(printer, "flush_buffer")
        ):
            printer.flush_buffer()

        # Add cutter feed lines at the end of the print job
        feed_lines = getattr(settings, "cutter_feed_lines", 3)
        if feed_lines > 0:
            printer.feed_direct(feed_lines)

    finally:
        # Always mark print as complete
        print_in_progress = False
        cancel_print_requested = False


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
    if position < 1 or position > 8:
        raise HTTPException(status_code=400, detail="Position must be 1-8")

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
