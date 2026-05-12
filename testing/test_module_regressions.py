"""Regression tests for merged module configuration features."""

from datetime import date, datetime
from types import SimpleNamespace

from app.modules import calendar as calendar_module
from app.modules import history as history_module
from app.modules import rss as rss_module
from app.modules import weather as weather_module


class _FakeWeatherResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class _WeatherPrinter:
    PRINTER_WIDTH_DOTS = 384

    def __init__(self):
        self.lines = []

    def print_header(self, text, *args, **kwargs):  # noqa: ARG002
        self.lines.append(str(text))

    def print_caption(self, text):
        self.lines.append(str(text))

    def print_line(self):
        self.lines.append("---")

    def print_subheader(self, text):
        self.lines.append(str(text))

    def print_bold(self, text):
        self.lines.append(str(text))

    def print_body(self, text):
        self.lines.append(str(text))

    def print_text(self, text, *args, **kwargs):  # noqa: ARG002
        self.lines.append(str(text))

    def print_image(self, _image):
        self.lines.append("[image]")

    def _get_font(self, _name):
        return None

    def feed(self, _lines):
        return None


class _FakeRSSResponse:
    content = b"<rss></rss>"

    def raise_for_status(self):
        return None


def test_get_weather_defaults_temperature_unit_when_config_missing(monkeypatch):
    weather_module.clear_weather_cache()
    captured = {}
    now = datetime(2026, 5, 12, 11, 0, 0)

    monkeypatch.setattr(weather_module.app.config.settings, "latitude", 42.0, raising=False)
    monkeypatch.setattr(weather_module.app.config.settings, "longitude", -71.0, raising=False)
    monkeypatch.setattr(
        weather_module.app.config.settings,
        "timezone",
        "America/New_York",
        raising=False,
    )
    monkeypatch.setattr(
        weather_module.app.config.settings,
        "city_name",
        "Worcester",
        raising=False,
    )
    monkeypatch.setattr(weather_module, "current_date", lambda: now.date())

    def fake_get(url, params=None, timeout=0):  # noqa: ARG001
        captured["params"] = dict(params or {})
        captured["timeout"] = timeout
        return _FakeWeatherResponse(
            {
                "current_weather": {"temperature": 72, "weathercode": 0},
                "daily": {
                    "time": [now.strftime("%Y-%m-%d")],
                    "temperature_2m_max": [75],
                    "temperature_2m_min": [65],
                    "weathercode": [0],
                    "precipitation_probability_max": [10],
                },
                "hourly": {
                    "time": [now.strftime("%Y-%m-%dT%H:%M")],
                    "temperature_2m": [72],
                    "weathercode": [0],
                    "precipitation_probability": [10],
                },
            }
        )

    monkeypatch.setattr(weather_module.requests, "get", fake_get)

    weather = weather_module.get_weather(None)

    assert captured["params"]["temperature_unit"] == "fahrenheit"
    assert captured["timeout"] == weather_module.WEATHER_REQUEST_TIMEOUT
    assert weather["temperature_unit"] == "fahrenheit"
    assert weather["city"] == "Worcester"
    assert weather["ok"] is True
    assert weather["forecast"][0]["day"] == "Today"


def test_history_module_uses_configured_local_date(monkeypatch):
    captured = {}

    def fake_get_events_for_date(target_date):
        captured["date"] = target_date
        return ["Example event"]

    monkeypatch.setattr(history_module, "current_date", lambda: date(2026, 5, 12))
    monkeypatch.setattr(history_module, "get_events_for_date", fake_get_events_for_date)

    events = history_module.get_events_for_today()

    assert events == ["Example event"]
    assert captured["date"] == date(2026, 5, 12)


def test_calendar_day_view_labels_today_using_configured_local_date(monkeypatch):
    printer = _WeatherPrinter()
    target_date = date(2026, 5, 12)
    events = {
        target_date: [
            {
                "sort_key": "09:00",
                "is_all_day": False,
                "time": "9:00 AM",
                "summary": "Breakfast meeting",
            }
        ]
    }

    monkeypatch.setattr(calendar_module, "current_date", lambda: target_date)

    calendar_module._print_calendar_day_view(printer, [target_date], events)

    assert "TODAY (05/12)" in printer.lines


