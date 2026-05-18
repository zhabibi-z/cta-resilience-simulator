"""
Batch experiment runner for the CTA L Motter-Lai resilience study.

Usage:
    python -m experiments.batch_runner

Reads experiments/config.yaml.
Writes two Parquet files per (alpha, strategy) cell into data/raw/:
  - timeseries_alpha{alpha}_strategy_{strategy}.parquet
  - summary_alpha{alpha}_strategy_{strategy}.parquet

Worker function _run_trial is module-level for multiprocessing.Pool pickling
compatibility on macOS (spawn start method).
"""

from __future__ import annotations

import multiprocessing
import pathlib
import sys
import time
from collections import defaultdict
from typing import Any

# Ensure project root is on sys.path when invoked as python -m experiments.batch_runner
_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import yaml
import pandas as pd


# ── Worker (module-level for pickle safety) ───────────────────────────────────

def _run_trial(task: dict[str, Any]) -> dict[str, Any]:
    """Execute a single simulation trial. Runs in a worker process."""
    from core.graph import build_graph
    from core.simulator import MotterLaiSimulator
    from experiments.seeds import make_rng

    G = build_graph()
    sim = MotterLaiSimulator(
        G=G,
        alpha=task["alpha"],
        max_ticks_multiplier=task["max_ticks_multiplier"],
        efficiency_collapse_threshold=task["collapse_threshold"],
        top_k_fraction=task["top_k_fraction"],
    )
    rng = make_rng(task["child_seed"])
    result = sim.run_trial(
        trial_id=task["trial_id"],
        strategy=task["strategy"],
        rng=rng,
        child_seed=task["child_seed"],
    )
    return {
        "timeseries": result.to_timeseries_records(),
        "summary":    result.to_summary_record(),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    config_path = pathlib.Path(__file__).parent / "config.yaml"
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    master_seed      = int(cfg["master_seed"])
    n_trials         = int(cfg["n_trials"])
    alpha_values     = [float(a) for a in cfg["alpha_values"]]
    strategies       = list(cfg["strategies"])
    max_ticks_mult   = int(cfg["termination_max_ticks_multiplier"])
    collapse_thresh  = float(cfg["efficiency_collapse_threshold"])
    top_k_fraction   = float(cfg.get("targeted_top_k_fraction", 0.0))
    output_dir       = _ROOT / cfg["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Generate child seeds ─────────────────────────────────────────────────
    from experiments.seeds import generate_trial_seeds
    seed_map = generate_trial_seeds(
        master_seed=master_seed,
        n_alpha=len(alpha_values),
        n_strategies=len(strategies),
        n_trials=n_trials,
    )

    # ── Build task list ──────────────────────────────────────────────────────
    tasks: list[dict] = []
    for a_idx, alpha in enumerate(alpha_values):
        for s_idx, strategy in enumerate(strategies):
            for trial_id in range(n_trials):
                child_seed = seed_map[(a_idx, s_idx, trial_id)]
                tasks.append({
                    "alpha":               alpha,
                    "strategy":            strategy,
                    "trial_id":            trial_id,
                    "child_seed":          child_seed,
                    "max_ticks_multiplier":max_ticks_mult,
                    "collapse_threshold":  collapse_thresh,
                    # top_k_fraction only meaningful for targeted; pass 0 for random
                    "top_k_fraction":      top_k_fraction if strategy == "targeted" else 0.0,
                })

    total      = len(tasks)
    n_cells    = len(alpha_values) * len(strategies)
    n_workers  = multiprocessing.cpu_count()

    print(f"\nCTA L Motter-Lai Batch Runner")
    print(f"{'─' * 45}")
    print(f"  Master seed  : {master_seed}")
    print(f"  Alpha levels : {len(alpha_values)}  {alpha_values}")
    print(f"  Strategies   : {strategies}")
    print(f"  Trials/cell  : {n_trials}")
    print(f"  Total trials : {total}")
    print(f"  Output cells : {n_cells}")
    print(f"  Workers      : {n_workers}")
    print(f"  Output dir   : {output_dir}")
    print(f"{'─' * 45}\n")

    # ── Run with progress reporting via imap_unordered ───────────────────────
    t_start = time.perf_counter()
    results: list[dict] = [None] * total  # type: ignore[list-item]
    task_index = {id(t): i for i, t in enumerate(tasks)}

    completed = 0
    report_every = max(1, total // 20)  # report at ~5% intervals

    # imap_unordered does not preserve order; collect with original index via enumeration
    ordered_results: list[dict | None] = [None] * total

    with multiprocessing.Pool(processes=n_workers) as pool:
        for i, res in enumerate(pool.imap_unordered(_run_trial, tasks, chunksize=4)):
            ordered_results[i] = res
            completed += 1
            if completed % report_every == 0 or completed == total:
                elapsed = time.perf_counter() - t_start
                rate = completed / elapsed if elapsed > 0 else 0
                eta = (total - completed) / rate if rate > 0 else 0
                print(
                    f"  [{completed:>5}/{total}]  "
                    f"{completed/total*100:5.1f}%  "
                    f"elapsed {elapsed:6.1f}s  "
                    f"ETA {eta:6.1f}s"
                )

    # NOTE: imap_unordered loses task association; re-run with imap to keep order
    # The progress loop above collected by arrival order, which is sufficient for
    # grouping. We re-run imap (ordered) for deterministic cell grouping.
    print("\n  Collecting ordered results...")
    t2 = time.perf_counter()
    with multiprocessing.Pool(processes=n_workers) as pool:
        ordered_results = list(pool.imap(_run_trial, tasks, chunksize=4))
    print(f"  Ordered collection complete in {time.perf_counter()-t2:.1f}s")

    # ── Group by (alpha, strategy) and write Parquet ─────────────────────────
    ts_groups:  defaultdict[tuple, list] = defaultdict(list)
    sum_groups: defaultdict[tuple, list] = defaultdict(list)

    runaway_count = 0
    for task, res in zip(tasks, ordered_results):
        key = (task["alpha"], task["strategy"])
        ts_groups[key].extend(res["timeseries"])
        sum_groups[key].append(res["summary"])
        if res["summary"]["termination_reason"] == "RUNAWAY":
            runaway_count += 1

    written = 0
    for (alpha, strategy), ts_records in sorted(ts_groups.items()):
        alpha_str = f"{alpha:.2f}"
        ts_path  = output_dir / f"timeseries_alpha{alpha_str}_strategy_{strategy}.parquet"
        sum_path = output_dir / f"summary_alpha{alpha_str}_strategy_{strategy}.parquet"

        pd.DataFrame(ts_records).to_parquet(ts_path,  index=False)
        pd.DataFrame(sum_groups[(alpha, strategy)]).to_parquet(sum_path, index=False)
        written += 2
        print(f"  → {ts_path.name}")
        print(f"  → {sum_path.name}")

    elapsed_total = time.perf_counter() - t_start
    print(f"\n{'─' * 45}")
    print(f"  Done.  {written} files written to {output_dir}")
    print(f"  Total wall time : {elapsed_total:.1f}s")
    if runaway_count:
        print(f"  WARNING: {runaway_count} RUNAWAY trials detected — "
              f"exclude from phi_c analysis (flag in summary files).")
    print()


if __name__ == "__main__":
    # Required guard for multiprocessing spawn on macOS/Windows
    multiprocessing.freeze_support()
    main()
