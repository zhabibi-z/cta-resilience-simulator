"""Canonical registry of the real CTA open-data sources used to build the network.

Every external data dependency is declared here (single source of truth) so provenance is
auditable — a hard requirement for a decision-support tool. All sources are public and require
no authentication.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Cache lives outside version control (see .gitignore); it is fully regenerable.
CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "cache"

# CTA schedule feed (GTFS) — full system: rail (route_type 1) + bus (route_type 3).
GTFS_URL = "https://www.transitchicago.com/downloads/sch_data/google_transit.zip"

# Chicago Data Portal (Socrata) datasets. IDs are stable dataset identifiers.
SOCRATA_DOMAIN = "data.cityofchicago.org"


@dataclass(frozen=True)
class SocrataDataset:
    dataset_id: str
    description: str

    @property
    def url(self) -> str:
        return f"https://{SOCRATA_DOMAIN}/resource/{self.dataset_id}.json"


# 'L' station-level rides (station_id == GTFS parent_station / "map_id", the 4xxxx ids).
L_STATION_RIDERSHIP = SocrataDataset("5neh-572f", "CTA 'L' station entries — daily totals")

# 'L' stops reference: geo (lat/lon), per-line boolean flags, station_name, map_id.
L_STOPS = SocrataDataset("8pix-ypme", "CTA 'L' (rail) stops — geo + line membership")

# Bus route-level rides (route == GTFS route_short_name / route_id for bus).
BUS_ROUTE_RIDERSHIP = SocrataDataset("jyb9-n7fm", "CTA bus routes — daily totals by route")

# CTA line codes as they appear in the 8pix-ypme boolean columns → human names.
L_LINE_COLUMNS = {
    "red": "Red",
    "blue": "Blue",
    "g": "Green",
    "brn": "Brown",
    "p": "Purple",
    "pexp": "Purple Express",
    "y": "Yellow",
    "pnk": "Pink",
    "o": "Orange",
}
