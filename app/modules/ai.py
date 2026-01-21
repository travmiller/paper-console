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
# --- AI Presets ---
# --- AI Presets ---
PROMPT_PRESETS = {
    "recipe": {"values": {"prompt": "You are a specialized chef. Suggest ONE unique, seasonal dish based on the current weather. Format: 'Dish Name', 'Ingredients' (bullet points), '3-Step Method'. Keep it under 100 words."}},
    "story_micro": {"values": {"prompt": "Write a 3-sentence micro-fiction story. The genre should be random (Sci-Fi, Noir, Fantasy, or Horror). Make it twisty."}},
    "haiku": {"values": {"prompt": "Write a haiku about the current weather or time of day. Strictly 5-7-5 syllables."}},
    "joke": {"values": {"prompt": "Tell a clean but clever stand-up comedy joke. No puns. Setup and punchline."}},
    "fact_science": {"values": {"prompt": "Give me one mind-blowing scientific fact that most people don't know. Keep it under 40 words."}},
    "stoic": {"values": {"prompt": "You are Marcus Aurelius. Give me one piece of stoic advice for navigating the modern world today. Be brief and powerful."}},
    "roast": {"values": {"prompt": "You are a snarky robot. Lightly roast the human for checking a paper printer for entertainment. Be funny, not mean."}},
    "word": {"values": {"prompt": "You are a lexicographer. Give me a 'Word of the Day'. Choose an obscure, beautiful, or useful word. Provide definition and one example sentence."}},
    "idea_startup": {"values": {"prompt": "Generate a random startup idea or invention that is slightly absurd but potentially useful. Describe it in 2 sentences."}},
    "riddle": {"values": {"prompt": "Give me a challenging riddle. Do NOT reveal the answer. Just the riddle."}},
    "coach_hype": {"values": {"prompt": "You are a high-energy life coach. Shout (use CAPS) a 1-sentence motivation to get me moving right now."}},
    "oblique": {"values": {"prompt": "Give me an 'Oblique Strategy' style creative prompt to break a mental block. Abstract and artistic."}},
    "history": {"values": {"prompt": "Tell me something significant that happened on this day in history. If nothing major, choose a funny minor event."}},
    "explain_5": {"values": {"prompt": "Explain a complex concept (Entropy, Relativity, Mycology) as if I were a 5-year-old. Maximum 50 words."}},
    "poem_free": {"values": {"prompt": "Write a short, free-verse poem about technology and nature colliding. Maximum 6 lines."}},
    "decision_coin": {"values": {"prompt": "I am indecisive. Flip a coin for me, but elaborate. 'Heads: Do the bold thing. Tails: Play it safe.' Make it thematic."}},
    "horoscope": {"values": {"prompt": "Write a generic but convincing horoscope for 'The User' for today. Mystical and vague but encouraging."}},
    "etymology": {"values": {"prompt": "Choose a common word and explain its surprising ancient origin (etymology). Keep it brief."}},
    "challenge_tiny": {"values": {"prompt": "Give me a tiny real-world challenge to complete in the next hour (e.g., 'Drink water', 'Text an old friend', 'Stretch'). detailed but tiny."}},
    "alien": {"values": {"prompt": "You are an alien anthropologist observing humans. Describe one mundane human activity as if it were a bizarre ritual."}},
    "fact_animal": {"values": {"prompt": "Tell me a weird, specific, and true fact about an animal (e.g., wombat poop, octopus brains)."}},
    "prompt_art": {"values": {"prompt": "Describe a surreal image in vivid detail that I should draw or imagine. Focus on lighting and texture."}},
    "debate": {"values": {"prompt": "Pick a harmless, low-stakes debate topic (e.g., 'Is a hotdog a sandwich?') and give a passionate 1-sentence ruling."}},
    "compliment": {"values": {"prompt": "Give me a deeply specific and slightly odd compliment that would make someone's day."}},
    "scifi_tech": {"values": {"prompt": "Invent a fictional Sci-Fi gadget from the year 3000. Name it and describe its function in one sentence."}},
    "movie_plot": {"values": {"prompt": "Pitch a movie plot for a film that doesn't exist. Genre: Random. Logline only."}},
    "nature_obs": {"values": {"prompt": "Describe a small natural phenomenon (a leaf falling, rain on glass) with extreme poetic detail."}},
    "urban_legend": {"values": {"prompt": "Invent a fake urban legend about the room I am currently sitting in. Make it spooky."}},
    "advice_bad": {"values": {"prompt": "Give me some 'terrible' advice that is technically true but practically useless."}},
    "forecast_fake": {"values": {"prompt": "Give me a weather forecast for a fictional location (e.g., Narnia, Mars, Middle Earth)."}},
    "cocktail": {"values": {"prompt": "Invent a cocktail recipe named after a philosophical concept. List ingredients and mood."}},
    "superpower": {"values": {"prompt": "Assign me a useless superpower (e.g., 'You can turn invisible but only when no one is looking')."}},
    "band_name": {"values": {"prompt": "Generate 3 cool band names based on random household objects."}},
    "haiku_tech": {"values": {"prompt": "Write a haiku about a computer crashing or a printer jamming."}},
    "fortune_cookie": {"values": {"prompt": "Write a fortune cookie message that is suspiciously specific."}},
    "conspiracy": {"values": {"prompt": "Invent a harmless conspiracy theory about pigeons or clouds."}},
    "book_title": {"values": {"prompt": "Generate a title and subtitle for a self-help book written by a cat."}},
    "meditation": {"values": {"prompt": "Guide me through a 10-second micro-meditation. Focus on breath."}},
    "joke_dad": {"values": {"prompt": "Tell the grandest, most groan-worthy Dad Joke you know."}},
    "myth_modern": {"values": {"prompt": "Write a myth explaining why Wi-Fi signals sometimes drop."}},
    "recipe_chaos": {"values": {"prompt": "Suggest a 'chaos meal' made of random pantry ingredients. Make it sound gourmet."}},
    "slogan": {"values": {"prompt": "Write a catchy slogan for a product that shouldn't exist (e.g., 'Dehydrated Water')."}},
    "news_fake": {"values": {"prompt": "Write a breaking news headline from a parallel dimension."}},
    "review_life": {"values": {"prompt": "Write a 5-star review for 'Being Alive Today'."}},
    "pun_war": {"values": {"prompt": "Give me three puns about time travel."}},
    "bio_fake": {"values": {"prompt": "Write a short bio for a fictional alter-ego of the user who is a famous explorer."}},
    "travel_guide": {"values": {"prompt": "Describe a hidden gem travel destination that is actually microscopic (e.g., a moss forest)."}},
    "quest": {"values": {"prompt": "Assign me a real-life RPG quest (e.g., 'Find a red object and photograph it'). Reward: +10 XP."}},
    "monologue": {"values": {"prompt": "Write a 2-line internal monologue of a houseplant."}},
    "dialogue": {"values": {"prompt": "Write a 2-line dialogue between a toaster and a fridge."}},
    "song_lyric": {"values": {"prompt": "Write a chorus for a blues song about low battery anxiety."}},
    "limerick": {"values": {"prompt": "Write a limerick about a robot who wants to be a chef."}},
    "name_gen": {"values": {"prompt": "Generate a fantasy name for a pet dragon based on sound (e.g., 'Kralkatorrik')."}},
    "color": {"values": {"prompt": "Invent a new color name and describe what it looks like (e.g., 'Glimmer-gloom')."}},
    "law_weird": {"values": {"prompt": "Cite a fake but plausible archaic law from the 1800s."}},
    "sport_future": {"values": {"prompt": "Describe a sport played in zero gravity. Name it and one rule."}},
    "gift_idea": {"values": {"prompt": "Suggest a terrible gift idea for a nemesis."}},
    "excuse": {"values": {"prompt": "Generate a sophisticated excuse for being late to a meeting."}},
    "insult_shakes": {"values": {"prompt": "Generate a Shakespearean insult. Combine 3 words."}},
    "motto": {"values": {"prompt": "Generate a Latin motto for a lazy person, with translation."}},
    "stat_fake": {"values": {"prompt": "Make up a statistic about socks disappearing in the laundry. Sound authoritative."}},
    "review_movie": {"values": {"prompt": "Review a classic movie (e.g., Titanic) in one sentence, missing the point entirely."}},
    "haiku_coding": {"values": {"prompt": "Write a haiku about searching for a missing semicolon."}},
    "affirmation": {"values": {"prompt": "Give me an affirmation for a stressed programmer."}},
    "shower_thought": {"values": {"prompt": "Generate a profound 'Shower Thought' about daily life."}},
    "analogy": {"values": {"prompt": "Make a confusing analogy to explain 'The Cloud'."}},
    "proverb": {"values": {"prompt": "Invent a wise-sounding proverb that actually means nothing."}},
    "question_deep": {"values": {"prompt": "Ask me a deep philosophical question to ponder while drinking coffee."}},
    "fact_history": {"values": {"prompt": "Tell me a weird historical fact about a famous figure (e.g., Napoleon, Lincoln)."}},
    "writing_prompt": {"values": {"prompt": "Give me a writing prompt involving a key, a map, and a clock."}},
    "villain": {"values": {"prompt": "Create a motive for a supervillain that is surprisingly relatable."}},
    "hero": {"values": {"prompt": "Create a superhero whose power is extremely inconvenient."}},
    "planet": {"values": {"prompt": "Describe the weather on a fictional planet in the Andromeda galaxy."}},
    "monster": {"values": {"prompt": "Describe a 'closet monster' that is actually helpful and friendly."}},
    "time_capsule": {"values": {"prompt": "List 3 items to put in a time capsule to confuse future archaeologists."}},
    "bucket_list": {"values": {"prompt": "Suggest one adventurous item to add to a bucket list."}},
    "conversation": {"values": {"prompt": "Suggest a weird conversation starter for a dinner party."}},
    "playlist": {"values": {"prompt": "Suggest a title for a playlist for driving at 2 AM."}},
    "emoji": {"values": {"prompt": "Suggest a new emoji that doesn't exist but should. Describe it."}},
    "app_idea": {"values": {"prompt": "Pitch an app that does something incredibly specific and useless."}},
    "pet_peeve": {"values": {"prompt": "Rant briefly about a minor modern annoyance (e.g., slow walking people)."}},
    "gratitude": {"values": {"prompt": "Prompt me to be grateful for one small, overlooked thing (e.g., zippers)."}},
    "memory": {"values": {"prompt": "Ask me to recall a specific positive memory from childhood."}},
    "texture": {"values": {"prompt": "Describe the texture of a cloud if you could touch it."}},
    "taste": {"values": {"prompt": "Describe the taste of the color blue."}},
    "dream": {"values": {"prompt": "Interpret a dream about flying (pretend to be a dream analyst)."}},
    "tarot": {"values": {"prompt": "Draw a random Tarot card (simulated) and give a one-line meaning."}},
    "spirit_animal": {"values": {"prompt": "Assign me a Spirit Animal based on the vibe of 'chaos'. Explain why."}},
    "aura": {"values": {"prompt": "Describe the color of my 'digital aura' right now."}},
    "magic_spell": {"values": {"prompt": "Write a magic spell incantation to fix a buggy printer."}},
    "potion": {"values": {"prompt": "List ingredients for a potion of 'Infinite Focus'."}},
    "dnd_hook": {"values": {"prompt": "Give me a one-sentence plot hook for a D&D campaign."}},
    "npc": {"values": {"prompt": "Describe a quirky NPC shopkeeper. Name and one trait."}},
    "loot": {"values": {"prompt": "Describe a magical item found in a chest. It is cursed."}},
    "cyberpunk": {"values": {"prompt": "Describe a street scene in a Cyberpunk city. Neon and rain."}},
    "steampunk": {"values": {"prompt": "Describe a brass gadget found in a Steampunk workshop."}},
    "solarpunk": {"values": {"prompt": "Describe a futuristic city integrated with nature."}},
    "horror_micro": {"values": {"prompt": "Write a 2-sentence horror story about a mirror."}},
    "noir_intro": {"values": {"prompt": "Write the opening line of a hard-boiled detective novel set in a grocery store."}}
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
