from datetime import datetime
from typing import Any, Dict
from app.module_registry import register_module
import feedparser
import requests

@register_module(
    type_id="wotd",
    label="Word of the Day",
    description="Prints the Word of the Day from Merriam Webster dictionary",
    icon="book",
    offline=False,
    category="content",
    config_schema={
        "type": "object",
        "properties": {}
    }
)
def format_text_receipt(printer, config: Dict[str, Any] = None, module_name: str = None):
    try:
        # Use requests with timeout instead of feedparser directly
        # This prevents hanging on slow/unresponsive feeds
        response = requests.get("https://www.merriam-webster.com/wotd/feed/rss2", timeout=10)
        response.raise_for_status()

        # Parse the fetched content
        feed = feedparser.parse(response.content)

        if not feed.entries:
            return
        
        # We only care about the first entry
        entry = feed.entries[0]

        word = entry.get("title", "No Word")
        definition = entry.get("merriam_shortdef", "No Definition")

        printer.print_header(module_name or "WORD OF THE DAY", icon="book")
        printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
        printer.print_line()

        printer.print_bold(word)
        printer.print_body(definition)

    except Exception:
        return