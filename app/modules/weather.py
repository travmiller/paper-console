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


def get_weather_condition_openweather(code: int) -> str:
    """Maps OpenWeather condition codes to text."""
    if code in [800]:
        return "Clear"
    if code in [801, 802]:
        return "Cloudy"
    if code in [803, 804]:
        return "Overcast"
    if code in [300, 301, 302, 310, 311, 312, 313, 314, 321, 500, 501, 502, 503, 504, 520, 521, 522, 531]:
        return "Rain"
    if code in [200, 201, 202, 210, 211, 212, 221, 230, 231, 232]:
        return "Storm"
    if code in [511, 600, 601, 602, 611, 612, 613, 615, 616, 620, 621, 622]:
        return "Snow"
    if code in [701, 711, 721, 731, 741, 751, 761, 762, 771, 781]:
        return "Fog"
    return "Unknown"


def get_weather(config: Optional[Dict[str, Any]] = None):
    """Fetches weather from OpenWeather API or Open-Meteo."""
    if config:
        # Support new nested location object
        location = config.get("location", {})
        latitude = location.get("latitude") or config.get("latitude") or app.config.settings.latitude
        longitude = location.get("longitude") or config.get("longitude") or app.config.settings.longitude
        timezone = location.get("timezone") or config.get("timezone") or app.config.settings.timezone
        city_name = location.get("city_name") or config.get("city_name") or app.config.settings.city_name
        api_key = config.get("openweather_api_key")
    else:
        latitude = app.config.settings.latitude
        longitude = app.config.settings.longitude
        timezone = app.config.settings.timezone
        city_name = app.config.settings.city_name
        api_key = None

    empty_forecast = [{"day": "--", "high": "--", "low": "--", "condition": "Unknown", "icon": "cloud"} for _ in range(7)]
    empty_hourly = []

    if api_key:
        try:
            url = "https://api.openweathermap.org/data/2.5/weather"
            params = {
                "lat": latitude,
                "lon": longitude,
                "appid": api_key,
                "units": "imperial",
            }
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()

            if resp.status_code == 200:
                current_temp = int(data["main"]["temp"])
                condition_code = data["weather"][0]["id"]
                condition = get_weather_condition_openweather(condition_code)
                high = int(data["main"]["temp_max"])
                low = int(data["main"]["temp_min"])
                city = data.get("name", city_name)

                forecast = []
                try:
                    forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
                    forecast_resp = requests.get(forecast_url, params=params, timeout=10)
                    forecast_data = forecast_resp.json()
                    
                    if forecast_resp.status_code == 200:
                        today_key = datetime.now().strftime("%Y-%m-%d")
                        days_seen = {}
                        for item in forecast_data.get("list", []):
                            dt = datetime.fromtimestamp(item["dt"])
                            day_key = dt.strftime("%Y-%m-%d")
                            if day_key == today_key:
                                continue
                            if day_key not in days_seen:
                                days_seen[day_key] = {
                                    "day": dt.strftime("%a"),
                                    "high": int(item["main"]["temp_max"]),
                                    "low": int(item["main"]["temp_min"]),
                                    "condition": get_weather_condition_openweather(item["weather"][0]["id"]),
                                }
                            else:
                                days_seen[day_key]["high"] = max(days_seen[day_key]["high"], int(item["main"]["temp_max"]))
                                days_seen[day_key]["low"] = min(days_seen[day_key]["low"], int(item["main"]["temp_min"]))
                        forecast = list(days_seen.values())[:7]
                except Exception:
                    pass

                return {
                    "current": current_temp,
                    "condition": condition,
                    "high": high,
                    "low": low,
                    "city": city,
                    "forecast": forecast if forecast else empty_forecast,
                    "hourly_forecast": [],
                }
        except Exception:
            pass

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
                precip_prob = int(daily_precip_prob[i]) if i < len(daily_precip_prob) and daily_precip_prob[i] is not None else None
                
                if date_obj == today:
                    day_label = "Today"
                    date_label = f"{dt.month}/{dt.day}"
                else:
                    day_label = dt.strftime("%a")
                    date_label = f"{dt.month}/{dt.day}"
                
                forecast.append({
                    "day": day_label,
                    "date": date_label,
                    "high": high,
                    "low": low,
                    "condition": condition,
                    "precipitation": precip_prob,
                })
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
            precip_prob = int(hourly_precip_prob[i]) if i < len(hourly_precip_prob) and hourly_precip_prob[i] is not None else None
            
            current_hour_dt = datetime.now().replace(minute=0, second=0, microsecond=0)
            if dt == current_hour_dt:
                time_display = "Now"
            else:
                time_display = dt.strftime("%I %p")
                if time_display.startswith("0"):
                    time_display = time_display[1:]
            
            hourly_forecast.append({
                "time": time_display,
                "hour": dt.strftime("%H"),
                "temperature": temp,
                "condition": condition,
                "precipitation": precip_prob,
            })
            
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
    if "thunderstorm" in condition_lower or "thunder" in condition_lower or "lightning" in condition_lower:
        return "storm"
    elif "snow" in condition_lower:
        return "snowflake"
    elif "rain" in condition_lower or "drizzle" in condition_lower or "showers" in condition_lower:
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
            icon_img = Image.open(icon_path)
            if icon_img.size != (size, size):
                icon_img = icon_img.resize((size, size), Image.NEAREST)
            if icon_img.mode != "1":
                icon_img = icon_img.convert("1")
                
            width, height = icon_img.size
            pixels = icon_img.load()
            for py in range(height):
                for px in range(width):
                    if pixels[px, py] == 0:
                        draw.point((x + px, y + py), fill=0)
        except Exception:
            pass


