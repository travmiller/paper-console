#!/bin/bash

# Download IBM Plex fonts from official GitHub repository
# This script downloads the woff2 files directly from the IBM Plex GitHub repo

FONTS_DIR="public/fonts"
mkdir -p "$FONTS_DIR"

BASE_URL="https://github.com/IBM/plex/raw/master/IBM-Plex-Sans/fonts/complete/woff2"
MONO_BASE_URL="https://github.com/IBM/plex/raw/master/IBM-Plex-Mono/fonts/complete/woff2"

echo "Downloading IBM Plex Sans fonts..."

# IBM Plex Sans - Regular (400)
curl -L -o "$FONTS_DIR/IBMPlexSans-Regular.woff2" \
  "$BASE_URL/IBMPlexSans-Regular.woff2"

# IBM Plex Sans - Medium (500)
curl -L -o "$FONTS_DIR/IBMPlexSans-Medium.woff2" \
  "$BASE_URL/IBMPlexSans-Medium.woff2"

# IBM Plex Sans - SemiBold (600)
curl -L -o "$FONTS_DIR/IBMPlexSans-SemiBold.woff2" \
  "$BASE_URL/IBMPlexSans-SemiBold.woff2"

# IBM Plex Sans - Bold (700)
curl -L -o "$FONTS_DIR/IBMPlexSans-Bold.woff2" \
  "$BASE_URL/IBMPlexSans-Bold.woff2"

echo "Downloading IBM Plex Mono fonts..."

# IBM Plex Mono - Regular (400)
curl -L -o "$FONTS_DIR/IBMPlexMono-Regular.woff2" \
  "$MONO_BASE_URL/IBMPlexMono-Regular.woff2"

# IBM Plex Mono - Medium (500)
curl -L -o "$FONTS_DIR/IBMPlexMono-Medium.woff2" \
  "$MONO_BASE_URL/IBMPlexMono-Medium.woff2"

# IBM Plex Mono - SemiBold (600)
curl -L -o "$FONTS_DIR/IBMPlexMono-SemiBold.woff2" \
  "$MONO_BASE_URL/IBMPlexMono-SemiBold.woff2"

# IBM Plex Mono - Bold (700)
curl -L -o "$FONTS_DIR/IBMPlexMono-Bold.woff2" \
  "$MONO_BASE_URL/IBMPlexMono-Bold.woff2"

echo "All fonts downloaded successfully!"

