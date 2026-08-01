"""Hardening optimization — the prescriptive layer.

Given a hazard and a protection budget, greedily choose which stations to harden (flood-proof /
back up so they cannot fail) to most improve resilience. This is the "so what": instead of only
scoring vulnerability, it recommends *where to invest*.

Greedy marginal-gain: repeatedly add the single station whose protection most increases the
objective (integrated resilience by default). Candidates are restricted to the stations that
actually fail in the unprotected scenario — protecting a station that never fails cannot help —
which also keeps it tractable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx

from core.hazards import Hazard
from core.load_models import BetweennessLoad, LoadModel
from core.resilience import ResilienceResult, run_resilience_scenario

OBJECTIVES = ("resilience", "robustness")


@dataclass
class HardeningResult:
    hardened: list[str]                 # ordered stations to protect (most valuable first)
    hardened_names: list[str]
    baseline_objective: float           # objective with no hardening
    final_objective: float              # objective after hardening the whole budget
    curve: list[tuple[int, float]]      # (n_hardened, objective) — diminishing-returns curve
    objective: str
    candidates_considered: int
    metadata: dict = field(default_factory=dict)


def _objective(res: ResilienceResult, which: str) -> float:
    return res.integrated_resilience if which == "resilience" else res.robustness


def greedy_hardening(
    G: nx.Graph,
    hazard: Hazard,
    alpha: float,
    budget: int = 5,
    load_model: LoadModel | None = None,
    objective: str = "resilience",
    max_candidates: int = 20,
    max_cascade_ticks: int = 8,
) -> HardeningResult:
    """Greedily select up to `budget` stations to harden against `hazard`.

    Defaults to sampled betweenness and a capped cascade depth so the many evaluations stay
    interactive; pass an exact `load_model` for a slower, higher-fidelity run.
    """
    if objective not in OBJECTIVES:
        raise ValueError(f"objective must be one of {OBJECTIVES}")
    load_model = load_model or BetweennessLoad(k=64)

    def evaluate(protected: set[str]) -> ResilienceResult:
        return run_resilience_scenario(
            G, seed=hazard.nodes, alpha=alpha, load_model=load_model,
            failed_edges=hazard.edges, protected=protected, max_cascade_ticks=max_cascade_ticks,
        )

    base = evaluate(set())
    base_obj = _objective(base, objective)

    # Only nodes that actually fail are worth protecting; rank by ridership to cap the pool.
    def rid(n: str) -> float:
        return float(G.nodes[n].get("ridership", 0.0) or 0.0)

    candidates = sorted(base.failed, key=rid, reverse=True)[:max_candidates]

    protected: set[str] = set()
    curve: list[tuple[int, float]] = [(0, base_obj)]
    remaining = list(candidates)

    for _ in range(min(budget, len(candidates))):
        best_node, best_obj = None, _objective(evaluate(protected), objective)
        for c in remaining:
            obj = _objective(evaluate(protected | {c}), objective)
            if obj > best_obj:
                best_node, best_obj = c, obj
        if best_node is None:
            break  # no further improvement possible
        protected.add(best_node)
        remaining.remove(best_node)
        curve.append((len(protected), best_obj))

    return HardeningResult(
        hardened=list(protected),
        hardened_names=[G.nodes[n].get("name", n) for n in protected],
        baseline_objective=base_obj,
        final_objective=curve[-1][1],
        curve=curve,
        objective=objective,
        candidates_considered=len(candidates),
        metadata={"hazard": hazard.label, "alpha": alpha, "budget": budget},
    )
