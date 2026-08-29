"""io_driveby 解析器单元测试：桥窗提取 / 数据边界 / 融合收敛。"""

from pathlib import Path
import zipfile

import numpy as np
import pytest

from qianpulse.engine import crossing_to_peaks, fuse_peaks
from qianpulse.io_driveby import discover_driveby_runs, load_driveby_run

DATA = Path(__file__).resolve().parents[1] / "data" / "drive_by_pilot"
pytestmark = pytest.mark.skipif(
    not any(DATA.glob("*.zip")), reason="drive_by_pilot 数据未入仓")


@pytest.fixture(scope="module")
def runs():
    return [load_driveby_run(p) for p in discover_driveby_runs(DATA)]


def test_discover_finds_all_runs():
    assert len(discover_driveby_runs(DATA)) == 3


def test_bridge_window_extracted(runs):
    for r in runs:
        assert r["window"] is not None
        enter, exit_ = r["window"]
        assert 0 < enter < exit_ < r["duration"]
        assert r["bridge"] is not None
        assert len(r["bridge"]["t"]) >= 64


def test_vertical_method_is_gravity_projected(runs):
    # ZIP 内含 Gravity.csv，必须走重力投影而不是设备 Z 轴
    assert all(r["vertical_method"] == "Gravity projected" for r in runs)


def test_simulation_boundary_enforced(runs):
    # manifest 声明 must_not_be_presented_as_real_world_measurement → 必须传播
    assert all(r["simulated"] is True for r in runs)
    assert all(r["bridge_id"] == "GZ-DEMO-017" for r in runs)


def test_sampling_and_duration(runs):
    for r in runs:
        assert 99.0 <= r["fs"] <= 101.0
        assert 50.0 <= r["duration"] <= 60.0
        assert r["sample_count"] == len(r["full"]["t"])


def test_gps_route_present(runs):
    for r in runs:
        assert r["gps"] is not None
        assert len(r["gps"][0]) >= 10
        assert 0.1 < r["route_km"] < 5.0  # 单次行车路线，不是跨省


def test_fusion_converges_to_manifest_frequency(runs):
    """manifest 声明 shared_bridge_frequency_hz=7.78：三次穿越融合必须收敛到它。"""
    votes = [crossing_to_peaks(r["bridge"])["peaks"] for r in runs]
    all_votes = np.concatenate(votes)
    _, density, dominant = fuse_peaks(all_votes)
    assert np.isfinite(dominant)
    assert abs(dominant - 7.78) < 0.25, f"融合主频 {dominant:.2f} 偏离 7.78"


def test_bridge_frequency_visible_in_each_run(runs):
    """每一次单独穿越的候选峰里，都应出现 7.78 Hz 附近的桥响应。"""
    for r in runs:
        peaks = crossing_to_peaks(r["bridge"])["peaks"]
        assert np.any(np.abs(peaks - 7.78) < 0.25), f"{r['source']} 未检出桥频: {peaks}"
