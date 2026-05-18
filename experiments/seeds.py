"""
Two-level deterministic seed architecture.

Master seed → SeedSequence → N independent child SeedSequences → child integer seeds.
Each child seed is keyed to an (alpha_idx, strategy_idx, trial_id) triple,
guaranteeing isolation and reproducibility regardless of execution order or
degree of parallelism.
"""

from __future__ import annotations

import numpy as np


def generate_trial_seeds(
    master_seed: int,
    n_alpha: int,
    n_strategies: int,
    n_trials: int,
) -> dict[tuple[int, int, int], int]:
    """Return a mapping (alpha_idx, strategy_idx, trial_id) → child_seed (int).

    Deterministic for any given master_seed and dimension sizes.
    Spawning is done upfront so the mapping is position-independent.
    """
    total = n_alpha * n_strategies * n_trials
    root = np.random.SeedSequence(master_seed)
    children = root.spawn(total)

    result: dict[tuple[int, int, int], int] = {}
    idx = 0
    for a_idx in range(n_alpha):
        for s_idx in range(n_strategies):
            for t_idx in range(n_trials):
                state = children[idx].generate_state(1, dtype=np.uint64)
                result[(a_idx, s_idx, t_idx)] = int(state[0])
                idx += 1
    return result


def make_rng(child_seed: int) -> np.random.Generator:
    """Create an isolated Generator from a child seed integer."""
    return np.random.default_rng(child_seed)
