"""Hermetic tests for the GTFS→rail builder using a synthetic in-memory feed (no network)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import networkx as nx
import pytest

from ingest.gtfs import gtfs_time_to_seconds
from ingest.rail import build_rail_graph
from ingest.ridership import attach_station_ridership

# A minimal but realistic GTFS: one 3-station rail line (Red) + one bus route that must be ignored.
_FILES = {
    "routes.txt": (
        "route_id,route_short_name,route_type\n"
        "Red,Red,1\n"
        "B9,9,3\n"
    ),
    "trips.txt": (
        "route_id,trip_id\n"
        "Red,T1\n"
        "B9,TB\n"
    ),
    "stop_times.txt": (
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
        "T1,08:00:00,08:00:00,P1,1\n"
        "T1,08:02:00,08:02:00,P2,2\n"      # S1->S2 = 120s
        "T1,08:05:30,08:05:30,P3,3\n"      # S2->S3 = 210s
        "TB,09:00:00,09:00:00,PB1,1\n"     # bus — must be excluded
        "TB,09:04:00,09:04:00,PB2,2\n"
    ),
    "stops.txt": (
        "stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station\n"
        "S1,Howard,42.019,-87.672,1,\n"
        "S2,Loyola,41.999,-87.661,1,\n"
        "S3,Granville,41.993,-87.659,1,\n"
        "P1,Howard Plat,42.019,-87.672,0,S1\n"
        "P2,Loyola Plat,41.999,-87.661,0,S2\n"
        "P3,Granville Plat,41.993,-87.659,0,S3\n"
        "PB1,Bus A,41.9,-87.6,0,\n"
        "PB2,Bus B,41.9,-87.6,0,\n"
    ),
}


@pytest.fixture
def gtfs_zip(tmp_path: Path) -> Path:
    p = tmp_path / "gtfs.zip"
    with zipfile.ZipFile(p, "w") as z:
        for name, content in _FILES.items():
            z.writestr(name, content)
    return p


def test_gtfs_time_parsing():
    assert gtfs_time_to_seconds("08:02:00") == 8 * 3600 + 120
    assert gtfs_time_to_seconds("25:30:00") == 25 * 3600 + 1800  # past-midnight service
    assert gtfs_time_to_seconds("bad") is None


def test_rail_graph_topology(gtfs_zip):
    G = build_rail_graph(gtfs_zip)
    assert G.number_of_nodes() == 3          # S1,S2,S3 — bus stops excluded
    assert G.number_of_edges() == 2          # S1-S2, S2-S3
    assert set(G.nodes()) == {"S1", "S2", "S3"}
    assert nx.is_connected(G)


def test_rail_edge_travel_times_and_lines(gtfs_zip):
    G = build_rail_graph(gtfs_zip)
    assert G["S1"]["S2"]["travel_time"] == pytest.approx(120.0)
    assert G["S2"]["S3"]["travel_time"] == pytest.approx(210.0)
    assert G["S1"]["S2"]["lines"] == ["Red"]
    assert G.nodes["S2"]["lines"] == ["Red"]


def test_geo_and_names(gtfs_zip):
    G = build_rail_graph(gtfs_zip)
    assert G.nodes["S1"]["name"] == "Howard"
    assert G.nodes["S1"]["lat"] == pytest.approx(42.019)


def test_attach_ridership(gtfs_zip):
    G = build_rail_graph(gtfs_zip)
    matched, unmatched = attach_station_ridership(G, {"S1": 5000.0, "S2": 3000.0})
    assert matched == 2
    assert unmatched == 1
    assert G.nodes["S1"]["ridership"] == 5000.0
    assert G.nodes["S3"]["ridership"] == 0.0
