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
