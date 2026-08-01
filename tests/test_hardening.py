"""Tests for node hardening (protected nodes) and the greedy hardening optimizer."""

from __future__ import annotations

import networkx as nx
import pytest

from core.hardening import greedy_hardening
from core.hazards import Hazard
from core.resilience import run_resilience_scenario


def _line() -> nx.Graph:
    """A-B-C-D-E path; C is the cut vertex whose loss splits the network."""
    G = nx.Graph()
    for n in "ABCDE":
        G.add_node(n, ridership=10.0, lat=41.9, lon=-87.6, layer="rail")
    nx.add_path(G, list("ABCDE"))
    for u, v in G.edges():
        G[u][v]["travel_time"] = 120.0
    return G


def test_protected_node_survives_the_hazard():
    G = _line()
    r = run_resilience_scenario(G, seed=["C"], alpha=5.0, protected=["C"])
    assert "C" not in r.failed                                   # hardened -> immune
    assert r.robustness == pytest.approx(r.baseline_performance)  # no service drop


def test_hardening_improves_resilience_and_picks_the_cut_vertex():
    G = _line()
    res = greedy_hardening(G, Hazard(nodes={"C"}), alpha=5.0, budget=1)
    assert res.hardened == ["C"]                     # protecting the cut vertex is optimal
    assert res.final_objective > res.baseline_objective
    assert res.curve[0][0] == 0 and res.curve[-1][0] == 1
    assert res.hardened_names == ["C"]               # names carried through


def test_hardening_curve_is_non_decreasing():
    G = _line()
    res = greedy_hardening(G, Hazard(nodes={"C"}), alpha=0.5, budget=3)
    objs = [o for _, o in res.curve]
    assert all(b >= a - 1e-9 for a, b in zip(objs, objs[1:], strict=False))  # marginal-gain monotone


def test_objective_validation():
    with pytest.raises(ValueError):
        greedy_hardening(_line(), Hazard(nodes={"C"}), alpha=1.0, objective="bogus")
