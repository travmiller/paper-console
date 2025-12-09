"""
Offline location lookup using GeoNames cities database.
Provides city name search with timezone and coordinate mapping for global locations.
"""

import csv
from typing import List, Dict, Optional
from pathlib import Path

# Cache for CSV data
_csv_cache: Optional[List[Dict[str, str]]] = None

# Country code to country name mapping (for display)
COUNTRY_NAMES = {
    "US": "United States",
    "CA": "Canada",
    "MX": "Mexico",
    "GB": "United Kingdom",
    "FR": "France",
    "DE": "Germany",
    "IT": "Italy",
    "ES": "Spain",
    "AU": "Australia",
    "NZ": "New Zealand",
    "JP": "Japan",
    "CN": "China",
    "IN": "India",
    "BR": "Brazil",
    "AR": "Argentina",
    "CL": "Chile",
    "CO": "Colombia",
    "PE": "Peru",
    "ZA": "South Africa",
    "EG": "Egypt",
    "KE": "Kenya",
    "NG": "Nigeria",
    "RU": "Russia",
    "TR": "Turkey",
    "SA": "Saudi Arabia",
    "AE": "United Arab Emirates",
    "IL": "Israel",
    "KR": "South Korea",
    "TH": "Thailand",
    "VN": "Vietnam",
    "PH": "Philippines",
    "ID": "Indonesia",
    "MY": "Malaysia",
    "SG": "Singapore",
    "IE": "Ireland",
    "NL": "Netherlands",
    "BE": "Belgium",
    "CH": "Switzerland",
    "AT": "Austria",
    "SE": "Sweden",
    "NO": "Norway",
    "DK": "Denmark",
    "FI": "Finland",
    "PL": "Poland",
    "CZ": "Czech Republic",
    "GR": "Greece",
    "PT": "Portugal",
    "RO": "Romania",
    "HU": "Hungary",
    "BG": "Bulgaria",
}


def _load_csv_data() -> List[Dict[str, str]]:
    """Load and cache the GeoNames cities CSV file."""
    global _csv_cache
    if _csv_cache is not None:
        return _csv_cache

    base_dir = Path(__file__).parent
    csv_path = base_dir / "data" / "geonames_cities.csv"

    if not csv_path.exists():
        return []

    _csv_cache = []
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                _csv_cache.append(row)
    except Exception as e:
        print(f"Error loading location database: {e}")
        return []

    return _csv_cache


def _format_location_name(row: Dict) -> str:
    """Format location name for display."""
    name = row.get("name", "").strip()
    admin1 = row.get("admin1_code", "").strip()  # State/Province
    country_code = row.get("country_code", "").strip()

    # For US, show state code; for others, show country
    if country_code == "US" and admin1:
        return f"{name}, {admin1}"
    elif country_code and country_code in COUNTRY_NAMES:
        return f"{name}, {COUNTRY_NAMES[country_code]}"
    elif country_code:
        return f"{name}, {country_code}"
    return name


def _calculate_match_score(
    query_lower: str, name: str, asciiname: str, alternatenames: str, population: int
) -> float:
    """
    Calculate a relevance score for a search match.
    Higher scores = better matches.
    """
    score = 0.0

    # Exact match gets highest score
    if name == query_lower or asciiname == query_lower:
        score += 10000.0
    # Exact phrase match (query is a complete word/phrase in the name)
    elif f" {query_lower} " in f" {name} " or f" {query_lower} " in f" {asciiname} ":
        score += 5000.0
    # Starts with query gets high score
    elif name.startswith(query_lower) or asciiname.startswith(query_lower):
        score += 3000.0
    # Contains query as word boundary (not just substring)
    elif query_lower in name.split() or query_lower in asciiname.split():
        score += 2000.0
    # Contains query gets medium score
    elif query_lower in name or query_lower in asciiname:
        score += 1000.0
    # Alternate names match gets lower score
    elif alternatenames and query_lower in alternatenames:
        score += 500.0

    # Boost score based on population (larger cities rank higher)
    # Normalize population to 0-100 range (cities with 10M+ get max boost)
    population_boost = min(population / 100000.0, 100.0)
    score += population_boost

    return score


