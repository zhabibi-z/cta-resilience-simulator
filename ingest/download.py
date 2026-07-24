"""Robust, cached fetching of the CTA sources.

Design goals (production, not prototype):
  * Idempotent local cache — re-runs are offline and instant; CI/tests never hit the network.
  * Explicit freshness control via `max_age_days` rather than silent staleness.
  * Full Socrata pagination (the API caps page size), so ridership pulls are complete.
  * Clear errors on HTTP/format failure instead of silent partial data.
"""

from __future__ import annotations

import json
import logging
import time
import zipfile
from pathlib import Path

import requests

from ingest.datasets import CACHE_DIR, SocrataDataset

log = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "cta-resilience-simulator/1.0 (+data ingestion)"})
_TIMEOUT = 60


def _is_fresh(path: Path, max_age_days: float | None) -> bool:
    if not path.exists():
        return False
    if max_age_days is None:
        return True
    age_days = (time.time() - path.stat().st_mtime) / 86400.0
    return age_days <= max_age_days


def download_gtfs(max_age_days: float | None = 30) -> Path:
    """Download the CTA GTFS zip into the cache and return its path (cached if fresh)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dest = CACHE_DIR / "cta_gtfs.zip"
    if _is_fresh(dest, max_age_days):
        log.info("GTFS cache hit: %s", dest)
        return dest

    from ingest.datasets import GTFS_URL

    log.info("Downloading GTFS from %s", GTFS_URL)
    with _SESSION.get(GTFS_URL, stream=True, timeout=_TIMEOUT) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(".zip.part")
        with tmp.open("wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
        tmp.replace(dest)

    # Fail fast if the download is not a valid zip.
    if not zipfile.is_zipfile(dest):
        dest.unlink(missing_ok=True)
        raise ValueError(f"Downloaded GTFS is not a valid zip: {GTFS_URL}")
    log.info("GTFS cached: %s (%.1f MB)", dest, dest.stat().st_size / 1e6)
    return dest


def fetch_socrata(dataset: SocrataDataset, max_age_days: float | None = 7,
                  page_size: int = 50_000, max_rows: int | None = None,
                  soql: dict | None = None) -> list[dict]:
    """Fetch a Socrata dataset with pagination; cache the assembled JSON.

    `soql` passes SoQL clauses ($select/$where/$group/$order) so aggregation can happen
    server-side — e.g. AVG(rides) grouped by station — instead of pulling millions of rows.
    Each distinct query is cached separately.
    """
    import hashlib

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    qhash = hashlib.sha1(json.dumps(soql or {}, sort_keys=True).encode()).hexdigest()[:8]
    cache_path = CACHE_DIR / f"socrata_{dataset.dataset_id}_{qhash}.json"
    if _is_fresh(cache_path, max_age_days):
        log.info("Socrata cache hit: %s", cache_path)
        return json.loads(cache_path.read_text())

    log.info("Fetching Socrata dataset %s (%s)", dataset.dataset_id, dataset.description)
    rows: list[dict] = []
    offset = 0
    order = (soql or {}).get("$order", ":id")
    while True:
        params = {"$limit": page_size, "$offset": offset, "$order": order}
        params.update({k: v for k, v in (soql or {}).items() if k != "$order"})
        resp = _SESSION.get(dataset.url, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        page = resp.json()
        if not page:
            break
        rows.extend(page)
        offset += len(page)
        if len(page) < page_size or (max_rows is not None and len(rows) >= max_rows):
            break
    if max_rows is not None:
        rows = rows[:max_rows]

    cache_path.write_text(json.dumps(rows))
    log.info("Socrata %s: %d rows cached", dataset.dataset_id, len(rows))
    return rows
