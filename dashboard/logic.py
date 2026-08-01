"""Pure (UI-free) logic for the decision dashboard — kept separate so it is unit-testable.

Turns dashboard controls into hazards, runs the resilience engine, and shapes results into the
tables the map and charts render. No Streamlit imports here.
"""

from __future__ import annotations

import networkx as nx
import pandas as pd

from core.geo_ref import LANDMARKS
from core.hazards import Hazard, RandomStationHazard, SpatialHazard, TargetedStationHazard
from core.load_models import BetweennessLoad, LoadModel, PassengerFlowLoad
from core.resilience import ResilienceResult, run_resilience_scenario

HAZARD_TYPES = ("Flood / storm (area)", "Attack busiest hubs", "Random failure")
LOAD_MODELS = ("Passenger flow", "Betweenness (baseline)")

# Node status colors (R, G, B) for the map.
STATUS_COLOR = {
    "hardened": (37, 99, 235),   # blue
    "failed":   (220, 38, 38),   # red
    "active":   (34, 197, 94),   # green
    "bus":      (148, 163, 184),  # gray (bus, only shown faintly)
}


def make_load_model(label: str) -> LoadModel:
    return PassengerFlowLoad() if label.startswith("Passenger") else BetweennessLoad()


def build_hazard(G: nx.Graph, hazard_type: str, *, landmark: str = "loop", radius_m: float = 2000.0,
                 k: int = 3, rng=None) -> Hazard:
    """Translate dashboard controls into a concrete Hazard."""
    import numpy as np

    rng = rng or np.random.default_rng(0)
    if hazard_type == "Flood / storm (area)":
        return SpatialHazard(landmark, radius_m=radius_m).generate(G, rng)
    if hazard_type == "Attack busiest hubs":
        return TargetedStationHazard(k=k, by="ridership").generate(G, rng)
    return RandomStationHazard(k=k).generate(G, rng)


def map_dataframe(G: nx.Graph, result: ResilienceResult | None = None,
                  hardened: set[str] | None = None) -> pd.DataFrame:
    """One row per node with position, size (ridership) and status colour for the map."""
    hardened = hardened or set()
    failed = set(result.failed) if result else set()
    rows = []
    for n, a in G.nodes(data=True):
        if a.get("lat") is None:
            continue
        if n in hardened:
            status = "hardened"
        elif a.get("layer") == "bus":
            status = "bus"
        elif n in failed:
            status = "failed"
        else:
            status = "active"
        rows.append({
            "name": a.get("name", n), "lat": a["lat"], "lon": a["lon"],
            "layer": a.get("layer"), "ridership": a.get("ridership", 0.0),
            "status": status, "color": list(STATUS_COLOR[status]),
        })
    return pd.DataFrame(rows)


def triangle_dataframe(result: ResilienceResult) -> pd.DataFrame:
    """Resilience triangle Q(t): step index, service fraction, and phase label."""
    return pd.DataFrame({
        "step": list(range(len(result.performance))),
        "served_fraction": result.performance,
        "phase": ["degradation" if i <= result.degradation_end else "recovery"
                  for i in range(len(result.performance))],
    })


def run_scenario(G: nx.Graph, hazard: Hazard, alpha: float, load_model_label: str,
                 recovery_order: str) -> ResilienceResult:
    return run_resilience_scenario(
        G, seed=hazard.nodes, alpha=alpha, failed_edges=hazard.edges,
        load_model=make_load_model(load_model_label), recovery_order=recovery_order,
    )


def kpis(result: ResilienceResult, n_nodes: int) -> dict:
    return {
        "Integrated resilience R": round(result.integrated_resilience, 3),
        "Robustness (min service)": round(result.robustness, 3),
        "Cascade size": f"{result.total_failed} / {n_nodes}",
        "Service at trough": f"{result.robustness * 100:.0f}%",
    }


def landmark_options() -> list[str]:
    return sorted(LANDMARKS)
