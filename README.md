# CTA 'L' Network Resilience Simulator

A cascading-failure simulator for the Chicago Transit Authority (CTA) 'L' rail
network, implementing the **Motter–Lai (2002)** overload model. It quantifies how
the network's efficiency collapses as stations fail and their passenger load
redistributes onto neighbours — under both **targeted** and **random** initial
failures — and estimates the critical removal fraction at which the system breaks
down.

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

## Reference

Motter AE, Lai Y-C. *Cascade-based attacks on complex networks.* Physical Review E
66, 065102(R) (2002).
