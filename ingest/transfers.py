"""Rail<->bus transfer edges — the coupling that makes the bilayer a bilayer.

A transfer edge connects a rail station to a nearby bus cell (within walking distance), so that
when rail fails, displaced demand can reach the bus layer, and a spatial hazard hitting a region
degrades both layers together.
"""

from __future__ import annotations

import logging

import networkx as nx

from ingest.geo import haversine_m

log = logging.getLogger(__name__)

_WALK_SPEED_MPS = 1.35  # ~4.9 km/h


def add_transfer_edges(G: nx.Graph, walk_max_m: float = 600.0) -> int:
    """Add rail<->bus transfer edges.

    Every rail station is connected to bus cells within `walk_max_m`; if none qualify (a bus-grid
    aggregation artefact), it is connected to its single nearest bus cell so the bilayer is always
    coupled — CTA rail stations essentially all have nearby bus service.
    """
    rail = [(n, a["lat"], a["lon"]) for n, a in G.nodes(data=True)
            if a.get("layer") == "rail" and a.get("lat") is not None]
    bus = [(n, a["lat"], a["lon"]) for n, a in G.nodes(data=True)
           if a.get("layer") == "bus" and a.get("lat") is not None]

    def _link(rn: str, bn: str, d: float) -> None:
        G.add_edge(rn, bn, layer="transfer", weight=d / _WALK_SPEED_MPS, distance_m=round(d))

    added = 0
    for rn, rlat, rlon in rail:
        nearest, nearest_d = None, float("inf")
        linked_here = False
        for bn, blat, blon in bus:
            if abs(rlat - blat) > 0.02 or abs(rlon - blon) > 0.02:
                continue
            d = haversine_m(rlat, rlon, blat, blon)
            if d < nearest_d:
                nearest, nearest_d = bn, d
            if d <= walk_max_m:
                _link(rn, bn, d)
                added += 1
                linked_here = True
        if not linked_here and nearest is not None:
            _link(rn, nearest, nearest_d)
            added += 1
    log.info("Transfer edges added: %d (walk <= %.0f m, nearest-cell fallback)", added, walk_max_m)
    return added