def draw_weather_forecast_image(forecast: list, total_width: int, fonts: Dict[str, Any]) -> Image.Image:
    """Draw 7-day forecast as an image."""
    if not forecast:
        return None
        
    num_days = min(len(forecast), 7)
    col_width = total_width // num_days
    icon_size = 24
    day_height = 114
    divider_width = 1
    
    # Create white image
    image = Image.new("1", (total_width, day_height), 1)
    draw = ImageDraw.Draw(image)
    
    font_sm = fonts.get("regular_sm")
    font_md = fonts.get("regular")
    font_lg = fonts.get("bold")
    
    for i, day_data in enumerate(forecast[:7]):
        col_x = i * col_width
        col_center = col_x + col_width // 2
        col_right = col_x + col_width
        day_top = 0
        day_bottom = day_height
        
        # Data
        day_label = day_data.get("day", "--")
        date_label = day_data.get("date", "")
        precip = day_data.get("precipitation")
        precip_value = precip if precip is not None else 0
        
        element_spacing = 12
        current_y = day_top + 8
        
        # 1. High Temp
        high = day_data.get("high", "--")
        high_str = f"{high}°" if high != "--" else "--"
        if font_lg:
            bbox = font_lg.getbbox(high_str)
            text_w = bbox[2] - bbox[0]
            text_x = col_center - text_w // 2
            draw.text((text_x, current_y), high_str, font=font_lg, fill=0)
            current_y += (bbox[3] - bbox[1])
        else:
            current_y += 16
        current_y += element_spacing
        
        # 2. Low Temp
        low = day_data.get("low", "--")
        low_str = f"{low}°" if low != "--" else "--"
        if font_md:
            bbox = font_md.getbbox(low_str)
            text_w = bbox[2] - bbox[0]
            text_x = col_center - text_w // 2
            draw.text((text_x, current_y), low_str, font=font_md, fill=0)
            current_y += (bbox[3] - bbox[1])
        else:
            current_y += 14
        current_y += element_spacing
        
        # 3. Icon
        icon_x = col_center - icon_size // 2
        icon_type = _get_icon_type(day_data.get("condition", ""))
        draw_icon_on_image(draw, icon_x, current_y, icon_type, icon_size)
        current_y += icon_size + element_spacing
        
        # 4. Precipitation
        precip_str = f"{precip_value}%"
        if font_sm:
            bbox = font_sm.getbbox(precip_str)
            text_w = bbox[2] - bbox[0]
            text_x = col_center - text_w // 2
            draw.text((text_x, current_y), precip_str, font=font_sm, fill=0)
            current_y += (bbox[3] - bbox[1])
        else:
            current_y += 10
        current_y += element_spacing
        
        # 5. Day/Date
        if font_sm:
            day_bbox = font_sm.getbbox(day_label)
            day_text_w = day_bbox[2] - day_bbox[0]
            day_text_x = col_center - day_text_w // 2
            draw.text((day_text_x, current_y), day_label, font=font_sm, fill=0)
            
            if date_label:
                date_bbox = font_sm.getbbox(date_label)
                date_text_w = date_bbox[2] - date_bbox[0]
                date_text_x = col_center - date_text_w // 2
                date_y = current_y + (day_bbox[3] - day_bbox[1]) + 2
                draw.text((date_text_x, date_y), date_label, font=font_sm, fill=0)
        
        # Dividers
        if i < num_days - 1:
            draw.line([(col_right - divider_width // 2, day_top), (col_right - divider_width // 2, day_bottom)], fill=0, width=divider_width)
        if i == 0:
            draw.line([(col_x, day_top), (col_x, day_bottom)], fill=0, width=divider_width)
        if i == num_days - 1:
            draw.line([(col_right - divider_width // 2, day_top), (col_right - divider_width // 2, day_bottom)], fill=0, width=divider_width)
            
    return image


def draw_hourly_forecast_image(hourly_forecast: list, total_width: int, fonts: Dict[str, Any]) -> Image.Image:
    """Draw 24-hour forecast as an image."""
    if not hourly_forecast:
        return None
        
    hours_per_row = 4
    num_rows = (len(hourly_forecast) + hours_per_row - 1) // hours_per_row
    col_width = (total_width - 16 - (hours_per_row - 1) * 5) // hours_per_row
    
    hour_spacing = 5
    icon_size = 24
    entry_height = 86
    row_spacing = 10
    total_height = (num_rows * entry_height) + ((num_rows - 1) * row_spacing) if num_rows > 0 else 0
    
    if total_height == 0:
        return None
        
    image = Image.new("1", (total_width, total_height), 1)
    draw = ImageDraw.Draw(image)
    
    font_sm = fonts.get("regular_sm")
    font_md = fonts.get("regular")
    
    # Grid Logic
    left_margin = 8
    actual_col_positions = []
    for col in range(hours_per_row):
        col_x = col * (col_width + hour_spacing) + left_margin
        actual_col_positions.append(col_x)
        
    leftmost_x = actual_col_positions[0]
    rightmost_x = min(total_width - 8, actual_col_positions[-1] + col_width)
    
    # Horizontal grid lines
    for row in range(num_rows + 1):
        line_y = row * (entry_height + row_spacing)
        draw.line([(leftmost_x, line_y), (rightmost_x, line_y)], fill=0, width=1)
        
    # Vertical grid lines
    for col_x in actual_col_positions:
        draw.line([(col_x, 0), (col_x, total_height)], fill=0, width=1)
    draw.line([(rightmost_x, 0), (rightmost_x, total_height)], fill=0, width=1)
    
    # Content
    for row in range(num_rows):
        row_y = row * (entry_height + row_spacing) 
        start_idx = row * hours_per_row
        end_idx = min(start_idx + hours_per_row, len(hourly_forecast))
        
        for col in range(start_idx, end_idx):
            hour_data = hourly_forecast[col]
            col_idx = col - start_idx
            col_x = col_idx * (col_width + hour_spacing) + left_margin
            col_center = col_x + col_width // 2
            
            # Time
            time_str = hour_data.get("time", "--")
            time_y = row_y + 2
            if font_sm:
                bbox = font_sm.getbbox(time_str)
                text_w = bbox[2] - bbox[0]
                text_x = col_center - text_w // 2
                draw.text((text_x, time_y), time_str, font=font_sm, fill=0)
                time_height = bbox[3] - bbox[1]
            else:
                time_height = 10
                
            # Icon
            icon_y = time_y + time_height + 8
            icon_x = col_center - icon_size // 2
            icon_type = _get_icon_type(hour_data.get("condition", ""))
            draw_icon_on_image(draw, icon_x, icon_y, icon_type, icon_size)
            
            # Temp
            temp = hour_data.get("temperature", "--")
            temp_str = f"{temp}°" if temp != "--" else "--"
            temp_y = icon_y + icon_size + 8
            if font_md:
                bbox = font_md.getbbox(temp_str)
                text_w = bbox[2] - bbox[0]
                text_x = col_center - text_w // 2
                draw.text((text_x, temp_y), temp_str, font=font_md, fill=0)
                temp_height = bbox[3] - bbox[1]
            else:
                temp_height = 12
                
            # Precip
            precip = hour_data.get("precipitation")
            precip_value = precip if precip is not None else 0
            precip_str = f"{precip_value}%"
            precip_y = temp_y + temp_height + 8
            if font_sm:
                bbox = font_sm.getbbox(precip_str)
                text_w = bbox[2] - bbox[0]
                text_x = col_center - text_w // 2
                draw.text((text_x, precip_y), precip_str, font=font_sm, fill=0)

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
            "openweather_api_key": {
                "type": "string", 
                "title": "OpenWeather API Key (Optional)",
                "description": "Leave duplicate keys blank to use free Open-Meteo API"
            },
            "location": {
                "type": "object",
                "title": "Location",
                "properties": {
                    "city_name": {"type": "string"},
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                    "timezone": {"type": "string"},
                    "state": {"type": "string"},
                    "zipcode": {"type": "string"}
                },
                "required": ["city_name", "latitude", "longitude"]
            }
        },
    },
    ui_schema={
        "openweather_api_key": {"ui:widget": "password"},
        "location": {"ui:widget": "location-search"}
    },
)
def format_weather_receipt(
    printer: PrinterDriver, config: Dict[str, Any] = None, module_name: str = None
):
    """Prints the weather receipt with current conditions, 24-hour forecast, and 7-day forecast."""
    weather = get_weather(config)

    # Header
    printer.print_header(module_name or "WEATHER", icon="cloud-sun")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()

    # Location
    printer.print_subheader(weather['city'].upper())
    
    # Weather icon and current conditions (Text-based for now, simple icon below)
    icon_type = _get_icon_type(weather['condition'])
    
    # Generate generic icon image for current conditions
    icon_size = 64
    icon_image = Image.new("1", (icon_size, icon_size), 1)
    icon_draw = ImageDraw.Draw(icon_image)
    draw_icon_on_image(icon_draw, 0, 0, icon_type, icon_size)
    printer.print_image(icon_image)
    
    # Current temperature - big and bold
    printer.print_bold(f"{weather['current']}°F")
    printer.print_body(weather['condition'])
    
    # High/Low for today
    printer.print_body(f"High {weather['high']}°F  ·  Low {weather['low']}°F")
    printer.print_line()
    
    # Get fonts from printer for image generation
    # Note: Accessing internal _get_font is acceptable for system fonts
    fonts = {
        "regular_sm": getattr(printer, "_get_font", lambda s: None)("regular_sm"),
        "regular": getattr(printer, "_get_font", lambda s: None)("regular"),
        "bold": getattr(printer, "_get_font", lambda s: None)("bold"),
    }
    printer_width = getattr(printer, 'PRINTER_WIDTH_DOTS', 384)
    
    # 24-Hour Forecast
    hourly_forecast = weather.get('hourly_forecast', [])
    if hourly_forecast:
        printer.print_subheader("24-HOUR FORECAST")
        printer.print_line()
        
        # Turn generic forecast data into an image
        hourly_image = draw_hourly_forecast_image(hourly_forecast, printer_width, fonts)
        if hourly_image:
            printer.print_image(hourly_image)
            
        printer.print_line()
    
    # 7-Day Forecast
    forecast = weather.get('forecast', [])
    if forecast:
        printer.print_subheader("7-DAY FORECAST")
        printer.print_line()
        
        # Turn generic forecast data into an image
        daily_image = draw_weather_forecast_image(forecast, printer_width, fonts)
        if daily_image:
            printer.print_image(daily_image)
            
        printer.print_line()