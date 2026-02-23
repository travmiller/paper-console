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

            event_instances = []

            if "RRULE" in component:
                # Expand recurring events (RRULE + optional EXDATE/RDATE) inside the view window.
                try:
                    rrule_start = start
                    if is_all_day:
                        rrule_start = datetime.combine(start, datetime.min.time())

                    rule = rrulestr(
                        component["RRULE"].to_ical().decode(), dtstart=rrule_start
                    )

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

                    exdate_keys = set()
                    exdate_prop = component.get("EXDATE")
                    if exdate_prop:
                        exdate_props = (
                            exdate_prop if isinstance(exdate_prop, list) else [exdate_prop]
                        )
                        for ex in exdate_props:
                            for ex_dt_val in getattr(ex, "dts", []):
                                ex_dt = ex_dt_val.dt
                                if isinstance(ex_dt, datetime):
                                    if ex_dt.tzinfo is None and rrule_start.tzinfo is not None:
                                        ex_dt = local_tz.localize(ex_dt)
                                    elif (
                                        ex_dt.tzinfo is not None
                                        and rrule_start.tzinfo is not None
                                    ):
                                        ex_dt = ex_dt.astimezone(local_tz)
                                    exdate_keys.add(ex_dt)
                                else:
                                    exdate_keys.add(ex_dt)

                    for dt in rule.between(query_start, query_end, inc=True):
                        if dt in exdate_keys or dt.date() in exdate_keys:
                            continue

                        if is_all_day:
                            event_instances.append((dt.date(), True))
                        else:
                            if dt.tzinfo is None and local_tz:
                                dt = local_tz.localize(dt)
                            event_instances.append((dt, False))

                    # Include RDATE manual additions that may not be part of RRULE expansion.
                    rdate_prop = component.get("RDATE")
                    if rdate_prop:
                        rdate_props = (
                            rdate_prop
                            if isinstance(rdate_prop, list)
                            else [rdate_prop]
                        )
                        for rdate_entry in rdate_props:
                            for rdate_dt_val in getattr(rdate_entry, "dts", []):
                                rdt = rdate_dt_val.dt
                                if isinstance(rdt, datetime):
                                    if rdt.tzinfo is None:
                                        rdt = local_tz.localize(rdt)
                                    else:
                                        rdt = rdt.astimezone(local_tz)
                                    if query_start <= rdt <= query_end:
                                        event_instances.append((rdt, False))
                                elif isinstance(rdt, date):
                                    if today <= rdt < end_date:
                                        event_instances.append((rdt, True))
                except Exception:
                    # Fallback to just the main event
                    if is_all_day:
                        event_instances.append((start, True))
                    else:
                        event_instances.append((start, False))
            else:
                # Single event
                event_instances.append((start, is_all_day))

            # Deduplicate recurring instances (can happen with overlapping RRULE/RDATE).
            deduped_instances = []
            seen_instance_keys = set()
            for evt_dt, evt_is_all_day in event_instances:
                key = (
                    evt_dt.isoformat()
                    if isinstance(evt_dt, datetime)
                    else str(evt_dt)
                )
                if key in seen_instance_keys:
                    continue
                seen_instance_keys.add(key)
                deduped_instances.append((evt_dt, evt_is_all_day))

            # Process instances
            for evt_dt, evt_is_all_day in deduped_instances:
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
    printer.feed(1)


def _calendar_grid_cell_size(printer) -> int:
    """Choose a cell size that fills most of the printer width."""
    dots_width = getattr(printer, "PRINTER_WIDTH_DOTS", None)
    if not isinstance(dots_width, int) or dots_width <= 0:
        chars_width = getattr(printer, "width", 42)
        dots_width = max(200, int(chars_width * 9))

    # Leave a small margin so print_image does not downscale.
    target_width = max(140, dots_width - 8)
    cell_size = (target_width - 4) // 7
    return max(14, min(56, cell_size))


