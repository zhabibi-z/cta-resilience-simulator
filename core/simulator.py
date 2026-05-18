"""
Strict Motter-Lai (2002) cascading failure simulator.

Model definition:
  - Initial load L_0(i) = unnormalized betweenness centrality on the full graph.
  - Capacity C(i) = (1 + alpha) * L_0(i), fixed for the lifetime of the simulation.
  - At each cascade tick, load is recomputed as BC on the current active subgraph.
  - All nodes with current_load > C(i) fail simultaneously in that tick.

No pygame dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
import networkx as nx
import numpy as np

from core.metrics import global_efficiency, unnormalized_betweenness, component_stats

TERMINATION_QUIESCENT        = "QUIESCENT"
TERMINATION_COLLAPSED        = "COLLAPSED"
TERMINATION_RUNAWAY          = "RUNAWAY"
TERMINATION_EFFICIENCY_ZERO  = "EFFICIENCY_ZERO"


@dataclass
class TickRecord:
    tick: int                          # -1 = baseline, 0 = post-seed, 1+ = cascade
    efficiency: float
    n_components: int
    largest_component_fraction: float  # S_max / n_total
    n_active: int
    n_cascaded_cumulative: int         # secondary failures only (seed not counted)
    n_failed_this_tick: int            # nodes that failed on THIS tick


@dataclass
class SimulationResult:
    trial_id: int
    alpha: float
    strategy: str
    child_seed: int
    seed_node: str
    timeseries: List[TickRecord]
    termination_reason: str
    phi_c: float      # removal fraction when E first drops below threshold * E_0
    total_nodes: int
    e0: float         # baseline global efficiency

    def to_timeseries_records(self) -> list[dict]:
        base = {
            "trial_id":    self.trial_id,
            "alpha":       self.alpha,
            "strategy":    self.strategy,
            "child_seed":  self.child_seed,
            "seed_node":   self.seed_node,
            "total_nodes": self.total_nodes,
            "e0":          self.e0,
        }
        records = []
        for tr in self.timeseries:
            r = dict(base)
            r["tick"]                         = tr.tick
            r["efficiency"]                   = tr.efficiency
            r["n_components"]                 = tr.n_components
            r["largest_component_fraction"]   = tr.largest_component_fraction
            r["n_active"]                     = tr.n_active
            r["n_cascaded_cumulative"]        = tr.n_cascaded_cumulative
            r["n_failed_this_tick"]           = tr.n_failed_this_tick
            records.append(r)
        return records

    def to_summary_record(self) -> dict:
        final = self.timeseries[-1] if self.timeseries else None
        return {
            "trial_id":                 self.trial_id,
            "alpha":                    self.alpha,
            "strategy":                 self.strategy,
            "child_seed":               self.child_seed,
            "seed_node":                self.seed_node,
            "total_nodes":              self.total_nodes,
            "e0":                       self.e0,
            "phi_c":                    self.phi_c,
            "total_ticks":              (self.timeseries[-1].tick if final else 0),
            "termination_reason":       self.termination_reason,
            "total_secondary_failures": (final.n_cascaded_cumulative if final else 0),
            "final_efficiency":         (final.efficiency if final else 0.0),
            "final_n_components":       (final.n_components if final else 0),
            "final_n_active":           (final.n_active if final else 0),
        }


class MotterLaiSimulator:
    """Encapsulates a single (graph, alpha) configuration.

    Create once per (graph, alpha) pair and call run_trial() repeatedly
    with different RNGs and strategies.
    """

    def __init__(
        self,
        G: nx.Graph,
        alpha: float,
        max_ticks_multiplier: int = 5,
        efficiency_collapse_threshold: float = 0.5,
        top_k_fraction: float = 0.0,
    ) -> None:
        self.G = G
        self.alpha = alpha
        self.max_ticks = max_ticks_multiplier * len(G)
        self.collapse_threshold = efficiency_collapse_threshold
        self.top_k_fraction = top_k_fraction
        self.n_total = len(G)

        # Fixed initial loads — computed once on the full graph
        raw_bc = unnormalized_betweenness(G)
        self.load_0: dict[str, float] = raw_bc
        self.capacity: dict[str, float] = {
            n: (1.0 + alpha) * raw_bc[n] for n in G.nodes()
        }

        # Baseline efficiency (full graph, no removals)
        self.e0 = global_efficiency(G)

        # Nodes sorted by descending BC for targeted strategy
        self._sorted_by_bc: list[str] = sorted(
            G.nodes(), key=lambda n: raw_bc[n], reverse=True
        )

        # Baseline component stats
        n_comp_base, lc_base = component_stats(G)
        self._baseline_n_components = n_comp_base
        self._baseline_lc_fraction = lc_base / self.n_total if self.n_total else 0.0

    # ── Seed node selection ────────────────────────────────────────────────────

    def _select_seed(self, strategy: str, rng: np.random.Generator) -> str:
        if strategy == "targeted":
            if self.top_k_fraction <= 0.0:
                # Strictly the single highest-BC node — deterministic.
                # All targeted trials with this alpha will be identical.
                return self._sorted_by_bc[0]
            k = max(1, int(len(self._sorted_by_bc) * self.top_k_fraction))
            idx = int(rng.integers(0, k))
            return self._sorted_by_bc[idx]
        # Random: uniform over all nodes
        nodes = list(self.G.nodes())
        idx = int(rng.integers(0, len(nodes)))
        return nodes[idx]

    # ── Main trial runner ──────────────────────────────────────────────────────

    def run_trial(
        self,
        trial_id: int,
        strategy: str,
        rng: np.random.Generator,
        child_seed: int,
    ) -> SimulationResult:
        seed_node = self._select_seed(strategy, rng)

        # Tick -1: baseline (full graph, zero removals)
        baseline = TickRecord(
            tick=-1,
            efficiency=self.e0,
            n_components=self._baseline_n_components,
            largest_component_fraction=self._baseline_lc_fraction,
            n_active=self.n_total,
            n_cascaded_cumulative=0,
            n_failed_this_tick=0,
        )

        active: set[str] = set(self.G.nodes()) - {seed_node}
        timeseries: list[TickRecord] = [baseline]
        n_cascaded = 0
        phi_c = 1.0   # sentinel: efficiency never collapsed below threshold
        termination_reason = ""

        # Tick 0: state immediately after seed removal, before cascade evaluation
        sg0 = self.G.subgraph(active)
        e0_post = global_efficiency(sg0) if len(active) > 1 else 0.0
        n_comp0, lc0 = component_stats(sg0)
        timeseries.append(TickRecord(
            tick=0,
            efficiency=e0_post,
            n_components=n_comp0,
            largest_component_fraction=lc0 / self.n_total,
            n_active=len(active),
            n_cascaded_cumulative=0,
            n_failed_this_tick=1,   # the seed node
        ))
        if self.e0 > 0.0 and e0_post < self.collapse_threshold * self.e0:
            phi_c = 1.0 / self.n_total

        # ── Cascade loop ───────────────────────────────────────────────────────
        tick = 0
        while True:
            tick += 1

            if len(active) <= 2:
                termination_reason = TERMINATION_COLLAPSED
                break

            if tick > self.max_ticks:
                termination_reason = TERMINATION_RUNAWAY
                break

            # Current loads: BC on active subgraph (unweighted, unnormalized)
            sg = self.G.subgraph(active)
            current_load = unnormalized_betweenness(sg)

            # Simultaneous failure of all overloaded nodes this tick
            overloaded = {
                n for n in active
                if current_load.get(n, 0.0) > self.capacity[n]
            }

            if not overloaded:
                termination_reason = TERMINATION_QUIESCENT
                break

            active -= overloaded
            n_cascaded += len(overloaded)

            # Metrics after this tick's failures
            sg_post = self.G.subgraph(active)
            e_now = global_efficiency(sg_post) if len(active) > 1 else 0.0
            n_comp, lc = component_stats(sg_post)

            timeseries.append(TickRecord(
                tick=tick,
                efficiency=e_now,
                n_components=n_comp,
                largest_component_fraction=lc / self.n_total,
                n_active=len(active),
                n_cascaded_cumulative=n_cascaded,
                n_failed_this_tick=len(overloaded),
            ))

            # Update phi_c: first crossing of the collapse threshold
            if phi_c == 1.0 and self.e0 > 0.0 and e_now < self.collapse_threshold * self.e0:
                n_removed = self.n_total - len(active)
                phi_c = n_removed / self.n_total

            if e_now == 0.0:
                termination_reason = TERMINATION_EFFICIENCY_ZERO
                break

        if not termination_reason:
            termination_reason = TERMINATION_QUIESCENT

        return SimulationResult(
            trial_id=trial_id,
            alpha=self.alpha,
            strategy=strategy,
            child_seed=child_seed,
            seed_node=seed_node,
            timeseries=timeseries,
            termination_reason=termination_reason,
            phi_c=phi_c,
            total_nodes=self.n_total,
            e0=self.e0,
        )
