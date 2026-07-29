"""Small geographic helpers (no external geo dependency)."""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

_EARTH_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two WGS84 points."""
    p1, p2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlmb = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlmb / 2) ** 2
    return 2 * _EARTH_M * asin(sqrt(a))


def grid_cell(lat: float, lon: float, size_deg: float) -> tuple[float, float]:
    """Snap a point to the centre of a `size_deg`-degree grid cell (for spatial aggregation)."""
    return (round(lat / size_deg) * size_deg, round(lon / size_deg) * size_deg)
