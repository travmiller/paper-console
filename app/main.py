from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import asyncio
import uuid
import os
from typing import Dict, Optional, List
from datetime import datetime
from app.config import settings, Settings, save_config, WebhookConfig, TextConfig, CalendarConfig, EmailConfig, ModuleInstance, ChannelModuleAssignment, ChannelConfig, PRINTER_WIDTH
from app.modules import astronomy, sudoku, news, rss, email_client, webhook, text, calendar, weather
import platform

# Auto-detect platform and use appropriate drivers
_is_raspberry_pi = platform.system() == "Linux" and os.path.exists("/proc/device-tree/model")

if _is_raspberry_pi:
    try:
        from app.drivers.printer_serial import PrinterDriver
        from app.drivers.dial_gpio import DialDriver
        print("[SYSTEM] Running on Raspberry Pi - using hardware drivers")
    except ImportError as e:
        print(f"[SYSTEM] Hardware drivers not available: {e}")
        print("[SYSTEM] Falling back to mock drivers")
        from app.drivers.printer_mock import PrinterDriver
        from app.drivers.dial_mock import DialDriver
else:
    from app.drivers.printer_mock import PrinterDriver
    from app.drivers.dial_mock import DialDriver
    print("[SYSTEM] Running on non-Raspberry Pi - using mock drivers")

# Global Hardware Instances
# Note: printer will be reinitialized when settings change
printer = PrinterDriver(width=PRINTER_WIDTH, invert=getattr(settings, 'invert_print', False))
dial = DialDriver()


# --- BACKGROUND TASKS ---

email_polling_task = None
scheduler_task = None

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
                        # Use the shortest interval if multiple email modules exist (future proofing)
                        if email_config.polling_interval < min_interval:
                            min_interval = email_config.polling_interval

            # Wait for the interval
            await asyncio.sleep(min_interval)
            
            if not email_modules:
                continue
            
            # Check each email module
            for module in email_modules:
                try:
                    emails = email_client.fetch_emails(module.config)
                    if emails:
                        print(f"[AUTO-POLL] Found {len(emails)} new email(s) in module '{module.name}'. Printing...")
                        email_client.format_email_receipt(printer, messages=emails, config=module.config, module_name=module.name)
                except Exception as e:
                    print(f"[AUTO-POLL] Error checking email module {module.id}: {e}")
                    
        except Exception as e:
            print(f"[AUTO-POLL] Error: {e}")
            await asyncio.sleep(60)  # Wait 1 minute before retrying on error

async def scheduler_loop():
    """
    Checks every minute if any channel is scheduled to run at the current time.
    """
    last_run_minute = ""
    
    while True:
        try:
            # Check every 10 seconds to be precise enough but not wasteful
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
                    print(f"[SCHEDULE] Channel {pos} scheduled for {current_time}. Triggering...")
                    await trigger_channel(pos)
                    
        except Exception as e:
            print(f"[SCHEDULE] Error: {e}")
            await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global email_polling_task, scheduler_task
    # Startup
    print("[SYSTEM] Starting PC-1...")
    email_polling_task = asyncio.create_task(email_polling_loop())
    scheduler_task = asyncio.create_task(scheduler_loop())
    yield
    # Shutdown
    print("[SYSTEM] Shutting down PC-1...")
    if email_polling_task:
        email_polling_task.cancel()
        try:
            await email_polling_task
        except asyncio.CancelledError:
            pass
    if scheduler_task:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
    
    # Cleanup hardware drivers
    if hasattr(printer, 'close'):
        printer.close()
    if hasattr(dial, 'cleanup'):
        dial.cleanup()


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
        "current_module": module_info
    }


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
    
    return {
        "state": "idle", 
        "current_channel": pos,
        "current_module": module_info
    }


# --- SETTINGS API ---


@app.get("/api/settings", response_model=Settings)
async def get_settings():
    return settings


@app.post("/api/settings")
async def update_settings(new_settings: Settings):
    """Updates the configuration and saves it to disk."""
    global settings, printer

    # Check if invert_print setting changed
    old_invert = getattr(settings, 'invert_print', False)
    new_invert = getattr(new_settings, 'invert_print', False)
    
    # Update in-memory
    settings = new_settings

    # Save to disk
    save_config(settings)
    
    # Reinitialize printer if invert setting changed
    if old_invert != new_invert:
        print(f"[SYSTEM] Printer invert setting changed to {new_invert}, reinitializing printer...")
        if hasattr(printer, 'close'):
            printer.close()
        printer = PrinterDriver(width=PRINTER_WIDTH, invert=new_invert)

    return {"message": "Settings saved", "config": settings}