def test_get_weather_retries_then_returns_unavailable_without_placeholder_rows(monkeypatch):
    weather_module.clear_weather_cache()
    calls = {"count": 0}

    def fake_get(url, params=None, timeout=0):  # noqa: ARG001
        calls["count"] += 1
        assert timeout == weather_module.WEATHER_REQUEST_TIMEOUT
        raise weather_module.requests.Timeout("request timed out")

    monkeypatch.setattr(weather_module.requests, "get", fake_get)
    monkeypatch.setattr(weather_module.time, "sleep", lambda *_: None)

    weather = weather_module.get_weather({"city_name": "Worcester"})

    assert calls["count"] == weather_module.WEATHER_REQUEST_ATTEMPTS
    assert weather["ok"] is False
    assert "timed out" in weather["error"]
    assert weather["forecast"] == []
    assert weather["hourly_forecast"] == []


def test_get_weather_rejects_invalid_success_response(monkeypatch):
    weather_module.clear_weather_cache()
    def fake_get(url, params=None, timeout=0):  # noqa: ARG001
        return _FakeWeatherResponse({"daily": {"time": []}})

    monkeypatch.setattr(weather_module.requests, "get", fake_get)

    weather = weather_module.get_weather({"city_name": "Worcester"})

    assert weather["ok"] is False
    assert "current_weather" in weather["error"]
    assert weather["forecast"] == []


def test_format_weather_receipt_prints_unavailable_message(monkeypatch):
    weather_module.clear_weather_cache()
    monkeypatch.setattr(
        weather_module,
        "get_weather",
        lambda _config=None, module_id=None: {
            "ok": False,
            "city": "Worcester",
            "error": "request timed out",
            "temperature_unit": "fahrenheit",
            "forecast": [],
            "hourly_forecast": [],
        },
    )

    printer = _WeatherPrinter()
    weather_module.format_weather_receipt(printer, {}, "WEATHER")
    output = "\n".join(printer.lines)

    assert "Forecast unavailable." in output
    assert "Could not load fresh weather data." in output
    assert "request timed out" in output
    assert "5-DAY FORECAST" not in output


def test_prefetch_weather_uses_longer_timeout_and_populates_cache(monkeypatch):
    weather_module.clear_weather_cache()
    captured = {}
    now = datetime(2026, 5, 12, 11, 0, 0)
    monkeypatch.setattr(weather_module, "current_date", lambda: now.date())
    monkeypatch.setattr(weather_module, "current_datetime", lambda: now)

    def fake_get(url, params=None, timeout=0):  # noqa: ARG001
        captured["timeout"] = timeout
        return _FakeWeatherResponse(
            {
                "current_weather": {"temperature": 72, "weathercode": 0},
                "daily": {
                    "time": [now.strftime("%Y-%m-%d")],
                    "temperature_2m_max": [75],
                    "temperature_2m_min": [65],
                    "weathercode": [0],
                    "precipitation_probability_max": [10],
                },
                "hourly": {
                    "time": [now.strftime("%Y-%m-%dT%H:%M")],
                    "temperature_2m": [72],
                    "weathercode": [0],
                    "precipitation_probability": [10],
                },
            }
        )

    monkeypatch.setattr(weather_module.requests, "get", fake_get)

    weather = weather_module.prefetch_weather({"city_name": "Worcester"}, module_id="weather-one")
    cached = weather_module.get_cached_weather({"city_name": "Worcester"}, module_id="weather-one")

    assert captured["timeout"] == weather_module.WEATHER_PREFETCH_TIMEOUT
    assert weather["ok"] is True
    assert cached is not None
    assert cached["city"] == "Worcester"
    assert cached["hourly_forecast"][0]["hour_iso"] == now.strftime("%Y-%m-%dT%H:%M")


def test_normalize_hourly_forecast_for_print_drops_prefetch_hour_and_keeps_explicit_labels():
    reference_time = datetime(2026, 5, 12, 11, 0, 0)

    hourly_forecast = [
        {
            "time": "10 AM",
            "hour": "10",
            "hour_iso": "2026-05-12T10:00",
            "temperature": 62,
            "condition": "Clear",
            "precipitation": 0,
        },
        {
            "time": "11 AM",
            "hour": "11",
            "hour_iso": "2026-05-12T11:00",
            "temperature": 64,
            "condition": "Clear",
            "precipitation": 0,
        },
        {
            "time": "12 PM",
            "hour": "12",
            "hour_iso": "2026-05-12T12:00",
            "temperature": 66,
            "condition": "Partly Cloudy",
            "precipitation": 10,
        },
    ]

    normalized = weather_module._normalize_hourly_forecast_for_print(
        hourly_forecast,
        reference_time=reference_time,
    )

    assert [row["hour"] for row in normalized] == ["11", "12"]
    assert [row["time"] for row in normalized] == ["11 AM", "12 PM"]


