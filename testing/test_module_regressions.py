"""Regression tests for merged module configuration features."""

from datetime import datetime
from types import SimpleNamespace

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

    def print_body(self, text):
        self.lines.append(str(text))

    def feed(self, _lines):
        return None


class _FakeRSSResponse:
    content = b"<rss></rss>"

    def raise_for_status(self):
        return None


def test_get_weather_defaults_temperature_unit_when_config_missing(monkeypatch):
    captured = {}
    now = datetime.now().replace(minute=0, second=0, microsecond=0)

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


def test_get_weather_retries_then_returns_unavailable_without_placeholder_rows(monkeypatch):
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
    def fake_get(url, params=None, timeout=0):  # noqa: ARG001
        return _FakeWeatherResponse({"daily": {"time": []}})

    monkeypatch.setattr(weather_module.requests, "get", fake_get)

    weather = weather_module.get_weather({"city_name": "Worcester"})

    assert weather["ok"] is False
    assert "current_weather" in weather["error"]
    assert weather["forecast"] == []


def test_format_weather_receipt_prints_unavailable_message(monkeypatch):
    monkeypatch.setattr(
        weather_module,
        "get_weather",
        lambda _config=None: {
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
