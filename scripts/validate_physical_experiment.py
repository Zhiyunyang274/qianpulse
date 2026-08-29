#!/usr/bin/env python3
"""Analyse the real Sensor Logger ZIP experiment without Streamlit."""
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
from qianpulse.ingestion import discover_physical_runs
from qianpulse.validation import analyse_physical_experiment
from qianpulse.signal import crossing_to_peaks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=str(ROOT / "data" / "physical_validation"))
    args = parser.parse_args()
    result = analyse_physical_experiment(discover_physical_runs(args.root))
    print("QianPulse Engine · physical validation")
    for state in ("baseline", "perturbed"):
        runs = result[state]
        print(f"{state} sample rate: {np.mean([r['sampling_rate_estimate'] for r in runs]):.2f} Hz")
        peaks = [crossing_to_peaks(r)["peaks"] for r in runs]
        print(f"{state} individual peaks: " + "; ".join(", ".join(f"{x:.3f}" for x in p) for p in peaks))
    print(f"fused baseline pulse: {result['baseline_group']['dominant_frequency']:.3f} Hz")
    print(f"fused perturbed pulse: {result['perturbed_group']['dominant_frequency']:.3f} Hz")
    print(f"response shift: {result['shift_percent']:.3f}%")
    print(f"within-state JS: {max(np.max(result['within_baseline']), np.max(result['within_perturbed'])):.3f}")
    print(f"cross-state JS: {np.min(result['cross_state']):.3f}")


if __name__ == "__main__":
    main()
