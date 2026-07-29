"""Passenger-centric performance metrics.

`global_efficiency` (topological) is retained; the headline decision-support metric is
`served_ridership_fraction` — the share of the system's ridership that is still attached to the
functioning core network. This is the quantity whose degradation-and-recovery over time forms the
resilience triangle.
"""

from __future__ import annotations

from collections.abc import Iterable

import networkx as nx

from core.metrics import global_efficiency  # re-exported for callers

__all__ = ["global_efficiency", "total_ridership", "served_ridership", "served_ridership_fraction"]


def total_ridership(G: nx.Graph) -> float:
    """Baseline ridership across all nodes (the denominator for the served fraction)."""
    return float(sum(a.get("ridership", 0.0) or 0.0 for _, a in G.nodes(data=True)))


def served_ridership(G: nx.Graph, active: Iterable[str]) -> float:
    """Ridership still attached to the LARGEST functioning component of the active subgraph.

    Riders on stranded fragments (or on failed nodes) count as unserved — a node only provides
    real service if it is connected to the network's functioning core.
    """
    active = [n for n in active if n in G]
    if not active:
        return 0.0
    sub = G.subgraph(active)
    if sub.number_of_nodes() == 0:
        return 0.0
    core = max(nx.connected_components(sub), key=len)
    return float(sum(G.nodes[n].get("ridership", 0.0) or 0.0 for n in core))


def served_ridership_fraction(G: nx.Graph, active: Iterable[str],
                              baseline_total: float | None = None) -> float:
    """served_ridership / baseline total ridership ∈ [0, 1] — the performance signal Q(t)."""
    denom = baseline_total if baseline_total is not None else total_ridership(G)
    if denom <= 0:
        return 0.0
    return served_ridership(G, active) / denom
