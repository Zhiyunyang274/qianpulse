"""io_driveby 解析器单元测试：桥窗提取 / 数据边界 / 融合收敛。

data/drive_by_pilot/ 同时包含：
- 真实外场采集 a*.zip / b*.zip（无标注 → 全程窗口模式）
- 模拟采集演练 sim_drive_*.zip（带 manifest，桥频 7.78 Hz）
"""

from pathlib import Path

import numpy as np
import pytest

from qianpulse.engine import crossing_to_peaks, fuse_peaks
from qianpulse.io_driveby import discover_driveby_runs, load_driveby_run

DATA = Path(__file__).resolve().parents[1] / "data" / "drive_by_pilot"
pytestmark = pytest.mark.skipif(
    not any(DATA.glob("*.zip")), reason="drive_by_pilot 数据未入仓")


@pytest.fixture(scope="module")
def all_runs():
    return [load_driveby_run(p) for p in discover_driveby_runs(DATA)]


@pytest.fixture(scope="module")
def real_runs(all_runs):
    return [r for r in all_runs if not r["simulated"]]


@pytest.fixture(scope="module")
def sim_runs(all_runs):
    return [r for r in all_runs if r["simulated"]]


# ---- 真实外场数据 ----

def test_real_runs_discovered(real_runs):
    assert len(real_runs) == 10  # a1–a6 正向 + b1–b4 反向


def test_real_runs_have_no_window(real_runs):
    # 本组采集未做 BRIDGE_ENTER/EXIT 标注 → window 为 None，走全程窗口
    assert all(r["window"] is None for r in real_runs)


def test_real_runs_not_marked_simulated(real_runs):
    assert all(r["simulated"] is False for r in real_runs)


def test_real_runs_vertical_method(real_runs):
    # 真实 iPhone 采集带 Gravity.csv → 必须走重力投影
    assert all(r["vertical_method"] == "Gravity projected" for r in real_runs)


def test_real_runs_sampling(real_runs):
    for r in real_runs:
        assert 99.0 <= r["fs"] <= 101.0
        assert 20.0 <= r["duration"] <= 60.0
        assert r["sample_count"] == len(r["full"]["t"])


def test_real_fusion_is_stable(real_runs):
    """10 次真实穿越（全程窗口）融合必须给出有限主频，且前后半段一致。"""
    segs = [r["bridge"] if r["bridge"] is not None else r["full"] for r in real_runs]
    votes = [crossing_to_peaks(seg)["peaks"] for seg in segs]
    all_votes = np.concatenate(votes)
    _, density, dominant = fuse_peaks(all_votes)
    assert np.isfinite(dominant)
    # 主峰密度显著高于带内中位（桥响应堆积 vs 噪声本底）
    assert density.max() > 3.0 * np.median(density)
    # 前半（a 向）与后半（含 b 向）都各自收敛到同一主频附近（±0.8 Hz）
    _, _, d1 = fuse_peaks(np.concatenate(votes[: len(votes) // 2]))
    _, _, d2 = fuse_peaks(np.concatenate(votes[len(votes) // 2:]))
    assert np.isfinite(d1) and np.isfinite(d2)
    assert abs(d1 - d2) < 0.8


# ---- 模拟演练数据（管线验证）----

def test_sim_runs_discovered(sim_runs):
    assert len(sim_runs) == 3


def test_sim_bridge_window_extracted(sim_runs):
    for r in sim_runs:
        assert r["window"] is not None
        enter, exit_ = r["window"]
        assert 0 < enter < exit_ < r["duration"]
        assert r["bridge"] is not None
        assert len(r["bridge"]["t"]) >= 64


def test_sim_vertical_method_is_gravity_projected(sim_runs):
    assert all(r["vertical_method"] == "Gravity projected" for r in sim_runs)


def test_sim_simulation_boundary_enforced(sim_runs):
    # manifest 声明 must_not_be_presented_as_real_world_measurement → 必须传播
    assert all(r["simulated"] is True for r in sim_runs)
    assert all(r["bridge_id"] == "GZ-DEMO-017" for r in sim_runs)


def test_sim_sampling_and_duration(sim_runs):
    for r in sim_runs:
        assert 99.0 <= r["fs"] <= 101.0
        assert 50.0 <= r["duration"] <= 60.0
        assert r["sample_count"] == len(r["full"]["t"])


def test_sim_gps_route_present(sim_runs):
    for r in sim_runs:
        assert r["gps"] is not None
        assert len(r["gps"][0]) >= 10
        assert 0.1 < r["route_km"] < 5.0  # 单次行车路线，不是跨省


def test_sim_fusion_converges_to_manifest_frequency(sim_runs):
    """manifest 声明 shared_bridge_frequency_hz=7.78：三次穿越融合必须收敛到它。"""
    votes = [crossing_to_peaks(r["bridge"])["peaks"] for r in sim_runs]
    all_votes = np.concatenate(votes)
    _, density, dominant = fuse_peaks(all_votes)
    assert np.isfinite(dominant)
    assert abs(dominant - 7.78) < 0.25, f"融合主频 {dominant:.2f} 偏离 7.78"


def test_sim_bridge_frequency_visible_in_each_run(sim_runs):
    """每一次单独穿越的候选峰里，都应出现 7.78 Hz 附近的桥响应。"""
    for r in sim_runs:
        peaks = crossing_to_peaks(r["bridge"])["peaks"]
        assert np.any(np.abs(peaks - 7.78) < 0.25), f"{r['source']} 未检出桥频: {peaks}"
