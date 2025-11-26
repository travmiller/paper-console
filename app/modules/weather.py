import requests
from datetime import datetime
from typing import Dict, Any
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


def get_weather():
    """Fetches weather from Open-Meteo (No Key Required)."""
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": app.config.settings.latitude,
            "longitude": app.config.settings.longitude,
            "current_weather": "true",
            "daily": "temperature_2m_max,temperature_2m_min",
            "timezone": app.config.settings.timezone,
            "temperature_unit": "fahrenheit",
        }

        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()

        current = data["current_weather"]
        daily = data["daily"]

        # Open-Meteo doesn't provide city name, so we use config or generic
        city_name = app.config.settings.city_name

        return {
            "current": int(current["temperature"]),
            "condition": get_weather_condition(current["weathercode"]),
            "high": int(daily["temperature_2m_max"][0]),
            "low": int(daily["temperature_2m_min"][0]),
            "city": city_name,
        }

    except Exception as e:
        print(f"Weather connection error: {e}")
        return {
            "current": "--",
            "condition": "Error",
            "high": "--",
            "low": "--",
            "city": "Error",
        }


def format_weather_receipt(printer: PrinterDriver, config: Dict[str, Any] = None, module_name: str = None):
    """Prints the weather receipt."""
    weather = get_weather()

    # Header
    printer.print_header((module_name or "WEATHER").upper())
    printer.print_text(datetime.now().strftime("%A, %b %d"))
    printer.print_line()

    # Weather Section
    printer.print_text(f"WEATHER IN {weather['city'].upper()}")
    printer.print_text(f"NOW:  {weather['current']}F  {weather['condition']}")
    printer.print_text(f"H/L:  {weather['high']}F / {weather['low']}F")
    printer.print_line()

