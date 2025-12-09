# GeoNames Global Location Database Setup

This project uses the GeoNames global cities database for offline location search. The database can include cities from various population thresholds.

## Database Information

- **Source**: GeoNames (https://www.geonames.org/)
- **Available Datasets**:
  - `cities500.zip`: Cities with population > 500 (~145K cities)
  - `cities1000.zip`: Cities with population > 1,000 (~130K cities)
  - `cities5000.zip`: Cities with population > 5,000 (~50K cities) **[default]**
  - `cities15000.zip`: Cities with population > 15,000 (~33K cities)
- **License**: Creative Commons Attribution 4.0
- **Format**: CSV
- **Location**: `app/data/geonames_cities.csv`

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
# Download default dataset (cities5000.zip - ~50K cities)
python manufacturing/scripts/download_geonames.py

# Or specify a different population threshold:
python manufacturing/scripts/download_geonames.py 500   # ~145K cities (largest)
python manufacturing/scripts/download_geonames.py 1000  # ~130K cities
python manufacturing/scripts/download_geonames.py 5000  # ~50K cities (default)
python manufacturing/scripts/download_geonames.py 15000 # ~33K cities (smallest)
```

This will:
1. Download the selected dataset from GeoNames
2. Extract the tab-separated data file
3. Convert to CSV format
4. Save to `app/data/geonames_cities.csv`
5. Clean up temporary files

**Note**: Larger datasets (500, 1000) will take longer to download and process, but provide more location coverage.

### Manual Download

If you prefer to download manually:

1. Visit https://download.geonames.org/export/dump/
2. Download your preferred dataset (e.g., `cities5000.zip`, `cities1000.zip`, etc.)
3. Extract the corresponding `.txt` file
4. Update the script variables or run the conversion script

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
2. Run `python manufacturing/scripts/download_geonames.py`
3. Restart the application

GeoNames updates their database regularly, so you may want to update periodically.

## Attribution

When using GeoNames data, please include attribution:

> This product includes GeoNames geographical data, which is made available under the Creative Commons Attribution 4.0 License.

GeoNames: https://www.geonames.org/
