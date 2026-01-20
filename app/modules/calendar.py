import requests
import pytz
from datetime import datetime, timedelta, date
from typing import List, Dict, Any
from icalendar import Calendar
from dateutil.rrule import rrulestr
from app.drivers.printer_mock import PrinterDriver
from app.config import CalendarConfig, format_time
import app.config
from app.module_registry import register_module
from PIL import Image, ImageDraw
import app.config  # Ensure app.config is imported for timezone access

APP_CONFIG = app.config  # Alias to avoid confusion if needed


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
                            "datetime": evt_dt if not evt_is_all_day else None,
                            "is_all_day": evt_is_all_day,
                        }
                    )

    # Sort events within each day
    for d in events_by_day:
        events_by_day[d].sort(key=lambda x: x["sort_key"])

    return events_by_day


def _print_calendar_timeline_view(printer, sorted_dates, all_events):
    """Detailed timeline view for 1 day - shows full day with hour markers and event bars."""
    if not sorted_dates:
        return
    
    d = sorted_dates[0]
    events = all_events[d]
    events.sort(key=lambda x: x["sort_key"])
    
    # Day header
    day_name = d.strftime("%A").upper()
    if d == date.today():
        day_name = "TODAY"
    
    printer.print_subheader(f"{day_name} ({d.strftime('%m/%d')})")
    
    # Print timeline visualization
    # Print timeline visualization
    width = printer.width
    font = getattr(printer, "_get_font", lambda s: None)("regular")
    font_sm = getattr(printer, "_get_font", lambda s: None)("regular_sm")
    
    # Generate image
    img = draw_calendar_day_timeline_image(
        width - 20, 120, d, events, False, font, font_sm
    )
    printer.print_image(img)
    printer.print_line()


def _print_calendar_month_view(printer, sorted_dates, all_events):
    """Full month calendar view with events."""
    from datetime import datetime
    import app.config
    
    # Get current month
    today = date.today()
    month_start = date(today.year, today.month, 1)
    
    # Calculate first day of week for the month (Monday = 0)
    first_weekday = month_start.weekday()
    
    # Calculate number of days in month
    if today.month == 12:
        next_month = date(today.year + 1, 1, 1)
    else:
        next_month = date(today.year, today.month + 1, 1)
    days_in_month = (next_month - month_start).days
    
    # For month view, we need to fetch events for the entire month
    # Re-fetch events for the full month range
    month_all_events = {}
    sources = []
    # We need access to config, but we'll parse for the full month
    # Calculate end date for the month
    month_end = next_month - timedelta(days=1)
    
    # Re-parse events for the entire month
    # This is a bit of a hack - we'll need to re-fetch, but for now use what we have
    # and extend it by parsing with a larger days_to_show
    # Actually, let's just use all_events we have and extend the range
    
    # Convert all_events to format expected by calendar grid (date string -> event count)
    # Also collect all events in the month
    events_by_date = {}
    month_events_by_date = {}  # All events in the current month
    
    for d, events in all_events.items():
        date_key = d.isoformat() if isinstance(d, date) else str(d)
        events_by_date[date_key] = len(events)
        
        # If date is in current month, add to month events
        if month_start <= d < next_month:
            month_events_by_date[d] = events
    
    # Print month header
    month_name = today.strftime("%B %Y").upper()
    printer.print_subheader(month_name)
    
    # Calculate grid start (first Sunday before or on month start)
    days_since_sunday = first_weekday + 1  # Monday=0, so +1
    grid_start = month_start - timedelta(days=days_since_sunday % 7)
    
    # Print full month calendar grid with event highlighting
    # Print full month calendar grid with event highlighting
    font_sm = getattr(printer, "_get_font", lambda s: None)("regular_sm")
    img = draw_calendar_grid_image(
        weeks=6,
        cell_size=14,
        start_date=grid_start,
        events_by_date=events_by_date,
        font=font_sm,
        highlight_date=today,
        month_start=month_start,
        month_end=next_month,
    )
    printer.print_image(img)
    printer.print_line()
    
    # Print all events from the month below calendar
    if month_events_by_date:
        printer.print_subheader("MONTH EVENTS")
        # Sort dates
        sorted_month_dates = sorted([d for d in month_events_by_date.keys() if month_start <= d < next_month])
        
        for d in sorted_month_dates:
            events = month_events_by_date[d]
            events.sort(key=lambda x: x["sort_key"])
            
            # Day header
            day_name = d.strftime("%A").upper()
            if d == date.today():
                day_name = "TODAY"
            elif d == date.today() + timedelta(days=1):
                day_name = "TOMORROW"
            
            printer.print_bold(f"{day_name} {d.strftime('%m/%d')}")
            
            for evt in events:
                time_str = evt["time"]
                summary = evt["summary"]
                
                # Truncate summary to fit
                max_len = printer.width - 12
                if len(summary) > max_len:
                    summary = summary[: max_len - 1] + ".."
                
                printer.print_body(f"  {time_str:<8}{summary}")
            
            printer.print_line()
    elif sorted_dates:
        # Fallback: show what we have
        printer.print_subheader("UPCOMING EVENTS")
        for d in sorted_dates:
            events = all_events[d]
            events.sort(key=lambda x: x["sort_key"])
            
            # Day header
            day_name = d.strftime("%A").upper()
            if d == date.today():
                day_name = "TODAY"
            elif d == date.today() + timedelta(days=1):
                day_name = "TOMORROW"
            
            printer.print_bold(f"{day_name} {d.strftime('%m/%d')}")
            
            for evt in events:
                time_str = evt["time"]
                summary = evt["summary"]
                
                # Truncate summary to fit
                max_len = printer.width - 12
                if len(summary) > max_len:
                    summary = summary[: max_len - 1] + ".."
                
                printer.print_body(f"  {time_str:<8}{summary}")
            
            printer.print_line()


