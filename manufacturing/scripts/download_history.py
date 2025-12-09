#!/usr/bin/env python3
"""
Download historical events from Wikipedia's "On This Day" API.
Creates a JSON database organized by month/day for offline use.
"""

import json
import requests
import time
from pathlib import Path
from datetime import datetime, timedelta

OUTPUT_FILE = Path("app/data/history.json")
API_BASE = "https://en.wikipedia.org/api/rest_v1/feed/onthisday/all"

# Proper User-Agent header required by Wikimedia
HEADERS = {
    "User-Agent": "PC-1-Paper-Console/1.0 (https://github.com/paper-console; contact@example.com) Python/3"
}


def fetch_events_for_date(month: int, day: int, retries: int = 3) -> list:
    """Fetch historical events for a specific date from Wikimedia API."""
    # API requires zero-padded format: 12/08 not 12/8
    url = f"{API_BASE}/{month:02d}/{day:02d}"

    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=15, headers=HEADERS)

            # Check for rate limiting (429) or server errors (5xx)
            if response.status_code == 429:
                wait_time = int(response.headers.get("Retry-After", 60))
                print(f"Rate limited. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                continue

            response.raise_for_status()
            data = response.json()

            # Extract just the events (not births/deaths/holidays)
            events = data.get("events", [])
            # Format as simple strings: "Year: Description"
            formatted = []
            for event in events:
                year = event.get("year", "?")
                text = event.get("text", "").strip()
                if text:
                    # Clean up HTML entities if any
                    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
                    formatted.append(f"{year}: {text}")
            return formatted

        except requests.exceptions.Timeout:
            if attempt < retries - 1:
                print(f"Timeout for {month}/{day}, retrying...")
                time.sleep(5)
                continue
            else:
                print(f"Timeout for {month}/{day} after {retries} attempts")
                return []
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                # No events for this date, return empty
                return []
            elif e.response.status_code == 429:
                wait_time = int(e.response.headers.get("Retry-After", 60))
                print(f"Rate limited. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            else:
                print(f"HTTP error for {month}/{day}: {e}")
                return []
        except Exception as e:
            print(f"Error fetching {month}/{day}: {e}")
            return []

    return []


def build_history_database():
    """Build a complete history database for all 365 days."""
    print("Downloading historical events from Wikimedia API...")
    print("This will take 10-15 minutes (respecting rate limits)...")
    print("Progress will be saved incrementally.\n")

    # Load existing data if it exists
    history = {}
    start_date = datetime(2024, 1, 1)  # Use 2024 for leap year (Feb 29)
    
    if OUTPUT_FILE.exists():
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
            print(f"Loaded existing database with {len(history)} months of data")
            
            # Find the last processed date
            last_month = max([int(m) for m in history.keys()]) if history else 0
            if last_month > 0:
                last_day = max([int(d) for d in history[str(last_month)].keys()]) if str(last_month) in history else 0
                if last_day > 0:
                    # Start from the day after the last processed day
                    start_date = datetime(2024, last_month, last_day) + timedelta(days=1)
                    print(f"Resuming from {start_date.strftime('%B %d')}...")
        except Exception as e:
            print(f"Warning: Could not load existing database: {e}")
            print("Starting fresh...")
            history = {}

    current_date = start_date
    end_date = datetime(2025, 1, 1)  # Go until end of year

    total_days = (end_date - datetime(2024, 1, 1)).days
    # Count already processed days
    already_processed = sum(
        len(month_data) 
        for month_data in history.values()
    ) if history else 0
    total_events = sum(
        len(events) 
        for month_data in history.values() 
        for events in month_data.values()
    ) if history else 0
    
    print(f"Already processed: {already_processed} days, {total_events} events")
    print(f"Remaining: {total_days - already_processed} days\n")

    while current_date < end_date:
        month = current_date.month
        day = current_date.day

        month_str = str(month)
        day_str = str(day)

        # Initialize month dict if needed
        if month_str not in history:
            history[month_str] = {}

        # Fetch events
        events = fetch_events_for_date(month, day)
        if events:
            history[month_str][day_str] = events
            total_events += len(events)
            print(f"OK {month:02d}/{day:02d}: {len(events)} events")
        else:
            # Don't store empty days to keep file size down
            print(f"  {month:02d}/{day:02d}: No events")

        # Move to next day
        current_date += timedelta(days=1)
        already_processed += 1

        # Save progress every 30 days
        if already_processed % 30 == 0:
            OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            print(
                f"  [Progress saved: {already_processed}/{total_days} days, {total_events} events so far]\n"
            )

        # Rate limiting: be nice to Wikimedia's servers
        # Wikimedia allows ~200 requests per minute, so we'll do ~2 per second
        time.sleep(0.6)  # ~1.6 requests per second (safe margin)

    # Final save
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    print(f"\nDatabase saved to {OUTPUT_FILE}")
    print(f"  Total days processed: {already_processed}")
    print(f"  Total events: {total_events}")
    if already_processed > 0:
        print(f"  Average events per day: {total_events/already_processed:.1f}")


if __name__ == "__main__":
    build_history_database()
