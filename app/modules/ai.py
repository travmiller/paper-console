"""
AI Module for Paper Console - Curator Pattern.

This module provides an AI assistant that makes confident decisions
based on context (time, weather) rather than asking clarifying questions.
"""

import logging
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

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


# --- Default AI Modes ---

# --- AI Presets ---
PROMPT_PRESETS = {
    "recipe": {
        "label": "Instant Recipe",
        "values": {
            "prompt": (
                "You are a Michelin star chef. "
                "Based on the time of day and weather, suggest ONE perfect dish. "
                "Format: Title, Ingredients (bullet points), 3-step instructions. "
                "Keep it under 100 words."
            )
        }
    },
    "story": {
        "label": "Micro-Story",
        "values": {
            "prompt": (
                "You are a master of flash fiction. "
                "Write a compelling story in exactly 3 sentences. "
                "Theme: Use the current weather as a mood setter."
            )
        }
    },
    "coach": {
        "label": "Life Coach",
        "values": {
            "prompt": (
                "You are a stoic philosopher. "
                "Give the user a single, hard-hitting piece of advice for their day. "
                "Be direct, not fluffy."
            )
        }
    },
    "roast": {
        "label": "Roast Me",
        "values": {
            "prompt": (
                "You are a snarky comedian. "
                "Roast the user for owning a 'Paper Console' in the current year. "
                "Be funny but not mean."
            )
        }
    },
    "explain": {
        "label": "Explain It",
        "values": {
            "prompt": (
                "You are a science communicator like Carl Sagan. "
                "Explain a random complex topic (Quantum Physics, Black Holes, Mycology) "
                "simply and beautifully in 50 words."
            )
        }
    }
}


# --- Context Gathering ---

def get_time_context() -> Dict[str, str]:
    """Get time-based context for AI."""
    now = datetime.now()
    hour = now.hour
    
    if 5 <= hour < 12:
        time_of_day = "morning"
    elif 12 <= hour < 17:
        time_of_day = "afternoon"
    elif 17 <= hour < 21:
        time_of_day = "evening"
    else:
        time_of_day = "night"
    
    # Determine season (Northern Hemisphere approximation)
    month = now.month
    if month in [12, 1, 2]:
        season = "winter"
    elif month in [3, 4, 5]:
        season = "spring"
    elif month in [6, 7, 8]:
        season = "summer"
    else:
        season = "fall"
    
    return {
        "time_of_day": time_of_day,
        "hour": str(hour),
        "season": season,
        "day_of_week": now.strftime("%A"),
        "date": now.strftime("%B %d")
    }


def get_weather_context() -> Dict[str, str]:
    """Get weather context from settings if available."""
    try:
        from app.config import settings
        # Try to get cached weather data if we have a weather module
        # For now, return basic location info
        return {
            "latitude": str(settings.latitude),
            "longitude": str(settings.longitude),
            "timezone": settings.timezone
        }
    except Exception:
        return {}


def build_context_string() -> str:
    """Build a context string for the AI."""
    time_ctx = get_time_context()
    weather_ctx = get_weather_context()
    
    context = f"Current context: It's {time_ctx['time_of_day']} ({time_ctx['day_of_week']}, {time_ctx['date']}). "
    context += f"Season: {time_ctx['season']}. "
    
    if weather_ctx.get("timezone"):
        context += f"Timezone: {weather_ctx['timezone']}. "
    
    return context


# --- State Management ---

def _get_state_path(module_id: str) -> Path:
    """Get the path to save module state."""
    module_dir = Path(__file__).parent
    state_dir = module_dir.parent / "data" / "ai_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / f"{module_id}.json"


def load_state(module_id: str) -> Dict[str, Any]:
    """Load module state (current mode, last prompt, etc.)."""
    path = _get_state_path(module_id)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_state(module_id: str, state: Dict[str, Any]):
    """Save module state."""
    path = _get_state_path(module_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving AI state: {e}")


def clear_state(module_id: str):
    """Clear module state."""
    path = _get_state_path(module_id)
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


def generate_content(
    api_key: str,
    model: str,
    mode_prompt: str,
    context: str
) -> Dict[str, Any]:
    """
    Generate content using the Curator pattern.
    No conversation history - just direct content generation.
    """
    client = get_openai_client(api_key)
    if not client:
        return {
            "content": "Error: OpenAI library not installed.",
            "success": False
        }

    # Curator system prompt - confident, no questions
    system_prompt = (
        "You are a CURATOR for the PC-1, a thermal printer.\n\n"
        "RULES:\n"
        "1. NEVER ask questions. Make confident decisions.\n"
        "2. Deliver the actual content (recipe, story, advice) immediately.\n"
        "3. Keep output under 100 words (thermal paper is limited).\n"
        "4. Be creative and surprising - make each result unique.\n"
        "5. Use the context (time, season) to inform your choices.\n\n"
        f"Your persona/task: {mode_prompt}\n"
    )

    user_message = f"{context}\n\nGenerate content now. Be creative and confident."

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=300
        )
        
        content = completion.choices[0].message.content
        return {
            "content": content.strip(),
            "success": True
        }
        
    except Exception as e:
        logger.error(f"OpenAI API Error: {e}")
        return {
            "content": f"Error: {str(e)}",
            "success": False
        }