def _print_calendar_compact_view(printer, sorted_dates, all_events):
    """Compact timeline view for 3 days with visual separators."""
    for i, d in enumerate(sorted_dates[:3]):
        events = all_events[d]
        events.sort(key=lambda x: x["sort_key"])
        
        # Day header
        day_name = d.strftime("%A").upper()
        if d == date.today():
            day_name = "TODAY"
        elif d == date.today() + timedelta(days=1):
            day_name = "TOMORROW"
        
        printer.print_subheader(f"{day_name} ({d.strftime('%m/%d')})")
        
        # Print events in compact list format
        for evt in events:
            time_str = evt["time"]
            summary = evt["summary"]
            
            # Truncate summary to fit
            max_len = printer.width - 8
            if len(summary) > max_len:
                summary = summary[: max_len - 1] + ".."
            
            printer.print_body(f"{time_str:<8}{summary}")
        
        if i < len(sorted_dates) - 1:
            printer.print_line()  # Separator


def _print_calendar_week_view(printer, sorted_dates, all_events):
    """Week view with mini calendar grid and compact event list."""
    # Convert all_events to format expected by calendar grid (date string -> event count)
    events_by_date = {}
    for d, events in all_events.items():
        date_key = d.isoformat() if isinstance(d, date) else str(d)
        events_by_date[date_key] = len(events)
    
    # Print mini calendar grid
    today = date.today()
    # Print mini calendar grid
    today = date.today()
    font_sm = getattr(printer, "_get_font", lambda s: None)("regular_sm")
    img = draw_calendar_grid_image(
        weeks=1, 
        cell_size=10, 
        start_date=today, 
        events_by_date=events_by_date,
        font=font_sm,
        highlight_date=today,
    )
    printer.print_image(img)
    printer.print_line()
    
    # Print events for each day
    for i, d in enumerate(sorted_dates):
        events = all_events[d]
        events.sort(key=lambda x: x["sort_key"])
        
        # Day header
        day_name = d.strftime("%A").upper()
        if d == date.today():
            day_name = "TODAY"
        elif d == date.today() + timedelta(days=1):
            day_name = "TOMORROW"
        
        printer.print_subheader(f"{day_name} ({d.strftime('%m/%d')})")
        
        # Print events in compact list format
        for evt in events:
            time_str = evt["time"]
            summary = evt["summary"]
            
            # Truncate summary to fit
            max_len = printer.width - 8
            if len(summary) > max_len:
                summary = summary[: max_len - 1] + ".."
            
            printer.print_body(f"{time_str:<8}{summary}")
        
        if i < len(sorted_dates) - 1:
            printer.print_line()


