"""Build the CTA rail ('L') layer from the real GTFS feed.

Stations are collapsed to GTFS parent_station (== the 4xxxx "map_id" that station-level ridership
is keyed on). Edges are consecutive stations on rail trips, weighted by the median scheduled
run time (seconds). Line membership is derived from the routes that traverse each edge/station.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from statistics import median

import networkx as nx

from ingest.gtfs import RAIL_LINE_NAMES, RAIL_ROUTE_TYPE, GTFSFeed, gtfs_time_to_seconds

log = logging.getLogger(__name__)


def _station_geo_and_names(feed: GTFSFeed) -> tuple[dict[str, tuple[float, float]], dict[str, str]]:
    """Map each map_id -> (lat, lon) and -> clean station name."""
    stops = feed.stops()
    geo: dict[str, list[tuple[float, float]]] = defaultdict(list)
    names: dict[str, str] = {}

    # Station-level rows (location_type == 1): authoritative name + geo, keyed by their own id.
    for _, row in stops[stops["location_type"] == 1].iterrows():
        sid = str(row["stop_id"])
        names[sid] = str(row["stop_name"])
        geo[sid].append((float(row["stop_lat"]), float(row["stop_lon"])))

    # Platform rows contribute geo to their parent, and a fallback name.
    plats = stops[(stops["location_type"] == 0) & stops["parent_station"].notna()]
    for _, row in plats.iterrows():
        parent = str(row["parent_station"])
        geo[parent].append((float(row["stop_lat"]), float(row["stop_lon"])))
        names.setdefault(parent, str(row["stop_name"]))

    centroids = {
        mid: (sum(la for la, _ in pts) / len(pts), sum(lo for _, lo in pts) / len(pts))
        for mid, pts in geo.items()
    }
    return centroids, names


def build_rail_graph(gtfs_path: Path) -> nx.Graph:
    """Return the rail layer as an undirected graph with geo, travel-time, and line attributes."""
    feed = GTFSFeed(gtfs_path)

    rail_routes = set(feed.route_ids(RAIL_ROUTE_TYPE))
    trips = feed.trips(rail_routes)
    trip_to_line = {
        t: RAIL_LINE_NAMES.get(r, r)
        for t, r in zip(trips["trip_id"], trips["route_id"], strict=True)
    }
    rail_trip_ids = set(trips["trip_id"])
    log.info("Rail routes: %d, rail trips: %d", len(rail_routes), len(rail_trip_ids))

    st = feed.stop_times_for_trips(rail_trip_ids)
    log.info("Rail stop_times rows: %d", len(st))

    # platform stop_id -> parent_station (map_id)
    stops = feed.stops()
    stop2station = {
        str(r.stop_id): str(r.parent_station)
        for r in stops.itertuples()
        if str(getattr(r, "parent_station", "nan")) not in ("nan", "None", "")
    }

    geo, names = _station_geo_and_names(feed)

    # Aggregate edges: {(a,b): {"times": [...], "lines": set()}}
    edges: dict[tuple[str, str], dict] = defaultdict(lambda: {"times": [], "lines": set()})
    st = st.sort_values(["trip_id", "stop_sequence"])
    for trip_id, grp in st.groupby("trip_id", sort=False):
        line = trip_to_line.get(str(trip_id), "?")
        rows = grp.to_dict("records")
        for cur, nxt in zip(rows, rows[1:], strict=False):
            a = stop2station.get(str(cur["stop_id"]))
            b = stop2station.get(str(nxt["stop_id"]))
            if not a or not b or a == b:
                continue
            key = tuple(sorted((a, b)))
            dep = gtfs_time_to_seconds(cur["departure_time"])
            arr = gtfs_time_to_seconds(nxt["arrival_time"])
            if dep is not None and arr is not None and 0 < arr - dep < 3600:
                edges[key]["times"].append(arr - dep)
            edges[key]["lines"].add(line)

    G = nx.Graph()
    node_lines: dict[str, set] = defaultdict(set)
    for (a, b), attrs in edges.items():
        node_lines[a] |= attrs["lines"]
        node_lines[b] |= attrs["lines"]

    for mid in node_lines:
        lat, lon = geo.get(mid, (None, None))
        G.add_node(
            mid, station_id=mid, name=names.get(mid, mid),
            lat=lat, lon=lon, lines=sorted(node_lines[mid]),
            ridership=0.0, layer="rail",
        )
    for (a, b), attrs in edges.items():
        tt = median(attrs["times"]) if attrs["times"] else 120.0
        G.add_edge(a, b, travel_time=float(tt), weight=float(tt),
                   lines=sorted(attrs["lines"]), layer="rail")

    log.info("Rail graph: %d stations, %d edges", G.number_of_nodes(), G.number_of_edges())
    return G
