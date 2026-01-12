from datetime import datetime
import pytz
from astral import LocationInfo
from astral.sun import sun
from astral.moon import phase
from typing import Dict, Any
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

def get_almanac_data():
    """Calculates local astronomical data for today."""
    tz = pytz.timezone(app.config.settings.timezone)
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
        "moon_phase": get_moon_phase_text(current_phase),
        "day_length": str(s["sunset"] - s["sunrise"]).split('.')[0] # HH:MM:SS
    }

def format_astronomy_receipt(printer, config: Dict[str, Any] = None, module_name: str = None):
    """Prints the Almanac to the provided printer driver."""
    
    data = get_almanac_data()
    
    printer.print_header(module_name or "ASTRONOMY")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_caption(app.config.settings.city_name)
    printer.print_line()
    
    # Sun section
    printer.print_subheader("SUNRISE")
    printer.print_bold(f"  {data['sunrise']}")
    printer.feed(1)
    printer.print_subheader("SUNSET")
    printer.print_bold(f"  {data['sunset']}")
    printer.print_caption(f"  Daylight: {data['day_length']}")
    printer.print_line()
    
    # Moon phase graphic - nice and large
    printer.print_moon_phase(data['moon_phase_val'], size=80)
    
    # Moon phase name centered
    printer.print_bold(data['moon_phase'].upper())
    printer.print_caption(f"Day {data['moon_phase_val']:.0f} of lunar cycle")
    printer.print_line()