@register_module(
    type_id="calendar",
    label="Calendar",
    description="Events from iCal calendar URLs",
    icon="calendar-blank",
    offline=False,
    category="content",
)
def format_calendar_receipt(
    printer: PrinterDriver, config: CalendarConfig, module_name: str = None
):
    """Fetches and prints the calendar agenda."""

    header_label = module_name or "CALENDAR"
    printer.print_header(header_label, icon="calendar-blank")
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

    # For month view, we need to parse events for the entire month
    days_to_show = config.days_to_show or 2
    if days_to_show == 2:  # Month view
        # Parse events for the entire current month
        today = date.today()
        month_start = date(today.year, today.month, 1)
        if today.month == 12:
            next_month = date(today.year + 1, 1, 1)
        else:
            next_month = date(today.year, today.month + 1, 1)
        days_in_month = (next_month - today).days
        parse_days = days_in_month + 1  # Include today through end of month
    else:
        parse_days = days_to_show
    
    for url in sources:
        ics_data = fetch_ics(url)
        if ics_data:
            events = parse_events(
                ics_data, parse_days, app.config.settings.timezone
            )
            for d, evts in events.items():
                if d not in all_events:
                    all_events[d] = []
                all_events[d].extend(evts)

    if not all_events:
        printer.print_body("No upcoming events.")
        return

    sorted_dates = sorted(all_events.keys())
    days_to_show = config.days_to_show or 2
    
    # Use different visualizations based on number of days
    if days_to_show == 1:
        # Detailed timeline view for single day
        _print_calendar_timeline_view(printer, sorted_dates, all_events)
    elif days_to_show == 2:
        # Full month view
        _print_calendar_month_view(printer, sorted_dates, all_events)
    elif days_to_show == 3:
        # Compact timeline view for 3 days
        _print_calendar_compact_view(printer, sorted_dates, all_events)
    else:  # 7 days
        # Week view with calendar grid
        _print_calendar_week_view(printer, sorted_dates, all_events)


