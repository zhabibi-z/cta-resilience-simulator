# CTA Multi-Modal Resilience — Decision-Support Tool

A resilience decision-support tool for the **Chicago Transit Authority (CTA) bus + rail network**,
built on **real open data** (GTFS + published ridership). It answers a planner's questions: *if a
disruption hits — a flood, a hub failure, a track outage — how badly does passenger service
degrade, how fast does it recover, and where should we invest to make it more resilient?*

It couples a **real bus+rail bilayer**, a **passenger-flow** cascade model, **recovery dynamics**
(the resilience triangle), realistic **hazards** (spatial flood/storm, targeted, edge/track), a
**percolation** sweep with random-graph baselines, a **hardening optimizer** (where to invest), and
an **interactive dashboard** — with the strict **Motter–Lai (2002)** overload model retained as the
scientific baseline.

**Run it:** `pip install -r requirements.txt && python -m ingest.network && streamlit run dashboard/app.py`

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

## Baseline model

The scientific baseline is strict **Motter–Lai (2002)** — kept intact and used as the reference
against which the passenger-flow engine (below) is compared:

- Initial load `L₀(i)` = unnormalized betweenness centrality on the full graph.
- Capacity `C(i) = (1 + α)·L₀(i)`, fixed for the run (`α` = tolerance parameter).
- Each cascade tick recomputes load on the surviving subgraph; every node whose
  current load exceeds its capacity fails simultaneously that tick.
- A run terminates when the cascade quiesces, the network collapses, or efficiency
  reaches zero. `φ_c` is the removal fraction at which global efficiency first drops
  below half of its baseline.

## Resilience engine — passenger-centric + recovery (Phase 1)

Beyond the strict topological baseline, the project models resilience the way the transit
literature defines it — **service impact and recovery**, not just failure :

- **Pluggable load models** ([`core/load_models.py`](core/load_models.py)) — `BetweennessLoad`
  (strict Motter–Lai baseline) and `PassengerFlowLoad` (gravity OD demand, `ridership_i ×
  ridership_j`, routed on travel-time shortest paths). The load model decides *what* cascades.
- **Passenger performance metric** ([`core/performance.py`](core/performance.py)) — *served
  ridership*: the share of the ridership base still attached to the functioning core network.
- **Disruption → recovery scenarios** ([`core/resilience.py`](core/resilience.py)) — a hazard
  triggers a cascade (degradation), then failed stations are restored in a chosen priority order
  at a repair rate (recovery), tracing the **resilience triangle** `Q(t)` and an **integrated
  resilience** score `R = mean(Q)/Q₀ ∈ [0,1]`.

Real-data example — disrupt the busiest station (Lake/Subway) at α = 0.15:

| Load model | Recovery order | Robustness (min service) | Integrated `R` | Cascade size |
|---|---|:---:|:---:|:---:|
| Betweenness (baseline) | ridership | 0.99 | 0.996 | 1 |
| **Passenger flow** | ridership | **0.25** | **0.82** | **336 / 771** |
| **Passenger flow** | random | 0.25 | 0.77 | 336 / 771 |

Real passenger load concentrates on hubs, so a single hub failure cascades to ~44% of the network
and cuts served ridership to 25% at the trough — a vulnerability the topological baseline misses.
And **restoring high-ridership stations first retains ~6% more integrated service** than arbitrary
order: an actionable recovery-prioritisation recommendation.

## Hazards & percolation (Phase 2)

Resilience is stress-tested with realistic disruptions, not just single-node removal
([`core/hazards.py`](core/hazards.py), [`core/percolation.py`](core/percolation.py)):

- **Spatial (flood/storm) hazards** fail every station *and* bus cell within a radius of a
  geographic point — a genuinely multi-modal disruption. *Flood the Loop* on the real bilayer:

  | Radius | Stations hit | Cascade | Min service | Integrated `R` |
  |---|---|:---:|:---:|:---:|
  | 1 km | 15 rail + 2 bus | 270 / 771 | 0.19 | 0.85 |
  | 2 km | 20 rail + 11 bus | 398 / 771 | 0.11 | 0.76 |
  | 3 km | 29 rail + 21 bus | 385 / 771 | 0.06 | 0.75 |

