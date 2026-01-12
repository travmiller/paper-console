from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any, Union
from datetime import datetime
import json
import os
import uuid

# Constants
PRINTER_WIDTH = 42  # Characters per line with Font B (small font)


class WebhookConfig(BaseModel):
    url: str = ""
    method: str = "GET"
    headers: Dict[str, str] = {}
    body: Optional[str] = None
    json_path: Optional[str] = None
    label: str = "Webhook"


class NewsConfig(BaseModel):
    news_api_key: Optional[str] = None


class RSSConfig(BaseModel):
    rss_feeds: List[str] = []


class EmailConfig(BaseModel):
    email_host: str = "imap.gmail.com"
    email_user: Optional[str] = None
    email_password: Optional[str] = None
    polling_interval: int = 30  # Default to 30 seconds
    auto_print_new: bool = True  # Whether to automatically print new emails


class TextConfig(BaseModel):
    label: str = "Note"
    content: str = ""


class ChecklistItem(BaseModel):
    text: str = ""


class ChecklistConfig(BaseModel):
    title: str = "Checklist"
    items: List[ChecklistItem] = []


class QRCodeConfig(BaseModel):
    """Configuration for QR code generation."""
    qr_type: str = "text"  # text, url, wifi, contact, phone, sms, email
    content: str = ""  # Main content (URL, text, phone number, etc.)
    label: str = "QR Code"  # Header label for the printout
    
    # WiFi-specific fields
    wifi_ssid: str = ""
    wifi_password: str = ""
    wifi_security: str = "WPA"  # WPA, WEP, or nopass
    wifi_hidden: bool = False
    
    # Contact (vCard) fields
    contact_name: str = ""
    contact_phone: str = ""
    contact_email: str = ""
    
    # QR code display settings (fixed for optimal scannability)
    size: int = 6  # Module size - larger = easier to scan
    error_correction: str = "H"  # High error correction for durability


class WeatherConfig(BaseModel):
    openweather_api_key: Optional[str] = None
    city_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = None


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


from pydantic import field_validator, Field


# Default module IDs (fixed UUIDs for predictable defaults)
DEFAULT_WEATHER_ID = "default-weather-001"
DEFAULT_ASTRONOMY_ID = "default-astronomy-001"
DEFAULT_SUDOKU_ID = "default-sudoku-001"
DEFAULT_MAZE_ID = "default-maze-001"
DEFAULT_QUOTES_ID = "default-quotes-001"
DEFAULT_HISTORY_ID = "default-history-001"
DEFAULT_TEXT_ID = "default-text-001"
DEFAULT_CHECKLIST_ID = "default-checklist-001"
DEFAULT_SYSTEM_MONITOR_ID = "default-system-monitor-001"


def _default_modules() -> Dict[str, ModuleInstance]:
    """Create default offline modules for out-of-box experience."""
    return {
        DEFAULT_WEATHER_ID: ModuleInstance(
            id=DEFAULT_WEATHER_ID,
            type="weather",
            name="Weather",
            config={},
        ),
        DEFAULT_ASTRONOMY_ID: ModuleInstance(
            id=DEFAULT_ASTRONOMY_ID,
            type="astronomy",
            name="Astronomy",
            config={},
        ),
        DEFAULT_SUDOKU_ID: ModuleInstance(
            id=DEFAULT_SUDOKU_ID,
            type="games",
            name="Sudoku",
            config={"difficulty": "medium"},
        ),
        DEFAULT_MAZE_ID: ModuleInstance(
            id=DEFAULT_MAZE_ID,
            type="maze",
            name="Maze",
            config={"difficulty": "medium"},
        ),
        DEFAULT_QUOTES_ID: ModuleInstance(
            id=DEFAULT_QUOTES_ID,
            type="quotes",
            name="Daily Quote",
            config={},
        ),
        DEFAULT_HISTORY_ID: ModuleInstance(
            id=DEFAULT_HISTORY_ID,
            type="history",
            name="On This Day",
            config={"count": 1},
        ),
        DEFAULT_TEXT_ID: ModuleInstance(
            id=DEFAULT_TEXT_ID,
            type="text",
            name="Note",
            config={"label": "Note", "content": ""},
        ),
        DEFAULT_CHECKLIST_ID: ModuleInstance(
            id=DEFAULT_CHECKLIST_ID,
            type="checklist",
            name="Checklist",
            config={"items": []},
        ),
        DEFAULT_SYSTEM_MONITOR_ID: ModuleInstance(
            id=DEFAULT_SYSTEM_MONITOR_ID,
            type="system_monitor",
            name="System Monitor",
            config={},
        ),
    }


