import json
import requests
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime
from app.utils import wrap_text

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

LOCAL_DB_PATH = Path("app/data/history.json")


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
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()

    if not selected_events:
        printer.print_body("No historical records")
        printer.print_body("found for today.")
    else:
        # Prepare timeline items
        timeline_items = []
        for event in selected_events:
            if " - " in event:
                year_str, description = event.split(" - ", 1)
                try:
                    year = int(year_str.strip())
                except:
                    year = 0
                timeline_items.append({"year": year, "text": description})
            else:
                timeline_items.append({"year": 0, "text": event})
        
        # Print timeline graphic
        printer.print_timeline(timeline_items, item_height=24)

    printer.print_line()
