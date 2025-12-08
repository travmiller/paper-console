"""
Offline location lookup using ZIP_Locale_Detail.csv
Provides zip code and city name search with timezone and coordinate mapping.
"""

import csv
import os
from typing import List, Dict, Optional, Tuple
from pathlib import Path

# State to timezone mapping (US states and territories)
STATE_TO_TIMEZONE = {
    # Eastern Time
    "AL": "America/New_York",  # Alabama (eastern part)
    "CT": "America/New_York",
    "DE": "America/New_York",
    "FL": "America/New_York",  # Most of Florida
    "GA": "America/New_York",
    "IN": "America/New_York",  # Most of Indiana
    "KY": "America/New_York",  # Eastern Kentucky
    "ME": "America/New_York",
    "MD": "America/New_York",
    "MA": "America/New_York",
    "MI": "America/New_York",  # Most of Michigan
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
    # Central Time
    "AR": "America/Chicago",
    "IL": "America/Chicago",
    "IA": "America/Chicago",
    "KS": "America/Chicago",  # Most of Kansas
    "LA": "America/Chicago",
    "MN": "America/Chicago",
    "MS": "America/Chicago",
    "MO": "America/Chicago",
    "NE": "America/Chicago",  # Most of Nebraska
    "ND": "America/Chicago",  # Most of North Dakota
    "OK": "America/Chicago",
    "SD": "America/Chicago",  # Most of South Dakota
    "TN": "America/Chicago",  # Most of Tennessee
    "TX": "America/Chicago",  # Most of Texas
    "WI": "America/Chicago",
    # Mountain Time
    "AZ": "America/Phoenix",  # Arizona doesn't observe DST
    "CO": "America/Denver",
    "ID": "America/Denver",  # Most of Idaho
    "MT": "America/Denver",
    "NM": "America/Denver",
    "UT": "America/Denver",
    "WY": "America/Denver",
    # Pacific Time
    "CA": "America/Los_Angeles",
    "NV": "America/Los_Angeles",  # Most of Nevada
    "OR": "America/Los_Angeles",  # Most of Oregon
    "WA": "America/Los_Angeles",
    # Alaska
    "AK": "America/Anchorage",
    # Hawaii
    "HI": "Pacific/Honolulu",
    # Territories
    "PR": "America/Puerto_Rico",
    "VI": "America/St_Thomas",
    "GU": "Pacific/Guam",
    "AS": "Pacific/Pago_Pago",
    "MP": "Pacific/Saipan",
}

# Approximate state center coordinates (lat, lon)
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

# Cache for CSV data
_csv_cache: Optional[List[Dict[str, str]]] = None


def _load_csv_data() -> List[Dict[str, str]]:
    """Load and cache the ZIP_Locale_Detail.csv file."""
    global _csv_cache
    if _csv_cache is not None:
        return _csv_cache

    base_dir = Path(__file__).parent
    csv_path = base_dir / "ZIP_Locale_Detail.csv"

    if not csv_path.exists():
        return []

    _csv_cache = []
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                _csv_cache.append(row)
    except Exception:
        return []

    return _csv_cache


def _get_timezone_for_state(state: str) -> str:
    """Get timezone for a state code."""
    return STATE_TO_TIMEZONE.get(state.upper(), "America/New_York")


def _get_coordinates_for_state(state: str) -> Tuple[float, float]:
    """Get approximate coordinates for a state."""
    return STATE_COORDINATES.get(state.upper(), (40.7128, -74.0060))  # Default to NYC


def search_locations(query: str, limit: int = 10) -> List[Dict]:
    """
    Search for locations by zip code or city name.
    Returns a list of location dictionaries with name, zip, state, timezone, lat, lon.
    """
    if not query or len(query.strip()) < 2:
        return []

    query = query.strip().upper()
    data = _load_csv_data()
    results = []

    # Check if query is a zip code (numeric, 5 digits)
    is_zip_search = query.isdigit() and len(query) == 5

    seen_locations = set()  # Track (zip, city, state) to avoid duplicates

    for row in data:
        zipcode = row.get("DELIVERY ZIPCODE", "").strip()
        locale_name = row.get("LOCALE NAME", "").strip().upper()
        city = row.get("PHYSICAL CITY", "").strip().upper()
        state = row.get("PHYSICAL STATE", "").strip()
        physical_zip = row.get("PHYSICAL ZIP", "").strip()

        # Create unique key
        location_key = (zipcode, city, state)

        if location_key in seen_locations:
            continue

        match = False
        if is_zip_search:
            # Exact zip code match
            if zipcode == query or physical_zip == query:
                match = True
        else:
            # City name search
            if (
                query in locale_name
                or query in city
                or locale_name.startswith(query)
                or city.startswith(query)
            ):
                match = True

        if match:
            seen_locations.add(location_key)
            timezone = _get_timezone_for_state(state)
            lat, lon = _get_coordinates_for_state(state)

            # Format display name
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
            results.append(result)

            if len(results) >= limit:
                break

    return results


def get_location_by_zip(zipcode: str) -> Optional[Dict]:
    """Get location details for a specific zip code."""
    results = search_locations(zipcode, limit=1)
    if results:
        return results[0]
    return None