def _default_channels() -> Dict[int, ChannelConfig]:
    """Create default channel assignments for out-of-box experience."""
    return {
        1: ChannelConfig(
            modules=[ChannelModuleAssignment(module_id=DEFAULT_HISTORY_ID, order=0)]
        ),
        2: ChannelConfig(
            modules=[ChannelModuleAssignment(module_id=DEFAULT_QUOTES_ID, order=0)]
        ),
        3: ChannelConfig(
            modules=[ChannelModuleAssignment(module_id=DEFAULT_ASTRONOMY_ID, order=0)]
        ),
        4: ChannelConfig(
            modules=[ChannelModuleAssignment(module_id=DEFAULT_SUDOKU_ID, order=0)]
        ),
        5: ChannelConfig(
            modules=[ChannelModuleAssignment(module_id=DEFAULT_MAZE_ID, order=0)]
        ),
        6: ChannelConfig(
            modules=[ChannelModuleAssignment(module_id=DEFAULT_TEXT_ID, order=0)]
        ),
        7: ChannelConfig(
            modules=[ChannelModuleAssignment(module_id=DEFAULT_CHECKLIST_ID, order=0)]
        ),
        8: ChannelConfig(
            modules=[ChannelModuleAssignment(module_id=DEFAULT_SYSTEM_MONITOR_ID, order=0)]
        ),
    }


class Settings(BaseModel):
    timezone: str = "America/New_York"
    latitude: float = 40.7128
    longitude: float = -74.0060
    city_name: str = "New York"
    state: Optional[str] = None
    time_format: str = "12h"  # "12h" for 12-hour format, "24h" for 24-hour format
    time_sync_mode: str = "manual"  # "manual" or "automatic" for time synchronization mode
    cutter_feed_lines: int = (
        3  # Number of empty lines to add at end of print job to clear cutter
    )
    max_print_lines: int = 200  # Maximum lines per print job (0 = no limit)
    
    # Font/text settings for bitmap rendering
    font_size: int = 16  # Font size in pixels (8-24) - 16 shows weight differences
    line_spacing: int = 2  # Extra pixels between lines (0-8)

    # Module Instances: Dictionary of module_id -> ModuleInstance
    # These are reusable module configurations that can be assigned to channels
    # Default includes offline modules for out-of-box experience
    modules: Dict[str, ModuleInstance] = Field(default_factory=_default_modules)

    # Universal Channel Configuration
    # Key is position (1-8), Value is the configuration for that channel
    # Default: Ch1=Weather, Ch2=Astronomy, Ch3=Sudoku, Ch4-8=Empty
    channels: Dict[int, ChannelConfig] = Field(default_factory=_default_channels)

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v):
        if not -90 <= v <= 90:
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v):
        if not -180 <= v <= 180:
            raise ValueError("Longitude must be between -180 and 180")
        return v

    @field_validator("cutter_feed_lines")
    @classmethod
    def validate_cutter_feed_lines(cls, v):
        if v < 0:
            return 0
        if v > 20:
            return 20
        return v

    @field_validator("time_format")
    @classmethod
    def validate_time_format(cls, v):
        if v not in ("12h", "24h"):
            return "12h"
        return v

    @field_validator("time_sync_mode")
    @classmethod
    def validate_time_sync_mode(cls, v):
        if v not in ("manual", "automatic"):
            return "manual"
        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v):
        try:
            import pytz

            pytz.timezone(v)
        except Exception:
            return "America/New_York"
        return v

    class Config:
        pass


