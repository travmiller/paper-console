"""
Offline location lookup using GeoNames cities database.
Provides city name search with timezone and coordinate mapping for global locations.
"""

import csv
import os
from typing import List, Dict, Optional, Tuple
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
    # Try new GeoNames database first, fall back to old ZIP database for compatibility
    csv_path = base_dir / "data" / "geonames_cities.csv"

    if not csv_path.exists():
        # Fallback to old database if GeoNames not available
        csv_path = base_dir / "data" / "ZIP_Locale_Detail.csv"
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


def _is_geonames_format(data: List[Dict]) -> bool:
    """Check if data is in GeoNames format."""
    if not data:
        return False
    first_row = data[0]
    return (
        "geonameid" in first_row or "latitude" in first_row and "longitude" in first_row
    )


def _format_location_name(row: Dict, is_geonames: bool) -> str:
    """Format location name for display."""
    if is_geonames:
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
    else:
        # Old ZIP format
        city = (
            row.get("PHYSICAL CITY", "").strip() or row.get("LOCALE NAME", "").strip()
        )
        state = row.get("PHYSICAL STATE", "").strip()
        if city and state:
            return f"{city}, {state}"
        return city or "Unknown"


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

    is_geonames = _is_geonames_format(data)
    scored_results = []
    zip_results = []  # For old ZIP format
    seen_locations = set()

    for row in data:
        if is_geonames:
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
                display_name = _format_location_name(row, is_geonames=True)

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
        else:
            # Old ZIP format (backward compatibility)
            zipcode = row.get("DELIVERY ZIPCODE", "").strip()
            locale_name = row.get("LOCALE NAME", "").strip().upper()
            city = row.get("PHYSICAL CITY", "").strip().upper()
            state = row.get("PHYSICAL STATE", "").strip()
            physical_zip = row.get("PHYSICAL ZIP", "").strip()

            location_key = (zipcode, city, state)

            if location_key in seen_locations:
                continue

            # Check if query is a zip code (numeric, 5 digits)
            is_zip_search = query_lower.isdigit() and len(query_lower) == 5

            match = False
            if is_zip_search:
                if (
                    zipcode == query_lower.upper()
                    or physical_zip == query_lower.upper()
                ):
                    match = True
            else:
                query_upper = query_lower.upper()
                if (
                    query_upper in locale_name
                    or query_upper in city
                    or locale_name.startswith(query_upper)
                    or city.startswith(query_upper)
                ):
                    match = True

            if match:
                seen_locations.add(location_key)

                # Use state-based timezone and coordinates (old method)
                timezone = STATE_TO_TIMEZONE.get(state.upper(), "America/New_York")
                lat, lon = STATE_COORDINATES.get(state.upper(), (40.7128, -74.0060))

                display_name = city.title() if city else locale_name.title()
                if not display_name:
                    display_name = f"Zip {zipcode}"

                result = {
                    "id": f"{zipcode}-{city}-{state}",
                    "name": display_name,
                    "zipcode": zipcode,
                    "city": city.title() if city else locale_name.title(),
                    "state": state,
                    "latitude": lat,
                    "longitude": lon,
                    "timezone": timezone,
                }
                zip_results.append(result)

                if len(zip_results) >= limit:
                    break

    # Sort by relevance score (descending) for GeoNames, or keep original order for ZIP
    if is_geonames and scored_results:
        scored_results.sort(key=lambda x: x.get("_score", 0), reverse=True)
        # Remove internal score before returning
        for result in scored_results:
            result.pop("_score", None)
        return scored_results[:limit]

    # For old ZIP format, return results as-is
    return zip_results[:limit]


def get_location_by_zip(zipcode: str) -> Optional[Dict]:
    """
    Get location details for a specific zip code (US only, for backward compatibility).
    For GeoNames database, this searches by city name instead.
    """
    # For GeoNames, zip codes aren't available, so this is mainly for backward compatibility
    data = _load_csv_data()
    if not data:
        return None

    is_geonames = _is_geonames_format(data)

    if is_geonames:
        # GeoNames doesn't have zip codes, return None
        return None
    else:
        # Old ZIP format
        results = search_locations(zipcode, limit=1)
        if results:
            return results[0]
        return None


