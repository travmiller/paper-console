from datetime import datetime, timedelta
import pytz
import math
import random
from astral import LocationInfo
from astral.sun import sun, zenith_and_azimuth
from astral.moon import phase
from typing import Dict, Any, List, Tuple
from PIL import Image, ImageDraw

import app.config
from app.config import format_time
from app.module_registry import register_module

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
    """Calculate sun altitude throughout a full 24-hour day.
    
    Returns a list of (datetime, altitude) tuples where altitude is in degrees.
    Altitude ranges from -90 (below horizon) to 90 (zenith).
    Shows a full sine wave with day on the left and night on the right.
    """
    # Get sunrise and sunset for the day
    s = sun(city.observer, date=now, tzinfo=tz)
    sunrise = s["sunrise"]
    sunset = s["sunset"]
    
    # Get sunrise for next day to complete the night period
    next_day = now + timedelta(days=1)
    s_next = sun(city.observer, date=next_day, tzinfo=tz)
    next_sunrise = s_next["sunrise"]
    
    # First, collect day period (sunrise to sunset) - will be on the left
    day_data = []
    current = sunrise.replace(minute=(sunrise.minute // 15) * 15, second=0, microsecond=0)
    while current <= sunset:
        try:
            zenith, _ = zenith_and_azimuth(city.observer, current, with_refraction=True)
            altitude = 90.0 - zenith
            day_data.append((current, altitude))
        except:
            day_data.append((current, -90.0))
        current += timedelta(minutes=15)
    
    # Then, collect night period (sunset to next sunrise) - will be on the right
    night_data = []
    current = sunset.replace(minute=(sunset.minute // 15) * 15, second=0, microsecond=0)
    while current < next_sunrise:
        try:
            zenith, _ = zenith_and_azimuth(city.observer, current, with_refraction=True)
            altitude = 90.0 - zenith
            night_data.append((current, altitude))
        except:
            night_data.append((current, -90.0))
        current += timedelta(minutes=15)
    
    # Combine: day first (left), then night (right)
    return day_data + night_data

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
        current_zenith, _ = zenith_and_azimuth(city.observer, now, with_refraction=True)
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

def draw_moon_phase_image(phase: float, size: int) -> Image.Image:
    """Draw a moon phase graphic with smooth terminator and surface detail."""
    # Create white image
    image = Image.new("1", (size, size), 1)
    draw = ImageDraw.Draw(image)
    
    x = 0
    y = 0
    
    # Normalize phase to 0-1 (0 = new, 0.5 = full, 1 = new)
    phase_normalized = (phase % 28) / 28.0

    # Calculate illumination (0 = new moon, 1 = full moon)
    illumination = (1 - math.cos(phase_normalized * 2 * math.pi)) / 2

    center_x = x + size // 2
    center_y = y + size // 2
    radius = size // 2
    inner_radius = radius - 2  # Account for outline

    # Draw the moon outline (black circle)
    draw.ellipse([x, y, x + size - 1, y + size - 1], outline=0, width=2)

    # Handle new moon (completely dark)
    if illumination < 0.01:
        # Just return current image (outline only)
        return image

    # Fill the whole moon white first (lit portion)
    draw.ellipse([x + 2, y + 2, x + size - 3, y + size - 3], fill=1)

    # Calculate terminator position
    # Terminator X position: moves from right edge to left edge as illumination increases
    terminator_x = center_x - (illumination * 2 - 1) * inner_radius

    # Draw shadow
    if phase_normalized < 0.5:
        # Waxing: right side illuminated, left side dark
        # Shadow is on the left side (px < terminator_x)
        for py in range(y + 2, y + size - 2):
            for px in range(x + 2, min(int(terminator_x) + 1, x + size - 2)):
                dx = px - center_x
                dy = py - center_y
                dist_sq = dx * dx + dy * dy
                if dist_sq <= inner_radius * inner_radius and px < terminator_x:
                    draw.point((px, py), fill=0)
    else:
        # Waning: left side illuminated, right side dark
        # Shadow is on the right side (px > terminator_x)
        for py in range(y + 2, y + size - 2):
            for px in range(max(int(terminator_x), x + 2), x + size - 2):
                dx = px - center_x
                dy = py - center_y
                dist_sq = dx * dx + dy * dy
                if dist_sq <= inner_radius * inner_radius and px > terminator_x:
                    draw.point((px, py), fill=0)

    # Add subtle surface texture (craters)
    random.seed(int(phase * 100))
    num_craters = max(3, size // 20)
    for _ in range(num_craters):
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(0, inner_radius * 0.7)
        crater_x = int(center_x + dist * math.cos(angle))
        crater_y = int(center_y + dist * math.sin(angle))
        
        dx = crater_x - center_x
        dy = crater_y - center_y
        if dx * dx + dy * dy > inner_radius * inner_radius:
            continue

        if phase_normalized < 0.5:
            if crater_x > terminator_x:
                crater_size = random.randint(1, max(1, size // 30))
                draw.ellipse(
                    [crater_x - crater_size, crater_y - crater_size, crater_x + crater_size, crater_y + crater_size],
                    fill=0, outline=1, width=1
                )
        else:
            if crater_x < terminator_x:
                crater_size = random.randint(1, max(1, size // 30))
                draw.ellipse(
                    [crater_x - crater_size, crater_y - crater_size, crater_x + crater_size, crater_y + crater_size],
                    fill=0, outline=1, width=1
                )

    # Redraw outline to ensure clean edges
    draw.ellipse([x, y, x + size - 1, y + size - 1], outline=0, width=2)
    return image

def draw_sun_path_image(
    sun_path: list,
    sunrise: datetime,
    sunset: datetime,
    current_time: datetime,
    current_altitude: float,
    sunrise_time: str,
    sunset_time: str,
    day_length: str,
    width: int,
    fonts: Dict[str, Any]
) -> Image.Image:
    """Draw a sun path curve visualization."""
    height = 200 # Fixed height for chart
    image = Image.new("1", (width, height), 1)
    draw = ImageDraw.Draw(image)
    
    font = fonts.get("regular")
    font_caption = fonts.get("caption")

    x = 0
    y = 0

    # Calculate drawing area
    curve_height = height - 60 
    curve_y = y + 20 
    curve_bottom = curve_y + curve_height - 20
    horizon_y = curve_y + (curve_height - 20) // 2

    # Find min/max altitude
    altitudes = [alt for _, alt in sun_path]
    min_alt = min(altitudes) if altitudes else -90
    max_alt = max(altitudes) if altitudes else 90

    alt_range = max(max_alt - min_alt, 10)
    alt_min = min_alt
    alt_max = max_alt

    # Draw title
    if font:
        draw.text((x, y), "SUN", font=font, fill=0)

    # Draw horizon line
    horizon_x_start = x + 10
    horizon_x_end = x + width - 10
    draw.line([(horizon_x_start, horizon_y), (horizon_x_end, horizon_y)], fill=0, width=1)

    # Draw sun path curve
    curve_width = horizon_x_end - horizon_x_start
    points = []
    current_point_idx = -1

    if sun_path:
        first_time = sun_path[0][0]
        last_time = sun_path[-1][0]
        time_range_seconds = (last_time - first_time).total_seconds()
    else:
        time_range_seconds = 24 * 3600

    for i, (dt, alt) in enumerate(sun_path):
        if time_range_seconds > 0:
            time_offset = (dt - first_time).total_seconds()
            time_of_day = time_offset / time_range_seconds
        else:
            time_of_day = (dt.hour * 60 + dt.minute) / (24 * 60)
            
        curve_x = horizon_x_start + int(time_of_day * curve_width)

        if alt_max > alt_min:
            normalized_alt = (alt - alt_min) / (alt_max - alt_min)
        else:
            normalized_alt = 0.5

        curve_y_pos = curve_y + int((1.0 - normalized_alt) * (curve_bottom - curve_y))
        points.append((curve_x, curve_y_pos))

        if abs((dt - current_time).total_seconds()) < 15 * 60:
            current_point_idx = i

    if len(points) > 1:
        if current_point_idx > 0:
            past_points = points[: current_point_idx + 1]
            for i in range(len(past_points) - 1):
                draw.line([past_points[i], past_points[i + 1]], fill=0, width=2)

        if current_point_idx < len(points) - 1:
            future_start = max(0, current_point_idx)
            future_points = points[future_start:]
            for i in range(len(future_points) - 1):
                if i % 2 == 0:
                    draw.line([future_points[i], future_points[i + 1]], fill=0, width=1)

    # Markers
    if sun_path and time_range_seconds > 0:
        sunrise_offset = (sunrise - first_time).total_seconds()
        sunrise_normalized = sunrise_offset / time_range_seconds
        sunrise_x = horizon_x_start + int(sunrise_normalized * curve_width)
    else:
        sunrise_x = horizon_x_start
    
    draw.ellipse([sunrise_x - 3, horizon_y - 3, sunrise_x + 3, horizon_y + 3], outline=0, width=1, fill=1)

    if sun_path and time_range_seconds > 0:
        sunset_offset = (sunset - first_time).total_seconds()
        sunset_normalized = sunset_offset / time_range_seconds
        sunset_x = horizon_x_start + int(sunset_normalized * curve_width)
    else:
        sunset_x = horizon_x_end
        
    draw.ellipse([sunset_x - 3, horizon_y - 3, sunset_x + 3, horizon_y + 3], outline=0, width=1, fill=1)

    # Current Sun position
    if current_point_idx >= 0 and current_point_idx < len(points):
        current_x, current_y = points[current_point_idx]
        marker_size = 8
        draw.ellipse(
            [current_x - marker_size, current_y - marker_size, current_x + marker_size, current_y + marker_size],
            outline=0, width=2, fill=1
        )
        ray_length = 4
        for angle in [0, 45, 90, 135]:
            rad = math.radians(angle)
            end_x = current_x + int(ray_length * math.cos(rad))
            end_y = current_y + int(ray_length * math.sin(rad))
            draw.line([(current_x, current_y), (end_x, end_y)], fill=0, width=1)

    # Labels
    if font:
        draw.text((x, horizon_y + 25), sunrise_time, font=font, fill=0)
        if font_caption:
            draw.text((x, horizon_y + 45), "Sunrise", font=font_caption, fill=0)

        text_bbox = font.getbbox(sunset_time)
        text_width = text_bbox[2] - text_bbox[0]
        sunset_text_x = x + width - text_width
        draw.text((sunset_text_x, horizon_y + 25), sunset_time, font=font, fill=0)
        if font_caption:
            caption_bbox = font_caption.getbbox("Sunset")
            caption_width = caption_bbox[2] - caption_bbox[0]
            draw.text((x + width - caption_width, horizon_y + 45), "Sunset", font=font_caption, fill=0)

        if day_length:
            text_bbox = font.getbbox(day_length)
            text_width = text_bbox[2] - text_bbox[0]
            duration_x = x + (width - text_width) // 2
            draw.text((duration_x, horizon_y + 25), day_length, font=font, fill=0)
            if font_caption:
                caption_bbox = font_caption.getbbox("Day Length")
                caption_width = caption_bbox[2] - caption_bbox[0]
                caption_x = x + (width - caption_width) // 2
                draw.text((caption_x, horizon_y + 45), "Day Length", font=font_caption, fill=0)

    return image


@register_module(
    type_id="astronomy",
    label="Astronomy",
    description="Sunrise, sunset, moon phase, and sun path visualization",
    icon="moon-stars",
    offline=True,
    category="content",
    config_schema={
        "type": "object",
        "properties": {}
    }
)
def format_astronomy_receipt(printer, config: Dict[str, Any] = None, module_name: str = None):
    """Prints the Almanac to the provided printer driver."""
    
    data = get_almanac_data()
    
    printer.print_header(module_name or "ASTRONOMY", icon="moon-stars")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()
    
    # Location
    printer.print_subheader(app.config.settings.city_name.upper())
    
    # Current time
    printer.print_bold("CURRENT TIME")
    printer.print_caption(format_time(data['current_time']))
    printer.print_line()
    
    # Get fonts and width
    fonts = {
        "regular": getattr(printer, "_get_font", lambda s: None)("regular"),
        "bold": getattr(printer, "_get_font", lambda s: None)("bold"),
        "caption": getattr(printer, "_get_font", lambda s: None)("caption"),
    }
    printer_width = getattr(printer, 'PRINTER_WIDTH_DOTS', 384)
    
    # Sun path visualization
    sun_image = draw_sun_path_image(
        data['sun_path'],
        data['sunrise_dt'],
        data['sunset_dt'],
        data['current_time'],
        data['current_altitude'],
        data['sunrise'],
        data['sunset'],
        data['day_length'],
        printer_width,
        fonts
    )
    printer.print_image(sun_image)
    printer.print_line()
    
    # Moon phase graphic
    moon_image = draw_moon_phase_image(data['moon_phase_val'], size=64)
    # Center moon image
    # To center it, we can create a full-width image and paste the moon in the center
    # OR rely on printer to center it (printer_serial does center images)
    printer.print_image(moon_image)
    
    # Moon data text
    printer.print_bold(data['moon_phase'].upper())
    printer.print_caption(f"Day {data['moon_phase_val']:.0f} of 28")
