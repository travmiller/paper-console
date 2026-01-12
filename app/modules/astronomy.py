from datetime import datetime, timedelta, date
import math
import pytz
from astral import LocationInfo
from astral.sun import sun, zenith_and_azimuth
from astral.moon import phase, moonrise, moonset
from typing import Dict, Any, List, Tuple, Optional
import app.config
from app.config import format_time

# Dynamic Location from Config
def get_city_info():
    return LocationInfo(
        app.config.settings.city_name, 
        "Local", 
        app.config.settings.timezone, 
        app.config.settings.latitude, 
        app.config.settings.longitude
    )

def get_moon_phase_text(moon_phase: float) -> str:
    """Returns ASCII text representing the current moon phase (0-27)."""
    # 0 .. 28 days roughly
    if moon_phase < 2 or moon_phase > 26: return "New"
    elif moon_phase < 6: return "Wax Crescent"
    elif moon_phase < 9: return "First Qtr"
    elif moon_phase < 12: return "Wax Gibbous"
    elif moon_phase < 16: return "Full"
    elif moon_phase < 20: return "Wan Gibbous"
    elif moon_phase < 23: return "Last Qtr"
    else: return "Wan Crescent"

def get_moon_illumination(moon_phase: float) -> float:
    """Calculate moon illumination percentage (0-100).
    
    Args:
        moon_phase: Moon phase value (0-28 day cycle)
    
    Returns:
        Illumination percentage (0.0 = new moon, 100.0 = full moon)
    """
    phase_normalized = (moon_phase % 28) / 28.0
    # Illumination follows a cosine curve
    illumination = (1 - math.cos(phase_normalized * 2 * math.pi)) / 2
    return illumination * 100.0

def find_next_full_moon(current_date: date) -> date:
    """Find the next full moon date after current_date.
    
    Full moon occurs at phase = 14 (approximately).
    """
    # Start searching from current date
    search_date = current_date
    max_days = 30  # Full moon cycle is ~29.5 days
    
    for _ in range(max_days):
        try:
            # phase() accepts date or datetime
            phase_val = phase(search_date)
            # Full moon is around phase 14 (0-28 cycle)
            if 13.5 <= phase_val <= 14.5:
                return search_date
        except Exception:
            pass
        search_date += timedelta(days=1)
    
    # Fallback: approximate next full moon (29.5 days)
    return current_date + timedelta(days=29)

def find_next_new_moon(current_date: date) -> date:
    """Find the next new moon date after current_date.
    
    New moon occurs at phase = 0 or 28 (approximately).
    """
    # Start searching from current date
    search_date = current_date
    max_days = 30  # New moon cycle is ~29.5 days
    
    for _ in range(max_days):
        try:
            # phase() accepts date or datetime
            phase_val = phase(search_date)
            # New moon is around phase 0 or 28 (0-28 cycle)
            if phase_val < 1.0 or phase_val > 27.0:
                return search_date
        except Exception:
            pass
        search_date += timedelta(days=1)
    
    # Fallback: approximate next new moon (29.5 days)
    return current_date + timedelta(days=29)

