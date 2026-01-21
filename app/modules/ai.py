"""
AI Module for Paper Console.

This module provides an interactive AI assistant that communicates via the
paper console. It uses the OpenAI API to generate responses and dynamic
choices for the user, creating an "infinite menu" experience.
"""

import logging
import json
import os
from typing import Dict, Any, List, Optional
from pathlib import Path
from pydantic import BaseModel

from app.module_registry import register_module
from app.selection_mode import enter_selection_mode, exit_selection_mode

logger = logging.getLogger(__name__)

# Try to import OpenAI, but don't fail if not installed
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    logger.warning("OpenAI library not found. AI module will not function.")


# --- State Management ---

def _get_conversation_path(module_id: str) -> Path:
    """Get the path to save conversation history."""
    module_dir = Path(__file__).parent
    state_dir = module_dir.parent / "data" / "ai_conversations"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / f"{module_id}.json"


def load_history(module_id: str) -> List[Dict[str, str]]:
    """Load conversation history from disk."""
    path = _get_conversation_path(module_id)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading AI history: {e}")
    return []


def save_history(module_id: str, history: List[Dict[str, str]]):
    """Save conversation history to disk."""
    path = _get_conversation_path(module_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving AI history: {e}")


def clear_history(module_id: str):
    """Clear conversation history."""
    path = _get_conversation_path(module_id)
    if path.exists():
        try:
            os.remove(path)
        except Exception:
            pass


# --- AI Logic ---

def get_openai_client(api_key: str):
    """Get OpenAI client."""
    if not HAS_OPENAI:
        return None
    return OpenAI(api_key=api_key)


def generate_response(
    api_key: str,
    model: str,
    system_prompt: str,
    history: List[Dict[str, str]],
    user_input: str
):
    """
    Generate a response from the AI.
    
    We ask the AI to return a JSON object with:
    - response_text: The main text to print.
    - options: A list of 1-7 short strings for the next choices.
    """
    client = get_openai_client(api_key)
    if not client:
        return {
            "response_text": "Error: OpenAI library not installed.",
            "options": ["Exit"]
        }

    # Prepare messages
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add instructions for JSON format
    json_instruction = (
        "\n\nIMPORTANT: You must respond in valid JSON format with the following structure:\n"
        "{\n"
        '  "response_text": "Your response here (keep it concise for thermal printer)",\n'
        '  "options": ["Option 1", "Option 2", ... max 7 options]\n'
        "}\n"
        "The 'options' should be suggested follow-up actions or topics for the user.\n"
        "CRITICAL INSTRUCTION: If the user asks for content (like a recipe, story, fact, etc.), provide the FULL CONTENT in 'response_text'. \n"
        "Do not just ask clarifying questions unless absolutely necessary. \n"
        "For example, if asked for a dinner idea, suggest a specific dish AND its recipe (or a brief summary of it), then use options for 'Different Idea', 'More Details', or related topics.\n"
        "DO NOT list the options in the 'response_text'. They will be displayed automatically by the UI as a menu.\n"
        "If you are providing a direct answer (like a recipe or fact) that concludes the immediate interaction, you may return an empty list [] for 'options'. The system will provide default continuation options (Start Over, Tell me more).\n"
        "Keep the text formatted nicely for a 42-column display.\n\n"
        "EXAMPLE of CORRECT response (Options):\n"
        "{\n"
        '  "response_text": "Spaghetti Carbonara:\\n1. Boil pasta.\\n2. Fry guanciale.\\n3. Mix eggs and cheese.\\n4. Combine all.",\n'
        '  "options": ["Vegetarian Version", "Wine Pairing", "Dessert Ideas"]\n'
        "}\n\n"
        "EXAMPLE of CORRECT response (Final/Direct Answer):\n"
        "{\n"
        '  "response_text": "The capital of France is Paris.",\n'
        '  "options": []\n'
        "}\n\n"
        "EXAMPLE of WRONG response (Do NOT do this):\n"
        "{\n"
        '  "response_text": "Here is a recipe... What would you like next?\\n1. Vegeterian Version\\n2. Wine Pairing",\n'
        '  "options": ["Vegetarian Version", "Wine Pairing"]\n'
        "}"
    )
    messages[0]["content"] += json_instruction
    
    # Add history
    messages.extend(history)
    
    # Add current user input
    messages.append({"role": "user", "content": user_input})

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        content = completion.choices[0].message.content
        return json.loads(content)
        
    except Exception as e:
        logger.error(f"OpenAI API Error: {e}")
        return {
            "response_text": f"Error communicating with AI: {str(e)}",
            "options": ["Retry", "Exit"]
        }


def reset_to_initial(printer, config: Dict[str, Any], module_id: str):
    """Reset to the initial state with configured prompts."""
    clear_history(module_id)
    
    initial_prompts = config.get("initial_prompts", [
        "Tell me a joke", "Give me a fun fact", "Play a game"
    ])
    # Limit to 7
    initial_prompts = initial_prompts[:7]
    
    # Enter selection mode for initial prompts
    enter_selection_mode(
        lambda pos: handle_selection(pos, printer, config, module_id, initial_prompts),
        module_id
    )

    print_ai_menu(printer, "How can I help you?", initial_prompts)


# --- Interaction Loop ---

def print_ai_menu(printer, text: str, options: List[str]):
    """Print the AI's response and the numbered options."""
    if hasattr(printer, "reset_buffer"):
        printer.reset_buffer()
        
    printer.print_header("AI ASSISTANT", icon="cpu")
    printer.print_body(text)
    printer.print_line()
    
    if not options:
        printer.print_caption("No options available.")
    else:
        printer.print_subheader("OPTIONS")
        for i, opt in enumerate(options, 1):
            if i > 7: break
            printer.print_body(f"[{i}] {opt}")
            
    printer.feed(1)
    printer.print_caption("[8] Exit / Reset")
    printer.print_line()
    
    if hasattr(printer, "flush_buffer"):
        printer.flush_buffer()


def handle_selection(
    dial_position: int,
    printer,
    config: Dict[str, Any],
    module_id: str,
    current_options: List[str]
):
    """Handle user selection from the menu."""
    
    # 8 is always Exit/Reset
    if dial_position == 8:
        # Check if we were already at root/initial. If so, exit mode.
        # Otherwise, offer to go back to root or exit completely.
        # For simplicity, let's just exit selection mode.
        exit_selection_mode()
        
        if hasattr(printer, "reset_buffer"):
            printer.reset_buffer()
        printer.print_header("AI ASSISTANT", icon="cpu")
        printer.print_body("Goodbye!")
        printer.print_line()
        if hasattr(printer, "flush_buffer"):
            printer.flush_buffer()
        return

    # Invalid selection
    if dial_position < 1 or dial_position > len(current_options):
        # Reprint current menu
        print_ai_menu(printer, "Invalid selection. Try again.", current_options)
        return

    # Valid selection
    selected_text = current_options[dial_position - 1]
    
    # Handle "Start Over" special case
    if selected_text == "Start Over":
        reset_to_initial(printer, config, module_id)
        return

    # 2. Call API
    api_key = config.get("openai_api_key")
    if not api_key:
        # Fallback to config.py settings if available
        # But here we assume config passed in is the merged config
        pass

    model = config.get("model", "gpt-4o-mini")
    system_prompt = config.get("system_prompt", "You are a helpful assistant.")
    
    history = load_history(module_id)
    
    # Generate response
    result = generate_response(api_key, model, system_prompt, history, selected_text)
    
    response_text = result.get("response_text", "Error: No response")
    new_options = result.get("options", [])

    # If options are empty, inject defaults
    if not new_options:
        new_options = ["Tell me more", "Start Over"]
    
    # Limit options
    new_options = new_options[:7]
    
    # 3. Update History
    history.append({"role": "user", "content": selected_text})
    history.append({"role": "assistant", "content": response_text}) # Should really store the JSON or just text? Text is standard.
    
    save_history(module_id, history)
    
    # 4. Re-enter selection mode with NEW options
    enter_selection_mode(
        lambda pos: handle_selection(pos, printer, config, module_id, new_options),
        module_id
    )

    # 5. Print Result & New Menu
    print_ai_menu(printer, response_text, new_options)



# --- Module Entry Point ---

@register_module(
    type_id="ai",
    label="AI Assistant",
    description="Interactive AI chat with infinite choices.",
    icon="cpu",
    offline=False,
    interactive=True,
    category="utilities",
    config_schema={
        "type": "object",
        "properties": {
            "openai_api_key": {
                "type": "string",
                "title": "OpenAI API Key",
                "description": "Your OpenAI API Key (starts with sk-)"
            },
            "model": {
                "type": "string", 
                "title": "Model",
                "default": "gpt-4o-mini",
                "enum": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]
            },
            "system_prompt": {
                "type": "string",
                "title": "System Persona",
                "default": "You are a helpful assistant.",
                "description": "Defines how the AI behaves."
            },
            "initial_prompts": {
                "type": "array",
                "title": "Initial Options",
                "items": {"type": "string"},
                "description": "The list of options shown when you start the module (max 7).",
                "maxItems": 7
            },
            "reset_chat": {
                "type": "boolean",
                "title": "Reset Conversation",
                "description": "Start a fresh conversation next time.",
                "default": False
            }
        },
        "required": ["openai_api_key"]
    },
)
def format_ai_utility(
    printer, config: Dict[str, Any] = None, module_name: str = None, module_id: str = None
):
    """
    Main entry point for the AI module.
    """
    config = config or {}
    
    if not module_id:
        module_id = "ai-default"
        
    # Check for reset flag
    if config.get("reset_chat"):
        clear_history(module_id)
        # We can't easily unset the flag in config here without saving back to `Settings`, 
        # so we just rely on the user unchecking it or us clearing it if we had a better config system.
        
    # Check API Key
    api_key = config.get("openai_api_key")
    if not api_key:
        printer.print_header(module_name or "AI Assistant", icon="cpu")
        printer.print_body("API Key Missing!")
        printer.print_body("Please configure openai_api_key in settings.")
        printer.print_line()
        return

    # Check history to decide if we resume or show initial
    history = load_history(module_id)
    
    if not history:
        reset_to_initial(printer, config, module_id)
    else:
        # Resume conversation
        # We need to generate a "What now?" state or just show the last state?
        # Ideally we'd have the *last set of options* saved too.
        # For now, let's just Generate a "Resume" menu.
        
        # Simplified resume: Just ask AI to summarize and give options
        printer.print_header(module_name or "AI Assistant", icon="cpu")
        printer.print_body("Resuming conversation...")
        
        # We trigger a "dummy" generic prompt to get the ball rolling again
        # OR we could just reset to initial if we can't restore options.
        # Let's try to restore by generating new options from context.
        result = generate_response(
            api_key, 
            config.get("model", "gpt-4o-mini"), 
            config.get("system_prompt", ""), 
            history, 
            "Resume conversation. Provide a brief summary of where we were and suggested next options."
        )
        
        response_text = result.get("response_text", "Resumed.")
        new_options = result.get("options", [])
        
        enter_selection_mode(
            lambda pos: handle_selection(pos, printer, config, module_id, new_options),
            module_id
        )

        print_ai_menu(printer, response_text, new_options)

