"""Canonical CTA network builder — the single entry point the rest of the system consumes.

Produces one attributed graph from real open data (GTFS topology/geo + Socrata ridership) and
caches it so downstream simulation/analysis is fast and offline. Phase 0 ships the rail layer;
the aggregated bus layer + transfer edges attach here in the next increment without changing this
interface.
"""

from __future__ import annotations

import logging
import pickle

import networkx as nx

from ingest.bus import DEFAULT_GRID_DEG, build_bus_graph
from ingest.datasets import CACHE_DIR
from ingest.download import download_gtfs
from ingest.rail import build_rail_graph
from ingest.ridership import (
    attach_station_ridership,
    bus_route_ridership,
    station_ridership,
)
from ingest.transfers import add_transfer_edges

log = logging.getLogger(__name__)

_NETWORK_CACHE = CACHE_DIR / "cta_network.gpickle"


def build_cta_network(ridership_since: str = "2023-01-01",
                      gtfs_max_age_days: float | None = 30,
                      bus: bool = True,
                      grid_size_deg: float = DEFAULT_GRID_DEG,
                      transfer_max_m: float = 500.0) -> nx.Graph:
    """Build the canonical CTA bilayer network from real data.

    rail (GTFS + station ridership) ∪ aggregated bus (GTFS + route ridership) coupled by
    walking-distance transfer edges. `bus=False` yields the rail-only graph.
    """
    gtfs = download_gtfs(max_age_days=gtfs_max_age_days)
    rail = build_rail_graph(gtfs)
    matched, _ = attach_station_ridership(rail, station_ridership(since=ridership_since))
    log.info("Ridership attached to %d/%d rail stations", matched, rail.number_of_nodes())

    if not bus:
        rail.graph.update(source="CTA GTFS + Chicago Data Portal ridership",
                          ridership_since=ridership_since, layers=["rail"])
        return rail

    bus_g = build_bus_graph(gtfs, bus_route_ridership(since=ridership_since), grid_size_deg)
    G = nx.union(rail, bus_g)  # rail ids are numeric map_ids, bus ids are "B:lat,lon" → disjoint
    n_transfers = add_transfer_edges(G, walk_max_m=transfer_max_m)
    G.graph.update(
        source="CTA GTFS + Chicago Data Portal ridership",
        ridership_since=ridership_since,
        layers=["rail", "bus"],
        n_transfer_edges=n_transfers,
    )
    return G


def load_or_build_network(force: bool = False, **kwargs) -> nx.Graph:
    """Return the cached network, building (and caching) it on first use or when `force`."""
    if not force and _NETWORK_CACHE.exists():
        log.info("Network cache hit: %s", _NETWORK_CACHE)
        with _NETWORK_CACHE.open("rb") as fh:
            return pickle.load(fh)
    G = build_cta_network(**kwargs)
    _NETWORK_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with _NETWORK_CACHE.open("wb") as fh:
        pickle.dump(G, fh)
    log.info("Network cached: %s", _NETWORK_CACHE)
    return G


def summarize(G: nx.Graph) -> dict:
    rail = [n for n, a in G.nodes(data=True) if a.get("layer") == "rail"]
    busn = [n for n, a in G.nodes(data=True) if a.get("layer") == "bus"]
    transfers = sum(1 for *_, a in G.edges(data=True) if a.get("layer") == "transfer")
    total_rides = sum(a.get("ridership", 0.0) for _, a in G.nodes(data=True))
    return {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "rail_stations": len(rail),
        "bus_cells": len(busn),
        "transfer_edges": transfers,
        "connected": nx.is_connected(G) if G.number_of_nodes() else False,
        "components": nx.number_connected_components(G),
        "total_weekday_boardings": round(total_rides),
        "layers": G.graph.get("layers"),
        "source": G.graph.get("source"),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    G = load_or_build_network(force=True)
    print("\n=== CTA network built from real data ===")
    for k, v in summarize(G).items():
        print(f"  {k:24s} {v}")


if __name__ == "__main__":
    main()
