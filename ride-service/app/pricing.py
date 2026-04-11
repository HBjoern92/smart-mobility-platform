import math

from app.config import settings


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Haversine formula – straight-line distance between two lat/lon points.
    Returns distance in kilometres.
    """
    R = 6371.0  # Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def calculate_price(distance_km: float) -> float:
    """EUR price = distance × price_per_km, rounded to 2 decimal places."""
    return round(distance_km * settings.price_per_km, 2)


def calculate_eta(distance_km: float) -> float:
    """ETA in minutes, assuming constant speed."""
    return round((distance_km / settings.speed_kmh) * 60, 1)
