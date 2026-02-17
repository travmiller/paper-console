from datetime import datetime, timedelta
import pytz
import math
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
    
    day_length_seconds = int((s["sunset"] - s["sunrise"]).total_seconds())
    day_hours = day_length_seconds // 3600
    day_minutes = (day_length_seconds % 3600) // 60

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
        "day_length": f"{day_hours}h {day_minutes:02d}m"
    }

def draw_moon_phase_image(phase: float, size: int) -> Image.Image:
    """Draw a moon phase with textured lunar shading for thermal printers."""
    grayscale = Image.new("L", (size, size), 255)
    gray_pixels = grayscale.load()

    center_x = size // 2
    center_y = size // 2
    radius = max(2, (size // 2) - 2)

    cycle = (phase % 28) / 28.0
    lunar_longitude = cycle * 2 * math.pi
    phase_angle = abs(lunar_longitude - math.pi)
    illumination = (math.cos(phase_angle) + 1) / 2

    # Waxing moon is lit on the right; waning moon is lit on the left.
    sun_x = math.sin(phase_angle) * (1 if cycle < 0.5 else -1)
    sun_z = math.cos(phase_angle)

    # Major maria (dark plains) to make the disc read as "moon", not a flat icon.
    maria = [
        (-0.36, -0.22, 0.22, 0.10),
        (-0.13, 0.11, 0.20, 0.09),
        (0.15, -0.07, 0.16, 0.08),
        (0.31, 0.23, 0.12, 0.07),
        (0.43, -0.20, 0.10, 0.06),
    ]

    for py in range(center_y - radius, center_y + radius + 1):
        ny = (py - center_y) / radius
        ny_sq = ny * ny
        if ny_sq > 1:
            continue

        row_half_width = math.sqrt(1 - ny_sq)
        row_x_min = max(center_x - radius, int(math.ceil(center_x - row_half_width * radius)))
        row_x_max = min(center_x + radius, int(math.floor(center_x + row_half_width * radius)))

        for px in range(row_x_min, row_x_max + 1):
            nx = (px - center_x) / radius
            nz_sq = 1 - nx * nx - ny_sq
            if nz_sq < 0:
                continue
            nz = math.sqrt(nz_sq)

            dot = nx * sun_x + nz * sun_z

            if dot <= 0:
                # Avoid heavy solid-black fill to reduce thermal print banding.
                if illumination < 0.08:
                    intensity = 62 + int(16 * nz)
                else:
                    intensity = 74 + int(14 * nz)
            else:
                # Lambertian lighting with mild limb darkening.
                diffuse = dot ** 0.82
                limb = 0.66 + 0.34 * nz
                intensity = 220 + int(35 * diffuse * limb)

                # Keep near-new moon cleaner with less surface noise.
                if illumination >= 0.08:
                    # Apply deterministic surface albedo features (maria/highlands).
                    albedo = 1.0
                    for maria_x, maria_y, sigma, depth in maria:
                        dx = nx - maria_x
                        dy = ny - maria_y
                        albedo -= depth * math.exp(-(dx * dx + dy * dy) / (2 * sigma * sigma))
                    highlands = 0.02 * math.exp(-(((nx + 0.20) ** 2) + ((ny - 0.34) ** 2)) / (2 * 0.11 * 0.11))
                    albedo = max(0.82, min(1.04, albedo + highlands))
                    intensity = int(intensity * albedo)

            gray_pixels[px, py] = max(0, min(255, intensity))

    # Ordered dithering creates stable grain and fewer dense black streaks.
    image = Image.new("1", (size, size), 1)
    pixels = image.load()
    bayer_8x8 = [
        [0, 48, 12, 60, 3, 51, 15, 63],
        [32, 16, 44, 28, 35, 19, 47, 31],
        [8, 56, 4, 52, 11, 59, 7, 55],
        [40, 24, 36, 20, 43, 27, 39, 23],
        [2, 50, 14, 62, 1, 49, 13, 61],
        [34, 18, 46, 30, 33, 17, 45, 29],
        [10, 58, 6, 54, 9, 57, 5, 53],
        [42, 26, 38, 22, 41, 25, 37, 21],
    ]
    for py in range(size):
        for px in range(size):
            level = gray_pixels[px, py]
            threshold = int(((bayer_8x8[py % 8][px % 8] + 0.5) / 64.0) * 255)
            pixels[px, py] = 1 if level >= threshold else 0

    draw = ImageDraw.Draw(image)
    draw.ellipse(
        [center_x - radius - 1, center_y - radius - 1, center_x + radius + 1, center_y + radius + 1],
        outline=0,
        width=2,
    )
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
    height = 220  # Fixed height with reserved label area to prevent overlap
    image = Image.new("1", (width, height), 1)
    draw = ImageDraw.Draw(image)
    
    font = fonts.get("regular")
    font_caption = fonts.get("caption")

    x = 0
    y = 0

    # Draw title and calculate chart/label layout with explicit separation.
    title_height = 12
    if font:
        draw.text((x, y), "SUN", font=font, fill=0)
        title_bbox = font.getbbox("SUN")
        title_height = max(10, title_bbox[3] - title_bbox[1])

    chart_top = y + title_height + 8
    label_value_y = height - 54
    label_caption_y = label_value_y + 20
    chart_bottom = label_value_y - 22
    horizon_y = chart_top + (chart_bottom - chart_top) // 2

    # Find min/max altitude
    altitudes = [alt for _, alt in sun_path]
    min_alt = min(altitudes) if altitudes else -90
    max_alt = max(altitudes) if altitudes else 90

    alt_range = max(max_alt - min_alt, 10)
    alt_min = min_alt
    alt_max = max_alt

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

        curve_y_pos = chart_top + int((1.0 - normalized_alt) * (chart_bottom - chart_top))
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
                if i % 3 != 1:
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
        draw.text((x, label_value_y), sunrise_time, font=font, fill=0)
        if font_caption:
            draw.text((x, label_caption_y), "Sunrise", font=font_caption, fill=0)

        text_bbox = font.getbbox(sunset_time)
        text_width = text_bbox[2] - text_bbox[0]
        sunset_text_x = x + width - text_width
        draw.text((sunset_text_x, label_value_y), sunset_time, font=font, fill=0)
        if font_caption:
            caption_bbox = font_caption.getbbox("Sunset")
            caption_width = caption_bbox[2] - caption_bbox[0]
            draw.text((x + width - caption_width, label_caption_y), "Sunset", font=font_caption, fill=0)

        if day_length:
            text_bbox = font.getbbox(day_length)
            text_width = text_bbox[2] - text_bbox[0]
            duration_x = x + (width - text_width) // 2
            draw.text((duration_x, label_value_y), day_length, font=font, fill=0)
            if font_caption:
                caption_bbox = font_caption.getbbox("Day Length")
                caption_width = caption_bbox[2] - caption_bbox[0]
                caption_x = x + (width - caption_width) // 2
                draw.text((caption_x, label_caption_y), "Day Length", font=font_caption, fill=0)

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
    moon_image = draw_moon_phase_image(data['moon_phase_val'], size=80)
    # Center moon image
    # To center it, we can create a full-width image and paste the moon in the center
    # OR rely on printer to center it (printer_serial does center images)
    printer.print_image(moon_image)
    
    # Moon data text
    printer.print_bold(data['moon_phase'].upper())
    printer.print_caption(f"Day {data['moon_phase_val']:.0f} of 28")
