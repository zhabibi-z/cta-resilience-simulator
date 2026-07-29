"""Disruption -> recovery scenarios and the resilience triangle.

This is the passenger-centric, recovery-inclusive engine that complements the strict Motter-Lai
baseline in `simulator.py`. A scenario:

  1. triggers an initial failure (seed nodes),
  2. lets the overload cascade play out (degradation), measuring passenger service each tick,
  3. restores failed nodes in a chosen priority order at a repair rate (recovery),

recording the performance curve Q(t) throughout. The area under Q(t) is the integrated resilience;
the dip-and-return shape is the resilience triangle (Bruneau et al.). Performance defaults to
served-ridership fraction, and the load model is pluggable (betweenness baseline or passenger flow).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from statistics import mean

import networkx as nx

from core.load_models import BetweennessLoad, LoadModel
from core.performance import served_ridership_fraction, total_ridership

RECOVERY_ORDERS = ("ridership", "centrality", "random")


@dataclass
class ResilienceResult:
    performance: list[float]       # Q(t): baseline, post-seed, each cascade tick, each recovery step
    degradation_end: int           # index where the cascade quiesces / recovery begins
    baseline_performance: float    # Q0
    robustness: float              # min Q(t) — how bad it got
    integrated_resilience: float   # R = mean(Q)/Q0 ∈ [0, 1] (area retained)
    total_failed: int              # secondary + seed failures at the trough
    seed: list[str]
    load_model: str
    recovery_order: str
    repair_rate: int
    metadata: dict = field(default_factory=dict)


def run_resilience_scenario(
    G: nx.Graph,
    seed: Iterable[str],
    alpha: float,
    load_model: LoadModel | None = None,
    recovery_order: str = "ridership",
    repair_rate: int = 1,
    max_cascade_ticks: int | None = None,
    failed_edges: Iterable[tuple[str, str]] = (),
) -> ResilienceResult:
    """Run one disruption→recovery scenario and return its resilience curve + metrics.

    `seed` are initially-failed nodes (stations); `failed_edges` are initially-failed links
    (track/route segments). Both are set by a hazard (see core.hazards). Capacities are still
    fixed on the intact network per Motter-Lai; the hazard then perturbs it.
    """
    load_model = load_model or BetweennessLoad()
    if recovery_order not in RECOVERY_ORDERS:
        raise ValueError(f"recovery_order must be one of {RECOVERY_ORDERS}")

    nodes = list(G.nodes())
    seed = [s for s in seed if s in G]
    baseline_total = total_ridership(G)

    # Fixed initial load & capacity (Motter-Lai: capacity set on the intact network).
    load0 = load_model.compute(G)
    capacity = {n: (1.0 + alpha) * load0[n] for n in nodes}
    rid = {n: float(G.nodes[n].get("ridership", 0.0) or 0.0) for n in nodes}

    # Working graph: same nodes/attrs as G, minus any initially-failed track/route edges.
    failed_edges = [e for e in failed_edges if G.has_edge(*e)]
    H = G.copy() if failed_edges else G
    H.remove_edges_from(failed_edges)

    def served(active_set) -> float:
        return served_ridership_fraction(H, active_set, baseline_total)

    # Baseline is the INTACT network (before any edges/nodes fail); the hazard then perturbs it.
    q0 = served_ridership_fraction(G, nodes, baseline_total)
    active = set(nodes) - set(seed)
    perf = [q0, served(active)]

    # ── Degradation: overload cascade ──────────────────────────────────────────
    cap_ticks = max_cascade_ticks if max_cascade_ticks is not None else len(nodes)
    for _ in range(cap_ticks):
        if len(active) <= 2:
            break
        load = load_model.compute(H.subgraph(active))
        overloaded = {n for n in active if load.get(n, 0.0) > capacity[n]}
        if not overloaded:
            break
        active -= overloaded
        perf.append(served(active))

    degradation_end = len(perf) - 1
    total_failed = len(nodes) - len(active)

    # ── Recovery: restore failed nodes by priority, at repair_rate per step ─────
    failed = [n for n in nodes if n not in active]
    if recovery_order == "ridership":
        failed.sort(key=lambda n: rid[n], reverse=True)          # restore high-ridership first
    elif recovery_order == "centrality":
        failed.sort(key=lambda n: load0[n], reverse=True)        # restore hubs first
    # "random": keep insertion order (deterministic; seed randomness upstream if needed)

    for i in range(0, len(failed), max(1, repair_rate)):
        active.update(failed[i:i + max(1, repair_rate)])
        perf.append(served(active))

    robustness = min(perf) if perf else 0.0
    integrated = (mean(perf) / q0) if q0 > 0 else 0.0

    return ResilienceResult(
        performance=perf,
        degradation_end=degradation_end,
        baseline_performance=q0,
        robustness=robustness,
        integrated_resilience=integrated,
        total_failed=total_failed,
        seed=list(seed),
        load_model=load_model.name,
        recovery_order=recovery_order,
        repair_rate=repair_rate,
    )