@app.post("/api/settings/reset")
async def reset_settings():
    """Resets all settings to their default values."""
    global settings
    
    # Create fresh settings instance (uses defaults from config.py)
    settings = Settings()
    
    # Save to disk (overwriting existing config.json)
    save_config(settings)
    
    return {"message": "Settings reset to defaults", "config": settings}


# --- MODULE MANAGEMENT API ---


@app.get("/api/modules")
async def list_modules():
    """List all module instances."""
    return {"modules": settings.modules}


@app.post("/api/modules")
async def create_module(module: ModuleInstance):
    """Create a new module instance."""
    global settings
    
    # If no ID provided, generate one
    if not module.id:
        module.id = str(uuid.uuid4())
    
    settings.modules[module.id] = module
    save_config(settings)
    
    return {"message": "Module created", "module": module}


@app.get("/api/modules/{module_id}")
async def get_module(module_id: str):
    """Get a specific module instance."""
    module = settings.modules.get(module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    return module


@app.put("/api/modules/{module_id}")
async def update_module(module_id: str, module: ModuleInstance):
    """Update a module instance."""
    global settings
    
    if module_id not in settings.modules:
        raise HTTPException(status_code=404, detail="Module not found")
    
    # Ensure ID matches
    module.id = module_id
    settings.modules[module_id] = module
    save_config(settings)
    
    return {"message": "Module updated", "module": module}


@app.delete("/api/modules/{module_id}")
async def delete_module(module_id: str):
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
            detail=f"Cannot delete module: it is assigned to channels {assigned_channels}. Remove it from channels first."
        )
    
    del settings.modules[module_id]
    save_config(settings)
    
    return {"message": "Module deleted"}


@app.post("/api/channels/{position}/modules")
async def assign_module_to_channel(position: int, module_id: str, order: Optional[int] = None):
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
        raise HTTPException(status_code=400, detail="Module already assigned to this channel")
    
    # Determine order (default to end)
    if order is None:
        order = max([a.order for a in channel.modules], default=-1) + 1
    
    # Add assignment
    channel.modules.append(ChannelModuleAssignment(module_id=module_id, order=order))
    save_config(settings)
    
    return {"message": "Module assigned to channel", "channel": channel}


@app.delete("/api/channels/{position}/modules/{module_id}")
async def remove_module_from_channel(position: int, module_id: str):
    """Remove a module from a channel."""
    global settings
    
    if position not in settings.channels:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    channel = settings.channels[position]
    
    if not channel.modules:
        raise HTTPException(status_code=404, detail="Module not assigned to this channel")
    
    # Remove assignment
    channel.modules = [a for a in channel.modules if a.module_id != module_id]
    save_config(settings)
    
    return {"message": "Module removed from channel", "channel": channel}


@app.post("/api/channels/{position}/modules/reorder")
async def reorder_channel_modules(position: int, module_orders: Dict[str, int]):
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
    
    save_config(settings)
    
    return {"message": "Modules reordered", "channel": channel}



@app.post("/api/channels/{position}/schedule")
async def update_channel_schedule(position: int, schedule: List[str]):
    """Update the print schedule for a channel."""
    global settings
    
    if position not in settings.channels:
        settings.channels[position] = ChannelConfig(modules=[])
    
    settings.channels[position].schedule = schedule
    save_config(settings)
    
    return {"message": "Schedule updated", "channel": settings.channels[position]}


# --- EVENT ROUTER ---


