# GeoNames Global Location Database Setup

This project uses the GeoNames global cities database for offline location search. The database includes over 32,000 cities worldwide with populations greater than 15,000.

## Database Information

- **Source**: GeoNames (https://www.geonames.org/)
- **Dataset**: cities15000.zip (cities with population > 15,000)
- **License**: Creative Commons Attribution 4.0
- **Format**: CSV
- **Location**: `app/data/geonames_cities.csv`
- **Size**: ~32,895 cities

## Features

- **Global Coverage**: Cities from all countries
- **Accurate Coordinates**: Latitude/longitude for each city
- **Timezone Support**: IANA timezone for each location
- **Population Data**: Sorted by population for better search results
- **Alternative Names**: Supports searching by alternate city names

## Setup

### Automatic Download

Run the download script to fetch and convert the GeoNames database:

```bash
python scripts/download_geonames.py
```

This will:
1. Download `cities15000.zip` from GeoNames
2. Extract the tab-separated data file
3. Convert to CSV format
4. Save to `app/data/geonames_cities.csv`
5. Clean up temporary files

### Manual Download

If you prefer to download manually:

1. Visit https://download.geonames.org/export/dump/
2. Download `cities15000.zip`
3. Extract `cities15000.txt`
4. Run the conversion script or manually convert to CSV

## Database Format

The CSV file contains the following columns:

- `geonameid`: Unique GeoNames identifier
- `name`: City name (original)
- `asciiname`: ASCII city name
- `alternatenames`: Comma-separated alternate names
- `latitude`: Latitude coordinate
- `longitude`: Longitude coordinate
- `country_code`: ISO country code (e.g., US, GB, CA)
- `admin1_code`: State/Province code (for US: state abbreviation)
- `admin2_code`: County/Region code
- `population`: City population
- `timezone`: IANA timezone (e.g., America/New_York, Europe/London)

## Usage

The location lookup module automatically detects and uses the GeoNames database:

```python
from app.location_lookup import search_locations

# Search for cities
results = search_locations("London", limit=10)
# Returns: [London, UK (pop: 8.9M), London, Canada (pop: 422K), ...]

results = search_locations("Malden", limit=5)
# Returns: [Malden, MA, New Malden, UK, ...]
```

## Backward Compatibility

The system maintains backward compatibility with the old US ZIP code database:
- If `geonames_cities.csv` exists, it uses GeoNames
- If not, it falls back to `ZIP_Locale_Detail.csv` (if present)
- Old ZIP code search still works for US locations

## Updating the Database

To update to the latest GeoNames data:

1. Delete `app/data/geonames_cities.csv`
2. Run `python scripts/download_geonames.py`
3. Restart the application

GeoNames updates their database regularly, so you may want to update periodically.

## Attribution

When using GeoNames data, please include attribution:

> This product includes GeoNames geographical data, which is made available under the Creative Commons Attribution 4.0 License.

GeoNames: https://www.geonames.org/
