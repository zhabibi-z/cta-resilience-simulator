"""Hazard models — what fails, and how the disruption is seeded.

A hazard turns a scenario name ("flood the Loop", "attack the busiest hub", "lose a track segment")
into the concrete set of initially-failed nodes and edges that the resilience engine then cascades
from. Spatial hazards use station/stop geography, so a flood or storm degrades BOTH the rail and
bus layers in a region at once — the multi-modal disruption the flood/storm literature calls for.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import networkx as nx
import numpy as np

from core.geo_ref import LANDMARKS
from core.load_models import BetweennessLoad, LoadModel
from ingest.geo import haversine_m


@dataclass
class Hazard:
    nodes: set[str] = field(default_factory=set)          # initially-failed stations/stops
    edges: list[tuple[str, str]] = field(default_factory=list)  # initially-failed track/route links
    label: str = "hazard"


class HazardModel(Protocol):
    def generate(self, G: nx.Graph, rng: np.random.Generator) -> Hazard: ...


def _node_ridership(G: nx.Graph, n: str) -> float:
    return float(G.nodes[n].get("ridership", 0.0) or 0.0)


class TargetedStationHazard:
    """Fail the k highest-impact stations (by load or by ridership)."""

    def __init__(self, k: int = 1, by: str = "load", load_model: LoadModel | None = None) -> None:
        self.k, self.by = k, by
        self.load_model = load_model or BetweennessLoad()

    def generate(self, G: nx.Graph, rng: np.random.Generator) -> Hazard:
        rail = [n for n, a in G.nodes(data=True) if a.get("layer") == "rail"]
        if self.by == "ridership":
            score = {n: _node_ridership(G, n) for n in rail}
        else:
            load = self.load_model.compute(G)
            score = {n: load.get(n, 0.0) for n in rail}
        top = sorted(rail, key=lambda n: score[n], reverse=True)[: self.k]
        return Hazard(nodes=set(top), label=f"targeted:{self.by}:k={self.k}")


class RandomStationHazard:
    """Fail k random stations (Monte-Carlo baseline)."""

    def __init__(self, k: int = 1) -> None:
        self.k = k

    def generate(self, G: nx.Graph, rng: np.random.Generator) -> Hazard:
        rail = [n for n, a in G.nodes(data=True) if a.get("layer") == "rail"]
        chosen = rng.choice(rail, size=min(self.k, len(rail)), replace=False)
        return Hazard(nodes=set(map(str, chosen)), label=f"random:k={self.k}")


class SpatialHazard:
    """Flood/storm: fail every node within `radius_m` of a geographic centre — both layers.

    `center` may be a (lat, lon) tuple or a named CTA landmark ("loop", "ohare", ...).
    """

    def __init__(self, center, radius_m: float = 1500.0, layers: tuple[str, ...] = ("rail", "bus")):
        self.center = LANDMARKS[center] if isinstance(center, str) else center
        self.radius_m = radius_m
        self.layers = layers

    def generate(self, G: nx.Graph, rng: np.random.Generator) -> Hazard:
        clat, clon = self.center
        hit = {
            n for n, a in G.nodes(data=True)
            if a.get("layer") in self.layers and a.get("lat") is not None
            and haversine_m(clat, clon, a["lat"], a["lon"]) <= self.radius_m
        }
        return Hazard(nodes=hit, label=f"spatial:({clat:.3f},{clon:.3f}):r={self.radius_m:.0f}m")


class EdgeHazard:
    """Fail specific track/route segments (edges), or the k highest-betweenness edges."""

    def __init__(self, edges: list[tuple[str, str]] | None = None, k_top: int = 0) -> None:
        self.edges = edges or []
        self.k_top = k_top

    def generate(self, G: nx.Graph, rng: np.random.Generator) -> Hazard:
        edges = list(self.edges)
        if self.k_top:
            eb = nx.edge_betweenness_centrality(G, weight="travel_time")
            edges += [e for e, _ in sorted(eb.items(), key=lambda x: x[1], reverse=True)[: self.k_top]]
        edges = [e for e in edges if G.has_edge(*e)]
        return Hazard(edges=edges, label=f"edge:n={len(edges)}")
