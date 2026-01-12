import requests
import pytz
from datetime import datetime, timedelta, date
from typing import List, Dict, Any
from icalendar import Calendar
from dateutil.rrule import rrulestr
from app.drivers.printer_mock import PrinterDriver
from app.config import CalendarConfig, format_time
import app.config


def fetch_ics(url: str) -> str:
    """Fetches the ICS file content from a URL."""
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        # Limit response size to prevent memory issues (1MB max for calendar)
        return response.text[: 1024 * 1024]
    except Exception:
        return None


def parse_events(
    ics_content: str, days_to_show: int, timezone_str: str
) -> Dict[date, List[Dict]]:
    """
    Parses ICS content and returns events grouped by date.
    Only includes events for Today -> Today + days_to_show.
    """
    if not ics_content:
        return {}

    try:
        cal = Calendar.from_ical(ics_content)
    except Exception:
        return {}

    # Timezone setup
    try:
        local_tz = pytz.timezone(timezone_str)
    except:
        local_tz = pytz.UTC

    now = datetime.now(local_tz)
    today = now.date()
    end_date = today + timedelta(days=days_to_show)

    # We want a window of time to search for events
    # Start from beginning of today
    start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # End at end of the last day
    end_dt = start_dt + timedelta(days=days_to_show)

    events_by_day = {}

    for component in cal.walk():
        if component.name == "VEVENT":
            summary = str(component.get("summary"))
            dtstart = component.get("dtstart")

            if not dtstart:
                continue

            # Normalize start time to datetime
            start = dtstart.dt

            # Handle all-day events (date objects)
            is_all_day = False
            if not isinstance(start, datetime):
                is_all_day = True
                # Convert to datetime for comparison logic (midnight local)
                # Note: All day events in ICS usually don't have TZ, so we assume local context or keep naive?
                # Usually safe to treat as date.
                pass
            else:
                # Ensure timezone awareness
                if start.tzinfo is None:
                    start = local_tz.localize(start)
                else:
                    start = start.astimezone(local_tz)

            # Simple logic: Just check if the start date matches our range
            # TODO: Handle recurring events properly using rrule?
            # For V1, we only look at the primary instance.
            # Complex recurrence expansion is heavy, but we can try simple expansion if 'RRULE' exists.

            event_instances = []

            if "RRULE" in component:
                # Attempt simple expansion
                try:
                    # Convert dtstart to proper datetime for rrule if it's a date
                    rrule_start = start
                    if is_all_day:
                        rrule_start = datetime.combine(start, datetime.min.time())

                    # Create rule
                    rule = rrulestr(
                        component["RRULE"].to_ical().decode(), dtstart=rrule_start
                    )

                    # Ensure query window is timezone-aware if rule is
                    query_start = start_dt
                    query_end = end_dt

                    if rrule_start.tzinfo is None:
                        # Rule is naive, so query must be naive
                        if query_start.tzinfo is not None:
                            query_start = query_start.replace(tzinfo=None)
                        if query_end.tzinfo is not None:
                            query_end = query_end.replace(tzinfo=None)
                    else:
                        # Rule is aware, so query must be aware
                        if query_start.tzinfo is None:
                            query_start = local_tz.localize(query_start)
                        if query_end.tzinfo is None:
                            query_end = local_tz.localize(query_end)

                    # Get instances in our small window
                    # strict=True raises error if tz mismatch, so be careful
                    for dt in rule.between(query_start, query_end, inc=True):
                        # convert back to localized if needed
                        if is_all_day:
                            event_instances.append((dt.date(), True))
                        else:
                            # if rule generates naive, localize it
                            if dt.tzinfo is None and local_tz:
                                dt = local_tz.localize(dt)
                            event_instances.append((dt, False))
                except Exception:
                    # Fallback to just the main event
                    if is_all_day:
                        event_instances.append((start, True))
                    else:
                        event_instances.append((start, False))
            else:
                # Single event
                event_instances.append((start, is_all_day))

            # Process instances
            for evt_dt, evt_is_all_day in event_instances:
                # Check bounds
                evt_date = (
                    evt_dt
                    if isinstance(evt_dt, date) and not isinstance(evt_dt, datetime)
                    else evt_dt.date()
                )

                if today <= evt_date < end_date:
                    if evt_date not in events_by_day:
                        events_by_day[evt_date] = []

                    time_str = "All Day"
                    if not evt_is_all_day:
                        time_str = format_time(evt_dt)

                    events_by_day[evt_date].append(
                        {
                            "time": time_str,
                            "summary": summary,
                            "sort_key": "00:00" if evt_is_all_day else time_str,
                        }
                    )

    # Sort events within each day
    for d in events_by_day:
        events_by_day[d].sort(key=lambda x: x["sort_key"])

    return events_by_day


def format_calendar_receipt(
    printer: PrinterDriver, config: CalendarConfig, module_name: str = None
):
    """Fetches and prints the calendar agenda."""

    header_label = module_name or config.label or "CALENDAR"
    printer.print_header(header_label)
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()

    # Collect calendar sources
    sources = []
    if config.ical_sources:
        for src in config.ical_sources:
            if src.url:
                sources.append(src.url)

    if not sources:
        printer.print_body("No iCal URLs configured.")
        return

    all_events = {}

    for url in sources:
        ics_data = fetch_ics(url)
        if ics_data:
            events = parse_events(
                ics_data, config.days_to_show or 2, app.config.settings.timezone
            )
            for d, evts in events.items():
                if d not in all_events:
                    all_events[d] = []
                all_events[d].extend(evts)

    if not all_events:
        printer.print_body("No upcoming events.")
        return

    sorted_dates = sorted(all_events.keys())

    for i, d in enumerate(sorted_dates):
        all_events[d].sort(key=lambda x: x["sort_key"])

        # Day header
        day_name = d.strftime("%A").upper()
        if d == date.today():
            day_name = "TODAY"
        elif d == date.today() + timedelta(days=1):
            day_name = "TOMORROW"

        printer.print_subheader(f"{day_name} ({d.strftime('%m/%d')})")

        for evt in all_events[d]:
            time_str = evt["time"]
            summary = evt["summary"]

            # Truncate summary to fit
            max_len = printer.width - 8
            if len(summary) > max_len:
                summary = summary[: max_len - 1] + ".."

            # Time in caption style, event in body
            printer.print_body(f"{time_str:<8}{summary}")

        if i < len(sorted_dates) - 1:
            printer.print_line()