def draw_calendar_grid_image(
    weeks: int,
    cell_size: int,
    start_date: date,
    events_by_date: dict,
    font,
    highlight_date=None,
    month_start=None,
    month_end=None,
) -> Image.Image:
    """Draw a calendar grid to an image."""
    from datetime import datetime, timedelta

    # Fixed parameters
    header_height = 10
    grid_width = 7 * cell_size
    grid_height = header_height + 2 + (weeks * cell_size)
    
    # Create image
    img = Image.new("1", (grid_width + 4, grid_height + 4), 1)  # White background
    draw = ImageDraw.Draw(img)
    x, y = 2, 0  # Offset

    # Day headers (S M T W T F S)
    day_names = ["S", "M", "T", "W", "T", "F", "S"]
    header_y = y + 2
    
    # Draw header background line
    draw.line(
        [
            (x, header_y + header_height),
            (x + grid_width, header_y + header_height),
        ],
        fill=0,
        width=1,
    )
    for i, day_name in enumerate(day_names):
        day_x = x + i * cell_size
        if font:
            bbox = font.getbbox(day_name)
            text_w = bbox[2] - bbox[0] if bbox else cell_size // 2
            text_x = day_x + (cell_size - text_w) // 2
            draw.text((text_x, header_y), day_name, font=font, fill=0)

    # Draw grid cells
    current_date = start_date if start_date else datetime.now().date()
    # Find first Sunday before or on start_date
    days_since_sunday = (current_date.weekday() + 1) % 7
    # If using Python's weekday: Mon=0...Sun=6. 
    # We want Sun=0...Sat=6 logic for this grid usually.
    # Current logic: python weekday(): Mon=0, Sun=6.
    # If today is Mon(0), days_since_sunday should be 1.
    # If today is Sun(6), days_since_sunday should be 0.
    days_since_sunday = (current_date.weekday() + 1) % 7
    grid_start = current_date - timedelta(days=days_since_sunday)

    for week in range(weeks):
        for day in range(7):
            cell_x = x + day * cell_size
            cell_y = y + 12 + week * cell_size  # +12 for header

            # Get date for this cell
            cell_date = grid_start + timedelta(days=week * 7 + day)

            # Check if this is the highlighted date (e.g., today)
            is_highlighted = highlight_date and cell_date == highlight_date

            # Check if date is in current month (for month view)
            is_current_month = True
            if month_start and month_end:
                is_current_month = month_start <= cell_date < month_end
            elif start_date:
                try:
                    # Check if start_date represents a month start
                    if start_date.day <= 7:  # Likely a month start
                        is_current_month = (
                            cell_date.month == start_date.month
                            and cell_date.year == start_date.year
                        )
                except:
                    pass

            # Check if date has events
            date_key = cell_date.isoformat()
            has_events = date_key in events_by_date and events_by_date[date_key] > 0

            # Draw cell border
            if is_highlighted:
                border_width = 2
            elif has_events:
                border_width = 2  # Also thick for events
            else:
                border_width = 1

            draw.rectangle(
                [cell_x, cell_y, cell_x + cell_size - 1, cell_y + cell_size - 1],
                outline=0,
                width=border_width,
            )

            # Fill cell background if highlighted or has events
            if is_highlighted:
                # Draw filled rectangle with checkerboard pattern for today
                for px in range(cell_x + 1, cell_x + cell_size - 1):
                    for py in range(cell_y + 1, cell_y + cell_size - 1):
                        if ((px - cell_x) + (py - cell_y)) % 3 < 2:
                            draw.point((px, py), fill=0)
            elif has_events and is_current_month:
                # Draw lighter pattern for dates with events
                for px in range(cell_x + 1, cell_x + cell_size - 1, 2):
                    for py in range(cell_y + 1, cell_y + cell_size - 1, 2):
                        draw.point((px, py), fill=0)

            # Draw day number
            day_num = str(cell_date.day)
            if font:
                bbox = font.getbbox(day_num)
                text_x = cell_x + 2
                text_y = cell_y + 2
                # Use inverted fill for highlighted dates, lighter for other months
                if is_highlighted:
                    text_fill = 1  # White on black
                elif not is_current_month:
                    text_fill = 0  # Black, but we'll make it lighter with pattern
                    # Draw lighter pattern for other months
                    for px in range(cell_x + 1, cell_x + cell_size - 1, 2):
                        for py in range(cell_y + 1, cell_y + cell_size - 1, 2):
                            draw.point((px, py), fill=0)
                else:
                    text_fill = 0  # Normal black
                draw.text((text_x, text_y), day_num, font=font, fill=text_fill)

            # Draw event indicator (dot) - only if not already highlighted
            if has_events and not is_highlighted:
                dot_x = cell_x + cell_size - 4
                dot_y = cell_y + cell_size - 4
                # Draw a small filled circle for events
                draw.ellipse([dot_x - 2, dot_y - 2, dot_x + 2, dot_y + 2], fill=0)
            elif has_events and is_highlighted:
                # For highlighted dates with events, draw a larger indicator
                dot_x = cell_x + cell_size - 5
                dot_y = cell_y + cell_size - 5
                # Draw white circle on black background
                draw.ellipse(
                    [dot_x - 2, dot_y - 2, dot_x + 2, dot_y + 2], fill=1, outline=0
                )
    
    return img


