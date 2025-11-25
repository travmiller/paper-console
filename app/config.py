from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any, Union
from datetime import datetime
import json
import os
import uuid
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Constants
PRINTER_WIDTH = 32  # Hardcoded printer width


class WebhookConfig(BaseModel):
    url: str = ""
    method: str = "GET"
    headers: Dict[str, str] = {}
    body: Optional[str] = None
    json_path: Optional[str] = None
    label: str = "Webhook"


class NewsConfig(BaseModel):
    news_api_key: Optional[str] = os.getenv("NEWS_API_KEY")


class RSSConfig(BaseModel):
    rss_feeds: List[str] = []


class EmailConfig(BaseModel):
    email_host: str = "imap.gmail.com"
    email_user: Optional[str] = os.getenv("EMAIL_USER")
    email_password: Optional[str] = os.getenv("EMAIL_PW")
    polling_interval: int = 30  # Default to 30 seconds
    auto_print_new: bool = True  # Whether to automatically print new emails


class TextConfig(BaseModel):
    label: str = "Note"
    content: str = ""


class CalendarSource(BaseModel):
    label: str
    url: str


class CalendarConfig(BaseModel):
    ical_sources: List[CalendarSource] = []
    label: str = "My Calendar"
    days_to_show: int = 2  # 1=Today, 2=Today+Tomorrow


class EmptyConfig(BaseModel):
    pass