# Keep old state mappings for backward compatibility with old ZIP database
STATE_TO_TIMEZONE = {
    "AL": "America/New_York",
    "CT": "America/New_York",
    "DE": "America/New_York",
    "FL": "America/New_York",
    "GA": "America/New_York",
    "IN": "America/New_York",
    "KY": "America/New_York",
    "ME": "America/New_York",
    "MD": "America/New_York",
    "MA": "America/New_York",
    "MI": "America/New_York",
    "NH": "America/New_York",
    "NJ": "America/New_York",
    "NY": "America/New_York",
    "NC": "America/New_York",
    "OH": "America/New_York",
    "PA": "America/New_York",
    "RI": "America/New_York",
    "SC": "America/New_York",
    "VT": "America/New_York",
    "VA": "America/New_York",
    "WV": "America/New_York",
    "DC": "America/New_York",
    "AR": "America/Chicago",
    "IL": "America/Chicago",
    "IA": "America/Chicago",
    "KS": "America/Chicago",
    "LA": "America/Chicago",
    "MN": "America/Chicago",
    "MS": "America/Chicago",
    "MO": "America/Chicago",
    "NE": "America/Chicago",
    "ND": "America/Chicago",
    "OK": "America/Chicago",
    "SD": "America/Chicago",
    "TN": "America/Chicago",
    "TX": "America/Chicago",
    "WI": "America/Chicago",
    "AZ": "America/Phoenix",
    "CO": "America/Denver",
    "ID": "America/Denver",
    "MT": "America/Denver",
    "NM": "America/Denver",
    "UT": "America/Denver",
    "WY": "America/Denver",
    "CA": "America/Los_Angeles",
    "NV": "America/Los_Angeles",
    "OR": "America/Los_Angeles",
    "WA": "America/Los_Angeles",
    "AK": "America/Anchorage",
    "HI": "Pacific/Honolulu",
    "PR": "America/Puerto_Rico",
    "VI": "America/St_Thomas",
    "GU": "Pacific/Guam",
    "AS": "Pacific/Pago_Pago",
    "MP": "Pacific/Saipan",
}

STATE_COORDINATES = {
    "AL": (32.806671, -86.791130),
    "AK": (61.370716, -152.404419),
    "AZ": (33.729759, -111.431221),
    "AR": (34.969704, -92.373123),
    "CA": (36.116203, -119.681564),
    "CO": (39.059811, -105.311104),
    "CT": (41.597782, -72.755371),
    "DE": (39.318523, -75.507141),
    "FL": (27.766279, -81.686783),
    "GA": (33.040619, -83.643074),
    "HI": (21.094318, -157.498337),
    "ID": (44.240459, -114.478828),
    "IL": (40.349457, -88.986137),
    "IN": (39.849426, -86.258278),
    "IA": (42.011539, -93.210526),
    "KS": (38.526600, -96.726486),
    "KY": (37.668140, -84.670067),
    "LA": (31.169546, -91.867805),
    "ME": (44.323535, -69.765261),
    "MD": (39.063946, -76.802101),
    "MA": (42.230171, -71.530106),
    "MI": (43.326618, -84.536095),
    "MN": (45.694454, -93.900192),
    "MS": (32.741646, -89.678696),
    "MO": (38.572954, -92.189283),
    "MT": (46.921925, -110.454353),
    "NE": (41.125370, -98.268082),
    "NV": (38.313515, -117.055374),
    "NH": (43.452492, -71.563896),
    "NJ": (40.298904, -74.521011),
    "NM": (34.840515, -106.248482),
    "NY": (42.165726, -74.948051),
    "NC": (35.630066, -79.806419),
    "ND": (47.528912, -99.784012),
    "OH": (40.388783, -82.764915),
    "OK": (35.565342, -96.928917),
    "OR": (44.572021, -122.070938),
    "PA": (40.590752, -77.209755),
    "RI": (41.680893, -71.51178),
    "SC": (33.856892, -80.945007),
    "SD": (44.299782, -99.438828),
    "TN": (35.747845, -86.692345),
    "TX": (31.054487, -97.563461),
    "UT": (40.150032, -111.862434),
    "VT": (44.045876, -72.710686),
    "VA": (37.769337, -78.169968),
    "WA": (47.400902, -121.490494),
    "WV": (38.491226, -80.954453),
    "WI": (44.268543, -89.616508),
    "WY": (42.755966, -107.302490),
    "DC": (38.907192, -77.036873),
    "PR": (18.220833, -66.590149),
    "VI": (18.335765, -64.896335),
    "GU": (13.444304, 144.793731),
    "AS": (-14.270972, -170.132217),
    "MP": (17.330830, 145.384690),
}
