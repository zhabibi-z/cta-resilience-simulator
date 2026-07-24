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

from ingest.datasets import CACHE_DIR
from ingest.download import download_gtfs
from ingest.rail import build_rail_graph
from ingest.ridership import attach_station_ridership, station_ridership

log = logging.getLogger(__name__)

_NETWORK_CACHE = CACHE_DIR / "cta_network.gpickle"


def build_cta_network(ridership_since: str = "2023-01-01",
                      gtfs_max_age_days: float | None = 30) -> nx.Graph:
    """Build the canonical CTA network from real data (rail layer + real ridership)."""
    gtfs = download_gtfs(max_age_days=gtfs_max_age_days)
    G = build_rail_graph(gtfs)
    matched, unmatched = attach_station_ridership(G, station_ridership(since=ridership_since))
    log.info("Ridership attached to %d/%d rail stations", matched, G.number_of_nodes())
    G.graph["source"] = "CTA GTFS + Chicago Data Portal ridership"
    G.graph["ridership_since"] = ridership_since
    G.graph["layers"] = ["rail"]
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
    total_rides = sum(a.get("ridership", 0.0) for _, a in G.nodes(data=True))
    return {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "rail_stations": len(rail),
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
