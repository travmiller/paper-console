import json
import requests
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime
from app.utils import wrap_text, wrap_text_pixels
from PIL import Image, ImageDraw
from app.module_registry import register_module

# We will use a curated "On This Day" dataset.
# There are several options, but zenorocha/voice-history is a good source of historical events in JSON.
# Alternatively, we can use a raw scrape from Wikipedia.
# For simplicity and reliability, we'll use a widely used JSON dataset hosted on GitHub.
# Source: https://github.com/zenorocha/voice-history (data/en_US.json) - simple events by date.
# Another good one: https://github.com/mubaris/potential-enigma (history.json)
# Let's use a composite approach or a reliable single source.
# We'll use a Zenorocha-style structure which is date-keyed.

HISTORY_DB_URL = (
    "https://raw.githubusercontent.com/mubaris/potential-enigma/master/history.json"
)
# Note: The above repo structure is: {"1": {"1": ["event1", "event2"], "2": [...]}, "2": {...}}
# i.e. {"Month": {"Day": ["list", "of", "events"]}}

LOCAL_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "history.json"


def ensure_history_db():
    """Downloads the history database if it doesn't exist."""
    if not LOCAL_DB_PATH.exists():
        try:
            print(f"Downloading history database from {HISTORY_DB_URL}...")
            response = requests.get(HISTORY_DB_URL, timeout=10)
            response.raise_for_status()

            # Ensure data directory exists
            LOCAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

            with open(LOCAL_DB_PATH, "w", encoding="utf-8") as f:
                f.write(response.text)

            print("History database downloaded successfully.")
        except Exception as e:
            print(f"Failed to download history database: {e}")
            # Fallback tiny DB
            fallback_data = {
                "1": {  # January
                    "1": ["1863: Emancipation Proclamation issued by Lincoln."],
                },
                "12": {  # December
                    "25": ["0: First Christmas (traditional)."],
                },
            }
            with open(LOCAL_DB_PATH, "w", encoding="utf-8") as f:
                json.dump(fallback_data, f)


def get_events_for_today() -> List[str]:
    """Reads events for the current date from the local database."""
    ensure_history_db()

    now = datetime.now()
    month = str(now.month)
    day = str(now.day)

    try:
        with open(LOCAL_DB_PATH, "r", encoding="utf-8") as f:
            history = json.load(f)

            # Navigate structure: Month -> Day -> List of Strings
            month_data = history.get(month, {})
            events = month_data.get(day, [])

            return events
    except Exception:
        return ["Error reading history database."]


@register_module(
    type_id="history",
    label="On This Day",
    description="Random historical events that happened on today's date",
    icon="hourglass",
    offline=True,
    category="content",
    config_schema={
        "type": "object",
        "properties": {
            "count": {"type": "integer", "title": "Number of Events", "default": 1}
        }
    }
)
def format_history_receipt(
    printer, config: Dict[str, Any] = None, module_name: str = None
):
    """Prints 'On This Day' historical events."""

    events = get_events_for_today()

    # Filter/Select events
    count = 1
    if config and "count" in config:
        try:
            count = int(config["count"])
        except:
            pass

    import random
    if len(events) > count:
        selected_events = random.sample(events, count)
    else:
        selected_events = events

    # Header
    printer.print_header(module_name or "ON THIS DAY", icon="hourglass")
    printer.print_caption(datetime.now().strftime("%B %d, %Y"))
    printer.print_line()

    if not selected_events:
        printer.print_body("No historical records")
        printer.print_body("found for today.")
    else:
        # Prepare timeline items
        timeline_items = []
        for event in selected_events:
            year = 0
            description = event
            
            # Try to parse year from various formats:
            # "1920: Description" or "1920 - Description" or "1920 Description"
            if " - " in event:
                # Format: "YEAR - Description"
                year_str, description = event.split(" - ", 1)
                try:
                    year = int(year_str.strip())
                except:
                    year = 0
            elif ": " in event:
                # Format: "YEAR: Description" (most common in history.json)
                parts = event.split(": ", 1)
                if len(parts) == 2:
                    year_str = parts[0].strip()
                    description = parts[1].strip()
                    try:
                        year = int(year_str)
                    except:
                        year = 0
            else:
                # Try to extract year from start of string if it starts with digits
                parts = event.split(None, 1)  # Split on first whitespace
                if parts and parts[0].isdigit():
                    try:
                        year = int(parts[0])
                        description = parts[1] if len(parts) > 1 else event
                    except:
                        description = event
            
            timeline_items.append({"year": year, "text": description})
        
        # Print timeline graphic
        # Print timeline graphic
        width = getattr(printer, "PRINTER_WIDTH_DOTS", 384)
        regular_font = getattr(printer, "_get_font", lambda s: None)("regular")
        
        img = draw_timeline_image(
            width, 
            timeline_items, 
            item_height=24, 
            font=regular_font
        )
        printer.print_image(img)

    printer.print_line()


def draw_timeline_image(
    width: int, 
    items: list, 
    item_height: int, 
    font
) -> Image.Image:
    """Draw a timeline graphic to an image."""
    
    # Calculate total height first (to create image)
    total_height = 0
    # Line height default
    line_height = getattr(font, "size", 24) if font else 24
    
    # We need to calculate height for each item to know total image height
    item_heights = []
    
    for item in items:
        # Calculate year width
        year = str(item.get("year", ""))
        year_width = 0
        if font and year and year != "0":
            try:
                bbox = font.getbbox(year)
                year_width = bbox[2] - bbox[0] if bbox else len(year) * 8
            except:
                year_width = len(year) * 8
        
        # Position vertical line after year with padding
        line_x = year_width + 12
        text_x = line_x + 10
        
        # Calculate available width for text
        max_text_width = width - text_x - 10
        
        # Calculate text height
        text = item.get("text", "")
        if font and text:
            wrapped_lines = wrap_text_pixels(text, font, max_text_width)
            actual_height = max(item_height, (len(wrapped_lines) * line_height) + 8)
        else:
            actual_height = item_height
            
        item_heights.append(actual_height)
        total_height += actual_height
        
    # Create image
    img = Image.new("1", (width, total_height), 1)  # White background
    draw = ImageDraw.Draw(img)
    
    current_y = 0
    x = 0
    
    for i, item in enumerate(items):
        item_y = current_y
        actual_height = item_heights[i]
        
        # Draw year label
        year = str(item.get("year", ""))
        year_width = 0
        if font and year and year != "0":
            try:
                bbox = font.getbbox(year)
                year_width = bbox[2] - bbox[0] if bbox else len(year) * 8
            except:
                year_width = len(year) * 8
            draw.text((x, item_y - 4), year, font=font, fill=0)
            
        # Draw vertical line
        line_x = x + year_width + 12
        text_x = line_x + 10
        max_text_width = width - text_x - 10
        
        # Draw text
        text = item.get("text", "")
        if font and text:
            wrapped_lines = wrap_text_pixels(text, font, max_text_width)
            text_y = item_y - 4
            for line in wrapped_lines:
                if line.strip():
                    draw.text((text_x, text_y), line, font=font, fill=0)
                    text_y += line_height
        elif text:
            draw.text((text_x, item_y - 4), text, fill=0)
            
        # Draw vertical timeline line to next item (if not last item)
        if i < len(items) - 1:
            line_end_y = item_y + actual_height
            draw.line([(line_x, item_y), (line_x, line_end_y)], fill=0, width=2)
            
        current_y += actual_height
        
    return img