def _print_calendar_month_view(printer, sorted_dates, all_events):
    """Full month calendar view with events."""

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
    
    # Calculate grid start (first Sunday before or on month start)
    days_since_sunday = first_weekday + 1  # Monday=0, so +1
    grid_start = month_start - timedelta(days=days_since_sunday % 7)
    
    # Print full month calendar grid with event highlighting.
    cell_size = _calendar_grid_cell_size(printer)
    font_sm = getattr(printer, "_get_font", lambda s: None)("regular_sm")
    img = draw_calendar_grid_image(
        weeks=6,
        cell_size=cell_size,
        start_date=grid_start,
        events_by_date=events_by_date,
        font=font_sm,
        highlight_date=today,
        month_start=month_start,
        month_end=next_month,
    )
    printer.print_image(img)
    printer.feed(1)
    
    # Print all events from the month below calendar
    if month_events_by_date:
        # Sort dates
        sorted_month_dates = sorted([d for d in month_events_by_date.keys() if month_start <= d < next_month])
        
        for i, d in enumerate(sorted_month_dates):
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
            
            if i < len(sorted_month_dates) - 1:
                printer.print_line()
    elif sorted_dates:
        # Fallback: show what we have
        printer.print_subheader("UPCOMING EVENTS")
        for i, d in enumerate(sorted_dates):
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
            
            if i < len(sorted_dates) - 1:
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
            printer.print_line()


