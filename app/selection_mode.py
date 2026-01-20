"""
Selection Mode System for Paper Console.

This module provides infrastructure for interactive modules that need to
override normal channel switching behavior. When selection mode is active,
button presses read the dial position and pass it to a callback function
instead of triggering the current channel.

Example usage:
    from app.selection_mode import enter_selection_mode, exit_selection_mode
    
    def my_callback(dial_position: int):
        if dial_position == 8:
            exit_selection_mode()
        else:
            # Process the choice...
            pass
    
    enter_selection_mode(my_callback, "my-module-id")
"""

import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


# --- Selection Mode State ---

_selection_mode_active = False
_selection_callback: Optional[Callable[[int], None]] = None
_current_module_id: Optional[str] = None


def is_selection_mode_active() -> bool:
    """Check if selection mode is currently active."""
    return _selection_mode_active


def get_current_module_id() -> Optional[str]:
    """Get the ID of the module that owns the current selection mode."""
    return _current_module_id


def enter_selection_mode(callback: Callable[[int], None], module_id: str):
    """
    Enter selection mode - the next button press will call callback(dial_position).
    
    Args:
        callback: Function to call with dial position (1-8) when button is pressed
        module_id: ID of the module that entered selection mode (for debugging)
    """
    global _selection_mode_active, _selection_callback, _current_module_id
    _selection_mode_active = True
    _selection_callback = callback
    _current_module_id = module_id
    logger.info(f"Selection mode: Entered for module {module_id}")


def exit_selection_mode():
    """Exit selection mode and return to normal channel switching."""
    global _selection_mode_active, _selection_callback, _current_module_id
    _selection_mode_active = False
    _selection_callback = None
    _current_module_id = None
    logger.info("Selection mode: Exited")


def handle_selection(dial_position: int) -> bool:
    """
    Handle a button press while in selection mode.
    
    This is called by main.py when the button is pressed and selection mode is active.
    
    Args:
        dial_position: The current dial position (1-8)
    
    Returns:
        True if handled (was in selection mode), False otherwise.
    """
    global _selection_callback
    if not _selection_mode_active or _selection_callback is None:
        return False
    
    try:
        _selection_callback(dial_position)
    except Exception as e:
        logger.error(f"Selection mode callback error: {e}")
        exit_selection_mode()
    
    return True