def search_locations(query: str, limit: int = 10) -> List[Dict]:
    """
    Smart search for locations by city name with relevance scoring.
    Returns a list of location dictionaries sorted by relevance.
    """
    if not query or len(query.strip()) < 2:
        return []

    query_lower = query.strip().lower()
    data = _load_csv_data()

    if not data:
        return []

    scored_results = []
    seen_locations = set()

    for row in data:
        # GeoNames format
        name = row.get("name", "").strip().lower()
        asciiname = row.get("asciiname", "").strip().lower()
        alternatenames = row.get("alternatenames", "").strip().lower()
        country_code = row.get("country_code", "").strip()
        admin1_code = row.get("admin1_code", "").strip()

        # Create unique key
        location_key = (name, admin1_code, country_code)

        if location_key in seen_locations:
            continue

        # Search in name, asciiname, and alternatenames
        # For multi-word queries, require at least one word to match prominently
        query_words = query_lower.split()
        match = False

        # Check if query matches name or asciiname
        if query_lower in name or query_lower in asciiname:
            match = True
        elif name.startswith(query_lower) or asciiname.startswith(query_lower):
            match = True
        # For multi-word queries, check if all words appear in name
        elif len(query_words) > 1:
            # All words must appear in name or asciiname
            if all(word in name or word in asciiname for word in query_words):
                match = True
        # Single word - check if it's a prominent match
        elif len(query_words) == 1:
            word = query_words[0]
            # Word must be at least 3 chars and appear in name/asciiname
            if len(word) >= 3 and (word in name or word in asciiname):
                match = True
            # Or check alternatenames for single short words
            elif len(word) < 3 and alternatenames and word in alternatenames:
                match = True
        # Check alternatenames as fallback
        elif alternatenames and query_lower in alternatenames:
            match = True

        if match:
            seen_locations.add(location_key)

            try:
                latitude = float(row.get("latitude", 0))
                longitude = float(row.get("longitude", 0))
                timezone = row.get("timezone", "").strip()
                population = int(row.get("population", 0) or 0)
            except (ValueError, TypeError):
                continue

            # Skip if coordinates are invalid
            if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                continue

            # Calculate relevance score
            score = _calculate_match_score(
                query_lower, name, asciiname, alternatenames, population
            )

            # Format display name
            display_name = _format_location_name(row)

            # For US locations, use admin1_code as state
            state = admin1_code if country_code == "US" else ""

            result = {
                "id": f"{row.get('geonameid', '')}-{name}-{admin1_code}-{country_code}",
                "name": display_name,
                "zipcode": "",  # GeoNames doesn't have zip codes
                "city": row.get("name", "").strip(),
                "state": state,
                "country_code": country_code,
                "latitude": latitude,
                "longitude": longitude,
                "timezone": timezone if timezone else "UTC",
                "population": population,
                "_score": score,  # Internal score for sorting
            }
            scored_results.append(result)

    # Sort by relevance score (descending)
    scored_results.sort(key=lambda x: x.get("_score", 0), reverse=True)
    # Remove internal score before returning
    for result in scored_results:
        result.pop("_score", None)
    return scored_results[:limit]


def get_location_by_zip(zipcode: str) -> Optional[Dict]:
    """
    Get location details for a zip code (backward compatibility).
    GeoNames database doesn't have zip codes, so this searches by zip code as a city name.
    Returns None if not found.
    """
    # GeoNames doesn't have zip codes, so search by zip code as a city name
    # This is mainly for backward compatibility
    if not zipcode or len(zipcode.strip()) != 5 or not zipcode.strip().isdigit():
        return None

    results = search_locations(zipcode, limit=1)
    if results:
        return results[0]
    return None
