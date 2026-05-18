"""Graph construction invariant tests."""

import pytest
import networkx as nx
from core.graph import build_graph


@pytest.fixture(scope="module")
def G():
    return build_graph()


def test_node_count(G):
    assert len(G.nodes) >= 100, f"Expected ≥100 nodes, got {len(G.nodes)}"


def test_edge_count(G):
    assert len(G.edges) >= 140, f"Expected ≥140 edges, got {len(G.edges)}"


def test_main_component_size(G):
    """Largest connected component must cover ≥90% of nodes."""
    lc = max(len(c) for c in nx.connected_components(G))
    fraction = lc / len(G.nodes)
    assert fraction >= 0.90, f"Largest component covers only {fraction:.1%} of nodes"


def test_node_attributes(G):
    required = {"name", "lat", "lon", "lines"}
    for n, d in G.nodes(data=True):
        missing = required - set(d.keys())
        assert not missing, f"Node {n} missing attributes: {missing}"


def test_node_attribute_types(G):
    for n, d in G.nodes(data=True):
        assert isinstance(d["lat"],   float), f"Node {n}: lat not float"
        assert isinstance(d["lon"],   float), f"Node {n}: lon not float"
        assert isinstance(d["name"],  str),   f"Node {n}: name not str"
        assert isinstance(d["lines"], list),  f"Node {n}: lines not list"


def test_lat_lon_bounds(G):
    for n, d in G.nodes(data=True):
        assert 41.60 <= d["lat"] <= 42.15, f"Node {n} lat={d['lat']} out of Chicago bounds"
        assert -88.05 <= d["lon"] <= -87.40, f"Node {n} lon={d['lon']} out of Chicago bounds"


def test_edge_attributes(G):
    for u, v, d in G.edges(data=True):
        assert "lines"  in d, f"Edge ({u},{v}) missing 'lines'"
        assert "weight" in d, f"Edge ({u},{v}) missing 'weight'"
        assert d["weight"] >= 1, f"Edge ({u},{v}) has non-positive weight"


def test_no_self_loops(G):
    loops = list(nx.selfloop_edges(G))
    assert not loops, f"Graph contains self-loops: {loops}"


def test_known_transfer_stations(G):
    """Key transfer hubs must be present and multi-line."""
    transfers = {
        "clark_lake":   {"Blue", "Brown", "Green", "Orange", "Pink", "Purple"},
        "belmont_red":  {"Red", "Brown", "Purple"},
        "fullerton":    {"Red", "Brown", "Purple"},
        "roosevelt_red":{"Red", "Orange", "Green"},
        "howard":       {"Red", "Purple", "Yellow"},
    }
    for node_id, expected_lines in transfers.items():
        assert node_id in G.nodes, f"Transfer station '{node_id}' missing from graph"
        actual = set(G.nodes[node_id]["lines"])
        assert expected_lines.issubset(actual), (
            f"Station '{node_id}' expected lines {expected_lines}, got {actual}"
        )


def test_terminals_present(G):
    terminals = ["95th_dan_ryan", "ohare", "forest_park", "midway",
                 "linden", "kimball", "oakton_skokie"]
    for t in terminals:
        assert t in G.nodes, f"Terminal station '{t}' missing from graph"


def test_build_graph_idempotent():
    """Two calls must return structurally identical graphs."""
    G1, G2 = build_graph(), build_graph()
    assert set(G1.nodes) == set(G2.nodes)
    assert set(G1.edges) == set(G2.edges)