def test_normalize_hourly_forecast_for_print_preserves_legacy_cached_rows():
    reference_time = datetime(2026, 5, 12, 11, 0, 0)

    hourly_forecast = [
        {
            "time": "11 AM",
            "hour": "11",
            "temperature": 64,
            "condition": "Clear",
            "precipitation": 0,
        },
        {
            "time": "12 PM",
            "hour": "12",
            "temperature": 66,
            "condition": "Partly Cloudy",
            "precipitation": 10,
        },
    ]

    normalized = weather_module._normalize_hourly_forecast_for_print(
        hourly_forecast,
        reference_time=reference_time,
    )

    assert [row["time"] for row in normalized] == ["11 AM", "12 PM"]


def test_get_cached_weather_discards_entries_older_than_ten_minutes():
    weather_module.clear_weather_cache()
    weather_module._store_weather_cache(
        {
            "ok": True,
            "city": "Worcester",
            "forecast": [],
            "hourly_forecast": [],
            "temperature_unit": "fahrenheit",
        },
        {"city_name": "Worcester"},
        module_id="weather-old",
    )

    cache_key = weather_module._weather_cache_key(
        {"city_name": "Worcester"},
        module_id="weather-old",
    )
    weather_module._WEATHER_CACHE[cache_key]["stored_at_monotonic"] -= (
        weather_module.WEATHER_CACHE_MAX_AGE_SECONDS + 1
    )

    assert weather_module.get_cached_weather(
        {"city_name": "Worcester"},
        module_id="weather-old",
    ) is None


def test_format_weather_receipt_scheduled_uses_cached_weather(monkeypatch):
    weather_module.clear_weather_cache()
    reference_time = datetime(2026, 5, 12, 11, 0, 0)
    monkeypatch.setattr(
        weather_module,
        "get_cached_weather",
        lambda _config=None, module_id=None, max_age_seconds=600: {
            "ok": True,
            "city": "Worcester",
            "current": 72,
            "condition": "Clear",
            "high": 75,
            "low": 65,
            "forecast": [],
            "hourly_forecast": [
                {
                    "time": "10 AM",
                    "hour": "10",
                    "hour_iso": "2026-05-12T10:00",
                    "temperature": 70,
                    "condition": "Clear",
                    "precipitation": 0,
                },
                {
                    "time": "11 AM",
                    "hour": "11",
                    "hour_iso": "2026-05-12T11:00",
                    "temperature": 72,
                    "condition": "Clear",
                    "precipitation": 0,
                },
                {
                    "time": "12 PM",
                    "hour": "12",
                    "hour_iso": "2026-05-12T12:00",
                    "temperature": 74,
                    "condition": "Partly Cloudy",
                    "precipitation": 10,
                },
            ],
            "temperature_unit": "fahrenheit",
        },
    )
    monkeypatch.setattr(
        weather_module,
        "get_weather",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("live weather should not be fetched")),
    )
    monkeypatch.setattr(weather_module, "draw_current_conditions_panel", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(weather_module, "_build_24_hour_summary", lambda *_args, **_kwargs: "Mild and clear.")
    captured = {}

    def fake_draw_hourly_forecast_image(hourly_forecast, *_args, **_kwargs):
        captured["hourly_forecast"] = hourly_forecast
        return object()

    monkeypatch.setattr(weather_module, "draw_hourly_forecast_image", fake_draw_hourly_forecast_image)
    monkeypatch.setattr(weather_module, "current_datetime", lambda: reference_time)

    printer = _WeatherPrinter()
    weather_module.format_weather_receipt(
        printer,
        {"city_name": "Worcester"},
        "WEATHER",
        module_id="weather-one",
        scheduled=True,
    )

    output = "\n".join(printer.lines)
    assert "Forecast unavailable." not in output
    assert "Mild and clear." in output
    assert [row["time"] for row in captured["hourly_forecast"]] == ["11 AM", "12 PM"]
    assert [row["hour"] for row in captured["hourly_forecast"]] == ["11", "12"]


def test_get_rss_articles_keeps_total_receipt_length_capped(monkeypatch):
    def fake_get(url, headers=None, timeout=0):  # noqa: ARG001
        return _FakeRSSResponse()

    def fake_parse(_content):
        return SimpleNamespace(
            entries=[
                {"title": f"Story {idx}", "summary": "Summary", "link": f"https://e/{idx}"}
                for idx in range(10)
            ],
            feed={"title": "Feed"},
        )

    monkeypatch.setattr(rss_module.requests, "get", fake_get)
    monkeypatch.setattr(rss_module.feedparser, "parse", fake_parse)

    articles = rss_module.get_rss_articles(
        {
            "rss_feeds": [f"https://feed/{idx}" for idx in range(10)],
            "num_articles": 10,
        }
    )

    assert len(articles) == 10