- **Edge/track failures** (segments, not just stations) and **targeted/random station** hazards.
- **Percolation sweep** — remove a growing fraction and trace the robustness curve → the critical
  fraction `φ_c`. Anchored against **null models** (Erdős–Rényi, Barabási–Albert) of the same size:

  | Network | `φ_c` targeted | `φ_c` random |
  |---|:---:|:---:|
  | **CTA (real)** | 0.275 | 0.375 |
  | Barabási–Albert (scale-free) | 0.125 | 0.400 |

  CTA shows the classic targeted-vs-random gap, but is **far more robust to targeted attack than a
  pure hub-and-spoke (scale-free) network** — a concrete, defensible statement about its topology.

## Hardening optimization (Phase 3)

The prescriptive layer ([`core/hardening.py`](core/hardening.py)): given a hazard and a protection
budget, greedily choose which stations to **harden** (flood-proof / back up so they cannot fail)
to most improve resilience. Candidates are restricted to stations that actually fail, and a fast
sampled-betweenness path keeps the thousands of trial cascades tractable.

> Example — attack on the three busiest hubs (O'Hare, Lake, Clark/Lake): hardening **Fullerton**
> then **Clark/Lake** raises integrated resilience `R` from 0.84 → 0.87. The optimizer returns a
> priority-ordered list and a diminishing-returns curve — a concrete *where-to-invest* recommendation.

## Decision dashboard (Phase 3)

The interactive front end ([`dashboard/app.py`](dashboard/app.py), Streamlit + a real CTA map):
pick a disruption (flood a region, attack the busiest hubs, random failure), tune the model, and
see — live — the cascade on the map, the resilience triangle, and a priority-ordered list of
stations to harden.

```bash
streamlit run dashboard/app.py
```

## Other entry points

- **Batch experiments** (`experiments/`) — headless, reproducible runs driven by
  `experiments/config.yaml`.
- **PyGame animation** (`cta_resilience_sim.py`) — a real-time cascade animation
  (optional; `pip install -r optional-viz.txt`).

## Quick start

```bash
pip install -r requirements.txt

# Build the real CTA bilayer (downloads + caches GTFS + ridership)
python -m ingest.network

# Interactive decision dashboard
streamlit run dashboard/app.py

# Tests
pytest
```

## Structure

```
ingest/                   # DATA LAYER — real CTA network from open data
  datasets.py             #   provenance registry (GTFS URL + Socrata dataset IDs)
  download.py             #   cached GTFS download + paginated/aggregating Socrata client
  gtfs.py                 #   memory-safe GTFS reader (streams the 363 MB stop_times)
  rail.py / bus.py        #   rail layer + aggregated bus layer builders
  ridership.py            #   real boardings -> node weights
  transfers.py / geo.py   #   rail<->bus transfer edges; haversine/grid helpers
  network.py              #   build_cta_network() -> the canonical bilayer (+ cache + CLI)

core/                     # ENGINE (headless, no pygame)
  load_models.py          #   LoadModel Strategy: BetweennessLoad (baseline) + PassengerFlowLoad
  performance.py          #   served-ridership performance metric
  resilience.py           #   disruption->recovery scenarios + the resilience triangle
  hazards.py / geo_ref.py #   spatial (flood/storm), targeted, edge hazards; named landmarks
  percolation.py          #   robustness sweep, phi_c, ER/BA null models
  hardening.py            #   greedy hardening optimizer (where to invest)
  simulator.py/metrics.py #   strict Motter–Lai baseline + pure metric functions
  graph.py                #   legacy hard-coded topology (automatic fallback)

dashboard/                # DECISION DASHBOARD
  app.py                  #   Streamlit UI (CTA map, resilience triangle, recommendations)
  logic.py                #   pure, UI-free logic (unit-tested)

experiments/              # reproducible batch harness (config.yaml + batch_runner.py)
cta_resilience_sim.py     # PyGame cascade animation
tests/                    # engine, data-layer, hazards, hardening, dashboard tests (75)
```

## Reproducibility

Every experiment is fully determined by `experiments/config.yaml` and a master seed
(default 42), with deterministic per-trial child seeds — re-running reproduces
identical results. `tests/test_reproducibility.py` guards this.

## References

**Model — the overload cascade at the project's core:**

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
