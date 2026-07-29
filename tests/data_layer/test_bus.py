"""Hermetic tests for the bus layer, transfer edges, and geo helpers."""

from __future__ import annotations

import zipfile
from pathlib import Path

import networkx as nx
import pytest

from ingest.bus import build_bus_graph
from ingest.geo import grid_cell, haversine_m
from ingest.transfers import add_transfer_edges

# One bus route whose 3 stops fall into 3 distinct 0.01-deg cells -> 3 nodes, 2 edges.
_FILES = {
    "routes.txt": "route_id,route_short_name,route_type\nRed,Red,1\nB9,9,3\n",
    "trips.txt": "route_id,trip_id\nRed,T1\nB9,TB\n",
    "stop_times.txt": (
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
        "TB,09:00:00,09:00:00,PB1,1\n"
        "TB,09:04:00,09:04:00,PB2,2\n"
        "TB,09:08:00,09:08:00,PB3,3\n"
    ),
    "stops.txt": (
        "stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station\n"
        "PB1,Bus 1,41.900,-87.650,0,\n"
        "PB2,Bus 2,41.900,-87.640,0,\n"
        "PB3,Bus 3,41.910,-87.640,0,\n"
    ),
}


@pytest.fixture
def gtfs_zip(tmp_path: Path) -> Path:
    p = tmp_path / "gtfs.zip"
    with zipfile.ZipFile(p, "w") as z:
        for name, content in _FILES.items():
            z.writestr(name, content)
    return p


# --- geo ---

def test_haversine_known_distance():
    # ~0.01 deg of latitude ≈ 1.11 km
    d = haversine_m(41.90, -87.65, 41.91, -87.65)
    assert 1050 < d < 1160


def test_grid_cell_snaps():
    assert grid_cell(41.9032, -87.6498, 0.01) == (pytest.approx(41.90), pytest.approx(-87.65))


# --- bus layer ---

def test_bus_graph_aggregates_to_cells(gtfs_zip):
    G = build_bus_graph(gtfs_zip, ridership={"9": 900.0}, grid_size_deg=0.01)
    assert G.number_of_nodes() == 3        # 3 distinct cells
    assert G.number_of_edges() == 2        # consecutive cells
    assert all(a["layer"] == "bus" for _, a in G.nodes(data=True))


def test_bus_ridership_apportioned(gtfs_zip):
    G = build_bus_graph(gtfs_zip, ridership={"9": 900.0}, grid_size_deg=0.01)
    # route ridership 900 split across its 3 cells
    assert sum(a["ridership"] for _, a in G.nodes(data=True)) == pytest.approx(900.0, abs=1.0)


# --- transfers ---

def test_transfer_within_walking_distance():
    G = nx.Graph()
    G.add_node("R1", layer="rail", lat=41.9000, lon=-87.6500)
    G.add_node("B:x", layer="bus", lat=41.9010, lon=-87.6500)   # ~110 m away
    G.add_node("B:far", layer="bus", lat=41.9500, lon=-87.6500)  # ~5.5 km away
    n = add_transfer_edges(G, walk_max_m=600)
    assert G.has_edge("R1", "B:x")
    assert not G.has_edge("R1", "B:far")
    assert G["R1"]["B:x"]["layer"] == "transfer"
    assert n == 1


def test_transfer_nearest_fallback_when_none_in_range():
    G = nx.Graph()
    G.add_node("R1", layer="rail", lat=41.9000, lon=-87.6500)
    G.add_node("B:only", layer="bus", lat=41.9100, lon=-87.6500)  # ~1.1 km, beyond 600 m
    add_transfer_edges(G, walk_max_m=600)
    assert G.has_edge("R1", "B:only")   # nearest-cell fallback guarantees coupling
