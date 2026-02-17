import os
import requests
from datetime import datetime
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw

import app.config
from app.drivers.printer_mock import PrinterDriver
from app.module_registry import register_module


def get_weather_condition(code: int) -> str:
    """Maps WMO Weather Codes to text per official WMO interpretation codes."""
    if code == 0:
        return "Clear"
    if code == 1:
        return "Mainly Clear"
    if code == 2:
        return "Partly Cloudy"
    if code == 3:
        return "Overcast"
    if code in [45, 48]:
        return "Fog"
    if code in [51, 53, 55]:
        return "Drizzle"
    if code in [56, 57]:
        return "Freezing Drizzle"
    if code in [61, 63, 65]:
        return "Rain"
    if code in [66, 67]:
        return "Freezing Rain"
    if code in [71, 73, 75]:
        return "Snow"
    if code == 77:
        return "Snow Grains"
    if code in [80, 81, 82]:
        return "Rain Showers"
    if code in [85, 86]:
        return "Snow Showers"
    if code == 95:
        return "Thunderstorm"
    if code in [96, 99]:
        return "Thunderstorm Hail"
    return "Unknown"


def get_weather(config: Optional[Dict[str, Any]] = None):
    """Fetches weather from Open-Meteo API."""
    if config:
        # Support new nested location object
        location = config.get("location", {})
        latitude = (
            location.get("latitude")
            or config.get("latitude")
            or app.config.settings.latitude
        )
        longitude = (
            location.get("longitude")
            or config.get("longitude")
            or app.config.settings.longitude
        )
        timezone = (
            location.get("timezone")
            or config.get("timezone")
            or app.config.settings.timezone
        )
        city_name = (
            location.get("city_name")
            or config.get("city_name")
            or app.config.settings.city_name
        )
    else:
        latitude = app.config.settings.latitude
        longitude = app.config.settings.longitude
        timezone = app.config.settings.timezone
        city_name = app.config.settings.city_name

    empty_forecast = [
        {
            "day": "--",
            "high": "--",
            "low": "--",
            "condition": "Unknown",
            "icon": "cloud",
        }
        for _ in range(7)
    ]
    empty_hourly = []

    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current_weather": "true",
            "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "hourly": "weathercode,temperature_2m,precipitation_probability",
            "timezone": timezone,
            "temperature_unit": "fahrenheit",
            "forecast_days": 8,
            "forecast_hours": 24,
        }

        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()

        current = data.get("current_weather", {})
        daily = data.get("daily", {})
        hourly = data.get("hourly", {})

        forecast = []
        daily_times = daily.get("time", [])
        daily_max = daily.get("temperature_2m_max", [])
        daily_min = daily.get("temperature_2m_min", [])
        daily_weathercode = daily.get("weathercode", [])
        daily_precip_prob = daily.get("precipitation_probability_max", [])

        today = datetime.now().date()

        for i in range(min(len(daily_times), 7)):
            try:
                dt = datetime.strptime(daily_times[i], "%Y-%m-%d")
                date_obj = dt.date()
                weather_code = daily_weathercode[i] if i < len(daily_weathercode) else 0
                condition = get_weather_condition(weather_code)
                high = int(daily_max[i]) if i < len(daily_max) else None
                low = int(daily_min[i]) if i < len(daily_min) else None
                precip_prob = (
                    int(daily_precip_prob[i])
                    if i < len(daily_precip_prob) and daily_precip_prob[i] is not None
                    else None
                )

                if date_obj == today:
                    day_label = "Today"
                    date_label = f"{dt.month}/{dt.day}"
                else:
                    day_label = dt.strftime("%a")
                    date_label = f"{dt.month}/{dt.day}"

                forecast.append(
                    {
                        "day": day_label,
                        "date": date_label,
                        "high": high,
                        "low": low,
                        "condition": condition,
                        "precipitation": precip_prob,
                    }
                )
            except (ValueError, IndexError, TypeError):
                continue

        today_high = int(daily_max[0]) if daily_max else None
        today_low = int(daily_min[0]) if daily_min else None

        hourly_forecast = []
        current_time = datetime.now()
        current_hour = current_time.replace(minute=0, second=0, microsecond=0)

        for i in range(len(hourly.get("time", []))):
            time_str = hourly["time"][i]
            time_str_clean = time_str.split("+")[0].split("Z")[0]

            try:
                if len(time_str_clean) == 16:
                    dt = datetime.strptime(time_str_clean, "%Y-%m-%dT%H:%M")
                elif len(time_str_clean) >= 19:
                    dt = datetime.strptime(time_str_clean[:19], "%Y-%m-%dT%H:%M:%S")
                else:
                    continue
            except Exception:
                continue

            if dt < current_hour:
                continue

            weather_code = hourly["weathercode"][i] if "weathercode" in hourly else 0
            condition = get_weather_condition(weather_code)
            temp = int(hourly["temperature_2m"][i]) if "temperature_2m" in hourly else 0
            hourly_precip_prob = hourly.get("precipitation_probability", [])
            precip_prob = (
                int(hourly_precip_prob[i])
                if i < len(hourly_precip_prob) and hourly_precip_prob[i] is not None
                else None
            )

            current_hour_dt = datetime.now().replace(minute=0, second=0, microsecond=0)
            if dt == current_hour_dt:
                time_display = "Now"
            else:
                time_display = dt.strftime("%I %p")
                if time_display.startswith("0"):
                    time_display = time_display[1:]

            hourly_forecast.append(
                {
                    "time": time_display,
                    "hour": dt.strftime("%H"),
                    "temperature": temp,
                    "condition": condition,
                    "precipitation": precip_prob,
                }
            )

            if len(hourly_forecast) >= 24:
                break

        return {
            "current": int(current.get("temperature", 0)),
            "condition": get_weather_condition(current.get("weathercode", 0)),
            "high": today_high,
            "low": today_low,
            "city": city_name,
            "forecast": forecast,
            "hourly_forecast": hourly_forecast,
        }

    except Exception:
        return {
            "current": "--",
            "condition": "Unavailable",
            "high": "--",
            "low": "--",
            "city": city_name,
            "forecast": empty_forecast,
            "hourly_forecast": empty_hourly,
        }


