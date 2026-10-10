"""Pure-Python geospatial helpers for map-based property search.

No PostGIS dependency: a bounding-box pre-filter runs in SQL and
a precise haversine refinement runs in Python. Works on both
SQLite (dev) and PostgreSQL (production).
"""

import math

from rest_framework.exceptions import ValidationError

EARTH_RADIUS_KM = 6371.0

# Approximate kilometres per degree of latitude.
KM_PER_LAT_DEG = 111.0

# Maximum allowed search radius (km).
MAX_RADIUS_KM = 200.0

# Well-known Kenya county centroids (public geographic facts).
# Used ONLY to centre the map when a county has no geocoded
# properties yet — property data itself always comes from the DB.
COUNTY_CENTROIDS = {
    "nairobi": (-1.2921, 36.8219),
    "mombasa": (-4.0435, 39.6682),
    "kiambu": (-1.1667, 36.8333),
    "nakuru": (-0.2819, 36.0635),
    "kisumu": (-0.1022, 34.7617),
    "machakos": (-1.5197, 37.2632),
    "kajiado": (-2.3750, 36.7833),
    "uasin gishu": (0.5333, 35.2833),
    "kericho": (-0.3690, 35.2822),
    "meru": (0.0476, 37.6505),
    "tharaka-nithi": (-0.5500, 38.0667),
    "embu": (-0.5333, 37.4500),
    "kitui": (-1.3667, 38.0167),
    "murang'a": (-0.7000, 37.1500),
    "nyandarua": (-0.4167, 36.6833),
    "nyeri": (-0.4167, 36.9500),
    "kakamega": (0.2833, 34.7500),
    "bungoma": (0.5667, 34.5667),
    "siaya": (0.0667, 34.2833),
    "kisii": (-0.6833, 34.7833),
    "busia": (0.4667, 34.1167),
    "bomet": (-0.7167, 35.3500),
    "nandi": (0.1667, 35.0000),
    "laikipia": (0.3500, 37.0833),
    "trans nzoia": (0.6167, 34.9667),
    "elgeyo-marakwet": (0.7833, 35.3000),
    "west pokot": (1.1500, 35.1333),
    "samburu": (0.8167, 37.0833),
    "turkana": (3.3167, 35.5833),
    "homabay": (-0.5333, 34.4500),
    "migori": (-1.0667, 34.4833),
    "nyamira": (-0.6833, 34.9167),
    "narok": (-1.0833, 35.8667),
    "kilifi": (-3.6333, 39.8500),
    "kwale": (-4.1667, 39.5167),
    "tana river": (-1.6333, 40.0667),
    "lamu": (-2.2667, 40.9000),
    "taita-taveta": (-3.3333, 38.3333),
    "garissa": (-0.4667, 39.6500),
    "wajir": (1.6833, 40.0500),
    "mandera": (3.9333, 41.8500),
    "marsabit": (2.3167, 37.9833),
    "isiolo": (0.3500, 37.5833),
    "baringo": (0.5333, 35.7500),
    "vihiga": (0.0333, 34.6833),
    "homa bay": (-0.5333, 34.4500),
}


def haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance between two points, in kilometres."""
    lat1, lng1, lat2, lng2 = map(
        math.radians, (float(lat1), float(lng1), float(lat2), float(lng2))
    )
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def bounding_box(lat, lng, radius_km):
    """Rough lat/lng bounding box that fully contains a radius circle."""
    lat_span = radius_km / KM_PER_LAT_DEG
    # Shrink the longitude span as you approach the poles.
    lng_span = radius_km / (KM_PER_LAT_DEG * max(math.cos(math.radians(lat)), 0.01))
    return (lat - lat_span, lat + lat_span, lng - lng_span, lng + lng_span)


def parse_latitude(raw):
    try:
        lat = float(raw)
    except (TypeError, ValueError):
        raise ValidationError({"latitude": "Must be a number."})
    if not -90.0 <= lat <= 90.0:
        raise ValidationError({"latitude": "Must be between -90 and 90."})
    return lat


def parse_longitude(raw):
    try:
        lng = float(raw)
    except (TypeError, ValueError):
        raise ValidationError({"longitude": "Must be a number."})
    if not -180.0 <= lng <= 180.0:
        raise ValidationError({"longitude": "Must be between -180 and 180."})
    return lng


def parse_radius(raw):
    if raw in (None, ""):
        return 10.0
    try:
        radius = float(raw)
    except (TypeError, ValueError):
        raise ValidationError({"radius": "Must be a number."})
    if not 0.1 <= radius <= MAX_RADIUS_KM:
        raise ValidationError(
            {"radius": f"Must be between 0.1 and {int(MAX_RADIUS_KM)} km."}
        )
    return radius


def parse_bound(raw, label, lower, upper):
    if raw in (None, ""):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValidationError({label: "Must be a number."})
    if not lower <= value <= upper:
        raise ValidationError({label: f"Must be between {lower} and {upper}."})
    return value


def county_centroid(county_name):
    """Approximate centroid for a county name, if known."""
    return COUNTY_CENTROIDS.get((county_name or "").strip().lower())
