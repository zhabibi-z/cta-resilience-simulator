"""Build an aggregated CTA bus layer from real GTFS.

The full bus network is ~10k stops — too fine (and bus-dominated) for a tractable cascade model.
We aggregate:
  * one representative trip per route defines that route's stop path (cheap: ~125 trips, not millions);
  * stops are snapped to a spatial grid, so a bus node is a ~1 km neighbourhood cell;
  * each route's ridership is apportioned evenly across the cells it traverses.

The result is a coarse but geographically-faithful bus layer that (a) provides substitution capacity
near rail, and (b) is itself hit by spatially-correlated hazards (flood/storm) — the bilayer the
rainstorm/flood literature calls for.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path

import networkx as nx

from ingest.geo import grid_cell
from ingest.gtfs import BUS_ROUTE_TYPE, GTFSFeed

log = logging.getLogger(__name__)

DEFAULT_GRID_DEG = 0.01  # ~1.1 km lat / ~0.8 km lon at Chicago's latitude


def _cell_id(cell: tuple[float, float]) -> str:
    return f"B:{cell[0]:.4f},{cell[1]:.4f}"


def build_bus_graph(gtfs_path: Path, ridership: dict[str, float] | None = None,
                    grid_size_deg: float = DEFAULT_GRID_DEG) -> nx.Graph:
    """Return the aggregated bus layer (grid-cell nodes, route-adjacency edges, ridership weights)."""
    feed = GTFSFeed(gtfs_path)
    ridership = ridership or {}

    routes_df = feed.table("routes.txt", dtype=str)
    bus_routes = set(feed.route_ids(BUS_ROUTE_TYPE))
    # route_id -> route_short_name: the short name (route number) is the key the ridership
    # dataset uses, so we label bus routes by it to join ridership robustly.
    rid_to_short = {
        r.route_id: (r.route_short_name if isinstance(r.route_short_name, str) else r.route_id)
        for r in routes_df.itertuples()
    }
    trips = feed.trips(bus_routes)
    # One representative trip per route (first seen) — enough to define the route's stop path.
    rep = trips.drop_duplicates(subset="route_id", keep="first")
    rep_trip_to_route = {
        t: rid_to_short.get(rid, rid)
        for t, rid in zip(rep["trip_id"], rep["route_id"], strict=True)
    }
    rep_trip_ids = set(rep["trip_id"])
    log.info("Bus routes: %d (representative trips: %d)", len(bus_routes), len(rep_trip_ids))

    st = feed.stop_times_for_trips(rep_trip_ids).sort_values(["trip_id", "stop_sequence"])

    stops = feed.stops()
    stop_geo = {
        str(r.stop_id): (float(r.stop_lat), float(r.stop_lon))
        for r in stops.itertuples()
    }

    cell_center: dict[str, tuple[float, float]] = {}
    cell_routes: dict[str, set[str]] = defaultdict(set)
    route_cells: dict[str, list[str]] = defaultdict(list)
    edges: dict[tuple[str, str], set[str]] = defaultdict(set)

    for trip_id, grp in st.groupby("trip_id", sort=False):
        route = rep_trip_to_route[str(trip_id)]
        seq_cells: list[str] = []
        for stop_id in grp["stop_id"].astype(str):
            geo = stop_geo.get(stop_id)
            if geo is None:
                continue
            cell = grid_cell(geo[0], geo[1], grid_size_deg)
            cid = _cell_id(cell)
            cell_center.setdefault(cid, cell)
            cell_routes[cid].add(route)
            if not seq_cells or seq_cells[-1] != cid:
                seq_cells.append(cid)
        route_cells[route] = seq_cells
        for a, b in zip(seq_cells, seq_cells[1:], strict=False):
            edges[tuple(sorted((a, b)))].add(route)

    # Apportion each route's ridership evenly across the cells it traverses.
    cell_ridership: dict[str, float] = defaultdict(float)
    for route, cells in route_cells.items():
        if not cells:
            continue
        share = float(ridership.get(route, 0.0)) / len(set(cells))
        for cid in set(cells):
            cell_ridership[cid] += share

    G = nx.Graph()
    for cid, center in cell_center.items():
        G.add_node(cid, node_id=cid, lat=center[0], lon=center[1], layer="bus",
                   ridership=round(cell_ridership.get(cid, 0.0), 1),
                   routes=sorted(cell_routes[cid]))
    for (a, b), routes in edges.items():
        if a == b:
            continue
        G.add_edge(a, b, layer="bus", routes=sorted(routes), weight=1.0)

    log.info("Bus layer: %d cells, %d edges", G.number_of_nodes(), G.number_of_edges())
    return G
