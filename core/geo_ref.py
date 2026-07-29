"""Named Chicago landmarks (lat, lon) for ergonomic spatial-hazard scenarios."""

from __future__ import annotations

LANDMARKS: dict[str, tuple[float, float]] = {
    "loop": (41.8786, -87.6251),        # downtown / the Loop
    "downtown": (41.8786, -87.6251),
    "ohare": (41.9786, -87.9048),       # O'Hare airport
    "midway": (41.7868, -87.7522),      # Midway airport
    "north_side": (41.9500, -87.6600),
    "south_side": (41.7500, -87.6200),
    "west_side": (41.8800, -87.7200),
    "riverfront": (41.8880, -87.6330),  # near the Chicago River (flood-relevant)
}
