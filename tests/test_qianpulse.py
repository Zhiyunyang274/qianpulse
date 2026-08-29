import numpy as np
from pathlib import Path

from qianpulse.engine import (
    bootstrap_baseline_divergence,
    convergence_curve,
    fingerprint_divergence,
    fuse_crossings,
)
from qianpulse.simulate import simulate_batch
from qianpulse.io_sensorlogger import discover_physical_runs
from qianpulse.physical_validation import analyse_physical_experiment
from qianpulse.pipeline import BridgePulseState, extract_feature_packet
from qianpulse.scale_simulation import run_scale_simulation
from qianpulse.scale_simulation import architecture_snapshot
import asyncio


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


def test_physical_validation_recomputes_clear_response_shift():
    data_root = Path(__file__).parents[1] / "data" / "physical_validation"
    if not data_root.exists():
        return
    discovered = discover_physical_runs(data_root)
    result = analyse_physical_experiment(discovered)

    assert len(result["baseline"]) == 3
    assert len(result["perturbed"]) == 3
    assert all(run["vertical_method"] == "Gravity projected"
               for run in result["baseline"] + result["perturbed"])
    assert 13.5 < result["baseline_group"]["dominant_frequency"] < 14.2
    assert 9.8 < result["perturbed_group"]["dominant_frequency"] < 10.5
    assert result["shift_percent"] < -20.0
    assert np.min(result["cross_state"]) > max(
        np.max(result["within_baseline"]), np.max(result["within_perturbed"])
    )


def test_physical_validation_supports_device_z_fallback():
    data_root = Path(__file__).parents[1] / "data" / "physical_validation"
    if not data_root.exists():
        return
    discovered = discover_physical_runs(data_root, vertical_method="z")
    result = analyse_physical_experiment(discovered)
    assert all(run["vertical_method"] == "Device Z axis"
               for run in result["baseline"] + result["perturbed"])
    assert result["shift_percent"] < -20.0


def test_feature_packet_and_incremental_bridge_state():
    crossings = simulate_batch(4, bridge_freq=7.8, seed=9)
    state = BridgePulseState("GZ-TEST")
    packets = [extract_feature_packet(c, "GZ-TEST", f"crossing-{i}") for i, c in enumerate(crossings)]
    updates = [state.update(packet) for packet in packets]
    assert updates[-1]["crossings"] == 4
    assert np.isfinite(updates[-1]["pulse_hz"])
    assert len(packets[-1].fingerprint) == 800


def test_bridge_state_rejects_wrong_partition():
    state = BridgePulseState("GZ-A")
    packet = extract_feature_packet(simulate_batch(1, seed=4)[0], "GZ-B", "c-1")
    try:
        state.update(packet)
    except ValueError:
        pass
    else:
        raise AssertionError("bridge partition mismatch must be rejected")


def test_local_scale_simulation_is_incremental_and_durable():
    result = asyncio.run(run_scale_simulation(fleet_size=20, crossings=40, workers=2))
    assert result["processed_count"] + result["rejected_count"] == 40
    assert result["low_quality_generated"] > 0
    assert result["rejected_count"] > 0
    assert result["rejected_debug_count"] == result["rejected_count"]
    assert result["bridge_state_updates"] == result["processed_count"]
    assert result["bridges_in_sqlite"] == 3
    assert 0.0 <= result["raw_retention_ratio"] <= 1.0
    assert result["full_history_rescan"] is False
    snap = architecture_snapshot(result)
    assert snap["label"] == "LOCAL SCALE SIMULATION"
    assert snap["stages"][2]["stage"] == "FeaturePacket"
