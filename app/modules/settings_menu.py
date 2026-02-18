"""
Settings Menu Module for Paper Console.

Provides a hardware-accessible settings menu using the selection mode system.
Users can access common settings and actions directly from the dial without
needing a phone or computer.

Options:
  [1] Show Channels - Print what's assigned to each channel
  [2] System Status - Network, storage, memory info
  [3] Reset WiFi - Enter AP mode for setup
  [4] Factory Reset - Clear all settings (with confirmation)
  [8] Exit
"""

import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


# --- Selection Mode (from shared module) ---

from app.selection_mode import (
    enter_selection_mode,
    exit_selection_mode,
)


# --- Menu Actions ---

def _print_channels(printer):
    """Print what's assigned to each channel."""
    from app.config import settings
    
    printer.print_header("CHANNELS", icon="list")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()
    
    for channel_num in range(1, 9):
        channel = settings.channels.get(channel_num)
        if channel and channel.modules:
            # Get module names
            module_names = []
            for assignment in sorted(channel.modules, key=lambda m: m.order):
                module_id = assignment.module_id
                if module_id in settings.modules:
                    module = settings.modules[module_id]
                    module_names.append(module.name)
            
            if module_names:
                modules_str = " + ".join(module_names)
                printer.print_body(f"[{channel_num}] {modules_str}")
            else:
                printer.print_caption(f"[{channel_num}] (empty)")
        else:
            printer.print_caption(f"[{channel_num}] (empty)")
    
    printer.print_line()
    printer.print_caption("Visit http://pc-1.local")
    printer.print_caption("to configure channels")
    printer.feed(1)


def _print_system_status(printer):
    """Print system status (reuse system_monitor module)."""
    from app.modules.system_monitor import format_system_monitor_receipt
    format_system_monitor_receipt(printer, {}, "SYSTEM STATUS")


def _trigger_ap_mode(printer):
    """Enter AP mode for WiFi setup."""
    import app.wifi_manager as wifi_manager
    import asyncio
    
    printer.print_header("WIFI RESET", icon="wifi")
    printer.print_line()
    printer.print_body("Starting WiFi setup mode...")
    printer.print_body("")
    printer.print_body("Connect to network:")
    printer.print_bold(f"  {wifi_manager.get_ap_ssid()}")
    printer.print_caption(f"  Password: {wifi_manager.get_ap_password()}")
    printer.print_line()
    printer.print_body("Then visit:")
    printer.print_bold("  http://10.42.0.1")
    printer.print_line()
    
    # Flush before triggering AP mode
    if hasattr(printer, "flush_buffer"):
        printer.flush_buffer()
    
    # Trigger AP mode in background
    try:
        wifi_manager.start_ap_mode()
    except Exception as e:
        logger.error(f"Failed to start AP mode: {e}")


def _confirm_factory_reset(printer, module_id: str):
    """Show factory reset confirmation."""
    # use global enter_selection_mode / exit_selection_mode
    
    printer.print_header("FACTORY RESET", icon="alert")
    printer.print_line()
    printer.print_bold("⚠ WARNING ⚠")
    printer.print_body("")
    printer.print_body("This will delete ALL")
    printer.print_body("settings and reboot.")
    printer.print_body("")
    printer.print_body("WiFi passwords, module")
    printer.print_body("configs, and channels")
    printer.print_body("will be erased.")
    printer.print_line()
    printer.print_subheader("ARE YOU SURE?")
    printer.feed(1)
    printer.print_body("  [1] Yes, Reset Everything")
    printer.print_caption("  [8] Cancel")
    printer.print_line()
    
    if hasattr(printer, "flush_buffer"):
        printer.flush_buffer()
    
    # Enter selection mode for confirmation
    def handle_reset_confirmation(dial_position: int):
        from app.hardware import printer as hw_printer
        
        if dial_position == 1:
            # Confirmed - do factory reset
            exit_selection_mode()
            _do_factory_reset(hw_printer)
        else:
            # Cancelled - return to main menu
            exit_selection_mode()
            
            if hasattr(hw_printer, "reset_buffer"):
                hw_printer.reset_buffer()
            
            hw_printer.print_header("SETTINGS", icon="settings")
            hw_printer.print_body("Factory reset cancelled.")
            hw_printer.print_line()
            hw_printer.feed(1)
            
            if hasattr(hw_printer, "flush_buffer"):
                hw_printer.flush_buffer()
    
    enter_selection_mode(handle_reset_confirmation, f"{module_id}-reset-confirm")


