from datetime import datetime, timedelta
import pytz
from astral import LocationInfo
from astral.sun import sun, zenith_and_azimuth
from astral.moon import phase
from typing import Dict, Any, List, Tuple
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
    
    # Moon phase graphic
    printer.print_moon_phase(data['moon_phase_val'], size=64)
    
    # Moon data text
    printer.print_bold(data['moon_phase'].upper())
    printer.print_caption(f"Day {data['moon_phase_val']:.0f} of 28")

