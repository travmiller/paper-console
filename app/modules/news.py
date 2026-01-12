import requests
from datetime import datetime
from typing import Dict, Any
from app.config import settings


def get_newsapi_articles(config: Dict[str, Any] = None):
    """Fetches news from NewsAPI."""
    if config is None:
        config = {}

    news_api_key = config.get("news_api_key")

    if not news_api_key:
        return []

    articles = []

    try:
        url = "https://newsapi.org/v2/top-headlines"
        params = {
            "country": "us",
            "apiKey": news_api_key,
            "pageSize": 3,
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if data.get("status") == "ok":
            for item in data.get("articles", []):
                articles.append(
                    {
                        "source": item["source"]["name"],
                        "title": item["title"],
                        "summary": item.get("description") or "",
                        "url": item.get("url") or "",
                    }
                )
    except Exception:
        pass

    return articles


# --- FORMATTER ---


from app.utils import wrap_text


def format_news_receipt(
    printer, config: Dict[str, Any] = None, module_name: str = None
):
    """Compiles and prints the NewsAPI receipt."""
    news_data = get_newsapi_articles(config)

    # Header
    printer.print_header((module_name or "NEWS API").upper())
    printer.print_text(datetime.now().strftime("%A, %b %d"))
    printer.print_line()

    # NEWS SECTION
    printer.print_text("TOP STORIES:")

    if not news_data:
        printer.print_text("No articles found.")
        printer.print_text("Check your API key.")
    else:
        for i, article in enumerate(news_data):
            # Truncate source if too long
            source = article["source"].upper()[:20]
            printer.print_text(f"[{source}]")

            # Wrap the headline
            wrapped_lines = wrap_text(
                article["title"], width=32, indent=2  # PRINTER_WIDTH
            )
            for line in wrapped_lines:
                printer.print_text(f"  {line}")

            # Wrap the summary (only if available)
            if article["summary"]:
                wrapped_summary = wrap_text(
                    article["summary"], width=32, indent=0  # PRINTER_WIDTH
                )
                # Limit summary lines to save paper
                for line in wrapped_summary[:4]:
                    printer.print_text(line)

                if len(wrapped_summary) > 4:
                    printer.print_text("...")

            # Print small fixed-size QR code linking to the full article
            if article.get("url"):
                printer.print_qr(article["url"], size=2, error_correction="L", fixed_size=True)

            printer.print_line()  # Separator between articles
