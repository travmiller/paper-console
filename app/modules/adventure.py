"""
Choose Your Own Adventure Module for Paper Console.

This module implements an interactive text adventure game that uses the
dial for selection and the button for confirmation. Position 8 is always
reserved for "Exit/Save & Quit".

The game enters "selection mode" after printing choices, overriding normal
channel switching behavior until the user makes a choice or exits.
"""

import json
import os
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path
from app.module_registry import register_module

logger = logging.getLogger(__name__)


# --- Game State ---

@dataclass
class AdventureState:
    """Persistent game state for an adventure playthrough."""
    current_node: str = "start"
    flags: Dict[str, bool] = field(default_factory=dict)
    visited_nodes: List[str] = field(default_factory=list)
    game_complete: bool = False
    ending_type: Optional[str] = None


def _get_state_path(module_id: str) -> Path:
    """Get the path to save game state for a specific module instance."""
    # __file__ is app/modules/adventure.py
    # Go up one dir to app/, then into data/adventure_saves/
    module_dir = Path(__file__).parent  # app/modules/
    state_dir = module_dir.parent / "data" / "adventure_saves"  # app/data/adventure_saves/
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / f"{module_id}.json"


def load_state(module_id: str) -> AdventureState:
    """Load game state from disk, or create new if not found."""
    state_path = _get_state_path(module_id)
    try:
        if state_path.exists():
            with open(state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return AdventureState(**data)
    except Exception as e:
        logger.warning(f"Could not load adventure state: {e}")
    return AdventureState()


def save_state(module_id: str, state: AdventureState):
    """Save game state to disk."""
    state_path = _get_state_path(module_id)
    try:
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(asdict(state), f, indent=2)
    except Exception as e:
        logger.error(f"Could not save adventure state: {e}")


def reset_state(module_id: str) -> AdventureState:
    """Reset game to beginning."""
    state = AdventureState()
    save_state(module_id, state)
    return state


# --- Story Loading ---

def _get_story_path() -> Path:
    """Get the path to the adventure story file."""
    # __file__ is app/modules/adventure.py
    # Go up one dir to app/, then into data/
    module_dir = Path(__file__).parent  # app/modules/
    return module_dir.parent / "data" / "adventure_story.json"  # app/data/adventure_story.json


def load_story() -> Dict[str, Any]:
    """Load the adventure story from JSON."""
    story_path = _get_story_path()
    try:
        with open(story_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Could not load adventure story: {e}")
        return {"nodes": {}, "meta": {"title": "Error", "version": "0"}}


def get_node(story: Dict, node_id: str) -> Optional[Dict]:
    """Get a story node by ID."""
    return story.get("nodes", {}).get(node_id)


def filter_choices(choices: List[Dict], state: AdventureState) -> List[Dict]:
    """Filter choices based on flags and state."""
    filtered = []
    for choice in choices:
        # Check required flags
        if "requires_flag" in choice:
            if not state.flags.get(choice["requires_flag"]):
                continue
        if "requires_not_flag" in choice:
            if state.flags.get(choice["requires_not_flag"]):
                continue
        filtered.append(choice)
    return filtered


# --- Selection Mode Integration ---

# Global state for selection mode
_selection_mode_active = False
_selection_callback = None
_current_module_id = None


def is_selection_mode_active() -> bool:
    """Check if selection mode is currently active."""
    return _selection_mode_active


def enter_selection_mode(callback, module_id: str):
    """
    Enter selection mode - the next button press will call callback(dial_position).
    
    Args:
        callback: Function to call with dial position (1-8) when button is pressed
        module_id: ID of the module that entered selection mode
    """
    global _selection_mode_active, _selection_callback, _current_module_id
    _selection_mode_active = True
    _selection_callback = callback
    _current_module_id = module_id
    logger.info(f"Adventure: Entered selection mode for module {module_id}")


def exit_selection_mode():
    """Exit selection mode and return to normal channel switching."""
    global _selection_mode_active, _selection_callback, _current_module_id
    _selection_mode_active = False
    _selection_callback = None
    _current_module_id = None
    logger.info("Adventure: Exited selection mode")


def handle_selection(dial_position: int) -> bool:
    """
    Handle a button press while in selection mode.
    
    Returns True if handled (was in selection mode), False otherwise.
    """
    global _selection_callback
    if not _selection_mode_active or _selection_callback is None:
        return False
    
    try:
        _selection_callback(dial_position)
    except Exception as e:
        logger.error(f"Adventure selection callback error: {e}")
        exit_selection_mode()
    
    return True


# --- Print Functions ---

def print_story_node(printer, story: Dict, node: Dict, state: AdventureState, module_name: str):
    """Print a story node with its text and available choices."""
    from datetime import datetime
    
    meta = story.get("meta", {})
    title = meta.get("title", "Adventure")
    
    # Header
    printer.print_header(module_name or title, icon="book")
    
    # Check if this is an ending
    if node.get("ending"):
        ending_type = node.get("ending_type", "unknown")
        
        # Ending-specific styling
        if ending_type == "perfect":
            printer.print_subheader("★ PERFECT ENDING ★")
        elif ending_type == "victory":
            printer.print_subheader("VICTORY!")
        elif ending_type == "partial":
            printer.print_subheader("PARTIAL SUCCESS")
        elif ending_type == "death":
            printer.print_subheader("GAME OVER")
        else:
            printer.print_subheader("THE END")
        
        printer.print_line()
    
    # Story text
    text = node.get("text", "")
    printer.print_body(text)
    printer.print_line()
    
    # If ending, show restart prompt
    if node.get("ending"):
        printer.feed(1)
        printer.print_caption("Your adventure has ended.")
        printer.print_caption("Press button to start anew.")
        printer.print_line()
        return
    
    # Print choices
    choices = node.get("choices", [])
    filtered_choices = filter_choices(choices, state)
    
    if not filtered_choices:
        printer.print_caption("No choices available...")
        printer.print_line()
        return
    
    printer.print_subheader("WHAT DO YOU DO?")
    printer.feed(1)
    
    # Print each choice with its dial number
    for i, choice in enumerate(filtered_choices, 1):
        dial_num = choice.get("dial", i)
        choice_text = choice.get("text", "???")
        # Use box drawing for visual hierarchy
        printer.print_body(f"  [{dial_num}] {choice_text}")
    
    printer.feed(1)
    
    # Always show Exit option on position 8
    printer.print_caption("  [8] Save & Exit")
    
    printer.print_line()
    
    # Instructions
    printer.print_caption("Turn dial to choice, press button")
    printer.feed(1)


def process_choice(module_id: str, dial_position: int, printer):
    """
    Process a player's choice and advance the game.
    
    This is called by the selection mode callback when button is pressed.
    """
    from app.hardware import printer as hw_printer
    
    # Use the hardware printer
    printer = hw_printer
    
    # Position 8 is always Exit
    if dial_position == 8:
        exit_selection_mode()
        
        # Print exit confirmation
        if hasattr(printer, "reset_buffer"):
            printer.reset_buffer()
        
        printer.print_header("ADVENTURE", icon="book")
        printer.print_body("Game saved. See you next time!")
        printer.print_line()
        printer.print_caption("Turn dial to select a channel,")
        printer.print_caption("then press button to continue.")
        printer.feed(1)
        
        if hasattr(printer, "flush_buffer"):
            printer.flush_buffer()
        return
    
    # Load current state and story
    state = load_state(module_id)
    story = load_story()
    current_node = get_node(story, state.current_node)
    
    if not current_node:
        logger.error(f"Adventure: Node not found: {state.current_node}")
        exit_selection_mode()
        return
    
    # Handle game over / endings - any button starts new game
    if current_node.get("ending"):
        state = reset_state(module_id)
        current_node = get_node(story, "start")
    else:
        # Find the selected choice
        choices = filter_choices(current_node.get("choices", []), state)
        selected_choice = None
        
        for choice in choices:
            if choice.get("dial") == dial_position:
                selected_choice = choice
                break
        
        if not selected_choice:
            # Invalid selection - just reprint current node
            if hasattr(printer, "reset_buffer"):
                printer.reset_buffer()
            
            printer.print_header("ADVENTURE", icon="book")
            printer.print_body(f"Invalid choice: {dial_position}")
            printer.print_caption("Please select a valid option.")
            printer.print_line()
            
            if hasattr(printer, "flush_buffer"):
                printer.flush_buffer()
            
            # Stay in selection mode
            return
        
        # Get next node
        next_node_id = selected_choice.get("next")
        if not next_node_id:
            logger.error(f"Adventure: No next node for choice")
            exit_selection_mode()
            return
        
        # Update state
        state.current_node = next_node_id
        state.visited_nodes.append(next_node_id)
        
        # Process the new node for flags
        new_node = get_node(story, next_node_id)
        if new_node:
            # Set flags from the node
            if "set_flag" in new_node:
                state.flags[new_node["set_flag"]] = True
            if "set_flag2" in new_node:
                state.flags[new_node["set_flag2"]] = True
            
            # Check for ending
            if new_node.get("ending"):
                state.game_complete = True
                state.ending_type = new_node.get("ending_type")
        
        current_node = new_node
    
    # Save state
    save_state(module_id, state)
    
    # Print the new node
    if hasattr(printer, "reset_buffer"):
        printer.reset_buffer()
    
    story = load_story()  # Ensure fresh story data
    print_story_node(printer, story, current_node, state, "ADVENTURE")
    
    if hasattr(printer, "flush_buffer"):
        printer.flush_buffer()
    
    # If not an ending, re-enter selection mode for next choice
    if not current_node.get("ending"):
        enter_selection_mode(
            lambda pos: process_choice(module_id, pos, printer),
            module_id
        )


# --- Module Registration ---

@register_module(
    type_id="adventure",
    label="Adventure Game",
    description="A choose-your-own-adventure text game! Make choices with the dial, confirm with button.",
    icon="book",
    offline=True,
    category="games",
    config_schema={
        "type": "object",
        "properties": {
            "reset_game": {
                "type": "boolean",
                "title": "Reset Game",
                "description": "Check this to start the adventure over from the beginning",
                "default": False
            }
        },
    },
)
def format_adventure_receipt(
    printer, config: Dict[str, Any] = None, module_name: str = None, module_id: str = None
):
    """
    Main entry point for the adventure module.
    
    Prints the current story state and enters selection mode for player input.
    """
    config = config or {}
    
    # Generate a module ID if not provided
    if not module_id:
        module_id = "adventure-default"
    
    # Check if reset requested
    if config.get("reset_game"):
        state = reset_state(module_id)
        # Clear the reset flag (this won't persist but clears the intent)
    else:
        state = load_state(module_id)
    
    # Load story
    story = load_story()
    meta = story.get("meta", {})
    
    # Get current node
    current_node = get_node(story, state.current_node)
    if not current_node:
        printer.print_header("ADVENTURE ERROR", icon="alert")
        printer.print_body(f"Story node not found: {state.current_node}")
        printer.print_caption("Try resetting the game in settings.")
        printer.print_line()
        return
    
    # Process any flags from current node (in case we're resuming)
    if "set_flag" in current_node and not state.flags.get(current_node["set_flag"]):
        state.flags[current_node["set_flag"]] = True
        save_state(module_id, state)
    
    # Print the current story node
    print_story_node(printer, story, current_node, state, module_name or meta.get("title", "Adventure"))
    
    # Enter selection mode (unless it's an ending)
    # Note: Selection mode will be checked by main.py's button handler
    if not current_node.get("ending"):
        enter_selection_mode(
            lambda pos: process_choice(module_id, pos, printer),
            module_id
        )
