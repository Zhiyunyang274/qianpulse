#!/usr/bin/env python3
"""Run the QianPulse engine demo without Streamlit."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qianpulse.simulation import simulate_batch
from qianpulse.fusion import fuse_crossings


def main():
    crossings = simulate_batch(50, bridge_freq=7.8, seed=42)
    pulse = fuse_crossings(crossings)
    print("QianPulse Engine · simulation")
    print(f"crossings: {len(crossings)}")
    print("true frequency: 7.800 Hz")
    print(f"recovered pulse: {pulse['dominant_frequency']:.3f} Hz")
    print(f"stability: {pulse['pulse_stability']:.3f}")


if __name__ == "__main__":
    main()
