"""Regression tests for merged module configuration features."""

from datetime import datetime
from types import SimpleNamespace

from app.modules import rss as rss_module
from app.modules import weather as weather_module


class _FakeWeatherResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


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
    assert weather["temperature_unit"] == "fahrenheit"
    assert weather["city"] == "Worcester"


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
