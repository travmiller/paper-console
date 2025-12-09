#!/usr/bin/env python3
"""
Download and process GeoNames cities database.
Downloads cities15000.zip (cities with population > 15,000) and converts to CSV format.
"""

import urllib.request
import zipfile
import csv
import os
from pathlib import Path

# GeoNames download URL
GEONAMES_URL = "https://download.geonames.org/export/dump/cities15000.zip"
GEONAMES_FILE = "cities15000.zip"
GEONAMES_TXT = "cities15000.txt"

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
                print(f"Removed {file}")
            except Exception as e:
                print(f"Could not remove {file}: {e}")


def main():
    """Main function."""
    print("GeoNames Cities Database Downloader")
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
        print("\nSuccess! GeoNames database ready at:", OUTPUT_CSV)
        print(f"  Total cities: Check the file for count")
    else:
        print("\nFailed to convert GeoNames data")

    # Cleanup
    print("\nCleaning up temporary files...")
    cleanup_temp_files()

    print("\nDone!")


if __name__ == "__main__":
    main()
