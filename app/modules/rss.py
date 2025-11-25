import feedparser
from datetime import datetime
from typing import Dict, Any
from app.config import settings


def wrap_text(text: str, width: int = 32, indent: int = 0) -> list[str]:
    """Wraps text to fit the printer width with optional indentation."""
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        available_width = width - indent

        if len(current_line) + len(word) + 1 <= available_width:
            current_line += word + " "
        else:
            lines.append(current_line.strip())
            current_line = word + " "

    if current_line:
        lines.append(current_line.strip())

    return lines


def get_rss_articles(config: Dict[str, Any] = None):
    """Fetches articles from RSS feeds."""
    if config is None:
        config = {"rss_feeds": []}
    
    rss_feeds = config.get("rss_feeds", [])
    
    # Filter out empty strings
    rss_feeds = [feed for feed in rss_feeds if feed and feed.strip()]
    
    if not rss_feeds:
        print("[RSS] No RSS feeds configured or all feeds are empty.")
        return []
    
    articles = []
    
    print(f"[RSS] Fetching {len(rss_feeds)} RSS feeds...")
    for feed_url in rss_feeds:
        print(f"[RSS] Parsing RSS: {feed_url[:60]}...")
        try:
            feed = feedparser.parse(feed_url)
            
            # Check if feed has entries
            if not feed.entries:
                print(f"[RSS] No entries found in feed: {feed_url[:60]}...")
                continue
            
            # Get top 2 entries from each feed
            for entry in feed.entries[:2]:
                # Clean up summary (remove HTML if possible, simple strip)
                summary = entry.get("summary", entry.get("description", "No summary."))
                # Basic HTML strip (better done with BS4, but keeping simple)
                summary = summary.replace("<p>", "").replace("</p>", "")
                
                articles.append({
                    "source": feed.feed.get("title", "RSS"),
                    "title": entry.get("title", "No Title"),
                    "summary": summary
                })
        except Exception as e:
            print(f"[RSS] Error fetching RSS {feed_url}: {e}")
    
    print(f"[RSS] Found {len(articles)} articles total")
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
                article["title"], width=32, indent=2  # PRINTER_WIDTH
            )
            for line in wrapped_lines:
                printer.print_text(f"  {line}")

            # Wrap the summary
            wrapped_summary = wrap_text(
                article["summary"], width=32, indent=0  # PRINTER_WIDTH
            )
            # Limit summary lines to save paper
            for line in wrapped_summary[:4]:
                printer.print_text(line)
            
            if len(wrapped_summary) > 4:
                printer.print_text("...")

            printer.print_line()  # Separator between articles

