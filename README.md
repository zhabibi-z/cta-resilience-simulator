# CTA 'L' Network Resilience Simulator

A cascading-failure simulator for the Chicago Transit Authority (CTA) 'L' rail
network, implementing the **Motter–Lai (2002)** overload model. It quantifies how
the network's efficiency collapses as stations fail and their passenger load
redistributes onto neighbours — under both **targeted** and **random** initial
failures — and estimates the critical removal fraction at which the system breaks
down.

> **Evolving into a decision-support tool.** The project is being extended from a topological
> cascade demo into a real-data, multi-modal (bus + rail) resilience decision-support tool with
> recovery dynamics, passenger-centric metrics, and hardening recommendations. **Phase 0 (below)
> ships the real-data foundation**; the strict Motter–Lai engine is retained as the baseline.

## Data foundation (real CTA open data)

The network is built from **real, public** sources — no hand-coded topology — with full,
auditable provenance ([`ingest/datasets.py`](ingest/datasets.py)):

| Layer | Source |
|-------|--------|
| Rail topology, geo, run-times | **CTA GTFS** (`transitchicago.com` schedule feed) |
| Rail station ridership (node weights) | Chicago Data Portal — *'L' station entries, daily totals* (`5neh-572f`) |
| Bus topology (aggregated) | **CTA GTFS** — representative trip per route, snapped to a ~1 km grid |
| Bus ridership (node weights) | Chicago Data Portal — *bus routes, daily totals* (`jyb9-n7fm`) |

Build the canonical **bus + rail bilayer** (downloads + caches real data, then caches the graph):

```bash
python -m ingest.network
# → bilayer: 143 rail stations + 628 bus cells, 1263 edges (151 rail<->bus transfers),
#   one connected component, ~898k weekday boardings (rail 328k + bus 569k)
```

**Rail:** stations collapse to GTFS `parent_station` (the `4xxxx` map_id ridership is keyed on);
edges are consecutive stations weighted by median scheduled run-time. **Bus:** one representative
trip per route defines its path, stops are snapped to a ~1 km spatial grid (a bus node ≈ a
neighbourhood), and each route's ridership is apportioned across the cells it traverses. **Transfer
edges** couple each rail station to nearby bus cells (walking distance, with a nearest-cell
fallback) — so rail failures can shift demand to bus, and a spatial hazard degrades both layers at
once. Downloads are cached/freshness-controlled (tests run offline); the legacy hard-coded topology
remains an automatic fallback.

## Model

Strict Motter–Lai (2002):

- Initial load `L₀(i)` = unnormalized betweenness centrality on the full graph.
- Capacity `C(i) = (1 + α)·L₀(i)`, fixed for the run (`α` = tolerance parameter).
- Each cascade tick recomputes load on the surviving subgraph; every node whose
  current load exceeds its capacity fails simultaneously that tick.
- A run terminates when the cascade quiesces, the network collapses, or efficiency
  reaches zero. `φ_c` is the removal fraction at which global efficiency first drops
  below half of its baseline.

## Two entry points

- **Batch experiments** (`core/` + `experiments/`) — headless, fully reproducible
  runs driven entirely by `experiments/config.yaml` (single source of truth: master
  seed, `α` grid, targeted-vs-random strategy, number of trials, thresholds).
- **Interactive visualization** (`cta_resilience_sim.py`) — a PyGame animation of the
  network, stations coloured by CTA line, showing a cascade propagate in real time.
  Written to be Pygbag/asyncio-compatible so it can also run in the browser.

## Quick start

```bash
pip install -r requirements.txt

# Reproducible batch experiment (writes results under data/raw/)
python -m experiments.batch_runner

# Interactive visualization
python cta_resilience_sim.py

# Tests: graph construction, simulator correctness, reproducibility
pytest
```

## Structure

```
core/                     # headless model (no pygame dependency)
  graph.py                #   CTA network construction
  simulator.py            #   strict Motter–Lai cascade engine
  metrics.py              #   global efficiency, betweenness, components (pure functions)
experiments/              # reproducible experiment harness
  config.yaml             #   all hyperparameters (seed, α grid, strategies, thresholds)
  batch_runner.py         #   runs the α × strategy × trial grid
  seeds.py                #   deterministic per-trial seeding
cta_resilience_sim.py     # interactive PyGame visualization
tests/                    # graph, simulator, and reproducibility tests
```

## Reproducibility

Every experiment is fully determined by `experiments/config.yaml` and a master seed
(default 42), with deterministic per-trial child seeds — re-running reproduces
identical results. `tests/test_reproducibility.py` guards this.

## References

**Model — the overload cascade this simulator implements:**

1. Motter AE, Lai Y-C. *Cascade-based attacks on complex networks.* Physical Review E
   **66**, 065102(R) (2002). [doi:10.1103/PhysRevE.66.065102](https://doi.org/10.1103/PhysRevE.66.065102)
   — introduces the load/capacity overload model (initial load = betweenness,
   capacity = (1+α)·load) used here.

**Foundational — targeted-vs-random attack tolerance it builds on:**

2. Albert R, Jeong H, Barabási A-L. *Error and attack tolerance of complex networks.*
   Nature **406**, 378–382 (2000). [doi:10.1038/35019019](https://doi.org/10.1038/35019019)
   — the targeted (high-centrality) vs. random failure framing that Motter–Lai
   extended with load dynamics.

**Domain — resilience of urban rail transit networks (incl. Chicago):**

3. *Topological Determinants of Resilience in Urban Rail Networks Facing Multi-Hazard
   Disruptions.* arXiv:2407.06359 (2024). [arxiv.org/abs/2407.06359](https://arxiv.org/abs/2407.06359)
   — percolation/attack analysis of nine urban rail networks including Chicago.

The Motter–Lai model was motivated by the Internet and power grids; applying it to the
CTA 'L' network is this project's framing.
