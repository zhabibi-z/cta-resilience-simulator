"""
Reproducibility guarantee tests.

A trial is reproducible iff re-running it with its logged child seed produces
bit-identical output across all time series metrics.

These tests must pass before any analysis pipeline runs.
"""

import numpy as np
import pytest

from core.graph import build_graph
from core.simulator import MotterLaiSimulator
from experiments.seeds import generate_trial_seeds, make_rng

MASTER_SEED = 42
N_REPRO_TRIALS = 10


def _extract_fingerprint(result) -> tuple:
    """Deterministic scalar fingerprint of a SimulationResult."""
    return (
        result.seed_node,
        result.termination_reason,
        result.phi_c,
        tuple(tr.tick               for tr in result.timeseries),
        tuple(tr.efficiency         for tr in result.timeseries),
        tuple(tr.n_active           for tr in result.timeseries),
        tuple(tr.n_cascaded_cumulative for tr in result.timeseries),
        tuple(tr.n_components       for tr in result.timeseries),
    )


def _run_with_seed(G, alpha: float, strategy: str, child_seed: int, trial_id: int = 0):
    sim = MotterLaiSimulator(G, alpha=alpha)
    rng = make_rng(child_seed)
    return sim.run_trial(trial_id=trial_id, strategy=strategy, rng=rng, child_seed=child_seed)


@pytest.fixture(scope="module")
def G():
    return build_graph()


@pytest.fixture(scope="module")
def child_seeds():
    """Generate N_REPRO_TRIALS child seeds from the master seed."""
    root = np.random.SeedSequence(MASTER_SEED)
    children = root.spawn(N_REPRO_TRIALS)
    return [int(c.generate_state(1, dtype=np.uint64)[0]) for c in children]


# ── Core reproducibility ───────────────────────────────────────────────────────

def test_random_trials_bit_identical(G, child_seeds):
    """Running the same child seed twice must produce bit-identical output."""
    for i, seed in enumerate(child_seeds):
        r1 = _extract_fingerprint(_run_with_seed(G, alpha=0.2, strategy="random", child_seed=seed))
        r2 = _extract_fingerprint(_run_with_seed(G, alpha=0.2, strategy="random", child_seed=seed))
        assert r1 == r2, (
            f"Trial {i} (seed={seed}): non-identical output on second run.\n"
            f"  seed_node: {r1[0]} vs {r2[0]}\n"
            f"  phi_c:     {r1[2]} vs {r2[2]}"
        )


def test_targeted_trials_bit_identical(G, child_seeds):
    """Targeted strategy (top_k=0) must be fully deterministic across all seeds."""
    fingerprints = [
        _extract_fingerprint(_run_with_seed(G, alpha=0.2, strategy="targeted", child_seed=s))
        for s in child_seeds[:5]
    ]
    # All targeted trials must target the same seed node
    seed_nodes = {fp[0] for fp in fingerprints}
    assert len(seed_nodes) == 1, (
        f"Targeted strategy selected different seed nodes across trials: {seed_nodes}"
    )
    # All efficiency trajectories must be identical
    for i, fp in enumerate(fingerprints[1:], start=1):
        assert fp[3] == fingerprints[0][3], f"Tick sequences differ between trial 0 and {i}"
        assert fp[4] == fingerprints[0][4], f"Efficiency trajectories differ between trial 0 and {i}"


def test_different_random_seeds_differ(G, child_seeds):
    """Different child seeds must produce different random trial seed nodes."""
    seed_nodes = set()
    for s in child_seeds:
        result = _run_with_seed(G, alpha=0.3, strategy="random", child_seed=s)
        seed_nodes.add(result.seed_node)
    assert len(seed_nodes) > 1, (
        "All different child seeds produced the same random seed node — "
        "RNG isolation is broken."
    )


def test_alpha_variation_changes_cascade(G, child_seeds):
    """Different alpha values must produce detectably different cascade dynamics.

    Uses targeted strategy (always selects the highest-BC node) to guarantee
    a non-trivial seed node regardless of child seed value. Terminal nodes
    with BC=0 produce zero cascade at all alpha levels and would make this
    test vacuous with random seed selection.
    """
    seed = child_seeds[0]
    results = {
        alpha: _run_with_seed(G, alpha=alpha, strategy="targeted", child_seed=seed)
        for alpha in [0.10, 0.50]
    }
    casc_low  = results[0.10].timeseries[-1].n_cascaded_cumulative
    casc_high = results[0.50].timeseries[-1].n_cascaded_cumulative
    phi_low   = results[0.10].phi_c
    phi_high  = results[0.50].phi_c
    assert phi_low != phi_high or casc_low != casc_high, (
        f"alpha=0.10 and alpha=0.50 produced identical outcomes on the highest-BC node "
        f"(phi_c: {phi_low} vs {phi_high}, cascade: {casc_low} vs {casc_high}) — "
        f"simulator is not reading alpha correctly."
    )


# ── Seed architecture correctness ─────────────────────────────────────────────

def test_generate_trial_seeds_deterministic():
    """generate_trial_seeds must return identical mappings on repeated calls."""
    m1 = generate_trial_seeds(MASTER_SEED, n_alpha=3, n_strategies=2, n_trials=5)
    m2 = generate_trial_seeds(MASTER_SEED, n_alpha=3, n_strategies=2, n_trials=5)
    assert m1 == m2, "generate_trial_seeds returned different mappings on second call"


def test_generate_trial_seeds_all_unique():
    """Every (alpha_idx, strategy_idx, trial_id) triple must map to a unique seed."""
    mapping = generate_trial_seeds(MASTER_SEED, n_alpha=3, n_strategies=2, n_trials=10)
    seeds = list(mapping.values())
    assert len(seeds) == len(set(seeds)), (
        f"Duplicate child seeds found — {len(seeds) - len(set(seeds))} collisions"
    )


def test_generate_trial_seeds_key_coverage():
    """All expected keys must be present in the mapping."""
    n_alpha, n_strat, n_trials = 2, 2, 5
    mapping = generate_trial_seeds(MASTER_SEED, n_alpha, n_strat, n_trials)
    assert len(mapping) == n_alpha * n_strat * n_trials
    for a in range(n_alpha):
        for s in range(n_strat):
            for t in range(n_trials):
                assert (a, s, t) in mapping, f"Key ({a},{s},{t}) missing from seed map"


def test_make_rng_produces_generator():
    rng = make_rng(12345)
    assert hasattr(rng, "integers"), "make_rng did not return a numpy Generator"


def test_rng_isolation():
    """Two RNGs from different seeds must produce different integer sequences."""
    rng1 = make_rng(111)
    rng2 = make_rng(222)
    seq1 = [int(rng1.integers(0, 10_000)) for _ in range(20)]
    seq2 = [int(rng2.integers(0, 10_000)) for _ in range(20)]
    assert seq1 != seq2, "Different child seeds produced identical RNG sequences"


def test_rng_same_seed_same_sequence():
    """Same seed must always produce the same integer sequence."""
    for seed in [0, 42, 99999]:
        seq1 = [int(make_rng(seed).integers(0, 10_000)) for _ in range(20)]
        seq2 = [int(make_rng(seed).integers(0, 10_000)) for _ in range(20)]
        assert seq1 == seq2, f"Same seed {seed} produced different sequences"
