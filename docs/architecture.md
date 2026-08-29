# QianPulse Engine architecture

QianPulse is an engine-first system. The Streamlit Console is an optional presentation layer over a pipeline that can run independently in batch jobs, edge devices, notebooks, or services.

## Runtime pipeline

```text
Vehicle / Edge
    ↓
Bridge geofence
    ↓
Short crossing window
    ↓
Quality control
    ↓
Feature extraction
    ↓
Feature packet
    ↓
Streaming queue
    ↓
partition by bridge_id
    ↓
incremental Bridge Pulse update
    ↓
baseline comparison
    ↓
inspection prioritization
```

The current repository implements the ingestion, conditioning, PSD, candidate extraction, fusion, baseline bootstrap, divergence, simulation, and physical-validation stages. `qianpulse.pipeline` now provides a runnable `FeaturePacket` contract, edge-side extraction, and an incremental `BridgePulseState` partitioned by `bridge_id`. A production deployment can place the first quality-control and feature-extraction stages on the vehicle or edge gateway.

## Retention and scale

QianPulse does not require uploading and retaining every 100 Hz raw IMU sample forever. A practical retention policy is:

- **Normal crossings:** retain feature-only packets for long-term operation
- **Sampled crossings:** retain selected raw windows for calibration and audit
- **Abnormal accepted crossings:** retain the full raw window and provenance for engineering review
- **Low-quality crossings:** reject before bridge-state update; retain only short-lived diagnostic metadata in `debug_rejected/`, never long-term raw data by default

Each bridge maintains incremental statistics (counts, pulse estimates, dispersion, and baseline envelopes). New crossings update those statistics rather than triggering a full scan of historical raw data. This keeps storage and compute proportional to new observations while preserving an auditable path back to selected raw windows.

The repository's `BridgePulseState.update()` demonstrates this incremental update boundary in-process. The local scale harness additionally demonstrates asyncio queue transport, SQLite durability, and simulated geofence events; managed queue infrastructure and production geospatial services remain deployment concerns.

## Local scale simulation boundary

`qianpulse.scale_simulation` and `scripts/run_scale_simulation.py` provide a **LOCAL SCALE SIMULATION** only. They use simulated vehicle geofence events, an asyncio local queue, `bridge_id` partitions, SQLite durable bridge state, and tiered local raw retention. No Kafka, Kubernetes, or external service is installed or implied. The measured `full_history_rescan` flag is false when updates use only the in-memory incremental state and SQLite state snapshot; this harness does not claim production throughput.

## Repository map

```text
qianpulse/
├── ingestion/     Sensor Logger and field-input adapters
├── signal/        Conditioning and spectral feature API
├── fusion/        Multi-crossing fusion and Bridge Pulse
├── screening/     Baseline comparison and screening decisions
├── simulation/    Deterministic demo fixtures
├── validation/    Physical experiment analysis
├── engine.py      Core numerical implementation
└── ...
scripts/
├── run_simulation.py
└── validate_physical_experiment.py
```
