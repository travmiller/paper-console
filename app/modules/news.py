import requests
from datetime import datetime
from typing import Dict, Any
from urllib.parse import urlparse, urlunparse
from app.config import settings
from app.module_registry import register_module


def clean_url(url: str) -> str:
    """Clean URL by removing query parameters and fragments.
    
    News URLs often have very long tracking parameters that bloat QR codes.
    Most articles load fine with just the base path.
    """
    if not url:
        return url
    try:
        parsed = urlparse(url)
        # Keep only scheme, netloc, and path (remove query and fragment)
        clean = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
        return clean
    except Exception:
        return url


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


@register_module(
    type_id="news",
    label="News API",
    description="Top headlines from NewsAPI (requires API key)",
    icon="newspaper",
    offline=False,
    category="content",
)
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
            # Print article with QR code below text on a new line
            cleaned_url = clean_url(article.get("url", ""))
            printer.print_article_block(
                source=article["source"],
                title=article["title"],
                summary=article.get("summary", ""),
                url=cleaned_url,
                qr_size=160,
                title_width=24,
                summary_width=28,
                max_summary_lines=2,
            )
            printer.print_line()
