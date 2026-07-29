"""Pluggable load models (Strategy).

The cascade engine asks a load model "how much load sits on each node given the current network?".
Swapping the model changes *what* cascades on — while the Motter-Lai capacity/overload mechanics
stay identical.

  * BetweennessLoad   — strict Motter-Lai (2002) baseline: unweighted betweenness centrality.
  * PassengerFlowLoad — real passenger load: a gravity OD demand (ridership_i x ridership_j) routed
                        on travel-time shortest paths; a node's load is the through-flow it carries.

BetweennessLoad is the default everywhere, so existing behaviour is unchanged.
"""

from __future__ import annotations

from typing import Protocol

import networkx as nx

from core.metrics import unnormalized_betweenness


class LoadModel(Protocol):
    name: str

    def compute(self, G: nx.Graph) -> dict[str, float]:
        """Return the current load on every node of G."""
        ...


class BetweennessLoad:
    """Strict Motter-Lai load: unweighted, unnormalized betweenness centrality."""

    name = "betweenness"

    def compute(self, G: nx.Graph) -> dict[str, float]:
        return unnormalized_betweenness(G)


def _edge_time(_u, _v, data: dict) -> float:
    # Route on scheduled run time where present (rail), else the generic weight, else 1 hop.
    return float(data.get("travel_time", data.get("weight", 1.0)))


class PassengerFlowLoad:
    """Gravity passenger-flow load.

    Demand between two stations is proportional to the product of their ridership; it travels the
    fastest (shortest travel-time) path, and each node accumulates the flow passing through it.
    To stay tractable on the full bilayer, only the `max_sources` highest-ridership nodes seed
    demand (they dominate real OD flow); this is exact for those origins.
    """

    name = "passenger_flow"

    def __init__(self, max_sources: int = 150) -> None:
        self.max_sources = max_sources

    def compute(self, G: nx.Graph) -> dict[str, float]:
        load = dict.fromkeys(G.nodes(), 0.0)
        rid = {n: float(G.nodes[n].get("ridership", 0.0) or 0.0) for n in G}
        total = sum(rid.values())
        if total <= 0:
            return load

        sources = sorted((n for n in G if rid[n] > 0), key=lambda n: rid[n], reverse=True)
        sources = sources[: self.max_sources]

        for s in sources:
            dist, paths = nx.single_source_dijkstra(G, s, weight=_edge_time)
            for t, path in paths.items():
                if t == s or rid[t] <= 0:
                    continue
                # Gravity demand with mild distance decay (dist in seconds/hops).
                demand = rid[s] * rid[t] / (total * (1.0 + dist[t] / 600.0))
                for through in path[1:-1]:
                    load[through] += demand
        return load
