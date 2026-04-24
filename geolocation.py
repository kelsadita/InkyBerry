"""
InkyBerry Geolocation Module
Auto-detects location via IP geolocation, with config fallback.
"""

import logging
import requests

logger = logging.getLogger("inkyberry.geolocation")

# Default fallback: New York, NY
DEFAULT_LAT = 40.7128
DEFAULT_LON = -74.0060
DEFAULT_CITY = "New York, NY"

_cached = None


def get_location(config):
    """
    Return (lat, lon, city_name).

    Priority:
      1. Config values if explicitly set (latitude + longitude both present)
      2. IP geolocation auto-detect (cached after first call)
      3. NYC defaults as final fallback
    """
    global _cached

    weather_cfg = config.get("weather", {})

    # If user explicitly set both lat/lon in config, use those
    if "latitude" in weather_cfg and "longitude" in weather_cfg:
        lat = weather_cfg["latitude"]
        lon = weather_cfg["longitude"]
        city = weather_cfg.get("location_name", "")
        if not city:
            city = f"{lat:.2f}, {lon:.2f}"
        logger.info(f"Using configured location: {city} ({lat}, {lon})")
        return lat, lon, city

    # Try auto-detect (cache result so we only call once per session)
    if _cached is not None:
        return _cached

    _cached = _auto_detect()
    return _cached


def _auto_detect():
    """Try IP geolocation services. Returns (lat, lon, city)."""
    # Try ip-api.com first (free, no key, 45 req/min)
    try:
        resp = requests.get(
            "http://ip-api.com/json/?fields=lat,lon,city,regionName",
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            lat = data.get("lat")
            lon = data.get("lon")
            city = data.get("city", "")
            region = data.get("regionName", "")
            if lat and lon:
                name = f"{city}, {region}" if region else city
                logger.info(f"Auto-detected location: {name} ({lat}, {lon})")
                return lat, lon, name
    except Exception as e:
        logger.debug(f"ip-api.com failed: {e}")

    # Fallback: ipinfo.io
    try:
        resp = requests.get("https://ipinfo.io/json", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            loc = data.get("loc", "")  # "lat,lon"
            if loc and "," in loc:
                lat, lon = [float(x) for x in loc.split(",")]
                city = data.get("city", "")
                region = data.get("region", "")
                name = f"{city}, {region}" if region else city
                logger.info(f"Auto-detected location: {name} ({lat}, {lon})")
                return lat, lon, name
    except Exception as e:
        logger.debug(f"ipinfo.io failed: {e}")

    # Final fallback
    logger.warning(f"Location auto-detect failed, using default: {DEFAULT_CITY}")
    return DEFAULT_LAT, DEFAULT_LON, DEFAULT_CITY