def get_sun_path_data(now: datetime, city: LocationInfo, tz: pytz.BaseTzInfo) -> List[Tuple[datetime, float]]:
    """Calculate sun altitude throughout the day.
    
    Returns a list of (datetime, altitude) tuples where altitude is in degrees.
    Altitude ranges from -90 (below horizon) to 90 (zenith).
    """
    # Get sunrise and sunset for the day
    s = sun(city.observer, date=now, tzinfo=tz)
    sunrise = s["sunrise"]
    sunset = s["sunset"]
    
    # Calculate points throughout the day (every 15 minutes)
    # Start 2 hours before sunrise, end 2 hours after sunset for full curve
    path_data = []
    start_time = sunrise - timedelta(hours=2)
    end_time = sunset + timedelta(hours=2)
    current = start_time.replace(minute=(start_time.minute // 15) * 15, second=0, microsecond=0)
    
    # Sample every 15 minutes from start to end
    while current <= end_time:
        try:
            zenith, azimuth = zenith_and_azimuth(city.observer, current, with_refraction=True)
            # Altitude = 90 - zenith (zenith is angle from vertical, altitude is angle from horizon)
            altitude = 90.0 - zenith
            path_data.append((current, altitude))
        except:
            # If calculation fails (e.g., polar regions), use -90 (below horizon)
            path_data.append((current, -90.0))
        current += timedelta(minutes=15)
    
    return path_data

def get_almanac_data():
    """Calculates local astronomical data for today."""
    tz = pytz.timezone(app.config.settings.timezone)
    now = datetime.now(tz)
    
    city = get_city_info()

    # Sun Calculations
    s = sun(city.observer, date=now, tzinfo=tz)
    
    # Calculate sun path for visualization
    sun_path = get_sun_path_data(now, city, tz)
    
    # Moon Calculations
    # Astral's phase() returns 0..28 roughly
    current_phase = phase(now)
    moon_illumination = get_moon_illumination(current_phase)
    
    # Calculate moonrise and moonset
    moonrise_time = None
    moonset_time = None
    try:
        moonrise_time = moonrise(city.observer, date=now.date(), tzinfo=tz)
    except (ValueError, Exception):
        pass  # Moon doesn't rise today
    
    try:
        moonset_time = moonset(city.observer, date=now.date(), tzinfo=tz)
    except (ValueError, Exception):
        pass  # Moon doesn't set today
    
    # Find next full and new moon
    next_full_moon = find_next_full_moon(now.date())
    next_new_moon = find_next_new_moon(now.date())
    
    # Calculate days until next phases
    days_to_full = (next_full_moon - now.date()).days
    days_to_new = (next_new_moon - now.date()).days
    
    # Calculate current sun position
    try:
        current_zenith, current_azimuth = zenith_and_azimuth(city.observer, now, with_refraction=True)
        current_altitude = 90.0 - current_zenith
    except:
        current_altitude = -90.0
    
    return {
        "date": now.strftime("%A, %b %d %Y"),
        "sunrise": format_time(s["sunrise"]),
        "sunset": format_time(s["sunset"]),
        "sunrise_dt": s["sunrise"],
        "sunset_dt": s["sunset"],
        "current_time": now,
        "current_altitude": current_altitude,
        "sun_path": sun_path,
        "moon_phase_val": current_phase,
        "moon_phase": get_moon_phase_text(current_phase),
        "moon_illumination": moon_illumination,
        "moonrise": format_time(moonrise_time) if moonrise_time else None,
        "moonset": format_time(moonset_time) if moonset_time else None,
        "moonrise_dt": moonrise_time,
        "moonset_dt": moonset_time,
        "next_full_moon": next_full_moon,
        "next_new_moon": next_new_moon,
        "days_to_full": days_to_full,
        "days_to_new": days_to_new,
        "day_length": str(s["sunset"] - s["sunrise"]).split('.')[0] # HH:MM:SS
    }

def format_astronomy_receipt(printer, config: Dict[str, Any] = None, module_name: str = None):
    """Prints the Almanac to the provided printer driver."""
    
    data = get_almanac_data()
    
    printer.print_header(module_name or "ASTRONOMY", icon="moon-stars")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()
    
    # Location
    printer.print_subheader(app.config.settings.city_name.upper())
    
    # Sun path visualization
    printer.print_sun_path(
        sun_path=data['sun_path'],
        sunrise=data['sunrise_dt'],
        sunset=data['sunset_dt'],
        current_time=data['current_time'],
        current_altitude=data['current_altitude'],
        sunrise_time=data['sunrise'],
        sunset_time=data['sunset'],
        day_length=data['day_length']
    )
    printer.print_line()
    
    # Enhanced moon phase graphic with info
    printer.print_moon_phase(
        phase=data['moon_phase_val'],
        size=64,
        illumination=data['moon_illumination'],
        moonrise=data['moonrise'],
        moonset=data['moonset'],
        next_full_moon=data['next_full_moon'],
        next_new_moon=data['next_new_moon'],
        days_to_full=data['days_to_full'],
        days_to_new=data['days_to_new']
    )

