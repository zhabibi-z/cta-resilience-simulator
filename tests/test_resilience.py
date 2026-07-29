"""Tests for the passenger-centric load models, performance metric, and resilience scenario."""

from __future__ import annotations

import networkx as nx
import pytest

from core.load_models import BetweennessLoad, PassengerFlowLoad
from core.performance import served_ridership_fraction
from core.resilience import run_resilience_scenario


def _line_graph() -> nx.Graph:
    """A-B-C-D-E path; C is the cut vertex. Ridership on every node."""
    G = nx.Graph()
    for n in "ABCDE":
        G.add_node(n, ridership=10.0, lat=41.9, lon=-87.6, layer="rail")
    nx.add_path(G, list("ABCDE"))
    for u, v in G.edges():
        G[u][v]["travel_time"] = 120.0
    return G


# --- load models ---

def test_betweenness_load_matches_baseline():
    G = _line_graph()
    load = BetweennessLoad().compute(G)
    # On a path, the middle node C lies on the most shortest paths -> highest load.
    assert load["C"] == max(load.values())
    assert load["A"] == pytest.approx(0.0)


def test_passenger_flow_load_concentrates_on_hub():
    G = _line_graph()
    load = PassengerFlowLoad().compute(G)
    assert load["C"] >= load["B"] >= load["A"]
    assert load["A"] == pytest.approx(0.0)  # endpoints carry no through-flow


# --- performance metric ---

def test_served_fraction_full_network_is_one():
    G = _line_graph()
    assert served_ridership_fraction(G, list(G.nodes())) == pytest.approx(1.0)


def test_served_fraction_drops_when_cut():
    G = _line_graph()  # total ridership 50
    # Remove the cut vertex C -> fragments {A,B} and {D,E}; largest serves 20/50.
    active = ["A", "B", "D", "E"]
    assert served_ridership_fraction(G, active) == pytest.approx(20.0 / 50.0)


# --- resilience scenario / triangle ---

def test_scenario_produces_recovering_triangle():
    G = _line_graph()
    r = run_resilience_scenario(G, seed=["C"], alpha=0.2, recovery_order="ridership")
    q0 = r.baseline_performance
    assert r.performance[0] == pytest.approx(q0)
    assert r.robustness < q0                       # service dropped (dip in the triangle)
    assert r.performance[-1] == pytest.approx(q0)  # fully recovered by the end
    assert 0.0 < r.integrated_resilience <= 1.0
    assert r.total_failed >= 1


def test_recovery_order_validation():
    G = _line_graph()
    with pytest.raises(ValueError):
        run_resilience_scenario(G, seed=["C"], alpha=0.2, recovery_order="bogus")


def test_ridership_recovery_beats_random_on_integral():
    # High-ridership-first recovery should retain at least as much area as arbitrary order.
    G = nx.star_graph(8)  # node 0 is the hub
    G = nx.relabel_nodes(G, {i: str(i) for i in G})
    for n in G:
        G.nodes[n].update(ridership=100.0 if n == "0" else 5.0, layer="rail")
    for u, v in G.edges():
        G[u][v]["travel_time"] = 60.0
    r_rid = run_resilience_scenario(G, seed=["0"], alpha=0.1, recovery_order="ridership")
    r_rnd = run_resilience_scenario(G, seed=["0"], alpha=0.1, recovery_order="random")
    assert r_rid.integrated_resilience >= r_rnd.integrated_resilience - 1e-9
