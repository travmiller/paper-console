import requests
from datetime import datetime
from typing import Dict, Any, Optional
import app.config
from app.drivers.printer_mock import PrinterDriver


def get_weather_condition(code: int) -> str:
    """Maps WMO Weather Codes to text per official WMO interpretation codes.
    
    WMO Weather Code reference:
    0: Clear sky
    1, 2, 3: Mainly clear, partly cloudy, and overcast
    45, 48: Fog and depositing rime fog
    51, 53, 55: Drizzle: Light, moderate, and dense intensity
    56, 57: Freezing Drizzle: Light and dense intensity
    61, 63, 65: Rain: Slight, moderate and heavy intensity
    66, 67: Freezing Rain: Light and heavy intensity
    71, 73, 75: Snow fall: Slight, moderate, and heavy intensity
    77: Snow grains
    80, 81, 82: Rain showers: Slight, moderate, and violent
    85, 86: Snow showers slight and heavy
    95: Thunderstorm: Slight or moderate
    96, 99: Thunderstorm with slight and heavy hail
    """
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
    if code in [51, 53, 55]:  # Drizzle
        return "Drizzle"
    if code in [56, 57]:  # Freezing Drizzle
        return "Freezing Drizzle"
    if code in [61, 63, 65]:  # Rain
        return "Rain"
    if code in [66, 67]:  # Freezing Rain
        return "Freezing Rain"
    if code in [71, 73, 75]:  # Snow fall
        return "Snow"
    if code == 77:  # Snow grains
        return "Snow Grains"
    if code in [80, 81, 82]:  # Rain showers
        return "Rain Showers"
    if code in [85, 86]:  # Snow showers
        return "Snow Showers"
    if code == 95:  # Thunderstorm
        return "Thunderstorm"
    if code in [96, 99]:  # Thunderstorm with hail
        return "Thunderstorm Hail"
    return "Unknown"


def get_weather_condition_openweather(code: int) -> str:
    """Maps OpenWeather condition codes to text."""
    # See https://openweathermap.org/weather-conditions
    if code in [800]:
        return "Clear"
    if code in [801, 802]:
        return "Cloudy"
    if code in [803, 804]:
        return "Overcast"
    if code in [
        300,
        301,
        302,
        310,
        311,
        312,
        313,
        314,
        321,
        500,
        501,
        502,
        503,
        504,
        520,
        521,
        522,
        531,
    ]:
        return "Rain"
    if code in [200, 201, 202, 210, 211, 212, 221, 230, 231, 232]:
        return "Storm"
    if code in [511, 600, 601, 602, 611, 612, 613, 615, 616, 620, 621, 622]:
        return "Snow"
    if code in [701, 711, 721, 731, 741, 751, 761, 762, 771, 781]:
        return "Fog"
    return "Unknown"