def _do_factory_reset(printer):
    """Actually perform factory reset."""
    import os
    import subprocess
    
    printer.print_header("RESETTING...", icon="alert")
    printer.print_line()
    printer.print_body("Clearing all settings...")
    printer.print_body("Device will reboot.")
    printer.print_line()
    printer.feed(1)
    
    if hasattr(printer, "flush_buffer"):
        printer.flush_buffer()
    
    # Delete config files
    try:
        import app.config as config_module
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(config_module.__file__)))
        config_path = os.path.join(base_dir, "config.json")
        backup_path = os.path.join(base_dir, "config.json.bak")
        welcome_marker = os.path.join(base_dir, ".welcome_printed")
        
        for path in [config_path, backup_path, welcome_marker]:
            if os.path.exists(path):
                os.remove(path)
    except Exception as e:
        logger.error(f"Error deleting config: {e}")
    
    # Forget WiFi networks
    try:
        import app.wifi_manager as wifi_manager
        wifi_manager.forget_all_wifi()
    except Exception as e:
        logger.error(f"Error forgetting WiFi: {e}")
    
    # Reboot
    try:
        subprocess.run(["sudo", "reboot"], check=False)
    except Exception as e:
        logger.error(f"Error rebooting: {e}")


# --- Main Menu Logic ---

def _show_main_menu(printer, module_id: str, module_name: str = None):
    """Print the main settings menu."""
    printer.print_header(module_name or "SETTINGS", icon="settings")
    printer.print_caption(datetime.now().strftime("%I:%M %p"))
    printer.print_line()
    
    printer.print_body("  [1] Show Channels")
    printer.print_body("  [2] System Status")
    printer.print_body("  [3] Reset WiFi")
    printer.print_body("  [4] Factory Reset")
    printer.feed(1)
    printer.print_caption("  [8] Exit")
    printer.print_line()
    printer.print_caption("Turn dial to choice, press button")
    printer.feed(1)


def _handle_menu_choice(module_id: str, dial_position: int, module_name: str):
    """Handle a menu selection."""
    from app.hardware import printer
    # use global enter_selection_mode / exit_selection_mode
    
    if dial_position == 8:
        # Exit
        exit_selection_mode()
        
        if hasattr(printer, "reset_buffer"):
            printer.reset_buffer()
        
        printer.print_header("SETTINGS", icon="settings")
        printer.print_body("Exiting settings menu.")
        printer.print_line()
        printer.print_caption("Turn dial to select a channel,")
        printer.print_caption("then press button to continue.")
        printer.feed(1)
        
        if hasattr(printer, "flush_buffer"):
            printer.flush_buffer()
        return
    
    if hasattr(printer, "reset_buffer"):
        printer.reset_buffer()
    
    if dial_position == 1:
        # Show Channels
        _print_channels(printer)
    elif dial_position == 2:
        # System Status
        _print_system_status(printer)
    elif dial_position == 3:
        # Reset WiFi (AP mode)
        _trigger_ap_mode(printer)
        return  # Don't re-enter menu after AP mode
    elif dial_position == 4:
        # Factory Reset (needs confirmation)
        _confirm_factory_reset(printer, module_id)
        return  # Confirmation handler will take over
    else:
        # Invalid choice
        printer.print_header("SETTINGS", icon="settings")
        printer.print_body(f"Invalid choice: {dial_position}")
        printer.print_caption("Please select a valid option.")
        printer.print_line()
    
    if hasattr(printer, "flush_buffer"):
        printer.flush_buffer()
    
    # Re-enter selection mode to return to menu or make another choice
    enter_selection_mode(
        lambda pos: _handle_menu_choice(module_id, pos, module_name),
        module_id
    )


# --- Public Entry Point ---

def format_settings_menu_receipt(
    printer, config: Dict[str, Any] = None, module_name: str = None, module_id: str = None
):
    """
    Main entry point for the settings menu module.
    
    Prints the menu and enters selection mode for user input.
    """
    # use global enter_selection_mode / exit_selection_mode
    
    # Generate a module ID if not provided
    if not module_id:
        module_id = "settings-default"
    
    # Show main menu
    _show_main_menu(printer, module_id, module_name)
    
    # Enter selection mode
    enter_selection_mode(
        lambda pos: _handle_menu_choice(module_id, pos, module_name or "SETTINGS"),
        module_id
    )