def migrate_old_config(data: dict) -> dict:
    """Migrate old config format (channels with single type) to new format (modules + assignments)."""
    if "modules" in data and data["modules"]:
        return data

    channels = data.get("channels", {})
    if not channels:
        return data

    first_channel = channels.get("1") or channels.get(1)
    if (
        first_channel
        and isinstance(first_channel, dict)
        and "type" in first_channel
        and "modules" not in first_channel
    ):
        # Migrate old format
        new_modules = {}
        new_channels = {}

        for pos, channel_data in channels.items():
            pos_int = int(pos) if isinstance(pos, str) else pos
            channel_type = channel_data.get("type", "off")
            channel_config = channel_data.get("config", {})

            if channel_type == "off":
                new_channels[pos_int] = ChannelConfig(modules=[])
            elif channel_type == "news":
                module_assignments = []

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

                if not module_assignments:
                    new_channels[pos_int] = ChannelConfig(modules=[])
                else:
                    new_channels[pos_int] = ChannelConfig(modules=module_assignments)
            else:
                module_id = str(uuid.uuid4())
                module_name = channel_type.title()

                new_modules[module_id] = ModuleInstance(
                    id=module_id,
                    type=channel_type,
                    name=module_name,
                    config=channel_config,
                )

                new_channels[pos_int] = ChannelConfig(
                    modules=[ChannelModuleAssignment(module_id=module_id, order=0)]
                )

        data["modules"] = {mid: mod.model_dump() for mid, mod in new_modules.items()}
        data["channels"] = {
            int(pos): ch.model_dump() for pos, ch in new_channels.items()
        }

    return data


def _try_load_config_file(config_path: str) -> Settings | None:
    """Attempt to load config from a specific file path. Returns None on failure."""
    if not os.path.exists(config_path):
        return None

    try:
        with open(config_path, "r") as f:
            data = json.load(f)

            # Check if channel 1 is a string (very old format)
            channels = data.get("channels", {})
            if channels and isinstance(channels.get("1"), str):
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

            # Ensure time_sync_mode is set (for backward compatibility with old configs)
            if "time_sync_mode" not in data:
                data["time_sync_mode"] = "manual"

            return Settings(**data)
    except Exception:
        return None


def load_config() -> Settings:
    """Load settings from config.json or backup, or return defaults."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config.json")
    backup_path = os.path.join(base_dir, "config.json.bak")

    # Try main config first
    settings = _try_load_config_file(config_path)
    if settings is not None:
        return settings

    # Main config failed, try backup
    if os.path.exists(backup_path):
        settings = _try_load_config_file(backup_path)
        if settings is not None:
            try:
                save_config(settings)
            except Exception:
                pass
            return settings

    # Both failed, return defaults
    return Settings()


def save_config(new_settings: Settings):
    """Saves the settings object to config.json using atomic write to prevent corruption."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config.json")
    backup_path = os.path.join(base_dir, "config.json.bak")
    temp_path = os.path.join(base_dir, "config.json.tmp")

    try:
        # Write to temp file first
        with open(temp_path, "w") as f:
            # Get the model dump and ensure time_sync_mode is always included
            settings_dict = new_settings.model_dump(exclude_unset=False)
            # Explicitly ensure time_sync_mode is present (for backward compatibility)
            if "time_sync_mode" not in settings_dict:
                settings_dict["time_sync_mode"] = "manual"
            json.dump(settings_dict, f, indent=4)
            f.flush()
            os.fsync(f.fileno())

        # Backup existing config
        if os.path.exists(config_path):
            try:
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                os.rename(config_path, backup_path)
            except Exception:
                pass

        # Atomic rename
        os.rename(temp_path, config_path)

    except Exception:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        raise


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
