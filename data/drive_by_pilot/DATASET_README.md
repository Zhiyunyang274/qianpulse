# QianPulse simulated drive-by dataset

This bundle contains 3 independent **SIMULATED** drive-by crossings for the same demo bridge `GZ-DEMO-017`.

Purpose:
- Single crossings contain different vehicle / road noise.
- All three share a bridge-only component near 7.8 Hz during the annotated bridge window.
- Suitable for demonstrating repeated-crossing fusion and GPS-aligned bridge-window extraction.

Files:
- sim_drive_bridgeA_001.zip
- sim_drive_bridgeA_002.zip
- sim_drive_bridgeA_003.zip

Each ZIP contains:
- Accelerometer.csv (~100 Hz)
- Gravity.csv (~100 Hz)
- Gyroscope.csv (~100 Hz)
- AccelerometerUncalibrated.csv
- GyroscopeUncalibrated.csv
- Location.csv (~1 Hz, synthetic route)
- Annotation.csv (BRIDGE_ENTER / BRIDGE_EXIT)
- Metadata.csv
- SIMULATION_MANIFEST.json

Important:
These are synthetic demo data and must be displayed as `SIMULATED DRIVE-BY DATA`, not as real field measurements.
