"""Engine-facing streaming primitives.

This module keeps the production boundary explicit: raw crossing data enters once,
the edge extracts a compact feature packet, and a bridge state is updated
incrementally without rescanning all historical crossings.
"""
from dataclasses import dataclass, asdict
from typing import Dict, Optional
import numpy as np

from qianpulse.engine import crossing_to_peaks, fingerprint_divergence, fuse_crossings


@dataclass
class FeaturePacket:
    bridge_id: str
    crossing_id: str
    sample_rate_hz: float
    duration_s: float
    dominant_frequency_hz: float
    candidate_peaks_hz: list
    quality: float
    fingerprint: list
    raw_retained: bool = False

    def to_dict(self):
        return asdict(self)


def extract_feature_packet(crossing: dict, bridge_id: str, crossing_id: str,
                           retain_raw: bool = False) -> FeaturePacket:
    """Run edge-side QC and spectral extraction for one crossing."""
    acc = np.asarray(crossing.get("acc", []), dtype=float).reshape(-1)
    fs = float(crossing.get("fs", 0.0))
    # Quality gate happens before spectral state updates. Short, invalid, or
    # non-physical sampling windows are rejected rather than contaminating a
    # bridge pulse with an unusable crossing.
    if len(acc) < 32 or not np.isfinite(fs) or fs < 10.0 or not np.all(np.isfinite(acc)):
        raise ValueError("Crossing failed quality control")
    result = crossing_to_peaks(crossing)
    if not np.isfinite(result["quality"]):
        raise ValueError("Crossing failed quality control")
    dominant = float(result["peaks"][np.argmax(result["peak_scores"])]) if len(result["peaks"]) else np.nan
    grid = np.linspace(3.0, 15.0, 800)
    fp = np.interp(grid, result["f"], result["pxx"], left=0.0, right=0.0)
    fp = fp / max(float(np.sum(fp)), 1e-12)
    return FeaturePacket(
        bridge_id=bridge_id, crossing_id=crossing_id,
        sample_rate_hz=float(crossing.get("fs", np.nan)),
        duration_s=float(len(crossing.get("acc", [])) / max(float(crossing.get("fs", 100)), 1e-9)),
        dominant_frequency_hz=dominant,
        candidate_peaks_hz=[float(x) for x in result["peaks"]],
        quality=float(result["quality"]), fingerprint=fp.tolist(),
        raw_retained=bool(retain_raw),
    )


class BridgePulseState:
    """Incremental bridge-level state built from feature packets."""
    def __init__(self, bridge_id: str, grid: Optional[np.ndarray] = None):
        self.bridge_id = bridge_id
        self.grid = np.asarray(grid if grid is not None else np.linspace(3.0, 15.0, 800))
        self.count = 0
        self.full_history_rescans = 0
        self._fingerprint_sum = np.zeros_like(self.grid)
        self._peak_values = []

    def update(self, packet: FeaturePacket) -> dict:
        if packet.bridge_id != self.bridge_id:
            raise ValueError(f"packet bridge_id {packet.bridge_id!r} does not match {self.bridge_id!r}")
        fp = np.asarray(packet.fingerprint, dtype=float)
        if len(fp) != len(self.grid):
            fp = np.interp(self.grid, np.linspace(self.grid.min(), self.grid.max(), len(fp)), fp)
        self._fingerprint_sum += fp
        self._peak_values.append(packet.dominant_frequency_hz)
        self.count += 1
        fused = self._fingerprint_sum / max(self.count, 1)
        pulse = float(self.grid[np.argmax(fused)]) if np.any(fused) else np.nan
        return {"bridge_id": self.bridge_id, "crossings": self.count,
                "pulse_hz": pulse, "stability": self.stability()}

    def stability(self) -> float:
        if self.count < 2:
            return 0.0
        spread = float(np.nanstd(self._peak_values))
        return float(np.clip(np.exp(-spread / 0.20), 0.0, 1.0))

    def compare(self, baseline: "BridgePulseState", threshold: float) -> dict:
        if baseline.bridge_id != self.bridge_id:
            raise ValueError("baseline and current states must share bridge_id")
        a = baseline._fingerprint_sum / max(baseline.count, 1)
        b = self._fingerprint_sum / max(self.count, 1)
        divergence = fingerprint_divergence(a, b)
        status = "RESPONSE SHIFT" if divergence > threshold else "NORMAL"
        return {"bridge_id": self.bridge_id, "divergence": divergence,
                "threshold": float(threshold), "status": status,
                "recommendation": "Recommend targeted engineering inspection" if status == "RESPONSE SHIFT" else "Continue routine monitoring"}
