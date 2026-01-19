import json
import random
import os
import requests
from typing import Dict, Any, List
from pathlib import Path
from app.utils import wrap_text

# Curated list of quotes (approx 5k) - clean and reliable source
# Using JamesFT/Database-Quotes-JSON
QUOTES_DB_URL = (
    "https://raw.githubusercontent.com/JamesFT/Database-Quotes-JSON/master/quotes.json"
)


# Resolve path relative to project root (same pattern as config.py)
def _get_quotes_db_path() -> Path:
    """Get the path to the quotes database file, resolving relative to project root."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return Path(base_dir) / "app" / "data" / "quotes.json"


LOCAL_DB_PATH = _get_quotes_db_path()


def ensure_quotes_db():
    """Downloads the quotes database if it doesn't exist."""
    quotes_path = _get_quotes_db_path()

    if not quotes_path.exists():
        try:
            print(f"Downloading quotes database from {QUOTES_DB_URL}...")
            response = requests.get(QUOTES_DB_URL, timeout=10)
            response.raise_for_status()

            # Ensure data directory exists
            quotes_path.parent.mkdir(parents=True, exist_ok=True)

            with open(quotes_path, "w", encoding="utf-8") as f:
                f.write(response.text)

            print("Quotes database downloaded successfully.")
        except Exception as e:
            print(f"Failed to download quotes database: {e}")
            # Fallback for offline/error: Create a tiny local DB
            fallback_data = [
                {
                    "quoteText": "The only way to do great work is to love what you do.",
                    "quoteAuthor": "Steve Jobs",
                },
                {
                    "quoteText": "Innovation distinguishes between a leader and a follower.",
                    "quoteAuthor": "Steve Jobs",
                },
                {
                    "quoteText": "Stay hungry, stay foolish.",
                    "quoteAuthor": "Steve Jobs",
                },
                {"quoteText": "Code is poetry.", "quoteAuthor": "WordPress"},
            ]
            quotes_path.parent.mkdir(parents=True, exist_ok=True)
            with open(quotes_path, "w", encoding="utf-8") as f:
                json.dump(fallback_data, f)


def get_random_quote() -> Dict[str, str]:
    """Reads a random quote from the local database."""
    ensure_quotes_db()

    try:
        quotes_path = _get_quotes_db_path()
        with open(quotes_path, "r", encoding="utf-8") as f:
            quotes = json.load(f)
            if not quotes:
                return {"quoteText": "No quotes found.", "quoteAuthor": "System"}
            if not isinstance(quotes, list):
                return {
                    "quoteText": "Invalid quotes database format.",
                    "quoteAuthor": "System",
                }
            return random.choice(quotes)
    except FileNotFoundError:
        return {"quoteText": "Quotes database file not found.", "quoteAuthor": "System"}
    except json.JSONDecodeError as e:
        return {
            "quoteText": f"Invalid JSON in quotes database: {e}",
            "quoteAuthor": "System",
        }
    except Exception as e:
        return {
            "quoteText": f"Error reading quotes database: {str(e)}",
            "quoteAuthor": "System",
        }


def format_quotes_receipt(
    printer, config: Dict[str, Any] = None, module_name: str = None
):
    """Prints a random quote."""
    from datetime import datetime

    quote = get_random_quote()
    text = quote.get("quoteText", "")
    author = quote.get("quoteAuthor", "Unknown")

    # Header
    printer.print_header(module_name or "QUOTE", icon="quotes")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()

    # Quote body in italics-style (using medium weight for emphasis)
    # Clean text: remove any embedded newlines and normalize whitespace
    import re
    text = re.sub(r'[\n\r\t]+', ' ', text)  # Replace all whitespace chars with single space
    text = " ".join(text.split())  # Normalize multiple spaces to single space
    
    # Don't pre-wrap! Let the printer's font-metric-based wrapping handle it.
    # The printer driver uses _wrap_text_by_width which uses actual font pixel metrics,
    # not character counts. Pre-wrapping with character-based wrap_text causes
    # double-wrapping and incorrect line breaks.
    # 
    # Simply pass the text with quotes - the printer will wrap it correctly based on
    # actual rendered width, and the quotes will naturally be at the start and end.
    printer.print_body(f'"{text}"')

    printer.feed(1)

    # Attribution
    if author:
        printer.print_caption(f"— {author}")

    printer.print_line()
