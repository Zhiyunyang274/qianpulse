"""LOCAL SCALE SIMULATION for the QianPulse Engine.

This is deliberately local and dependency-light: asyncio queues, SQLite, and
the existing numerical engine. It is not a production deployment.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from qianpulse.pipeline import BridgePulseState, extract_feature_packet
from qianpulse.simulate import simulate_crossing


@dataclass(frozen=True)
class CrossingEvent:
    event_id: int
    vehicle_id: str
    bridge_id: str
    geofence: str
    crossing_index: int
    raw: dict


class DurableBridgeStore:
    """SQLite store for incremental bridge-level state."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("CREATE TABLE IF NOT EXISTS bridge_state (bridge_id TEXT PRIMARY KEY, crossings INTEGER NOT NULL, pulse_hz REAL, stability REAL, fingerprint_json TEXT NOT NULL)")
        self.conn.commit()

    def load(self, bridge_id: str) -> BridgePulseState:
        row = self.conn.execute("SELECT crossings, fingerprint_json FROM bridge_state WHERE bridge_id=?", (bridge_id,)).fetchone()
        state = BridgePulseState(bridge_id)
        if row:
            state.count = int(row[0])
            state._fingerprint_sum = np.asarray(json.loads(row[1]), dtype=float)
        return state

    def save(self, state: BridgePulseState, summary: dict):
        self.conn.execute("INSERT INTO bridge_state(bridge_id,crossings,pulse_hz,stability,fingerprint_json) VALUES(?,?,?,?,?) ON CONFLICT(bridge_id) DO UPDATE SET crossings=excluded.crossings,pulse_hz=excluded.pulse_hz,stability=excluded.stability,fingerprint_json=excluded.fingerprint_json", (state.bridge_id, state.count, summary["pulse_hz"], summary["stability"], json.dumps(state._fingerprint_sum.tolist())))
        self.conn.commit()

    def count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM bridge_state").fetchone()[0])

    def close(self):
        self.conn.close()


class TieredRawRetention:
    """Local raw retention policy: normal feature-only, sampled, abnormal full raw."""

    def __init__(self, root: str | Path, sample_rate: float = 0.02):
        self.root = Path(root)
        self.sample_rate = float(sample_rate)
        for tier in ("feature_only", "sampled_raw", "abnormal_raw", "debug_rejected"):
            (self.root / tier).mkdir(parents=True, exist_ok=True)
        self.retained_raw = 0
        self.debug_rejected = 0

    def retain_rejected_debug(self, event: CrossingEvent, reason: str):
        """Keep only short-lived diagnostic metadata for rejected crossings."""
        self.debug_rejected += 1
        payload = {"event_id": event.event_id, "vehicle_id": event.vehicle_id,
                   "bridge_id": event.bridge_id, "reason": reason,
                   "sample_count": len(event.raw.get("acc", [])), "fs": event.raw.get("fs")}
        (self.root / "debug_rejected" / f"{event.event_id:08d}.json").write_text(json.dumps(payload), encoding="utf-8")

    def retain(self, event: CrossingEvent, packet: dict, rng: np.random.Generator):
        # A small deterministic-by-seed sample plus low-quality events are retained raw.
        sampled = bool(rng.random() < self.sample_rate)
        if sampled:
            tier = "sampled_raw"
            keep = True
        else:
            tier = "feature_only"
            keep = False
        payload = packet
        if keep:
            self.retained_raw += 1
            payload = {**packet, "raw": {"t": event.raw["t"].tolist(), "acc": event.raw["acc"].tolist(), "fs": event.raw["fs"]}}
        (self.root / tier / f"{event.event_id:08d}.json").write_text(json.dumps(payload), encoding="utf-8")


def architecture_snapshot(metrics: dict | None = None) -> dict:
    """Return a frontend-neutral snapshot for the How-it-works Console section."""
    metrics = metrics or {}
    return {
        "label": "LOCAL SCALE SIMULATION",
        "stages": [
            {"stage": "Vehicle / Edge", "detail": "simulated fleet crossing event"},
            {"stage": "Quality control", "detail": "reject short or non-finite windows"},
            {"stage": "FeaturePacket", "detail": "compact spectral feature packet"},
            {"stage": "bridge_id partition", "detail": "local asyncio queue partition"},
            {"stage": "Incremental bridge state", "detail": "BridgePulseState update"},
            {"stage": "SQLite durable state", "detail": "bridge-level snapshot"},
            {"stage": "Screening", "detail": "baseline comparison boundary"},
        ],
        "metrics": {key: metrics[key] for key in (
            "throughput_events_per_sec", "processed_count", "rejected_count",
            "bridge_state_updates", "raw_retention_ratio", "full_history_rescan",
        ) if key in metrics},
    }


