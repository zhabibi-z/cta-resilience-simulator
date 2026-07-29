"""
Stateless metric functions operating on NetworkX subgraphs.

All functions are pure: no global state, no side effects.
"""

from __future__ import annotations

import networkx as nx


def global_efficiency(G: nx.Graph) -> float:
    """Mean inverse shortest-path length over all ordered node pairs.

    Disconnected pairs contribute 0 (d = infinity). Returns 0.0 for graphs
    with fewer than 2 nodes.
    """
    n = G.number_of_nodes()
    if n < 2:
        return 0.0
    return nx.global_efficiency(G)


def unnormalized_betweenness(G: nx.Graph) -> dict[str, float]:
    """Raw (unnormalized) betweenness centrality for all nodes in G.

    Uses unweighted shortest paths per strict Motter-Lai (2002) convention.
    Disconnected components are handled correctly: pairs with no path contribute 0.
    """
    return nx.betweenness_centrality(G, normalized=False, weight=None)


def component_stats(G: nx.Graph) -> tuple[int, int]:
    """Return (number_of_components, size_of_largest_component)."""
    comps = list(nx.connected_components(G))
    if not comps:
        return 0, 0
    return len(comps), max(len(c) for c in comps)
