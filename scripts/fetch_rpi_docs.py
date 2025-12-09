#!/usr/bin/env python3
"""
Script to fetch and save Raspberry Pi configuration documentation.
This creates a local reference file that Cursor can index.
"""

import requests
from pathlib import Path
from bs4 import BeautifulSoup
import json
from datetime import datetime

DOCS_URL = "https://www.raspberrypi.com/documentation/computers/configuration.html"
OUTPUT_DIR = Path(__file__).parent.parent / "docs"
OUTPUT_FILE = OUTPUT_DIR / "raspberry-pi-config-full.md"


def fetch_documentation():
    """Fetch the Raspberry Pi configuration documentation."""
    print(f"Fetching documentation from {DOCS_URL}...")

    try:
        response = requests.get(DOCS_URL, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Extract main content
        # Try to find the main content area (adjust selectors as needed)
        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", class_="content")
        )

        if not main_content:
            # Fallback: get body content
            main_content = soup.find("body")

        # Extract text content
        content = []
        content.append(f"# Raspberry Pi Configuration Documentation\n\n")
        content.append(f"**Source:** {DOCS_URL}\n")
        content.append(f"**Fetched:** {datetime.now().isoformat()}\n\n")
        content.append("---\n\n")

        # Extract headings and paragraphs
        for element in main_content.find_all(
            ["h1", "h2", "h3", "h4", "p", "ul", "ol", "pre", "code"]
        ):
            if element.name.startswith("h"):
                level = int(element.name[1])
                text = element.get_text(strip=True)
                if text:
                    content.append(f"{'#' * level} {text}\n\n")
            elif element.name == "p":
                text = element.get_text(strip=True)
                if text:
                    content.append(f"{text}\n\n")
            elif element.name in ["ul", "ol"]:
                for li in element.find_all("li", recursive=False):
                    text = li.get_text(strip=True)
                    if text:
                        content.append(f"- {text}\n")
                content.append("\n")
            elif element.name in ["pre", "code"]:
                text = element.get_text()
                if text.strip():
                    content.append(f"```\n{text}\n```\n\n")

        # Save to file
        OUTPUT_DIR.mkdir(exist_ok=True)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("".join(content))

        print(f"✓ Documentation saved to {OUTPUT_FILE}")
        print(f"  File size: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")

        return True

    except requests.RequestException as e:
        print(f"✗ Error fetching documentation: {e}")
        return False
    except Exception as e:
        print(f"✗ Error processing documentation: {e}")
        return False


if __name__ == "__main__":
    success = fetch_documentation()
    exit(0 if success else 1)
