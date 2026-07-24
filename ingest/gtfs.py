"""Memory-safe reader over the CTA GTFS feed.

stop_times.txt is ~360 MB (bus-dominated), so it is never loaded whole: callers pass the set of
rail trip_ids and we stream-filter in chunks. Small tables are read directly.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd

# CTA GTFS route_type 1 == rail ('L'); 3 == bus.
RAIL_ROUTE_TYPE = 1
BUS_ROUTE_TYPE = 3

# GTFS rail route_id -> human line name.
RAIL_LINE_NAMES = {
    "Red": "Red", "Blue": "Blue", "G": "Green", "Brn": "Brown",
    "Org": "Orange", "Pink": "Pink", "P": "Purple", "Y": "Yellow",
}


def gtfs_time_to_seconds(t: str) -> int | None:
    """Parse a GTFS HH:MM:SS time (which may exceed 24:00:00) into seconds past midnight."""
    if not isinstance(t, str) or t.count(":") != 2:
        return None
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


class GTFSFeed:
    def __init__(self, zip_path: Path) -> None:
        self._zip = zipfile.ZipFile(zip_path)

    def table(self, name: str, **kwargs) -> pd.DataFrame:
        with self._zip.open(name) as fh:
            return pd.read_csv(fh, **kwargs)

    def route_ids(self, route_type: int) -> list[str]:
        r = self.table("routes.txt", dtype={"route_id": str})
        return r.loc[r["route_type"] == route_type, "route_id"].astype(str).tolist()

    def trips(self, route_ids: set[str]) -> pd.DataFrame:
        t = self.table("trips.txt", dtype={"route_id": str, "trip_id": str})
        return t.loc[t["route_id"].isin(route_ids), ["route_id", "trip_id"]].copy()

    def stop_times_for_trips(self, trip_ids: set[str], chunksize: int = 500_000) -> pd.DataFrame:
        """Stream stop_times.txt, keeping only rows for the given trips."""
        cols = ["trip_id", "departure_time", "arrival_time", "stop_id", "stop_sequence"]
        kept: list[pd.DataFrame] = []
        with self._zip.open("stop_times.txt") as fh:
            for chunk in pd.read_csv(
                fh, usecols=cols, dtype={"trip_id": str, "stop_id": str}, chunksize=chunksize
            ):
                sub = chunk[chunk["trip_id"].isin(trip_ids)]
                if not sub.empty:
                    kept.append(sub)
        return pd.concat(kept, ignore_index=True) if kept else pd.DataFrame(columns=cols)

    def stops(self) -> pd.DataFrame:
        return self.table(
            "stops.txt",
            dtype={"stop_id": str, "parent_station": str, "location_type": "Int64"},
        )
