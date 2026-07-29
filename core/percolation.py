"""Percolation robustness sweep.

Complements the single-trigger cascade: progressively remove a *fraction* of the network and
measure how service degrades, giving a robustness curve and the critical removal fraction phi_c
(where performance first falls below half its baseline). Removal order can be targeted (attack the
most central/busiest first), by ridership, or random (Monte-Carlo). Null-model helpers let the
real network's phi_c be compared against random graphs of the same size.
"""

from __future__ import annotations

import networkx as nx
import numpy as np

from core.load_models import BetweennessLoad, LoadModel
from core.performance import served_ridership_fraction, total_ridership

REMOVAL_ORDERS = ("targeted", "ridership", "random")
METRICS = ("served_ridership", "largest_component")


def _removal_order(G: nx.Graph, order: str, load_model: LoadModel, rng: np.random.Generator):
    nodes = list(G.nodes())
    if order == "random":
        rng.shuffle(nodes)
    elif order == "ridership":
        nodes.sort(key=lambda n: float(G.nodes[n].get("ridership", 0.0) or 0.0), reverse=True)
    elif order == "targeted":
        load = load_model.compute(G)
        nodes.sort(key=lambda n: load.get(n, 0.0), reverse=True)
    else:
        raise ValueError(f"order must be one of {REMOVAL_ORDERS}")
    return nodes


def robustness_curve(G: nx.Graph, order: str = "targeted", metric: str = "served_ridership",
                     steps: int = 25, load_model: LoadModel | None = None,
                     rng: np.random.Generator | None = None) -> list[tuple[float, float]]:
    """Return [(fraction_removed, performance)] as nodes are removed in `order`."""
    if metric not in METRICS:
        raise ValueError(f"metric must be one of {METRICS}")
    load_model = load_model or BetweennessLoad()
    rng = rng or np.random.default_rng(0)
    n = G.number_of_nodes()
    if n == 0:
        return []
    order_list = _removal_order(G, order, load_model, rng)
    baseline_total = total_ridership(G)

    curve: list[tuple[float, float]] = []
    remaining = set(G.nodes())
    it = iter(order_list)
    removed = 0
    for f in np.linspace(0.0, 1.0, steps + 1):
        target = int(round(f * n))
        while removed < target:
            remaining.discard(next(it))
            removed += 1
        H = G.subgraph(remaining)
        if metric == "largest_component":
            perf = (max((len(c) for c in nx.connected_components(H)), default=0) / n)
        else:
            perf = served_ridership_fraction(H, remaining, baseline_total)
        curve.append((float(f), float(perf)))
    return curve


def critical_fraction(curve: list[tuple[float, float]], threshold: float = 0.5) -> float:
    """phi_c: the removal fraction at which performance first drops below `threshold` * baseline."""
    if not curve:
        return 1.0
    baseline = curve[0][1]
    if baseline <= 0:
        return 0.0
    for f, perf in curve:
        if perf < threshold * baseline:
            return f
    return 1.0


def null_model(G: nx.Graph, kind: str = "er", seed: int = 42) -> nx.Graph:
    """A random graph with the same node count and (approx) edge count for phi_c comparison.

    Ridership is copied from G (shuffled) so the served-ridership metric is comparable. 'er' =
    Erdos-Renyi (random), 'ba' = Barabasi-Albert (scale-free hubs).
    """
    n, m = G.number_of_nodes(), G.number_of_edges()
    rng = np.random.default_rng(seed)
    if kind == "ba":
        mm = max(1, round(m / n))
        H = nx.barabasi_albert_graph(n, mm, seed=seed)
    else:
        p = min(1.0, 2 * m / (n * (n - 1))) if n > 1 else 0.0
        H = nx.gnp_random_graph(n, p, seed=seed)
    H = nx.relabel_nodes(H, {i: str(i) for i in H})
    rid = [float(a.get("ridership", 0.0) or 0.0) for _, a in G.nodes(data=True)]
    rng.shuffle(rid)
    for node, r in zip(H.nodes(), rid, strict=False):
        H.nodes[node]["ridership"] = r
    return H