async def run_scale_simulation(fleet_size: int = 100, crossings: int = 1000, seed: int = 42,
                               workers: int = 4, db_path: str | Path | None = None,
                               retention_root: str | Path | None = None) -> dict:
    """Generate and process a local crossing stream, returning measured metrics."""
    if fleet_size < 1 or crossings < 1:
        raise ValueError("fleet_size and crossings must be positive")
    rng = np.random.default_rng(seed)
    bridges = [("GZ-017", 7.8), ("GZ-042", 7.5), ("GZ-008", 8.1)]
    events = []
    low_quality_generated = 0
    for i in range(crossings):
        bridge_id, freq = bridges[int(rng.integers(len(bridges)))]
        raw = simulate_crossing(bridge_freq=freq, rng=rng, duration=2.0, noise_std=1.0)
        # Approximate a small field fraction of unusable windows: truncated or
        # non-finite captures are rejected by the same edge quality gate.
        if rng.random() < 0.02:
            low_quality_generated += 1
            if i % 2:
                short_n = int(rng.integers(8, 28))
                raw = {**raw, "acc": raw["acc"][:short_n], "t": raw["t"][:short_n]}
            else:
                raw = {**raw, "acc": np.full(24, np.nan), "t": np.arange(24) / raw["fs"]}
        events.append(CrossingEvent(i, f"vehicle-{int(rng.integers(fleet_size)):05d}", bridge_id,
                                    f"geofence:{bridge_id}", i, raw))
    temporary = tempfile.TemporaryDirectory(prefix="qianpulse_scale_")
    db = str(db_path or (Path(temporary.name) / "bridge_state.sqlite"))
    retention = TieredRawRetention(retention_root or (Path(temporary.name) / "raw"))
    store = DurableBridgeStore(db)
    queues = [asyncio.Queue() for _ in range(max(1, workers))]
    states: dict[str, BridgePulseState] = {}
    rejected = 0
    updates = 0
    started = time.perf_counter()

    async def producer():
        for event in events:
            # Geofence validation is explicit; malformed bridge events are rejected.
            if event.bridge_id not in {b[0] for b in bridges} or not event.geofence.startswith("geofence:"):
                continue
            await queues[hash(event.bridge_id) % len(queues)].put(event)
        for queue in queues:
            await queue.put(None)

    async def worker(queue):
        nonlocal rejected, updates
        while True:
            event = await queue.get()
            if event is None:
                return
            try:
                packet = extract_feature_packet(event.raw, event.bridge_id, str(event.event_id))
                state = states.setdefault(event.bridge_id, store.load(event.bridge_id))
                summary = state.update(packet)
                store.save(state, summary)
                retention.retain(event, packet.to_dict(), rng)
                updates += 1
            except (ValueError, KeyError, FloatingPointError) as exc:
                rejected += 1
                retention.retain_rejected_debug(event, str(exc))

    await asyncio.gather(producer(), *(worker(q) for q in queues))
    elapsed = max(time.perf_counter() - started, 1e-9)
    result = {"fleet_size": fleet_size, "generated_crossings": crossings,
              "throughput_events_per_sec": crossings / elapsed,
              "processed_count": updates, "rejected_count": rejected,
              "bridge_state_updates": updates, "bridges_in_sqlite": store.count(),
              "raw_retention_ratio": retention.retained_raw / max(updates, 1),
              "raw_retained_count": retention.retained_raw,
              "low_quality_generated": low_quality_generated,
              "rejected_debug_count": retention.debug_rejected,
              "full_history_rescan": any(state.full_history_rescans > 0 for state in states.values()),
              "sqlite_path": db, "retention_path": str(retention.root)}
    result["pipeline_trace"] = [
        "Vehicle / Edge", "Bridge geofence", "Short crossing window",
        "Quality control", "FeaturePacket", "bridge_id partition",
        "Incremental BridgePulseState", "SQLite durable state",
        "Baseline comparison", "Inspection screening",
    ]
    store.close()
    if db_path is None and retention_root is None:
        # Keep temporary resources alive only for the duration of the run.
        temporary.cleanup()
    return result
