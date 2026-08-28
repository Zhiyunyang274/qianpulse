import numpy as np

from qianpulse.engine import (
    bootstrap_baseline_divergence,
    convergence_curve,
    fingerprint_divergence,
    fuse_crossings,
)
from qianpulse.simulate import simulate_batch


def test_baseline_pulse_recovers_bridge_frequency():
    fused = fuse_crossings(simulate_batch(50, bridge_freq=7.8, seed=42))
    assert abs(fused["dominant_frequency"] - 7.8) < 0.20


def test_single_crossing_is_defined_and_convergence_is_reasonable():
    crossings = simulate_batch(50, bridge_freq=7.8, seed=42)
    one = fuse_crossings(crossings[:1])
    assert np.isfinite(one["dominant_frequency"])
    curve = convergence_curve(crossings, counts=(1, 5, 10, 20, 30, 50))
    errors = [abs(item["dominant_frequency"] - 7.8) for item in curve]
    assert errors[-1] < 0.20
    assert curve[-1]["bootstrap_std_hz"] < curve[1]["bootstrap_std_hz"]


def test_shifted_fingerprint_exceeds_baseline_variability():
    baseline = simulate_batch(60, bridge_freq=7.8, seed=42)
    shifted = simulate_batch(60, bridge_freq=7.2, seed=142)
    base = fuse_crossings(baseline[:30])
    current = fuse_crossings(shifted[:30])
    threshold = bootstrap_baseline_divergence(baseline[:40], seed=50)["threshold95"]
    assert fingerprint_divergence(base["fingerprint"], current["fingerprint"]) > threshold


def test_same_state_is_not_an_alert_against_its_own_baseline():
    baseline = simulate_batch(60, bridge_freq=7.8, seed=42)
    a = fuse_crossings(baseline[:30])
    b = fuse_crossings(baseline[30:60])
    threshold = bootstrap_baseline_divergence(baseline[:40], seed=50)["threshold95"]
    assert fingerprint_divergence(a["fingerprint"], b["fingerprint"]) < threshold * 2.0