class ModuleInstance(BaseModel):
    """A module instance with its configuration."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str  # e.g., "news", "games" (Sudoku), "calendar"
    name: str = ""  # User-friendly name for the module instance
    config: Dict[str, Any] = {}


class ChannelModuleAssignment(BaseModel):
    """A module assignment within a channel with ordering."""

    module_id: str
    order: int = 0  # Order within the channel (0 = first)


class ChannelConfig(BaseModel):
    """Channel configuration - can have multiple modules assigned."""

    # New format: list of module assignments
    modules: List[ChannelModuleAssignment] = []

    # Schedule: List of times in "HH:MM" 24h format to automatically print this channel
    schedule: List[str] = []


class Settings(BaseModel):
    timezone: str = "America/New_York"
    latitude: float = 40.7128
    longitude: float = -74.0060
    city_name: str = "New York"
    time_format: str = "12h"  # "12h" for 12-hour format, "24h" for 24-hour format
    cutter_feed_lines: int = 4  # Number of empty lines to add at end of print job to clear cutter
    invert_print: bool = False  # Rotate print output 180 degrees (for upside-down printers)

    # Global Weather API (shared across modules if needed)
    openweather_api_key: Optional[str] = os.getenv("OPENWEATHER_API_KEY")

    # Module Instances: Dictionary of module_id -> ModuleInstance
    # These are reusable module configurations that can be assigned to channels
    modules: Dict[str, ModuleInstance] = {}

    # Universal Channel Configuration
    # Key is position (1-8), Value is the configuration for that channel
    # Channels can have multiple modules assigned (new format)
    channels: Dict[int, ChannelConfig] = {}

    class Config:
        pass


def migrate_old_config(data: dict) -> dict:
    """Migrate old config format (channels with single type) to new format (modules + assignments)."""
    if "modules" in data and data["modules"]:
        # Already in new format
        return data

    # Check if this is the old format
    channels = data.get("channels", {})
    if not channels:
        return data

    # Check if channel 1 has old format (type field directly)
    first_channel = channels.get("1") or channels.get(1)
    if (
        first_channel
        and isinstance(first_channel, dict)
        and "type" in first_channel
        and "modules" not in first_channel
    ):
        print("[MIGRATION] Detected old config format. Migrating to modular format...")

        # Create new structure
        new_modules = {}
        new_channels = {}

        for pos, channel_data in channels.items():
            pos_int = int(pos) if isinstance(pos, str) else pos
            channel_type = channel_data.get("type", "off")
            channel_config = channel_data.get("config", {})

            if channel_type == "off":
                new_channels[pos_int] = ChannelConfig(modules=[])
            elif channel_type == "news":
                # Special handling: Split old "news" modules that had both NewsAPI and RSS
                # into separate News API and RSS modules
                module_assignments = []

                # Check if it has NewsAPI config
                has_newsapi = channel_config.get(
                    "enable_newsapi", True
                ) and channel_config.get("news_api_key")
                if has_newsapi:
                    news_module_id = str(uuid.uuid4())
                    new_modules[news_module_id] = ModuleInstance(
                        id=news_module_id,
                        type="news",
                        name="News API",
                        config={"news_api_key": channel_config.get("news_api_key", "")},
                    )
                    module_assignments.append(
                        ChannelModuleAssignment(module_id=news_module_id, order=0)
                    )

                # Check if it has RSS feeds
                rss_feeds = channel_config.get("rss_feeds", [])
                if rss_feeds:
                    rss_module_id = str(uuid.uuid4())
                    new_modules[rss_module_id] = ModuleInstance(
                        id=rss_module_id,
                        type="rss",
                        name="RSS Feeds",
                        config={"rss_feeds": rss_feeds},
                    )
                    module_assignments.append(
                        ChannelModuleAssignment(
                            module_id=rss_module_id, order=1 if has_newsapi else 0
                        )
                    )

                # If neither, create empty channel
                if not module_assignments:
                    new_channels[pos_int] = ChannelConfig(modules=[])
                else:
                    new_channels[pos_int] = ChannelConfig(modules=module_assignments)
            else:
                # Create a module instance for this channel
                module_id = str(uuid.uuid4())
                module_name = channel_type.title()

                new_modules[module_id] = ModuleInstance(
                    id=module_id,
                    type=channel_type,
                    name=module_name,
                    config=channel_config,
                )

                # Assign module to channel
                new_channels[pos_int] = ChannelConfig(
                    modules=[ChannelModuleAssignment(module_id=module_id, order=0)]
                )

        data["modules"] = {mid: mod.model_dump() for mid, mod in new_modules.items()}
        # Convert channel positions to int keys for Pydantic
        data["channels"] = {
            int(pos): ch.model_dump() for pos, ch in new_channels.items()
        }

        print(
            f"[MIGRATION] Created {len(new_modules)} module instances across {len(new_channels)} channels."
        )

    return data


def load_config() -> Settings:
    """Load settings from config.json or return defaults."""
    # Get absolute path to config.json (one directory up from this file)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config.json")

    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            try:
                data = json.load(f)

                # Check if channel 1 is a string (very old format)
                channels = data.get("channels", {})
                if channels and isinstance(channels.get("1"), str):
                    print(
                        "Detected very old config format. Migrating/Resetting to new default structure."
                    )
                    return Settings()

                # Migrate old format to new format if needed
                data = migrate_old_config(data)

                # Normalize channel keys to integers (JSON loads them as strings)
                if "channels" in data and data["channels"]:
                    normalized_channels = {}
                    for key, value in data["channels"].items():
                        try:
                            normalized_channels[int(key)] = value
                        except (ValueError, TypeError):
                            normalized_channels[key] = value
                    data["channels"] = normalized_channels

                return Settings(**data)
            except Exception as e:
                print(f"Error loading config: {e}")
                import traceback

                traceback.print_exc()

    return Settings()


def save_config(new_settings: Settings):
    """Saves the settings object to config.json."""
    # Get absolute path to config.json (one directory up from this file)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config.json")

    with open(config_path, "w") as f:
        json.dump(new_settings.model_dump(), f, indent=4)


def format_time(dt: datetime, time_format: Optional[str] = None) -> str:
    """
    Format a datetime object according to the time_format setting.

    Args:
        dt: datetime object to format
        time_format: Optional override (defaults to settings.time_format)

    Returns:
        Formatted time string (12h: "3:45 PM" or 24h: "15:45")
    """
    if time_format is None:
        time_format = settings.time_format

    if time_format == "24h":
        return dt.strftime("%H:%M")
    else:  # Default to 12h
        return dt.strftime("%I:%M %p").lstrip(
            "0"
        )  # Remove leading zero, e.g., "3:45 PM" instead of "03:45 PM"


# Global settings instance
settings = load_config()
