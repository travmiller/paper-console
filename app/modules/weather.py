import requests
from datetime import datetime
from typing import Dict, Any, Optional
import app.config
from app.drivers.printer_mock import PrinterDriver


def get_weather_condition(code: int) -> str:
    """Maps WMO Weather Codes to text."""
    # See https://open-meteo.com/en/docs
    if code == 0:
        return "Clear"
    if code in [1, 2, 3]:
        return "Cloudy"
    if code in [45, 48]:
        return "Fog"
    if code in [51, 53, 55, 61, 63, 65]:
        return "Rain"
    if code in [71, 73, 75, 85, 86]:
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

    # If OpenWeather API key is provided, use OpenWeather API
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

                return {
                    "current": current_temp,
                    "condition": condition,
                    "high": high,
                    "low": low,
                    "city": city,
                }
        except Exception:
            # Fall through to Open-Meteo if OpenWeather fails
            pass

    # Use Open-Meteo (free, no key required)
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current_weather": "true",
            "daily": "temperature_2m_max,temperature_2m_min",
            "timezone": timezone,
            "temperature_unit": "fahrenheit",
        }

        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()

        current = data["current_weather"]
        daily = data["daily"]

        return {
            "current": int(current["temperature"]),
            "condition": get_weather_condition(current["weathercode"]),
            "high": int(daily["temperature_2m_max"][0]),
            "low": int(daily["temperature_2m_min"][0]),
            "city": city_name,
        }

    except Exception:
        return {
            "current": "--",
            "condition": "Unavailable",
            "high": "--",
            "low": "--",
            "city": city_name,
        }


def format_weather_receipt(
    printer: PrinterDriver, config: Dict[str, Any] = None, module_name: str = None
):
    """Prints the weather receipt."""
    weather = get_weather(config)

    # Header
    printer.print_header((module_name or "WEATHER").upper())
    printer.print_text(datetime.now().strftime("%A, %b %d"))
    printer.print_line()

    # Weather Section
    printer.print_text(f"WEATHER IN {weather['city'].upper()}")
    printer.print_text(f"NOW:  {weather['current']}F  {weather['condition']}")
    printer.print_text(f"H/L:  {weather['high']}F / {weather['low']}F")
    printer.print_line()
