from datetime import datetime
import pytz
from astral import LocationInfo
from astral.sun import sun
from astral.moon import phase
from typing import Dict, Any
from app.config import settings, format_time

# Dynamic Location from Config
def get_city_info():
    return LocationInfo(
        settings.city_name, 
        "Local", 
        settings.timezone, 
        settings.latitude, 
        settings.longitude
    )

def get_moon_emoji(moon_phase: float) -> str:
    """Returns an emoji representing the current moon phase (0-27)."""
    # 0 .. 28 days roughly
    if moon_phase < 2 or moon_phase > 26: return "🌑" # New
    elif moon_phase < 6: return "🌒" # Waxing Crescent
    elif moon_phase < 9: return "🌓" # First Quarter
    elif moon_phase < 12: return "🌔" # Waxing Gibbous
    elif moon_phase < 16: return "🌕" # Full
    elif moon_phase < 20: return "🌖" # Waning Gibbous
    elif moon_phase < 23: return "🌗" # Last Quarter
    else: return "🌘" # Waning Crescent

def get_almanac_data():
    """Calculates local astronomical data for today."""
    tz = pytz.timezone(settings.timezone)
    now = datetime.now(tz)
    
    city = get_city_info()

    # Sun Calculations
    s = sun(city.observer, date=now, tzinfo=tz)
    
    # Moon Calculations
    # Astral's phase() returns 0..28 roughly
    current_phase = phase(now)
    
    return {
        "date": now.strftime("%A, %b %d %Y"),
        "sunrise": format_time(s["sunrise"]),
        "sunset": format_time(s["sunset"]),
        "moon_phase_val": current_phase,
        "moon_emoji": get_moon_emoji(current_phase),
        "day_length": str(s["sunset"] - s["sunrise"]).split('.')[0] # HH:MM:SS
    }

def format_astronomy_receipt(printer, config: Dict[str, Any] = None, module_name: str = None):
    """Prints the Almanac to the provided printer driver."""
    # Config can be used to toggle specific sections if we want later
    
    data = get_almanac_data()
    
    printer.print_header((module_name or "ASTRONOMY").upper())
    printer.print_text(f"{settings.city_name}")
    printer.print_text(f"{data['date']}")
    printer.print_line()
    
    printer.print_text(f"SUNRISE: {data['sunrise']}")
    printer.print_text(f"SUNSET:  {data['sunset']}")
    printer.print_text(f"LENGTH:  {data['day_length']}")
    printer.print_line()
    
    printer.print_text(f"MOON:    {data['moon_emoji']}")
    printer.print_text(f"PHASE:   {data['moon_phase_val']:.1f} / 28")
    
    printer.feed(1)
