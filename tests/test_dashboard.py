"""Tests for the dashboard's pure logic layer (no Streamlit)."""

from __future__ import annotations

import networkx as nx
import numpy as np

from core.resilience import run_resilience_scenario
from dashboard import logic

RNG = np.random.default_rng(0)


def _graph() -> nx.Graph:
    G = nx.Graph()
    G.add_node("R1", layer="rail", lat=41.9000, lon=-87.6500, ridership=100.0, name="Hub")
    G.add_node("R2", layer="rail", lat=41.9010, lon=-87.6500, ridership=50.0, name="R2")
    G.add_node("B1", layer="bus", lat=41.9005, lon=-87.6505, ridership=20.0, name="B1")
    nx.add_path(G, ["R1", "R2", "B1"])
    for u, v in G.edges():
        G[u][v]["travel_time"] = 120.0
    return G


def test_build_hazard_types():
    G = _graph()
    assert logic.build_hazard(G, "Attack busiest hubs", k=1).nodes == {"R1"}
    spatial = logic.build_hazard(G, "Flood / storm (area)", landmark="loop", radius_m=50)
    assert isinstance(spatial.nodes, set)
    assert len(logic.build_hazard(G, "Random failure", k=1, rng=RNG).nodes) == 1


def test_map_dataframe_statuses():
    G = _graph()
    res = run_resilience_scenario(G, seed=["R2"], alpha=5.0)
    df = logic.map_dataframe(G, res)
    by_name = df.set_index("name")["status"].to_dict()
    assert by_name["R2"] == "failed"      # seeded failure
    assert by_name["Hub"] == "active"
    assert by_name["B1"] == "bus"


def test_map_dataframe_marks_hardened():
    G = _graph()
    df = logic.map_dataframe(G, result=None, hardened={"R1"})
    assert df.set_index("name")["status"].to_dict()["Hub"] == "hardened"


def test_triangle_dataframe_shape():
    G = _graph()
    res = run_resilience_scenario(G, seed=["R2"], alpha=5.0)
    tri = logic.triangle_dataframe(res)
    assert list(tri.columns) == ["step", "served_fraction", "phase"]
    assert len(tri) == len(res.performance)
    assert set(tri["phase"]) <= {"degradation", "recovery"}


def test_kpis_keys():
    G = _graph()
    res = run_resilience_scenario(G, seed=["R2"], alpha=5.0)
    k = logic.kpis(res, G.number_of_nodes())
    assert "Integrated resilience R" in k and "Cascade size" in k
