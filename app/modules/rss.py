import feedparser
import requests
from datetime import datetime
from typing import Dict, Any
from bs4 import BeautifulSoup
import re
from app.config import settings

# Maximum size for RSS feed content (500KB)
MAX_FEED_SIZE = 500 * 1024


def clean_text(text: str) -> str:
    """Cleans text by removing HTML, normalizing encoding, and removing non-printable characters."""
    if not text:
        return ""

    # Handle bytes - decode to string first
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8", errors="replace")
        except:
            try:
                text = text.decode("latin-1", errors="replace")
            except:
                return ""

    # Convert to string if needed
    if not isinstance(text, str):
        try:
            text = str(text)
        except:
            return ""

    # Remove HTML tags using BeautifulSoup
    try:
        soup = BeautifulSoup(text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
    except:
        # Fallback: simple regex removal
        text = re.sub(r"<[^>]+>", "", text)

    # Remove HTML entities (decode common ones)
    import html

    try:
        text = html.unescape(text)
    except:
        # Fallback manual replacement
        text = text.replace("&nbsp;", " ")
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')
        text = text.replace("&#39;", "'")
        text = text.replace("&apos;", "'")

    # Remove non-printable characters (keep only ASCII printable)
    # This will remove emojis, Japanese characters, and other multi-byte characters
    # that thermal printers can't handle properly
    text = "".join(
        char for char in text if (32 <= ord(char) < 127) or char in ["\n", "\t", "\r"]
    )

    # Normalize whitespace
    text = " ".join(text.split())

    return text.strip()


from app.utils import wrap_text


def get_rss_articles(config: Dict[str, Any] = None):
    """Fetches articles from RSS feeds."""
    if config is None:
        config = {"rss_feeds": []}

    rss_feeds = config.get("rss_feeds", [])

    # Filter out empty strings
    rss_feeds = [feed for feed in rss_feeds if feed and feed.strip()]

    if not rss_feeds:
        return []

    articles = []

    for feed_url in rss_feeds:
        try:
            # Use requests with timeout instead of feedparser directly
            # This prevents hanging on slow/unresponsive feeds
            response = requests.get(feed_url, timeout=10)
            response.raise_for_status()

            # Limit response size to prevent memory issues
            content = response.content[:MAX_FEED_SIZE]

            # Parse the fetched content
            feed = feedparser.parse(content)

            if not feed.entries:
                continue

            # Get top 2 entries from each feed
            for entry in feed.entries[:2]:
                title = clean_text(entry.get("title", "No Title"))
                summary = clean_text(
                    entry.get("summary", entry.get("description", "No summary."))
                )
                source = clean_text(feed.feed.get("title", "RSS"))

                link = entry.get("link", "")
                articles.append({"source": source, "title": title, "summary": summary, "url": link})
        except Exception:
            # Silently skip failed feeds
            continue

    return articles[:10]  # Cap at 10 items total


def format_rss_receipt(printer, config: Dict[str, Any] = None, module_name: str = None):
    """Compiles and prints the RSS feed receipt."""
    articles = get_rss_articles(config)

    # Header
    printer.print_header((module_name or "RSS FEEDS").upper())
    printer.print_text(datetime.now().strftime("%A, %b %d"))
    printer.print_line()

    # ARTICLES SECTION
    printer.print_text("TOP STORIES:")

    if not articles:
        printer.print_text("No articles found.")
        printer.print_text("Check your RSS feed URLs.")
    else:
        for i, article in enumerate(articles):
            # Truncate source if too long
            source = article["source"].upper()[:20]
            printer.print_text(f"[{source}]")

            # Wrap the headline
            wrapped_lines = wrap_text(
                article["title"], width=42, indent=2  # PRINTER_WIDTH (Font B)
            )
            for line in wrapped_lines:
                printer.print_text(f"  {line}")

            # Wrap the summary
            wrapped_summary = wrap_text(
                article["summary"], width=42, indent=0  # PRINTER_WIDTH (Font B)
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
