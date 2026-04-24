#!/bin/bash
# Download Erik Flowers Weather Icons font for the weather plugin

FONT_DIR="$HOME/inkyberry/fonts"
FONT_FILE="$FONT_DIR/weathericons-regular-webfont.ttf"

mkdir -p "$FONT_DIR"

if [ -f "$FONT_FILE" ]; then
    echo "Weather icons font already downloaded: $FONT_FILE"
    exit 0
fi

echo "Downloading Erik Flowers Weather Icons font..."
curl -L -o "$FONT_FILE" \
    "https://github.com/erikflowers/weather-icons/raw/master/font/weathericons-regular-webfont.ttf"

if [ -f "$FONT_FILE" ]; then
    echo "Downloaded successfully: $FONT_FILE"
else
    echo "Download failed!"
    exit 1
fi
