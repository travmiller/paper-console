import requests
from datetime import datetime
from typing import Dict, Any, Optional
import app.config
from app.drivers.printer_mock import PrinterDriver


def get_weather_condition(code: int) -> str:
    """Maps WMO Weather Codes to text.
    
    WMO Weather Code reference:
    0: Clear sky
    1: Mainly clear
    2: Partly cloudy
    3: Overcast
    45, 48: Fog
    51, 53, 55: Drizzle (light, moderate, dense)
    61, 63, 65: Rain (slight, moderate, heavy)
    66, 67: Freezing rain (light, heavy)
    71, 73, 75: Snow fall (slight, moderate, heavy)
    77: Snow grains
    80, 81, 82: Rain showers (slight, moderate, violent)
    85, 86: Snow showers (slight, heavy)
    95, 96, 99: Thunderstorm (slight, moderate, heavy)
    """
    if code == 0:
        return "Clear"
    if code == 1:
        return "Mainly Clear"  # Mostly sunny
    if code == 2:
        return "Partly Cloudy"  # Partly cloudy
    if code == 3:
        return "Overcast"  # Cloudy
    if code in [45, 48]:
        return "Fog"
    if code in [51, 53, 55, 61, 63, 65, 66, 67, 80, 81, 82]:
        return "Rain"
    if code in [71, 73, 75, 77, 85, 86]:
        return "Snow"
    if code in [95, 96, 99]:
        return "Storm"
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
            
            # Build hourly forecast (next 24 hours, skip current hour)
            hourly_forecast = []
            current_time = datetime.now()
            current_hour = current_time.replace(minute=0, second=0, microsecond=0)
            
            for i in range(len(hourly.get("time", []))):
                time_str = hourly["time"][i]
                dt = datetime.strptime(time_str, "%Y-%m-%dT%H:%M")
                
                # Skip past hours and current hour
                if dt <= current_hour:
                    continue
                
                weather_code = hourly["weathercode"][i] if "weathercode" in hourly else 0
                condition = get_weather_condition(weather_code)
                temp = int(hourly["temperature_2m"][i]) if "temperature_2m" in hourly else 0
                
                hourly_forecast.append({
                    "time": dt.strftime("%I:%M %p"),
                    "hour": dt.strftime("%H"),
                    "temperature": temp,
                    "condition": condition,
                })
                
                # Limit to 24 hours
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
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "current_weather": "true",
                "daily": "weathercode,temperature_2m_max,temperature_2m_min",
                "timezone": timezone,
                "temperature_unit": "fahrenheit",
                "forecast_days": 8,  # Request 8 days so we get 7 after skipping today
            }

            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()

            current = data["current_weather"]
            daily = data["daily"]

            # Build 7-day forecast (skip today, start from tomorrow)
            forecast = []
            # Start from index 1 to skip today (index 0 is today, which we show separately)
            for i in range(1, min(len(daily.get("time", [])), 8)):  # Get next 7 days (indices 1-7)
                date_str = daily["time"][i]
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                weather_code = daily["weathercode"][i] if "weathercode" in daily else 0
                condition = get_weather_condition(weather_code)
                
                forecast.append({
                    "day": dt.strftime("%a"),
                    "date": dt.strftime("%d"),
                    "high": int(daily["temperature_2m_max"][i]),
                    "low": int(daily["temperature_2m_min"][i]),
                    "condition": condition,
                })

            return {
                "current": int(current["temperature"]),
                "condition": get_weather_condition(current["weathercode"]),
                "high": int(daily["temperature_2m_max"][0]),
                "low": int(daily["temperature_2m_min"][0]),
                "city": city_name,
                "forecast_type": "daily",
                "forecast": forecast,
            }

    except Exception:
        return {
            "current": "--",
            "condition": "Unavailable",
            "high": "--",
            "low": "--",
            "city": city_name,
            "forecast": empty_forecast,
        }


def _get_icon_type(condition: str) -> str:
    """Map weather condition to icon type (maps to Phosphor PNG icons)."""
    condition_lower = condition.lower()
    if condition_lower == "clear":
        return "sun"  # Maps to sun.png
    elif "mainly clear" in condition_lower or "partly cloudy" in condition_lower:
        return "cloud-sun"  # Maps to cloud-sun.png
    elif "rain" in condition_lower:
        return "rain"  # Maps to cloud-rain.png
    elif "snow" in condition_lower:
        return "snow"  # Maps to cloud-snow.png
    elif "storm" in condition_lower or "thunder" in condition_lower or "lightning" in condition_lower:
        return "storm"  # Maps to cloud-lightning.png
    elif "fog" in condition_lower or "mist" in condition_lower:
        return "cloud-fog"  # Maps to cloud-fog.png
    elif "cloud" in condition_lower or "overcast" in condition_lower:
        return "cloud"  # Maps to cloud.png
    else:
        return "cloud"  # Default


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