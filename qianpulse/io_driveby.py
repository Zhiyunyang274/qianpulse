"""Drive-by ZIP 解析：读 Annotation 桥窗 + Sensor Logger 加速度 + GPS。

每个 ZIP 是一次完整行车记录（含上桥/下桥/下桥后），本模块负责：
- 列名自适应读取（与 io_sensorlogger 同一套规则）
- 从 Annotation.csv 提取 BRIDGE_ENTER / BRIDGE_EXIT 桥窗
- 从 SIMULATION_MANIFEST.json / Metadata.csv 判断数据是否为模拟（严格标注，不冒充真实）
- 产出与引擎兼容的 crossing dict（t / acc / fs / source），供频域分析直接使用
"""

from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

from .io_sensorlogger import _find_column, _time_values


def _load_member_csv(archive, names, member):
    """按不区分大小写的文件名从 ZIP 里读一个 CSV 成员。"""
    key = names.get(member.lower())
    if not key:
        return None
    with archive.open(key) as handle:
        return pd.read_csv(handle)


def _bridge_window(annotation):
    """从 Annotation.csv 提取 (enter, exit) 桥窗秒；缺标注返回 None。"""
    if annotation is None:
        return None
    label_col = _find_column(annotation.columns, ["label"])
    time_col = _find_column(annotation.columns, ["seconds_elapsed", "elapsed", "time"])
    if not label_col or not time_col:
        return None
    enter = annotation.loc[annotation[label_col].str.upper().str.contains("ENTER", na=False), time_col]
    exit_ = annotation.loc[annotation[label_col].str.upper().str.contains("EXIT", na=False), time_col]
    if len(enter) == 0 or len(exit_) == 0:
        return None
    return float(enter.iloc[0]), float(exit_.iloc[0])


def load_driveby_run(path):
    """读一个车载记录 ZIP，返回完整行车记录 + 桥窗切片 + 元信息。

    返回 dict：full（全程）、bridge（桥窗切片）、window（enter/exit 秒）、
    simulated（bool）、gps、route_km、fs。
    """
    path = Path(path)
    if not path.is_file() or path.suffix.lower() != ".zip":
        raise ValueError(f"Expected a drive-by ZIP: {path}")
    with ZipFile(path) as archive:
        names = {Path(n).name.lower(): n for n in archive.namelist()}

        acc_frame = _load_member_csv(archive, names, "accelerometer.csv")
        if acc_frame is None:
            raise ValueError(f"Accelerometer.csv not found in {path.name}")
        cols = [_find_column(acc_frame.columns, [axis, f"acceleration{axis}"]) for axis in "xyz"]
        if not all(cols):
            raise ValueError(f"Three-axis acceleration not found in {path.name}")
        xyz = acc_frame[cols].apply(pd.to_numeric, errors="coerce").to_numpy(float)
        times = _time_values(acc_frame)
        good = np.isfinite(times) & np.all(np.isfinite(xyz), axis=1)
        times, xyz = times[good], xyz[good]
        if len(times) < 64:
            raise ValueError(f"Too few valid samples in {path.name}")

        # 竖直向加速度：优先用 Gravity.csv 投影（桥梁竖弯振动只出现在竖直向，
        # 三轴幅值会被水平车噪稀释——幅值口径下 7.8Hz 分量几乎不可见）。
        method = "Device Z axis"
        acc = xyz[:, 2]
        gravity_frame = _load_member_csv(archive, names, "gravity.csv")
        if gravity_frame is not None:
            g_cols = [_find_column(gravity_frame.columns, [axis]) for axis in "xyz"]
            if all(g_cols):
                g_times = _time_values(gravity_frame)
                g_xyz = gravity_frame[g_cols].apply(pd.to_numeric, errors="coerce").to_numpy(float)
                g_good = np.isfinite(g_times) & np.all(np.isfinite(g_xyz), axis=1)
                g_times, g_xyz = g_times[g_good], g_xyz[g_good]
                if len(g_times) >= 2:
                    projected = np.column_stack(
                        [np.interp(times, g_times, g_xyz[:, i]) for i in range(3)]
                    )
                    norms = np.linalg.norm(projected, axis=1)
                    if np.all(norms > 1e-9):
                        acc = np.sum(xyz * projected, axis=1) / norms
                        method = "Gravity projected"
        acc = acc - np.median(acc)

        annotation = _load_member_csv(archive, names, "annotation.csv")
        window = _bridge_window(annotation)

        manifest_raw = names.get("simulation_manifest.json")
        simulated = False
        bridge_id = ""
        if manifest_raw:
            import json
            with archive.open(manifest_raw) as handle:
                manifest = json.load(handle)
            simulated = bool(manifest.get("must_not_be_presented_as_real_world_measurement", False))
            bridge_id = str(manifest.get("bridge_id", ""))

        gps = None
        location = _load_member_csv(archive, names, "location.csv")
        if location is not None:
            lat_col = _find_column(location.columns, ["latitude", "lat"])
            lon_col = _find_column(location.columns, ["longitude", "lon", "lng"])
            if lat_col and lon_col:
                lat = pd.to_numeric(location[lat_col], errors="coerce").to_numpy(float)
                lon = pd.to_numeric(location[lon_col], errors="coerce").to_numpy(float)
                ok = np.isfinite(lat) & np.isfinite(lon)
                if ok.any():
                    gps = (lat[ok], lon[ok])

    dt = np.diff(times)
    valid_dt = dt[(dt > 0) & np.isfinite(dt)]
    if not len(valid_dt):
        raise ValueError(f"No valid sampling intervals in {path.name}")
    fs = float(1.0 / np.median(valid_dt))

    route_km = 0.0
    if gps is not None:
        lat, lon = gps
        if len(lat) >= 2:
            lat_r, lon_r = np.radians(lat), np.radians(lon)
            dlat, dlon = np.diff(lat_r), np.diff(lon_r)
            a = np.sin(dlat / 2) ** 2 + np.cos(lat_r[:-1]) * np.cos(lat_r[1:]) * np.sin(dlon / 2) ** 2
            route_km = float(6371.0 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1))).sum())

    bridge = None
    if window is not None:
        enter, exit_ = window
        lo, hi = max(0, int(enter * fs)), min(len(times), int(exit_ * fs))
        if hi - lo >= 64:
            bridge = {"t": times[lo:hi] - times[lo], "acc": acc[lo:hi], "fs": fs}

    return {
        "full": {"t": times - times[0], "acc": acc, "fs": fs},
        "bridge": bridge,
        "window": window,
        "simulated": simulated,
        "bridge_id": bridge_id,
        "gps": gps,
        "route_km": route_km,
        "source": path.name,
        "sample_count": int(len(times)),
        "duration": float(times[-1] - times[0]),
        "fs": fs,
        "vertical_method": method,
    }


def discover_driveby_runs(root):
    """发现目录下全部车载 ZIP，按文件名排序。"""
    root = Path(root)
    if not root.is_dir():
        return []
    return sorted(root.glob("*.zip"))
