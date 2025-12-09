#!/usr/bin/env python3
"""
Download and process GeoNames cities database.
Downloads GeoNames cities data and converts to CSV format.

Available datasets:
- cities500.zip: Cities with population > 500 (~145K cities)
- cities1000.zip: Cities with population > 1,000 (~130K cities)
- cities5000.zip: Cities with population > 5,000 (~50K cities)
- cities15000.zip: Cities with population > 15,000 (~33K cities) [default]
"""

import urllib.request
import zipfile
import csv
import os
import sys
from pathlib import Path

# Default population threshold (can be overridden via command line)
DEFAULT_THRESHOLD = "5000"  # cities5000.zip for more locations

# GeoNames download URLs
GEONAMES_DATASETS = {
    "500": {
        "url": "https://download.geonames.org/export/dump/cities500.zip",
        "file": "cities500.zip",
        "txt": "cities500.txt",
        "description": "Cities with population > 500 (~145K cities)",
    },
    "1000": {
        "url": "https://download.geonames.org/export/dump/cities1000.zip",
        "file": "cities1000.zip",
        "txt": "cities1000.txt",
        "description": "Cities with population > 1,000 (~130K cities)",
    },
    "5000": {
        "url": "https://download.geonames.org/export/dump/cities5000.zip",
        "file": "cities5000.zip",
        "txt": "cities5000.txt",
        "description": "Cities with population > 5,000 (~50K cities)",
    },
    "15000": {
        "url": "https://download.geonames.org/export/dump/cities15000.zip",
        "file": "cities15000.zip",
        "txt": "cities15000.txt",
        "description": "Cities with population > 15,000 (~33K cities)",
    },
}

# Get threshold from command line or use default
threshold = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_THRESHOLD
if threshold not in GEONAMES_DATASETS:
    print(f"Invalid threshold: {threshold}")
    print(f"Available options: {', '.join(GEONAMES_DATASETS.keys())}")
    sys.exit(1)

dataset = GEONAMES_DATASETS[threshold]
GEONAMES_URL = dataset["url"]
GEONAMES_FILE = dataset["file"]
GEONAMES_TXT = dataset["txt"]

# Output directory
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "app" / "data"
OUTPUT_CSV = DATA_DIR / "geonames_cities.csv"

# GeoNames format (tab-separated)
# Columns: geonameid, name, asciiname, alternatenames, latitude, longitude,
#          feature class, feature code, country code, cc2, admin1 code, admin2 code,
#          admin3 code, admin4 code, population, elevation, dem, timezone, modification date


def download_geonames():
    """Download GeoNames cities database."""
    print(f"Downloading {GEONAMES_URL}...")
    zip_path = DATA_DIR / GEONAMES_FILE

    try:
        urllib.request.urlretrieve(GEONAMES_URL, zip_path)
        print(f"Downloaded to {zip_path}")
        return zip_path
    except Exception as e:
        print(f"Error downloading: {e}")
        return None


def extract_geonames(zip_path):
    """Extract the cities file from zip."""
    print(f"Extracting {zip_path}...")
    txt_path = DATA_DIR / GEONAMES_TXT

    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extract(GEONAMES_TXT, DATA_DIR)
        print(f"Extracted to {txt_path}")
        return txt_path
    except Exception as e:
        print(f"Error extracting: {e}")
        return None


def convert_to_csv(txt_path):
    """Convert GeoNames tab-separated file to CSV with our format."""
    print(f"Converting {txt_path} to CSV...")

    # GeoNames column indices
    GEONAMEID = 0
    NAME = 1
    ASCIINAME = 2
    ALTERNATENAMES = 3
    LATITUDE = 4
    LONGITUDE = 5
    FEATURE_CLASS = 6
    FEATURE_CODE = 7
    COUNTRY_CODE = 8
    ADMIN1_CODE = 10  # State/Province code
    ADMIN2_CODE = 11  # County/Region
    POPULATION = 14
    TIMEZONE = 17

    cities_written = 0

    try:
        with open(txt_path, "r", encoding="utf-8") as infile, open(
            OUTPUT_CSV, "w", encoding="utf-8", newline=""
        ) as outfile:
            writer = csv.writer(outfile)
            # Write header
            writer.writerow(
                [
                    "geonameid",
                    "name",
                    "asciiname",
                    "alternatenames",
                    "latitude",
                    "longitude",
                    "country_code",
                    "admin1_code",
                    "admin2_code",
                    "population",
                    "timezone",
                ]
            )

            for line in infile:
                fields = line.strip().split("\t")
                if len(fields) < 18:
                    continue

                # Only include cities (feature class P, feature codes PPL, PPLA, PPLA2, etc.)
                feature_class = fields[FEATURE_CLASS]
                feature_code = fields[FEATURE_CODE]

                if feature_class == "P":  # Populated place
                    geonameid = fields[GEONAMEID]
                    name = fields[NAME]
                    asciiname = fields[ASCIINAME]
                    alternatenames = (
                        fields[ALTERNATENAMES] if len(fields) > ALTERNATENAMES else ""
                    )
                    latitude = fields[LATITUDE]
                    longitude = fields[LONGITUDE]
                    country_code = fields[COUNTRY_CODE]
                    admin1_code = (
                        fields[ADMIN1_CODE] if len(fields) > ADMIN1_CODE else ""
                    )
                    admin2_code = (
                        fields[ADMIN2_CODE] if len(fields) > ADMIN2_CODE else ""
                    )
                    population = fields[POPULATION] if len(fields) > POPULATION else "0"
                    timezone = fields[TIMEZONE] if len(fields) > TIMEZONE else ""

                    writer.writerow(
                        [
                            geonameid,
                            name,
                            asciiname,
                            alternatenames,
                            latitude,
                            longitude,
                            country_code,
                            admin1_code,
                            admin2_code,
                            population,
                            timezone,
                        ]
                    )
                    cities_written += 1

        print(f"Converted {cities_written} cities to {OUTPUT_CSV}")
        return True
    except Exception as e:
        print(f"Error converting: {e}")
        return False


def cleanup_temp_files():
    """Remove temporary download files."""
    temp_files = [DATA_DIR / GEONAMES_FILE, DATA_DIR / GEONAMES_TXT]
    for file in temp_files:
        if file.exists():
            try:
                file.unlink()
                print(f"Removed {file.name}")
            except Exception as e:
                print(f"Could not remove {file.name}: {e}")


def main():
    """Main function."""
    print("GeoNames Cities Database Downloader")
    print("=" * 50)
    print(f"Dataset: {dataset['description']}")
    print(f"Downloading: {GEONAMES_FILE}")
    print("=" * 50)

    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Download
    zip_path = download_geonames()
    if not zip_path:
        return

    # Extract
    txt_path = extract_geonames(zip_path)
    if not txt_path:
        return

    # Convert to CSV
    if convert_to_csv(txt_path):
        print("\n" + "=" * 50)
        print("Success! GeoNames database ready at:", OUTPUT_CSV)
        print(f"Dataset: {dataset['description']}")
        print("=" * 50)
    else:
        print("\nFailed to convert GeoNames data")

    # Cleanup
    print("\nCleaning up temporary files...")
    cleanup_temp_files()

    print("\nDone!")


if __name__ == "__main__":
    main()