def _print_calendar_week_view(printer, sorted_dates, all_events):
    """Week view with mini calendar grid and compact event list."""
    # Convert all_events to format expected by calendar grid (date string -> event count)
    events_by_date = {}
    for d, events in all_events.items():
        date_key = d.isoformat() if isinstance(d, date) else str(d)
        events_by_date[date_key] = len(events)
    
    # Print week calendar grid.
    today = date.today()
    cell_size = _calendar_grid_cell_size(printer)
    font_sm = getattr(printer, "_get_font", lambda s: None)("regular_sm")
    img = draw_calendar_grid_image(
        weeks=1,
        cell_size=cell_size,
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


def _resolve_view_mode(config: CalendarConfig) -> str:
    """Resolve calendar view mode from modern or legacy config fields."""
    mode = (getattr(config, "view_mode", None) or "").strip().lower()
    if mode in {"day", "week", "month"}:
        return mode

    # Legacy fallback from previous numeric days_to_show options.
    legacy = getattr(config, "days_to_show", None)
    if legacy == 1:
        return "day"
    if legacy == 2:
        return "month"
    if legacy in {3, 7}:
        return "week"
    return "month"


@register_module(
    type_id="calendar",
    label="Calendar",
    description="Events from iCal calendar URLs",
    icon="calendar-blank",
    offline=False,
    category="content",
    config_schema={
        "type": "object",
        "properties": {
            "ical_sources": {
                "type": "array",
                "title": "iCal Sources",
                "items": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "title": "iCal URL"},
                        "name": {"type": "string", "title": "Label (Optional)"},
                    }
                }
            },
            "view_mode": {
                "type": "string",
                "title": "View Mode",
                "enum": ["day", "week", "month"],
                "enumNames": ["Day", "Week", "Month"],
                "default": "month"
            }
        }
    },
    ui_schema={
        "ical_sources": {
            "items": {
                 "url": {"ui:placeholder": "https://calendar.google.com/..."}
            }
        }
    }
)
def format_calendar_receipt(
    printer: PrinterDriver, config: CalendarConfig, module_name: str = None
):
    """Fetches and prints the calendar agenda."""

    header_label = module_name or "CALENDAR"
    printer.print_header(header_label, icon="calendar-blank")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.feed(1)

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

    view_mode = _resolve_view_mode(config)

    if view_mode == "month":
        # Parse events for the entire current month
        today = date.today()
        if today.month == 12:
            next_month = date(today.year + 1, 1, 1)
        else:
            next_month = date(today.year, today.month + 1, 1)
        parse_days = (next_month - today).days + 1  # Include today through end of month
    elif view_mode == "day":
        parse_days = 1
    else:
        parse_days = 7
    
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

    # Use different visualizations by explicit view mode.
    if view_mode == "day":
        _print_calendar_timeline_view(printer, sorted_dates, all_events)
    elif view_mode == "month":
        _print_calendar_month_view(printer, sorted_dates, all_events)
    else:
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
    from datetime import timedelta

    if not start_date:
        start_date = date.today()

    # Align the grid so columns are always Sunday -> Saturday.
    days_since_sunday = (start_date.weekday() + 1) % 7
    grid_start = start_date - timedelta(days=days_since_sunday)

    day_key_top_pad = 4
    day_key_bottom_pad = 2
    day_key_to_grid_gap = 4

    header_height = 12
    if font:
        bbox = font.getbbox("M")
        font_h = bbox[3] - bbox[1] if bbox else 0
        header_height = max(header_height, font_h + day_key_top_pad + day_key_bottom_pad)
    grid_width = 7 * cell_size
    grid_top = 2 + header_height + day_key_to_grid_gap
    grid_height = weeks * cell_size

    img = Image.new("1", (grid_width + 4, grid_top + grid_height + 2), 1)
    draw = ImageDraw.Draw(img)
    x0, y0 = 2, 2

    # Day headers (S M T W T F S).
    day_names = ["S", "M", "T", "W", "T", "F", "S"]
    for i, day_name in enumerate(day_names):
        day_x = x0 + i * cell_size
        if font:
            gx0, gy0, gx1, gy1 = draw.textbbox((0, 0), day_name, font=font)
            text_w = gx1 - gx0
            text_h = gy1 - gy0
            key_inner_h = max(1, header_height - day_key_top_pad - day_key_bottom_pad)
            text_x = day_x + (cell_size - text_w) // 2 - gx0
            text_y = y0 + day_key_top_pad + (key_inner_h - text_h) // 2 - gy0
            draw.text((text_x, text_y), day_name, font=font, fill=0)
        else:
            draw.text((day_x + (cell_size // 2), y0), day_name, fill=0)

    for week in range(weeks):
        for day in range(7):
            cell_x = x0 + day * cell_size
            cell_y = grid_top + week * cell_size
            cell_date = grid_start + timedelta(days=week * 7 + day)

            is_today = bool(highlight_date and cell_date == highlight_date)
            is_current_month = True
            if month_start and month_end:
                is_current_month = month_start <= cell_date < month_end

            raw_event_count = events_by_date.get(cell_date.isoformat(), 0)
            try:
                event_count = max(0, min(6, int(raw_event_count)))
            except (TypeError, ValueError):
                event_count = 0

            border_width = 2 if is_today else 1

            draw.rectangle(
                [cell_x, cell_y, cell_x + cell_size - 1, cell_y + cell_size - 1],
                outline=0,
                width=border_width,
            )

            # Day number. Only today is inverted.
            day_num = str(cell_date.day)
            text_fill = 0
            text_x = cell_x + 2
            text_y = cell_y + 2

            if is_today:
                pad = 1
                if font:
                    gx0, gy0, gx1, gy1 = draw.textbbox((0, 0), day_num, font=font)
                else:
                    gx0, gy0, gx1, gy1 = 0, 0, max(5, len(day_num) * 5), 7

                text_w = gx1 - gx0
                text_h = gy1 - gy0
                min_side = max(text_w, text_h) + (pad * 2)
                preferred_side = max(min_side, int(cell_size * 0.42))
                side = min(cell_size - 2, preferred_side)

                box_x0 = cell_x + 1
                box_y0 = cell_y + 1
                box_x1 = box_x0 + side
                box_y1 = box_y0 + side
                draw.rectangle([box_x0, box_y0, box_x1, box_y1], fill=0)

                # Center text in the square while accounting for glyph bbox offsets.
                text_x = box_x0 + ((side - text_w) // 2) - gx0
                text_y = box_y0 + ((side - text_h) // 2) - gy0
                text_fill = 1

            if font:
                draw.text((text_x, text_y), day_num, font=font, fill=text_fill)
            else:
                draw.text((text_x, text_y), day_num, fill=text_fill)

            # Draw event dots around the lower-middle area of the cell (up to 6 dots).
            if event_count > 0:
                dots_per_row = 3
                dot_size = 3 if cell_size < 20 else 4
                dot_gap = 2
                row_gap = 2
                rows = (event_count + dots_per_row - 1) // dots_per_row
                dots_h = rows * dot_size + (rows - 1) * row_gap
                target_center_y = cell_y + int(cell_size * (2 / 3))
                start_y = target_center_y - (dots_h // 2)
                min_y = cell_y + 2
                max_y = cell_y + cell_size - dots_h - 2
                start_y = max(min_y, min(start_y, max_y))

                dots_drawn = 0
                for row in range(rows):
                    row_count = min(dots_per_row, event_count - dots_drawn)
                    row_w = row_count * dot_size + (row_count - 1) * dot_gap
                    start_x = cell_x + (cell_size - row_w) // 2
                    y = start_y + row * (dot_size + row_gap)

                    for i in range(row_count):
                        x = start_x + i * (dot_size + dot_gap)
                        draw.ellipse(
                            [x, y, x + dot_size - 1, y + dot_size - 1],
                            fill=0,
                        )
                    dots_drawn += row_count

            # Crosshatch dates outside this month in month-view to de-emphasize.
            if month_start and month_end and not is_current_month:
                for px in range(cell_x + 2, cell_x + cell_size - 2, 3):
                    draw.point((px, cell_y + 2), fill=0)
                    draw.point((px, cell_y + cell_size - 3), fill=0)

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