def draw_calendar_day_timeline_image(
    width: int,
    height: int,
    day: date,
    events: list,
    compact: bool,
    font,
    font_sm,
) -> Image.Image:
    """Draw a timeline visualization for a single calendar day to an image."""
    from datetime import datetime, time as dt_time
    import pytz

    # Create image
    img = Image.new("1", (width, height), 1)  # White background
    draw = ImageDraw.Draw(img)
    x, y = 0, 0

    # Timeline area
    timeline_x = x + 10
    timeline_y = y + 20
    timeline_width = width - 20
    timeline_height = height - 60 if not compact else height - 40

    # Get timezone
    try:
        tz = pytz.timezone(APP_CONFIG.settings.timezone)
    except:
        tz = pytz.UTC

    # Current time
    now = datetime.now(tz)
    today = now.date()
    is_today = day == today

    # Draw timeline axis (horizontal line)
    axis_y = timeline_y + timeline_height // 2
    draw.line(
        [(timeline_x, axis_y), (timeline_x + timeline_width, axis_y)],
        fill=0,
        width=2,
    )

    # Draw hour markers
    if not compact:
        for hour in [0, 6, 12, 18, 24]:
            display_hour = 0 if hour == 24 else hour
            marker_x = timeline_x + int((hour / 24) * timeline_width)
            # Draw tick mark
            draw.line(
                [(marker_x, axis_y - 5), (marker_x, axis_y + 5)],
                fill=0,
                width=1,
            )
            # Draw hour label
            if font_sm:
                hour_str = f"{display_hour:02d}:00"
                bbox = font_sm.getbbox(hour_str)
                text_w = bbox[2] - bbox[0] if bbox else 20
                draw.text(
                    (marker_x - text_w // 2, axis_y + 8),
                    hour_str,
                    font=font_sm,
                    fill=0,
                )

    # Draw current time indicator (if today)
    if is_today and not compact:
        current_hour = now.hour
        current_minute = now.minute
        current_pos = (current_hour * 60 + current_minute) / (24 * 60)
        current_x = timeline_x + int(current_pos * timeline_width)
        # Draw vertical line
        draw.line(
            [(current_x, timeline_y), (current_x, timeline_y + timeline_height)],
            fill=0,
            width=1,
        )
        # Draw triangle indicator
        triangle_size = 4
        draw.polygon(
            [
                (current_x, timeline_y),
                (current_x - triangle_size, timeline_y + triangle_size),
                (current_x + triangle_size, timeline_y + triangle_size),
            ],
            fill=0,
        )

    # Draw events
    event_y_offset = 0
    for event in events:
        time_str = event.get("time", "")
        summary = event.get("summary", "")
        event_dt = event.get("datetime")
        is_all_day = event.get("is_all_day", False)

        if is_all_day:
            # All-day event: draw full-width bar at top
            bar_y = timeline_y + event_y_offset
            bar_height = 12
            draw.rectangle(
                [
                    (timeline_x, bar_y),
                    (timeline_x + timeline_width, bar_y + bar_height),
                ],
                outline=0,
                width=1,
                fill=0,
            )
            # Draw text
            if font_sm:
                draw.text(
                    (timeline_x + 4, bar_y + 2),
                    f"All Day: {summary[:30]}",
                    font=font_sm,
                    fill=1,  # White text on black background
                )
            event_y_offset += bar_height + 4
        elif event_dt and not compact:
            # Timed event: position by time
            event_hour = event_dt.hour
            event_minute = event_dt.minute
            event_pos = (event_hour * 60 + event_minute) / (24 * 60)
            event_x = timeline_x + int(event_pos * timeline_width)

            # Draw event marker (circle)
            marker_radius = 4
            marker_y = axis_y
            draw.ellipse(
                [
                    event_x - marker_radius,
                    marker_y - marker_radius,
                    event_x + marker_radius,
                    marker_y + marker_radius,
                ],
                fill=0,
            )

            # Draw event text above or below timeline
            text_y = (
                marker_y - 20
                if marker_y > timeline_y + timeline_height // 2
                else marker_y + 12
            )
            if font_sm:
                # Truncate summary
                max_text_width = timeline_width // 3
                if len(summary) > max_text_width // 6:
                    summary = summary[: max_text_width // 6 - 3] + "..."
                draw.text((event_x + 6, text_y), summary, font=font_sm, fill=0)
                # Draw time below
                draw.text(
                    (event_x + 6, text_y + 12), time_str, font=font_sm, fill=0
                )
        else:
            # Compact mode: just list events
            if font:
                text = f"{time_str:<8}{summary[:30]}"
                draw.text(
                    (timeline_x, timeline_y + event_y_offset),
                    text,
                    font=font,
                    fill=0,
                )
                event_y_offset += 18
    
    return img
