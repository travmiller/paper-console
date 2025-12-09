import json
import requests
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime

# We will use a curated "On This Day" dataset.
# There are several options, but zenorocha/voice-history is a good source of historical events in JSON.
# Alternatively, we can use a raw scrape from Wikipedia.
# For simplicity and reliability, we'll use a widely used JSON dataset hosted on GitHub.
# Source: https://github.com/zenorocha/voice-history (data/en_US.json) - simple events by date.
# Another good one: https://github.com/mubaris/potential-enigma (history.json)
# Let's use a composite approach or a reliable single source. 
# We'll use a Zenorocha-style structure which is date-keyed.

HISTORY_DB_URL = "https://raw.githubusercontent.com/mubaris/potential-enigma/master/history.json"
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
                "1": { # January
                    "1": ["1863: Emancipation Proclamation issued by Lincoln."],
                },
                "12": { # December
                    "25": ["0: First Christmas (traditional)."],
                }
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

def format_history_receipt(printer, config: Dict[str, Any] = None, module_name: str = None):
    """Prints 'On This Day' historical events."""
    
    events = get_events_for_today()
    
    # Filter/Select events
    # The dataset might have MANY events. We should pick 3-5 random ones or top ones.
    # config could specify "count"
    count = 3
    if config and "count" in config:
        try:
            count = int(config["count"])
        except:
            pass
            
    # Randomize if we have more than requested
    import random
    if len(events) > count:
        selected_events = random.sample(events, count)
    else:
        selected_events = events

    # Header
    printer.print_header((module_name or "ON THIS DAY").upper())
    printer.print_text(datetime.now().strftime("%A, %b %d"))
    printer.print_line()
    
    if not selected_events:
        printer.print_text("No historical records")
        printer.print_text("found for today.")
    else:
        for i, event in enumerate(selected_events):
            # The event strings often start with year: "1945 - Some event"
            # We print it as is, maybe cleaning up formatting if needed.
            printer.print_text(f"* {event}")
            
            if i < len(selected_events) - 1:
                printer.feed(1)
                
    printer.print_line()
    printer.feed(1)