def get_weather(config: Optional[Dict[str, Any]] = None):
    """
    Fetches weather from OpenWeather API (if API key provided) or Open-Meteo (free, no key).
    Uses module config location if provided, otherwise falls back to global settings.
    Returns current weather, 7-day forecast, and 24-hour forecast.
    """
    # Get location from config or fall back to global settings
    if config:
        latitude = config.get("latitude") or app.config.settings.latitude
        longitude = config.get("longitude") or app.config.settings.longitude
        timezone = config.get("timezone") or app.config.settings.timezone
        city_name = config.get("city_name") or app.config.settings.city_name
        api_key = config.get("openweather_api_key")
    else:
        latitude = app.config.settings.latitude
        longitude = app.config.settings.longitude
        timezone = app.config.settings.timezone
        city_name = app.config.settings.city_name
        api_key = None

    # Default forecast structure
    empty_forecast = [{"day": "--", "high": "--", "low": "--", "condition": "Unknown", "icon": "cloud"} for _ in range(7)]
    empty_hourly = []

    # If OpenWeather API key is provided, use OpenWeather API
    if api_key:
        try:
            # Current weather
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

                # Try to get forecast from OpenWeather 5-day/3-hour forecast
                forecast = []
                try:
                    forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
                    forecast_resp = requests.get(forecast_url, params=params, timeout=10)
                    forecast_data = forecast_resp.json()
                    
                    if forecast_resp.status_code == 200:
                        # Group by day and get daily highs/lows
                        # Skip today - get forecast starting from tomorrow
                        today_key = datetime.now().strftime("%Y-%m-%d")
                        days_seen = {}
                        for item in forecast_data.get("list", []):
                            dt = datetime.fromtimestamp(item["dt"])
                            day_key = dt.strftime("%Y-%m-%d")
                            # Skip today - we show it separately in current conditions
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
                        
                        # Get next 7 days (skip today)
                        forecast = list(days_seen.values())[:7]
                except Exception:
                    pass

                # For OpenWeather, we only get daily forecast from the API
                # We'll need to use Open-Meteo for hourly forecast
                return {
                    "current": current_temp,
                    "condition": condition,
                    "high": high,
                    "low": low,
                    "city": city,
                    "forecast": forecast if forecast else empty_forecast,
                    "hourly_forecast": [],  # OpenWeather doesn't provide hourly in free tier
                }
        except Exception:
            # Fall through to Open-Meteo if OpenWeather fails
            pass

    # Use Open-Meteo (free, no key required)
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        
        # Fetch both daily and hourly forecasts in a single request
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current_weather": "true",
            "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "hourly": "weathercode,temperature_2m,precipitation_probability",
            "timezone": timezone,
            "temperature_unit": "fahrenheit",
            "forecast_days": 8,  # Request 8 days so we get 7 after skipping today (index 0)
            "forecast_hours": 24,  # Request 24 hours for hourly forecast
        }
        
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()  # Raise exception for bad status codes
        data = resp.json()
        
        current = data.get("current_weather", {})
        daily = data.get("daily", {})
        hourly = data.get("hourly", {})
        
        # Build 7-day forecast (include today, then next 6 days)
        forecast = []
        daily_times = daily.get("time", [])
        daily_max = daily.get("temperature_2m_max", [])
        daily_min = daily.get("temperature_2m_min", [])
        daily_weathercode = daily.get("weathercode", [])
        daily_precip_prob = daily.get("precipitation_probability_max", [])
        
        # Get today's date for comparison
        today = datetime.now().date()
        
        # Start from index 0 to include today, then next 6 days (indices 0-6)
        for i in range(min(len(daily_times), 7)):
            try:
                # Parse ISO8601 date (format: "2022-07-01")
                date_str = daily_times[i]
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                date_obj = dt.date()
                
                # Get weather code (WMO code) - defaults to 0 (Clear sky) if missing
                weather_code = daily_weathercode[i] if i < len(daily_weathercode) else 0
                condition = get_weather_condition(weather_code)
                
                # Get temperatures (convert to int, handle missing data)
                high = int(daily_max[i]) if i < len(daily_max) else None
                low = int(daily_min[i]) if i < len(daily_min) else None
                
                # Get precipitation probability
                precip_prob = int(daily_precip_prob[i]) if i < len(daily_precip_prob) and daily_precip_prob[i] is not None else None
                
                # Format day label: "Today" for today, otherwise "Mon 1/19" format
                # Remove leading zeros from dates for cleaner display
                if date_obj == today:
                    day_label = "Today"
                    # Format date without leading zeros: "1/19" instead of "01/19"
                    month = str(dt.month)
                    day = str(dt.day)
                    date_label = f"{month}/{day}"
                else:
                    day_label = dt.strftime("%a")  # Day abbreviation (Mon, Tue, etc.)
                    # Format date without leading zeros: "1/20" instead of "01/20"
                    month = str(dt.month)
                    day = str(dt.day)
                    date_label = f"{month}/{day}"
                
                forecast.append({
                    "day": day_label,
                    "date": date_label,
                    "high": high,
                    "low": low,
                    "condition": condition,
                    "precipitation": precip_prob,
                })
            except (ValueError, IndexError, TypeError) as e:
                # Skip invalid entries but continue processing
                continue
        
        # Get today's high/low from index 0 (if available)
        today_high = int(daily_max[0]) if daily_max and len(daily_max) > 0 else None
        today_low = int(daily_min[0]) if daily_min and len(daily_min) > 0 else None
        
        # Build hourly forecast (next 24 hours)
        hourly_forecast = []
        
        # Get current time for filtering
        current_time = datetime.now()
        current_hour = current_time.replace(minute=0, second=0, microsecond=0)
        
        for i in range(len(hourly.get("time", []))):
            time_str = hourly["time"][i]
            # Parse ISO8601 time (format: "2022-07-01T00:00" or "2022-07-01T00:00:00")
            # Remove timezone suffix if present (e.g., "+00:00" or "Z")
            time_str_clean = time_str.split("+")[0].split("Z")[0]
            
            try:
                if len(time_str_clean) == 16:  # "2022-07-01T00:00"
                    dt = datetime.strptime(time_str_clean, "%Y-%m-%dT%H:%M")
                elif len(time_str_clean) >= 19:  # "2022-07-01T00:00:00"
                    dt = datetime.strptime(time_str_clean[:19], "%Y-%m-%dT%H:%M:%S")
                else:
                    continue
            except Exception:
                continue
            
            # Skip past hours (keep current hour and future hours)
            if dt < current_hour:
                continue
            
            weather_code = hourly["weathercode"][i] if "weathercode" in hourly else 0
            condition = get_weather_condition(weather_code)
            temp = int(hourly["temperature_2m"][i]) if "temperature_2m" in hourly else 0
            
            # Get precipitation probability
            hourly_precip_prob = hourly.get("precipitation_probability", [])
            precip_prob = int(hourly_precip_prob[i]) if i < len(hourly_precip_prob) and hourly_precip_prob[i] is not None else None
            
            # Format time for display
            # Show "Now" for current hour, otherwise 12-hour format with AM/PM
            current_hour_dt = datetime.now().replace(minute=0, second=0, microsecond=0)
            if dt == current_hour_dt:
                time_display = "Now"
            else:
                time_display = dt.strftime("%I %p")  # "11 AM", "2 PM" format
                if time_display.startswith("0"):
                    time_display = time_display[1:]  # Remove leading zero from hour
            
            hourly_forecast.append({
                "time": time_display,
                "hour": dt.strftime("%H"),
                "temperature": temp,
                "condition": condition,
                "precipitation": precip_prob,
            })
            
            # Limit to 24 hours
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

    except Exception as e:
        # Log error for debugging
        import logging
        try:
            logging.error(f"Weather API error: {e}")
        except:
            pass  # Ignore logging errors
        
        # Return error response with both forecast types
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
    """Map weather condition to icon type based on WMO weather codes.
    
    Maps to Phosphor PNG icons with improved specificity:
    - Clear (0) → sun
    - Mainly Clear (1) → cloud-sun
    - Partly Cloudy (2) → cloud-sun
    - Overcast (3) → cloud
    - Fog (45, 48) → cloud-fog
    - Drizzle/Freezing Drizzle/Rain/Freezing Rain/Rain Showers (51-82) → cloud-rain
    - Snow/Snow Grains/Snow Showers (71-86) → snowflake (more specific than cloud-snow)
    - Thunderstorm/Thunderstorm Hail (95-99) → cloud-lightning
    """
    condition_lower = condition.lower()
    
    # Thunderstorm (codes 95, 96, 99) - check FIRST to avoid false matches
    if "thunderstorm" in condition_lower or "thunder" in condition_lower or "lightning" in condition_lower:
        return "storm"  # Maps to cloud-lightning.png
    
    # Snow-related (codes 71, 73, 75, 77, 85, 86) - check before rain
    elif "snow" in condition_lower:
        return "snowflake"  # Maps to snowflake.png (more specific than cloud-snow)
    
    # Rain-related (codes 51-67, 80-82): Drizzle, Freezing Drizzle, Rain, Freezing Rain, Rain Showers
    elif "rain" in condition_lower or "drizzle" in condition_lower or "showers" in condition_lower:
        return "rain"  # Maps to cloud-rain.png
    
    # Clear sky (code 0)
    elif condition_lower == "clear":
        return "sun"  # Maps to sun.png
    
    # Mainly clear (code 1) or Partly cloudy (code 2)
    elif condition_lower == "mainly clear" or condition_lower == "partly cloudy":
        return "cloud-sun"  # Maps to cloud-sun.png
    
    # Overcast (code 3)
    elif condition_lower == "overcast":
        return "cloud"  # Maps to cloud.png
    
    # Fog (codes 45, 48)
    elif condition_lower == "fog" or "mist" in condition_lower:
        return "cloud-fog"  # Maps to cloud-fog.png
    
    # Default fallback
    else:
        return "cloud"  # Maps to cloud.png


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
    
    # Weather icon - large for current conditions
    icon_type = _get_icon_type(weather['condition'])
    printer.print_icon(icon_type, size=64)
    
    # Current temperature - big and bold
    printer.print_bold(f"{weather['current']}°F")
    printer.print_body(weather['condition'])
    
    # High/Low for today
    printer.print_body(f"High {weather['high']}°F  ·  Low {weather['low']}°F")
    printer.print_line()
    
    # 24-Hour Forecast
    hourly_forecast = weather.get('hourly_forecast', [])
    if hourly_forecast:
        printer.print_subheader("24-HOUR FORECAST")
        printer.print_line()
        
        # Print hourly forecast
        printer.print_hourly_forecast(hourly_forecast)
        printer.print_line()
    
    # 7-Day Forecast
    forecast = weather.get('forecast', [])
    if forecast:
        printer.print_subheader("7-DAY FORECAST")
        printer.print_line()
        
        # Print forecast as a visual row with icons
        printer.print_weather_forecast(forecast)
        printer.print_line()