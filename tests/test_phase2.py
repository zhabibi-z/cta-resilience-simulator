"""Tests for hazards, percolation robustness, and edge-failure scenarios."""

from __future__ import annotations

import networkx as nx
import numpy as np
import pytest

from core.hazards import EdgeHazard, SpatialHazard, TargetedStationHazard
from core.percolation import critical_fraction, null_model, robustness_curve
from core.resilience import run_resilience_scenario

RNG = np.random.default_rng(0)


def _geo_graph() -> nx.Graph:
    """Two rail + one bus node near (41.90,-87.65); one rail node far away."""
    G = nx.Graph()
    G.add_node("R1", layer="rail", lat=41.9000, lon=-87.6500, ridership=100.0)
    G.add_node("R2", layer="rail", lat=41.9010, lon=-87.6500, ridership=50.0)   # ~110 m away
    G.add_node("B1", layer="bus", lat=41.9005, lon=-87.6505, ridership=20.0)    # ~60 m away
    G.add_node("R9", layer="rail", lat=42.0500, lon=-87.6500, ridership=10.0)   # ~17 km away
    nx.add_path(G, ["R9", "R1", "R2", "B1"])
    for u, v in G.edges():
        G[u][v]["travel_time"] = 120.0
    return G


# --- hazards ---

def test_targeted_station_hazard_picks_busiest():
    G = _geo_graph()
    h = TargetedStationHazard(k=1, by="ridership").generate(G, RNG)
    assert h.nodes == {"R1"}   # highest ridership rail station


def test_spatial_hazard_hits_region_both_layers():
    G = _geo_graph()
    h = SpatialHazard(center=(41.9005, -87.6502), radius_m=500).generate(G, RNG)
    assert h.nodes == {"R1", "R2", "B1"}   # rail + bus within 500 m
    assert "R9" not in h.nodes             # far rail station spared


def test_edge_hazard_returns_valid_edges():
    G = _geo_graph()
    h = EdgeHazard(edges=[("R1", "R2"), ("X", "Y")]).generate(G, RNG)
    assert ("R1", "R2") in h.edges
    assert ("X", "Y") not in h.edges       # non-existent edge dropped


# --- percolation ---

def test_robustness_curve_starts_full_ends_empty():
    G = _geo_graph()
    curve = robustness_curve(G, order="targeted", steps=10)
    assert curve[0][0] == 0.0 and curve[0][1] == pytest.approx(1.0, abs=1e-6)
    assert curve[-1][0] == pytest.approx(1.0)
    assert curve[-1][1] == pytest.approx(0.0, abs=1e-6)


def test_targeted_collapses_faster_than_random():
    # Star: attacking the hub first collapses connectivity immediately.
    G = nx.star_graph(20)
    G = nx.relabel_nodes(G, {i: str(i) for i in G})
    for n in G:
        G.nodes[n]["ridership"] = 100.0 if n == "0" else 1.0
    phi_targeted = critical_fraction(robustness_curve(G, order="targeted", steps=40))
    phi_random = critical_fraction(
        robustness_curve(G, order="random", steps=40, rng=np.random.default_rng(1))
    )
    assert phi_targeted <= phi_random


def test_null_model_same_size():
    G = _geo_graph()
    H = null_model(G, kind="er")
    assert H.number_of_nodes() == G.number_of_nodes()


# --- edge-failure scenario ---

def test_edge_failure_reduces_service():
    G = _geo_graph()
    # Failing the R1-R2 track splits the far side off; served ridership drops.
    r = run_resilience_scenario(G, seed=[], alpha=5.0, failed_edges=[("R1", "R2")])
    assert r.robustness < r.baseline_performance
