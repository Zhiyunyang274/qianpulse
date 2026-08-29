#!/usr/bin/env python3
"""Run the LOCAL SCALE SIMULATION (no Streamlit or external infrastructure)."""
from pathlib import Path
import argparse
import asyncio
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from qianpulse.scale_simulation import run_scale_simulation


def main():
    p = argparse.ArgumentParser(description="QianPulse LOCAL SCALE SIMULATION")
    p.add_argument("--vehicles", type=int, default=1000)
    p.add_argument("--crossings", type=int, default=10000)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--db", type=str, default=None, help="optional SQLite path to retain durable state")
    p.add_argument("--retention-root", type=str, default=None, help="optional local tiered-retention directory")
    p.add_argument("--json", action="store_true", help="also print the measured result as JSON")
    args = p.parse_args()
    result = asyncio.run(run_scale_simulation(args.vehicles, args.crossings, args.seed, args.workers, args.db, args.retention_root))
    print("QianPulse · LOCAL SCALE SIMULATION")
    for key in ("fleet_size", "generated_crossings", "low_quality_generated", "throughput_events_per_sec", "processed_count", "rejected_count", "rejected_debug_count", "bridge_state_updates", "bridges_in_sqlite", "raw_retention_ratio", "raw_retained_count", "full_history_rescan"):
        value = result[key]
        print(f"{key}: {value:.4f}" if isinstance(value, float) else f"{key}: {value}")
    if args.json:
        print(json.dumps(result, default=str))


if __name__ == "__main__":
    main()