def execute_module(module: ModuleInstance):
    """Execute a single module instance."""
    module_type = module.type
    config = module.config
    module_name = module.name or module_type.upper()
    
    print(f"[MODULE] Executing {module.name or module_type} (type: {module_type})")
    
    # Dispatch Logic
    if module_type == "webhook":
        try:
            action_config = WebhookConfig(**config)
            webhook.run_webhook(action_config, printer, module_name)
        except Exception as e:
            print(f"[ERROR] Webhook config invalid: {e}")
            printer.print_text("Webhook Configuration Error")
        return
    
    if module_type == "text":
        try:
            text_config = TextConfig(**config)
            text.format_text_receipt(printer, text_config, module_name)
        except Exception as e:
            print(f"[ERROR] Text config invalid: {e}")
            printer.print_text("Text Configuration Error")
        return
    
    if module_type == "calendar":
        try:
            cal_config = CalendarConfig(**config)
            calendar.format_calendar_receipt(printer, cal_config, module_name)
        except Exception as e:
            print(f"[ERROR] Calendar config invalid: {e}")
            printer.print_text("Calendar Configuration Error")
        return
    
    if module_type == "news":
        try:
            news.format_news_receipt(printer, config, module_name)
        except Exception as e:
            print(f"[ERROR] NewsAPI config invalid: {e}")
            printer.print_text("NewsAPI Configuration Error")
        return
    
    if module_type == "rss":
        try:
            rss.format_rss_receipt(printer, config, module_name)
        except Exception as e:
            print(f"[ERROR] RSS config invalid: {e}")
            printer.print_text("RSS Configuration Error")
        return
    
    if module_type == "email":
        try:
            email_config = EmailConfig(**config)
            emails = email_client.fetch_emails(config)
            email_client.format_email_receipt(printer, messages=emails, config=config, module_name=module_name)
        except Exception as e:
            print(f"[ERROR] Email module failed: {e}")
            printer.print_text(f"Email Error: {e}")
        return
    
    if module_type == "games":
        try:
            sudoku.format_sudoku_receipt(printer, config, module_name)
        except Exception as e:
            print(f"[ERROR] Sudoku module failed: {e}")
            printer.print_text(f"Sudoku Error: {e}")
        return
    
    if module_type == "astronomy":
        try:
            astronomy.format_astronomy_receipt(printer, module_name=module_name)
        except Exception as e:
            print(f"[ERROR] Astronomy module failed: {e}")
            printer.print_text(f"Astronomy Error: {e}")
        return
    
    if module_type == "weather":
        try:
            weather.format_weather_receipt(printer, config, module_name)
        except Exception as e:
            print(f"[ERROR] Weather module failed: {e}")
            printer.print_text(f"Weather Error: {e}")
        return
    
    if module_type == "off":
        print("[SYSTEM] Module is disabled. Skipping.")
        return
    
    print(f"[SYSTEM] Unknown module type '{module_type}'")


async def trigger_channel(position: int):
    """
    Executes all modules assigned to a specific channel position.
    """
    # Reset printer buffer at start of print job (for invert mode)
    if hasattr(printer, 'reset_buffer'):
        printer.reset_buffer()
    
    # Get the full ChannelConfig object
    channel = settings.channels.get(position)
    
    if not channel:
        print(f"[SYSTEM] Invalid channel config for position {position}")
        return
    
    # New format: multiple modules
    if channel.modules:
        print(f"[EVENT] Triggered Channel {position} -> {len(channel.modules)} module(s)")
        
        # Sort modules by order
        sorted_modules = sorted(channel.modules, key=lambda m: m.order)
        
        for assignment in sorted_modules:
            module = settings.modules.get(assignment.module_id)
            if module:
                execute_module(module)
                # Add a separator between modules
                if assignment != sorted_modules[-1]:
                    printer.feed(1)
            else:
                print(f"[ERROR] Module {assignment.module_id} not found in module registry")
        
        # Add cutter feed lines at the end of the print job
        feed_lines = getattr(settings, 'cutter_feed_lines', 3)
        
        # If invert is enabled, add final feed to buffer, then flush everything
        if hasattr(printer, 'invert') and printer.invert and hasattr(printer, 'print_buffer'):
            # Add final feed lines to buffer (they'll be at the end, which becomes the start after reversal)
            if feed_lines > 0:
                printer.print_buffer.append(('feed', feed_lines))
            # Flush the entire buffer (reversed) - this prints all content + feed lines
            printer.flush_buffer()
            print(f"[SYSTEM] Added {feed_lines} feed line(s) to clear cutter (inverted)")
        else:
            # Normal mode: just feed normally
            if feed_lines > 0:
                printer.feed(feed_lines)
                print(f"[SYSTEM] Added {feed_lines} feed line(s) to clear cutter")
        return
    
    print(f"[SYSTEM] Channel {position} has no modules assigned")


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




# --- STATIC FILES (FRONTEND) ---

# Mount the built React app
# Ensure 'web/dist' exists (run 'npm run build' in web/ directory first)
if os.path.exists("web/dist"):
    app.mount("/assets", StaticFiles(directory="web/dist/assets"), name="assets")
    
    # Serve index.html for the root and any client-side routes
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # If path starts with api/, let it fall through to API routes
        if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
            raise HTTPException(status_code=404, detail="Not found")
            
        # Otherwise serve the React app
        return FileResponse("web/dist/index.html")
else:
    print("[WARNING] web/dist directory not found. Frontend will not be served.")
