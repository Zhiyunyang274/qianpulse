"""Best-effort importer for iPhone Sensor Logger accelerometer exports."""

from pathlib import Path
from zipfile import ZipFile
import tempfile
import re
import numpy as np
import pandas as pd


def _normalise(name):
    return re.sub(r"[^a-z0-9]+", "", str(name).lower())


def _find_column(columns, candidates):
    normalised = {_normalise(c): c for c in columns}
    for candidate in candidates:
        if _normalise(candidate) in normalised:
            return normalised[_normalise(candidate)]
    for key, original in normalised.items():
        if any(_normalise(candidate) in key for candidate in candidates):
            return original
    return None


def _read_csv(path):
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.read_csv(path, sep=";", engine="python")


def _crossing_from_frame(frame, source="Sensor Logger"):
    x_col = _find_column(frame.columns, ["x", "accelerationx", "accelerometerx", "ax"])
    y_col = _find_column(frame.columns, ["y", "accelerationy", "accelerometery", "ay"])
    z_col = _find_column(frame.columns, ["z", "accelerationz", "accelerometerz", "az"])
    if not x_col or not y_col or not z_col:
        return None
    time_col = _find_column(frame.columns, ["timestamp", "time", "seconds_elapsed", "elapsed", "unix_time"])
    xyz = frame[[x_col, y_col, z_col]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(xyz) < 32:
        return None
    if time_col:
        times = pd.to_numeric(frame.loc[xyz.index, time_col], errors="coerce").to_numpy(float)
        if np.any(~np.isfinite(times)) or np.ptp(times) <= 0:
            times = np.arange(len(xyz), dtype=float) / 100.0
        elif np.nanmedian(np.diff(times)) > 1.0:
            times = (times - times[0]) / 1000.0
        else:
            times = times - times[0]
    else:
        times = np.arange(len(xyz), dtype=float) / 100.0
    dt = np.diff(times)
    fs = float(1.0 / np.nanmedian(dt[(dt > 0) & np.isfinite(dt)])) if np.any((dt > 0) & np.isfinite(dt)) else 100.0
    # Magnitude is orientation agnostic and works when no gravity vector is exported.
    acc = np.sqrt(np.square(xyz.to_numpy(float)).sum(axis=1))
    acc = acc - np.median(acc)
    return {"t": times, "acc": acc, "fs": float(np.clip(fs, 10.0, 1000.0)),
            "source": source, "sampling_rate_estimate": fs}


def load_sensorlogger_export(path):
    """Load a CSV, directory, or ZIP and return a list of crossing dicts.

    Each CSV is treated as one crossing. Files without x/y/z columns are skipped.
    """
    path = Path(path)
    temp_dir = None
    try:
        if path.is_file() and path.suffix.lower() == ".zip":
            temp_dir = tempfile.TemporaryDirectory(prefix="qianpulse_sensorlogger_")
            with ZipFile(path) as archive:
                archive.extractall(temp_dir.name)
            root = Path(temp_dir.name)
        elif path.is_dir():
            root = path
        elif path.is_file() and path.suffix.lower() == ".csv":
            root = path.parent
        else:
            raise FileNotFoundError(path)
        files = [path] if path.is_file() and path.suffix.lower() == ".csv" else sorted(root.rglob("*.csv"))
        crossings = []
        for csv_path in files:
            crossing = _crossing_from_frame(_read_csv(csv_path), source=csv_path.name)
            if crossing is not None:
                crossings.append(crossing)
        return crossings
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


def _time_values(frame):
    """Return elapsed seconds using Sensor Logger's preferred clock."""
    time_col = _find_column(
        frame.columns, ["seconds_elapsed", "elapsed", "timestamp", "time", "unix_time"]
    )
    if not time_col:
        return np.arange(len(frame), dtype=float) / 100.0
    values = pd.to_numeric(frame[time_col], errors="coerce").to_numpy(float)
    if np.any(~np.isfinite(values)) or np.ptp(values) <= 0:
        return np.arange(len(frame), dtype=float) / 100.0
    delta = np.nanmedian(np.diff(values))
    if delta > 1e6:  # nanoseconds since epoch
        values = (values - values[0]) / 1e9
    elif delta > 1.0:  # milliseconds since epoch
        values = (values - values[0]) / 1e3
    else:
        values = values - values[0]
    return values


def load_physical_run(path, vertical_method="gravity"):
    """Read one Sensor Logger ZIP as a physical-validation run.

    Accelerometer.csv is mandatory. Gravity projection is used when requested
    and available; otherwise device Z is a transparent fallback. Gravity is
    interpolated onto accelerometer timestamps because exports can differ by
    one sample.
    """
    path = Path(path)
    if not path.is_file() or path.suffix.lower() != ".zip":
        raise ValueError(f"Expected a Sensor Logger ZIP: {path}")
    with ZipFile(path) as archive:
        names = {Path(name).name.lower(): name for name in archive.namelist()}
        acc_name = names.get("accelerometer.csv")
        if not acc_name:
            raise ValueError(f"Accelerometer.csv not found in {path.name}")
        with archive.open(acc_name) as handle:
            frame = pd.read_csv(handle)

        cols = [_find_column(frame.columns, [axis, f"acceleration{axis}"]) for axis in "xyz"]
        if not all(cols):
            raise ValueError(f"Three-axis acceleration not found in {path.name}")
        xyz = frame[cols].apply(pd.to_numeric, errors="coerce").to_numpy(float)
        times = _time_values(frame)
        good = np.isfinite(times) & np.all(np.isfinite(xyz), axis=1)
        times, xyz = times[good], xyz[good]
        if len(times) < 32:
            raise ValueError(f"Too few valid acceleration samples in {path.name}")

        method = "Device Z axis"
        acc = xyz[:, 2]
        gravity_name = names.get("gravity.csv")
        if vertical_method == "gravity" and gravity_name:
            with archive.open(gravity_name) as handle:
                gravity = pd.read_csv(handle)
            gravity_cols = [_find_column(gravity.columns, [axis]) for axis in "xyz"]
            if all(gravity_cols):
                gravity_times = _time_values(gravity)
                gravity_xyz = gravity[gravity_cols].apply(pd.to_numeric, errors="coerce").to_numpy(float)
                gravity_good = np.isfinite(gravity_times) & np.all(np.isfinite(gravity_xyz), axis=1)
                gravity_times, gravity_xyz = gravity_times[gravity_good], gravity_xyz[gravity_good]
                if len(gravity_times) >= 2:
                    projected_g = np.column_stack(
                        [np.interp(times, gravity_times, gravity_xyz[:, i]) for i in range(3)]
                    )
                    norms = np.linalg.norm(projected_g, axis=1)
                    if np.all(norms > 1e-9):
                        acc = np.sum(xyz * projected_g, axis=1) / norms
                        method = "Gravity projected"

    dt = np.diff(times)
    valid_dt = dt[(dt > 0) & np.isfinite(dt)]
    if not len(valid_dt):
        raise ValueError(f"No valid sampling intervals in {path.name}")
    median_dt = float(np.median(valid_dt))
    fs = 1.0 / median_dt
    jitter_ms = float(np.sqrt(np.mean(np.square(valid_dt - median_dt))) * 1000.0)
    return {
        "t": times - times[0],
        "acc": acc,
        "fs": fs,
        "source": path.name,
        "sample_count": int(len(times)),
        "duration": float(times[-1] - times[0]),
        "sampling_rate_estimate": fs,
        "sampling_jitter_ms": jitter_ms,
        "vertical_method": method,
    }


def discover_physical_runs(root, vertical_method="gravity"):
    """Discover every ZIP below baseline/ and perturbed/ directories."""
    root = Path(root)
    runs = {"baseline": [], "perturbed": []}
    for state in runs:
        directory = root / state
        paths = sorted(directory.glob("*.zip")) if directory.is_dir() else []
        for path in paths:
            run = load_physical_run(path, vertical_method=vertical_method)
            run["state"] = state
            runs[state].append(run)
    return runs
