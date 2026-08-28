"""Deterministic, intentionally dirty demo signals for QianPulse."""

import numpy as np


def simulate_crossing(fs=100, duration=8.0, bridge_freq=7.8, vehicle_freq=None,
                      noise_std=0.45, rng=None):
    rng = np.random.default_rng() if rng is None else rng
    n = max(32, int(fs * duration))
    t = np.arange(n) / fs
    vehicle_freq = float(vehicle_freq if vehicle_freq is not None else rng.uniform(1.2, 3.0))
    bridge_amp = rng.uniform(0.45, 1.1)
    vehicle_amp = rng.uniform(0.5, 1.3)
    phase = rng.uniform(0, 2 * np.pi)
    envelope = np.exp(-0.5 * ((t - duration / 2) / (duration / 4.5)) ** 2)
    bridge = bridge_amp * envelope * np.sin(2 * np.pi * bridge_freq * t + phase)
    vehicle = vehicle_amp * np.sin(2 * np.pi * vehicle_freq * t + rng.uniform(0, 2 * np.pi))
    roughness_freq = rng.uniform(10, 18)
    roughness = rng.uniform(0.05, 0.25) * np.sin(2 * np.pi * roughness_freq * t + rng.uniform(0, 2 * np.pi))
    noise = rng.normal(0, noise_std, size=n)
    impulses = np.zeros(n)
    for _ in range(int(rng.integers(1, 4))):
        idx = int(rng.integers(int(0.5 * fs), max(int(0.5 * fs) + 1, int((duration - 0.5) * fs))))
        width = int(rng.integers(2, 8))
        end = min(n, idx + width)
        if end - idx >= 2:
            impulses[idx:end] += rng.uniform(0.7, 1.8) * np.hanning(end - idx)
    acc = bridge + vehicle + roughness + noise + impulses
    return {"t": t, "acc": acc, "bridge_freq": float(bridge_freq),
            "vehicle_freq": vehicle_freq, "fs": int(fs)}


def simulate_batch(n_crossings=40, fs=100, duration=8.0, bridge_freq=7.8, seed=42):
    rng = np.random.default_rng(seed)
    return [simulate_crossing(fs=fs, duration=duration, bridge_freq=bridge_freq,
                              vehicle_freq=rng.uniform(1.2, 3.0),
                              noise_std=rng.uniform(0.30, 0.60), rng=rng)
            for _ in range(n_crossings)]
