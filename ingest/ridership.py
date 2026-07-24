"""Real CTA ridership → network weights.

Station-level 'L' boardings (keyed by map_id, matching GTFS parent_station) become rail node
weights; bus route boardings become the weight applied to the aggregated bus layer. Ridership is
averaged over a recent window of weekday service using server-side Socrata aggregation.
"""

from __future__ import annotations

import logging

from ingest.datasets import BUS_ROUTE_RIDERSHIP, L_STATION_RIDERSHIP
from ingest.download import fetch_socrata

log = logging.getLogger(__name__)

# daytype 'W' = weekday (also 'A' Saturday, 'U' Sunday/holiday).
_WEEKDAY = "W"


def station_ridership(since: str = "2023-01-01") -> dict[str, float]:
    """Mean weekday daily boardings per 'L' station (map_id) since `since` (YYYY-MM-DD)."""
    rows = fetch_socrata(
        L_STATION_RIDERSHIP,
        soql={
            "$select": "station_id, avg(rides) as avg_rides",
            "$where": f"daytype='{_WEEKDAY}' AND date >= '{since}T00:00:00'",
            "$group": "station_id",
            "$order": "station_id",
        },
    )
    out = {str(r["station_id"]): float(r["avg_rides"]) for r in rows if r.get("avg_rides")}
    log.info("Station ridership: %d stations (mean weekday boardings since %s)", len(out), since)
    return out


def bus_route_ridership(since: str = "2023-01-01") -> dict[str, float]:
    """Mean weekday daily boardings per bus route since `since`."""
    rows = fetch_socrata(
        BUS_ROUTE_RIDERSHIP,
        soql={
            "$select": "route, avg(rides) as avg_rides",
            "$where": f"daytype='{_WEEKDAY}' AND date >= '{since}T00:00:00'",
            "$group": "route",
            "$order": "route",
        },
    )
    out = {str(r["route"]): float(r["avg_rides"]) for r in rows if r.get("avg_rides")}
    log.info("Bus route ridership: %d routes", len(out))
    return out


def attach_station_ridership(graph, ridership: dict[str, float]) -> tuple[int, int]:
    """Attach ridership to rail nodes in-place. Returns (matched, unmatched) counts."""
    matched = 0
    for node, attrs in graph.nodes(data=True):
        if attrs.get("layer") != "rail":
            continue
        r = ridership.get(str(node))
        if r is not None:
            attrs["ridership"] = float(r)
            matched += 1
    unmatched = sum(
        1 for _, a in graph.nodes(data=True)
        if a.get("layer") == "rail" and a.get("ridership", 0.0) == 0.0
    )
    return matched, unmatched