def _get_icon_type(condition: str) -> str:
    """Map weather condition to icon type."""
    condition_lower = condition.lower()
    if (
        "thunderstorm" in condition_lower
        or "thunder" in condition_lower
        or "lightning" in condition_lower
    ):
        return "storm"
    elif "snow" in condition_lower:
        return "snowflake"
    elif (
        "rain" in condition_lower
        or "drizzle" in condition_lower
        or "showers" in condition_lower
    ):
        return "rain"
    elif condition_lower == "clear":
        return "sun"
    elif condition_lower in ["mainly clear", "partly cloudy"]:
        return "cloud-sun"
    elif condition_lower == "overcast":
        return "cloud"
    elif condition_lower == "fog" or "mist" in condition_lower:
        return "cloud-fog"
    else:
        return "cloud"


def draw_icon_on_image(draw: ImageDraw.Draw, x: int, y: int, icon_type: str, size: int):
    """Draw a weather icon onto a PIL ImageDraw context."""
    icon_aliases = {
        "clear": "sun",
        "rain": "cloud-rain",
        "snow": "cloud-snow",
        "snowflake": "snowflake",
        "storm": "cloud-lightning",
        "cloud-fog": "cloud-fog",
        "fog": "cloud-fog",
        "mist": "cloud-fog",
        "cloud-sun": "cloud-sun",
        "cloud": "cloud",
        "sun": "sun",
    }

    file_name = icon_aliases.get(icon_type.lower(), icon_type.lower())

    # Path logic to find icons folder
    # app/modules/weather.py -> app/modules -> app -> project_root
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(app_dir)
    icon_path = os.path.join(project_root, "icons", "regular", f"{file_name}.png")

    if os.path.exists(icon_path):
        try:
            icon_img = Image.open(icon_path).convert("RGBA")
            if icon_img.size != (size, size):
                icon_img = icon_img.resize((size, size), Image.NEAREST)

            # Flatten alpha then threshold to stable 1-bit output.
            bg = Image.new("RGBA", icon_img.size, (255, 255, 255, 255))
            bg.alpha_composite(icon_img)
            icon_mono = bg.convert("L").point(
                lambda value: 0 if value < 160 else 255, mode="1"
            )

            width, height = icon_mono.size
            pixels = icon_mono.load()

            # Center based on drawn pixels (not source canvas) so spacing above/below looks even.
            left = width
            top = height
            right = -1
            bottom = -1
            for py in range(height):
                for px in range(width):
                    if pixels[px, py] == 0:
                        left = min(left, px)
                        top = min(top, py)
                        right = max(right, px)
                        bottom = max(bottom, py)

            if right == -1:
                return

            glyph_w = (right - left) + 1
            glyph_h = (bottom - top) + 1
            offset_x = ((size - glyph_w) // 2) - left
            offset_y = ((size - glyph_h) // 2) - top

            for py in range(height):
                for px in range(width):
                    if pixels[px, py] == 0:
                        draw_x = x + px + offset_x
                        draw_y = y + py + offset_y
                        if x <= draw_x < (x + size) and y <= draw_y < (y + size):
                            draw.point((draw_x, draw_y), fill=0)
        except Exception:
            pass


def _draw_centered_text(
    draw: ImageDraw.Draw, text: str, center_x: int, y: int, font: Any
) -> int:
    """Draw text centered on x with a top-aligned y and return text height."""
    bbox = font.getbbox(text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    text_x = int(round(center_x - (text_w / 2) - bbox[0]))
    text_y = y - bbox[1]
    draw.text((text_x, text_y), text, font=font, fill=0)
    return text_h


def _draw_left_text(
    draw: ImageDraw.Draw, text: str, x: int, y: int, font: Any
) -> int:
    """Draw text left-aligned with a top-aligned y and return text height."""
    bbox = font.getbbox(text)
    text_h = bbox[3] - bbox[1]
    text_x = x - bbox[0]
    text_y = y - bbox[1]
    draw.text((text_x, text_y), text, font=font, fill=0)
    return text_h


def _format_temperature(value: Any, include_unit: bool = False) -> str:
    """Format temperatures using ASCII-only output for thermal printer reliability."""
    if value in (None, "", "--"):
        return "--"

    try:
        temp_int = int(round(float(value)))
    except (TypeError, ValueError):
        return str(value)

    return f"{temp_int}F" if include_unit else f"{temp_int}"


def draw_current_conditions_panel(
    weather: Dict[str, Any], total_width: int, fonts: Dict[str, Any]
) -> Image.Image:
    """Draw current conditions with centered date/location above a full-width box."""
    if total_width <= 0:
        return None

    font_caption = fonts.get("regular_sm") or fonts.get("regular")
    font_body = fonts.get("regular") or font_caption
    font_sub = fonts.get("semibold") or fonts.get("bold") or font_body
    font_temp = fonts.get("bold_lg") or fonts.get("bold") or font_body
    if not all([font_caption, font_body, font_sub, font_temp]):
        return None

    city = str(weather.get("city") or "LOCATION").upper()
    section_title = "CURRENT WEATHER"
    condition = str(weather.get("condition") or "Unavailable")
    temperature = _format_temperature(weather.get("current"), include_unit=True)
    high = _format_temperature(weather.get("high"), include_unit=True)
    low = _format_temperature(weather.get("low"), include_unit=True)
    stats_line = f"H {high}   L {low}"
    date_line = datetime.now().strftime("%a, %b %d, %Y")
    icon_type = _get_icon_type(condition)

    date_h = font_caption.getbbox(date_line)[3] - font_caption.getbbox(date_line)[1]
    city_h = font_sub.getbbox(city)[3] - font_sub.getbbox(city)[1]
    section_h = font_sub.getbbox(section_title)[3] - font_sub.getbbox(section_title)[1]

    outside_top = 12
    outside_gap = 4
    gap_after_city = 24
    gap_after_section = 8
    box_height = 108
    panel_bottom_padding = 2
    panel_height = (
        outside_top
        + date_h
        + outside_gap
        + city_h
        + gap_after_city
        + section_h
        + gap_after_section
        + box_height
        + panel_bottom_padding
    )
    panel = Image.new("1", (total_width, panel_height), 1)
    draw = ImageDraw.Draw(panel)

    # Date + location + section label above the box.
    date_y = outside_top
    city_y = date_y + date_h + outside_gap
    section_y = city_y + city_h + gap_after_city
    _draw_centered_text(draw, date_line, total_width // 2, date_y, font_caption)
    _draw_centered_text(draw, city, total_width // 2, city_y, font_sub)
    _draw_left_text(draw, section_title, 2, section_y, font_sub)

    # Match grid footprint width (same visual left/right inset as 12-hour and 5-day grids).
    x0 = 2
    y0 = section_y + section_h + gap_after_section
    x1 = total_width - 4
    y1 = y0 + box_height - 1
    if x1 <= x0 or y1 <= y0:
        return None

    draw.rectangle([(x0, y0), (x1, y1)], outline=0, width=1)
    split_x = x0 + int((x1 - x0) * 0.45)
    draw.line([(split_x, y0), (split_x, y1)], fill=0, width=1)

    icon_size = 52
    icon_x = x0 + ((split_x - x0) - icon_size) // 2
    icon_y = y0 + ((y1 - y0) - icon_size) // 2 - 1
    draw_icon_on_image(draw, icon_x, icon_y, icon_type, icon_size)

    # Right-side text stack is vertically centered within the middle cell.
    gap_after_temp = 5
    gap_after_condition = 3
    temp_h = font_temp.getbbox(temperature)[3] - font_temp.getbbox(temperature)[1]
    cond_h = font_body.getbbox(condition)[3] - font_body.getbbox(condition)[1]
    stats_h = font_caption.getbbox(stats_line)[3] - font_caption.getbbox(stats_line)[1]
    text_block_h = temp_h + gap_after_temp + cond_h + gap_after_condition + stats_h

    text_cell_top = y0
    text_cell_bottom = y1
    text_start_y = text_cell_top + max((text_cell_bottom - text_cell_top - text_block_h) // 2, 0)
    text_x = split_x + 10

    current_y = text_start_y
    current_y += _draw_left_text(draw, temperature, text_x, current_y, font_temp)
    current_y += gap_after_temp
    current_y += _draw_left_text(draw, condition, text_x, current_y, font_body)
    current_y += gap_after_condition
    _draw_left_text(draw, stats_line, text_x, current_y, font_caption)

    return panel


def draw_weather_forecast_image(
    forecast: list, total_width: int, fonts: Dict[str, Any]
) -> Image.Image:
    """Draw a compact daily forecast image optimized for 58mm receipts."""
    if not forecast:
        return None

    max_days = 5 if total_width <= 384 else 7
    visible_forecast = forecast[:max_days]
    num_days = len(visible_forecast)
    if num_days == 0:
        return None

    side_padding = 2
    content_width = max(total_width - (side_padding * 2), num_days)
    col_width = max(content_width // num_days, 1)
    grid_width = col_width * num_days
    grid_left = (total_width - grid_width) // 2
    icon_size = 20
    divider_width = 1

    font_sm = fonts.get("regular_sm")
    font_md = fonts.get("regular")
    font_lg = fonts.get("bold")
    low_font = font_sm or font_md

    sample_day = "Today"
    sample_date = "12/31"
    sample_high = "100"
    sample_low = "-10"
    sample_precip = "100%"
    element_spacing = 7
    precip_spacing = 5
    icon_vertical_nudge = 2
    top_padding = 6
    bottom_padding = 12

    day_text_h = (
        (font_sm.getbbox(sample_day)[3] - font_sm.getbbox(sample_day)[1]) if font_sm else 10
    )
    date_text_h = (
        (font_sm.getbbox(sample_date)[3] - font_sm.getbbox(sample_date)[1]) if font_sm else 10
    )
    high_text_h = (
        (font_lg.getbbox(sample_high)[3] - font_lg.getbbox(sample_high)[1]) if font_lg else 16
    )
    low_text_h = (
        (low_font.getbbox(sample_low)[3] - low_font.getbbox(sample_low)[1]) if low_font else 14
    )
    precip_text_h = (
        (font_sm.getbbox(sample_precip)[3] - font_sm.getbbox(sample_precip)[1]) if font_sm else 10
    )

    # Fixed row anchors keep each cell aligned, regardless of glyph-specific descenders.
    day_y = top_padding
    date_y = day_y + day_text_h + 2
    high_y = date_y + date_text_h + element_spacing
    low_y = high_y + high_text_h + element_spacing
    icon_y = low_y + low_text_h + element_spacing + icon_vertical_nudge
    precip_y = icon_y + icon_size + precip_spacing

    day_height = precip_y + precip_text_h + bottom_padding

    image = Image.new("1", (total_width, day_height), 1)
    draw = ImageDraw.Draw(image)

    border_left = grid_left
    border_right = grid_left + grid_width - 1
    draw.rectangle([(border_left, 0), (border_right, day_height - 1)], outline=0, width=1)

    for i, day_data in enumerate(visible_forecast):
        col_x = grid_left + (i * col_width)
        col_center = col_x + col_width // 2
        col_right = col_x + col_width

        day_label = day_data.get("day", "--")
        date_label = day_data.get("date", "")

        if font_sm:
            _draw_centered_text(draw, day_label, col_center, day_y, font_sm)
            if date_label:
                _draw_centered_text(draw, date_label, col_center, date_y, font_sm)

        high = day_data.get("high", "--")
        high_str = _format_temperature(high)
        if font_lg:
            _draw_centered_text(draw, high_str, col_center, high_y, font_lg)

        low = day_data.get("low", "--")
        low_str = _format_temperature(low)
        if low_font:
            _draw_centered_text(draw, low_str, col_center, low_y, low_font)

        icon_x = col_center - icon_size // 2
        icon_type = _get_icon_type(day_data.get("condition", ""))
        draw_icon_on_image(draw, icon_x, icon_y, icon_type, icon_size)

        precip = day_data.get("precipitation")
        precip_value = precip if precip is not None else 0
        if font_sm:
            _draw_centered_text(draw, f"{precip_value}%", col_center, precip_y, font_sm)

        if i < num_days - 1:
            draw.line(
                [
                    (col_right - divider_width // 2, 0),
                    (col_right - divider_width // 2, day_height - 1),
                ],
                fill=0,
                width=divider_width,
            )

    return image


def draw_hourly_forecast_image(
    hourly_forecast: list, total_width: int, fonts: Dict[str, Any]
) -> Image.Image:
    """Draw a compact 12-hour forecast image."""
    if not hourly_forecast:
        return None

    visible_hours = hourly_forecast[:12]
    if not visible_hours:
        return None

    hours_per_row = 3
    num_rows = (len(visible_hours) + hours_per_row - 1) // hours_per_row
    hour_spacing = 0
    side_padding = 2
    available_width = max(total_width - (side_padding * 2), hours_per_row)
    col_width = max(
        (available_width - ((hours_per_row - 1) * hour_spacing)) // hours_per_row, 1
    )
    grid_width = (hours_per_row * col_width) + ((hours_per_row - 1) * hour_spacing)
    icon_size = 20
    top_padding = 6
    between_blocks = 6
    bottom_padding = 12
    row_spacing = 0
    icon_vertical_nudge = 2

    if num_rows == 0:
        return None

    font_sm = fonts.get("regular_sm")
    font_md = fonts.get("regular")

    sample_time = "12 PM"
    sample_temp = "100"
    sample_precip = "100%"
    time_height = (
        (font_sm.getbbox(sample_time)[3] - font_sm.getbbox(sample_time)[1]) if font_sm else 10
    )
    temp_height = (
        (font_md.getbbox(sample_temp)[3] - font_md.getbbox(sample_temp)[1]) if font_md else 12
    )
    precip_height = (
        (font_sm.getbbox(sample_precip)[3] - font_sm.getbbox(sample_precip)[1]) if font_sm else 10
    )
    entry_height = (
        top_padding
        + time_height
        + between_blocks
        + icon_size
        + between_blocks
        + temp_height
        + between_blocks
        + precip_height
        + bottom_padding
    )
    total_height = (num_rows * entry_height) + ((num_rows - 1) * row_spacing)

    image = Image.new("1", (total_width, total_height), 1)
    draw = ImageDraw.Draw(image)

    left_margin = (total_width - grid_width) // 2
    actual_col_positions = []
    for col in range(hours_per_row):
        col_x = col * (col_width + hour_spacing) + left_margin
        actual_col_positions.append(col_x)

    leftmost_x = actual_col_positions[0]
    rightmost_x = actual_col_positions[-1] + col_width

    draw.rectangle([(leftmost_x, 0), (rightmost_x - 1, total_height - 1)], outline=0, width=1)

    for row in range(1, num_rows):
        line_y = row * (entry_height + row_spacing)
        draw.line([(leftmost_x, line_y), (rightmost_x - 1, line_y)], fill=0, width=1)

    for col in range(1, hours_per_row):
        line_x = actual_col_positions[col]
        draw.line([(line_x, 0), (line_x, total_height - 1)], fill=0, width=1)

    for row in range(num_rows):
        row_y = row * (entry_height + row_spacing)
        start_idx = row * hours_per_row
        end_idx = min(start_idx + hours_per_row, len(visible_hours))

        # Fixed row anchors avoid per-value vertical drift.
        time_y = row_y + top_padding
        icon_y = time_y + time_height + between_blocks + icon_vertical_nudge
        temp_y = icon_y + icon_size + between_blocks
        precip_y = temp_y + temp_height + between_blocks

        for col in range(start_idx, end_idx):
            hour_data = visible_hours[col]
            col_idx = col - start_idx
            col_x = col_idx * (col_width + hour_spacing) + left_margin
            col_center = col_x + col_width // 2

            time_str = hour_data.get("time", "--")
            if font_sm:
                _draw_centered_text(draw, time_str, col_center, time_y, font_sm)

            icon_x = col_center - icon_size // 2
            icon_type = _get_icon_type(hour_data.get("condition", ""))
            draw_icon_on_image(draw, icon_x, icon_y, icon_type, icon_size)

            temp = hour_data.get("temperature", "--")
            temp_str = _format_temperature(temp)
            if font_md:
                _draw_centered_text(draw, temp_str, col_center, temp_y, font_md)

            precip = hour_data.get("precipitation")
            precip_value = precip if precip is not None else 0
            if font_sm:
                precip_str = f"{precip_value}%"
                _draw_centered_text(draw, precip_str, col_center, precip_y, font_sm)

    return image


@register_module(
    type_id="weather",
    label="Weather Forecast",
    description="Current conditions, 24-hour, and 7-day forecast",
    icon="cloud-sun",
    offline=False,
    category="content",
    config_schema={
        "type": "object",
        "properties": {
            "location": {
                "type": "object",
                "title": "Location",
                "properties": {
                    "city_name": {"type": "string"},
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                    "timezone": {"type": "string"},
                    "state": {"type": "string"},
                    "zipcode": {"type": "string"},
                },
                "required": ["city_name", "latitude", "longitude"],
            }
        },
    },
    ui_schema={"location": {"ui:widget": "location-search"}},
)
def format_weather_receipt(
    printer: PrinterDriver, config: Dict[str, Any] = None, module_name: str = None
):
    """Prints weather with current conditions plus compact hourly/daily forecasts."""
    weather = get_weather(config)

    # Header
    printer.print_header(module_name or "WEATHER", icon="cloud-sun")

    printer_width = getattr(
        printer,
        "_get_content_width",
        lambda: getattr(printer, "PRINTER_WIDTH_DOTS", 384),
    )()

    # Get fonts from printer for image generation
    # Note: Accessing internal _get_font is acceptable for system fonts
    fonts = {
        "regular_sm": getattr(printer, "_get_font", lambda s: None)("regular_sm"),
        "regular": getattr(printer, "_get_font", lambda s: None)("regular"),
        "bold": getattr(printer, "_get_font", lambda s: None)("bold"),
        "bold_lg": getattr(printer, "_get_font", lambda s: None)("bold_lg"),
        "semibold": getattr(printer, "_get_font", lambda s: None)("semibold"),
    }

    panel_image = draw_current_conditions_panel(weather, printer_width, fonts)
    if panel_image:
        printer.print_image(panel_image)
    else:
        # Fallback to text-only output if panel render fails.
        printer.print_subheader((weather.get("city") or "LOCATION").upper())
        printer.print_text(_format_temperature(weather.get("current"), include_unit=True), "bold_lg")
        printer.print_body(weather.get("condition") or "Unavailable")
        printer.print_body(
            f"High {_format_temperature(weather.get('high'), include_unit=True)} | "
            f"Low {_format_temperature(weather.get('low'), include_unit=True)}"
        )
    printer.feed(1)

    # 12-Hour Forecast
    hourly_forecast = weather.get("hourly_forecast", [])
    if hourly_forecast:
        printer.print_subheader("12-HOUR FORECAST")

        # Turn generic forecast data into an image
        hourly_image = draw_hourly_forecast_image(hourly_forecast, printer_width, fonts)
        if hourly_image:
            printer.print_image(hourly_image)

        printer.feed(1)

    # 5-Day Forecast
    forecast = weather.get("forecast", [])
    if forecast:
        printer.print_subheader("5-DAY FORECAST")

        # Turn generic forecast data into an image
        daily_image = draw_weather_forecast_image(forecast, printer_width, fonts)
        if daily_image:
            printer.print_image(daily_image)

        printer.feed(1)
