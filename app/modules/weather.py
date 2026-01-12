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
    Returns current weather and 7-day forecast.
    """
    # Get location from config or fall back to global settings
    if config:
        latitude = config.get("latitude") or app.config.settings.latitude
        longitude = config.get("longitude") or app.config.settings.longitude
        timezone = config.get("timezone") or app.config.settings.timezone
        city_name = config.get("city_name") or app.config.settings.city_name
        api_key = config.get("openweather_api_key")
        forecast_type = config.get("forecast_type", "daily")  # "daily" or "hourly"
    else:
        latitude = app.config.settings.latitude
        longitude = app.config.settings.longitude
        timezone = app.config.settings.timezone
        city_name = app.config.settings.city_name
        api_key = None
        forecast_type = "daily"

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

                return {
                    "current": current_temp,
                    "condition": condition,
                    "high": high,
                    "low": low,
                    "city": city,
                    "forecast": forecast if forecast else empty_forecast,
                }
        except Exception:
            # Fall through to Open-Meteo if OpenWeather fails
            pass

    # Use Open-Meteo (free, no key required)
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        
        if forecast_type == "hourly":
            # Fetch hourly forecast (next 24 hours)
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "current_weather": "true",
                "hourly": "weathercode,temperature_2m",
                "timezone": timezone,
                "temperature_unit": "fahrenheit",
                "forecast_hours": 24,
            }
            
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            
            current = data["current_weather"]
            hourly = data["hourly"]
            
            # Build hourly forecast (next 24 hours)
            # According to Open-Meteo docs, forecast_hours=24 returns 24 hours from current hour
            hourly_forecast = []
            
            # Get current time for filtering (API returns data starting from current hour with forecast_hours=24)
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
                # Note: API with forecast_hours=24 should already filter this, but we double-check
                if dt < current_hour:
                    continue
                
                weather_code = hourly["weathercode"][i] if "weathercode" in hourly else 0
                condition = get_weather_condition(weather_code)
                temp = int(hourly["temperature_2m"][i]) if "temperature_2m" in hourly else 0
                
                # Format time for display (12-hour format with AM/PM)
                # Remove leading zero from hour (e.g., "01:00 PM" -> "1:00 PM")
                time_display = dt.strftime("%I:%M %p")
                if time_display.startswith("0"):
                    time_display = time_display[1:]  # Remove leading zero from hour
                
                hourly_forecast.append({
                    "time": time_display,
                    "hour": dt.strftime("%H"),
                    "temperature": temp,
                    "condition": condition,
                })
                
                # Limit to 24 hours (API should already provide exactly 24, but be safe)
                if len(hourly_forecast) >= 24:
                    break
            
            return {
                "current": int(current["temperature"]),
                "condition": get_weather_condition(current["weathercode"]),
                "high": int(current["temperature"]),  # Use current for hourly
                "low": int(current["temperature"]),
                "city": city_name,
                "forecast_type": "hourly",
                "hourly_forecast": hourly_forecast,
            }
        else:
            # Fetch daily forecast (default)
            # According to Open-Meteo docs:
            # - daily data requires timezone parameter
            # - data starts at 00:00 local time when timezone is set
            # - forecast_days defaults to 7, can be up to 16
            # - daily aggregations are 24-hour aggregations from hourly values
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "current_weather": "true",
                "daily": "weathercode,temperature_2m_max,temperature_2m_min",
                "timezone": timezone,  # Required for daily data
                "temperature_unit": "fahrenheit",
                "forecast_days": 8,  # Request 8 days so we get 7 after skipping today (index 0)
            }

            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()  # Raise exception for bad status codes
            data = resp.json()

            current = data.get("current_weather", {})
            daily = data.get("daily", {})

            # Validate we have the required data
            if not daily.get("time") or not daily.get("temperature_2m_max") or not daily.get("temperature_2m_min"):
                raise ValueError("Missing required daily forecast data")

            # Build 7-day forecast (skip today, start from tomorrow)
            # According to docs: daily data starts from today (index 0) at 00:00 local time
            forecast = []
            daily_times = daily.get("time", [])
            daily_max = daily.get("temperature_2m_max", [])
            daily_min = daily.get("temperature_2m_min", [])
            daily_weathercode = daily.get("weathercode", [])
            
            # Start from index 1 to skip today (index 0 is today, which we show separately)
            # Get next 7 days (indices 1-7)
            for i in range(1, min(len(daily_times), 8)):
                try:
                    # Parse ISO8601 date (format: "2022-07-01")
                    date_str = daily_times[i]
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    
                    # Get weather code (WMO code) - defaults to 0 (Clear sky) if missing
                    weather_code = daily_weathercode[i] if i < len(daily_weathercode) else 0
                    condition = get_weather_condition(weather_code)
                    
                    # Get temperatures (convert to int, handle missing data)
                    high = int(daily_max[i]) if i < len(daily_max) else None
                    low = int(daily_min[i]) if i < len(daily_min) else None
                    
                    forecast.append({
                        "day": dt.strftime("%a"),  # Day abbreviation (Mon, Tue, etc.)
                        "date": dt.strftime("%d"),  # Day of month
                        "high": high,
                        "low": low,
                        "condition": condition,
                    })
                except (ValueError, IndexError, TypeError) as e:
                    # Skip invalid entries but continue processing
                    continue

            # Get today's high/low from index 0
            today_high = int(daily_max[0]) if daily_max else None
            today_low = int(daily_min[0]) if daily_min else None

            return {
                "current": int(current.get("temperature", 0)),
                "condition": get_weather_condition(current.get("weathercode", 0)),
                "high": today_high,
                "low": today_low,
                "city": city_name,
                "forecast_type": "daily",
                "forecast": forecast,
            }

    except Exception as e:
        # Log error for debugging
        import logging
        try:
            logging.error(f"Weather API error: {e}")
        except:
            pass  # Ignore logging errors
        
        # Return error response with appropriate forecast type
        error_response = {
            "current": "--",
            "condition": "Unavailable",
            "high": "--",
            "low": "--",
            "city": city_name,
            "forecast_type": forecast_type,
        }
        
        if forecast_type == "hourly":
            error_response["hourly_forecast"] = []
        else:
            error_response["forecast"] = empty_forecast
        
        return error_response


def _get_icon_type(condition: str) -> str:
    """Map weather condition to icon type based on WMO weather codes.
    
    Maps to Phosphor PNG icons:
    - Clear (0) → sun
    - Mainly Clear (1) → cloud-sun
    - Partly Cloudy (2) → cloud-sun
    - Overcast (3) → cloud
    - Fog (45, 48) → cloud-fog
    - Drizzle/Freezing Drizzle/Rain/Freezing Rain/Rain Showers (51-82) → cloud-rain
    - Snow/Snow Grains/Snow Showers (71-86) → cloud-snow
    - Thunderstorm/Thunderstorm Hail (95-99) → cloud-lightning
    """
    condition_lower = condition.lower()
    
    # Clear sky (code 0)
    if condition_lower == "clear":
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
    
    # Thunderstorm (codes 95, 96, 99) - check before rain to avoid false matches
    elif "thunderstorm" in condition_lower or "thunder" in condition_lower or "lightning" in condition_lower:
        return "storm"  # Maps to cloud-lightning.png
    
    # Snow-related (codes 71, 73, 75, 77, 85, 86) - check before rain
    elif "snow" in condition_lower:
        return "snow"  # Maps to cloud-snow.png
    
    # Rain-related (codes 51-67, 80-82): Drizzle, Freezing Drizzle, Rain, Freezing Rain, Rain Showers
    elif "rain" in condition_lower or "drizzle" in condition_lower or "showers" in condition_lower:
        return "rain"  # Maps to cloud-rain.png
    
    # Default fallback
    else:
        return "cloud"  # Maps to cloud.png


def format_weather_receipt(
    printer: PrinterDriver, config: Dict[str, Any] = None, module_name: str = None
):
    """Prints the weather receipt with current conditions and 7-day forecast."""
    weather = get_weather(config)

    # Header
    printer.print_header(module_name or "WEATHER", icon="cloud-sun")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()

    # Location
    printer.print_subheader(weather['city'].upper())
    
    # Weather icon - large for current conditions
    icon_type = _get_icon_type(weather['condition'])
    printer.print_icon(icon_type, size=48)
    
    # Current temperature - big and bold
    printer.print_bold(f"{weather['current']}°F")
    printer.print_body(weather['condition'])
    
    # High/Low for today
    printer.print_body(f"High {weather['high']}°F  ·  Low {weather['low']}°F")
    printer.print_line()
    
    # Check forecast type
    forecast_type = weather.get('forecast_type', 'daily')
    
    if forecast_type == "hourly":
        # Hourly Forecast
        hourly_forecast = weather.get('hourly_forecast', [])
        if hourly_forecast:
            printer.print_subheader("24-HOUR FORECAST")
            printer.print_line()
            
            # Print hourly forecast
            printer.print_hourly_forecast(hourly_forecast)
            printer.print_line()
    else:
        # Daily Forecast
        forecast = weather.get('forecast', [])
        if forecast:
            printer.print_subheader("7-DAY FORECAST")
            printer.print_line()
            
            # Print forecast as a visual row with icons
            printer.print_weather_forecast(forecast)
            printer.print_line()