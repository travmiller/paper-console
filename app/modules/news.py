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

    # Header with date
    printer.print_header(module_name or "NEWS", icon="newspaper")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()

    if not news_data:
        printer.print_body("No articles found.")
        printer.print_caption("Check your API key.")
    else:
        for i, article in enumerate(news_data):
            # Source as subheader
            source = article["source"].upper()[:24]
            printer.print_subheader(source)

            # Headline in bold
            wrapped_lines = wrap_text(article["title"], width=42, indent=0)
            for line in wrapped_lines:
                printer.print_bold(line)

            # Summary in regular body text
            if article["summary"]:
                wrapped_summary = wrap_text(article["summary"], width=42, indent=0)
                for line in wrapped_summary[:4]:
                    printer.print_body(line)
                if len(wrapped_summary) > 4:
                    printer.print_caption("...")

            # QR code linking to full article
            if article.get("url"):
                printer.print_qr(article["url"], size=2, error_correction="L", fixed_size=True)

            printer.print_line()
