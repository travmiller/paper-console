import feedparser
from datetime import datetime
from typing import Dict, Any
from bs4 import BeautifulSoup
import re
from app.config import settings


def clean_text(text: str) -> str:
    """Cleans text by removing HTML, normalizing encoding, and removing non-printable characters."""
    if not text:
        return ""
    
    # Handle bytes - decode to string first
    if isinstance(text, bytes):
        try:
            text = text.decode('utf-8', errors='replace')
        except:
            try:
                text = text.decode('latin-1', errors='replace')
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
        text = re.sub(r'<[^>]+>', '', text)
    
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
    text = ''.join(char for char in text if (32 <= ord(char) < 127) or char in ['\n', '\t', '\r'])
    
    # Normalize whitespace
    text = ' '.join(text.split())
    
    return text.strip()


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
                # Clean up text - remove HTML, normalize encoding, remove emojis
                title = clean_text(entry.get("title", "No Title"))
                summary = clean_text(entry.get("summary", entry.get("description", "No summary.")))
                source = clean_text(feed.feed.get("title", "RSS"))
                
                articles.append({
                    "source": source,
                    "title": title,
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