# --- Printing ---

def print_content(printer, mode_label: str, content: str):
    """Print AI content to paper."""
    if hasattr(printer, "reset_buffer"):
        printer.reset_buffer()
        
    printer.print_header(mode_label.upper(), icon="cpu")
    printer.print_body(content)
    printer.print_line()
    
    # Simple reroll options
    printer.print_subheader("OPTIONS")
    printer.print_body("[1] Reroll")
    printer.print_body("[2] Back to Menu")
    printer.feed(1)
    printer.print_caption("[8] Exit")
    printer.print_line()
    
    if hasattr(printer, "flush_buffer"):
        printer.flush_buffer()






# --- Selection Handlers ---

def handle_content_selection(
    dial_position: int,
    printer,
    config: Dict[str, Any],
    module_id: str,
    prompt: str,
    module_name: str
):
    """Handle selection after content is shown (Reroll / Exit)."""
    
    # Exit
    if dial_position == 8:
        clear_state(module_id)
        exit_selection_mode()
        if hasattr(printer, "reset_buffer"):
            printer.reset_buffer()
        printer.print_header(module_name.upper(), icon="cpu")
        printer.print_body("See you next time!")
        printer.print_line()
        if hasattr(printer, "flush_buffer"):
            printer.flush_buffer()
        return
    
    # [1] Reroll
    if dial_position == 1:
        api_key = config.get("openai_api_key")
        model = config.get("model", "gpt-4o-mini")
        context = build_context_string()
        
        result = generate_content(api_key, model, prompt, context)
        
        # Stay in content mode
        enter_selection_mode(
            lambda pos: handle_content_selection(pos, printer, config, module_id, prompt, module_name),
            module_id
        )
        
        print_content(printer, module_name, result["content"])
        return
    
    # [2] Back to Menu - NOT APPLICABLE (Just Exit)
    if dial_position == 2:
        # Treat as exit for now in single-prompt mode, or maybe loop back?
        # Let's just exit.
        clear_state(module_id)
        exit_selection_mode()
        return

    # Invalid - reprint current view
    print_content(printer, module_name, "Select [1] to Reroll or [8] to Exit.")


# --- Module Entry Point ---

@register_module(
    type_id="ai",
    label="AI Assistant",
    description="AI curator that delivers content based on context.",
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
            "prompt": {
                "type": "string",
                "title": "Prompt",
                "description": "The system instruction for the AI."
            }
        },
        "required": ["openai_api_key", "prompt"]
    },
    ui_schema={
        "prompt": {
            "ui:widget": "textarea",
            "ui:options": {
                "rows": 5
            },
            "ui:randomExample": [p["values"]["prompt"] for p in PROMPT_PRESETS.values()]
        }
    },
)
def format_ai_utility(
    printer, config: Dict[str, Any] = None, module_name: str = None, module_id: str = None
):
    """
    Main entry point for the AI module (Curator pattern).
    """
    config = config or {}
    
    if not module_id:
        module_id = "ai-default"
    
    # Check API Key
    api_key = config.get("openai_api_key")
    if not api_key:
        printer.print_header(module_name or "AI Assistant", icon="cpu")
        printer.print_body("API Key Missing!")
        printer.print_body("Please configure openai_api_key in settings.")
        printer.print_line()
        return

    # Get prompt from config
    prompt = config.get("prompt")
    if not prompt:
        # Fallback if unconfigured?
        prompt = "You are a helpful assistant. Provide a random interesting fact."
    
    # Check if we have a saved state (resuming)
    state = load_state(module_id)
    # We don't really need state for resuming to a mode anymore, 
    # but we can check if we were "active".
    # For now, just generate fresh.
    
    # Generate content
    context = build_context_string()
    model = config.get("model", "gpt-4o-mini")
    
    result = generate_content(api_key, model, prompt, context)
    
    # Enter content view mode
    enter_selection_mode(
        lambda pos: handle_content_selection(pos, printer, config, module_id, prompt, module_name or "AI"),
        module_id
    )
    
    print_content(printer, module_name or "AI Assistant", result["content"])
