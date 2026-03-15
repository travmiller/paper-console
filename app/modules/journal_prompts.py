import json
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from app.module_registry import register_module


def _get_journal_prompts_db_path() -> Path:
    """Get the bundled journal prompts database path."""
    return Path(__file__).resolve().parent.parent / "data" / "journal_prompts.json"


def _normalize_prompt_entry(entry: Any) -> str | None:
    """Accept simple prompt strings or {'prompt': '...'} objects."""
    if isinstance(entry, str):
        prompt = entry.strip()
    elif isinstance(entry, dict):
        prompt = str(entry.get("prompt", "")).strip()
    else:
        return None

    if not prompt:
        return None

    prompt = re.sub(r"[\n\r\t]+", " ", prompt)
    return " ".join(prompt.split())


def _load_journal_prompts() -> list[str]:
    """Load and validate the bundled prompt corpus."""
    prompts_path = _get_journal_prompts_db_path()

    try:
        with open(prompts_path, "r", encoding="utf-8") as prompts_file:
            prompts = json.load(prompts_file)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []
    except Exception:
        return []

    if not isinstance(prompts, list):
        return []

    normalized_prompts = []
    for entry in prompts:
        normalized_prompt = _normalize_prompt_entry(entry)
        if normalized_prompt:
            normalized_prompts.append(normalized_prompt)

    return normalized_prompts


def get_random_prompt() -> str:
    """Return a random journal prompt from the local corpus."""
    prompts = _load_journal_prompts()
    if not prompts:
        return "No journal prompts are available on this device."
    return random.choice(prompts)


@register_module(
    type_id="journal_prompts",
    label="Journal Prompt",
    description="Prints a random journal prompt from a bundled offline library",
    icon="book",
    offline=True,
    category="content",
    config_schema={
        "type": "object",
        "properties": {},
    },
)
def format_journal_prompt_receipt(
    printer, config: Dict[str, Any] = None, module_name: str = None
):
    """Print a random journal prompt."""
    prompt = get_random_prompt()

    printer.print_header(module_name or "JOURNAL PROMPT", icon="book")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()
    printer.print_body(prompt)
