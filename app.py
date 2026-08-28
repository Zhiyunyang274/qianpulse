import tempfile
import time
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from qianpulse.engine import (
    bootstrap_baseline_divergence,
    convergence_curve,
    crossing_to_peaks,
    fingerprint_divergence,
    fuse_crossings,
)
from qianpulse.io_sensorlogger import load_sensorlogger_export
from qianpulse.simulate import simulate_batch

st.set_page_config(page_title="黔脉 QianPulse", page_icon="🌉", layout="wide")
st.markdown("""
<style>
.stApp { background: #071018; color: #e7f0f5; }
[data-testid="stHeader"] { background: rgba(7,16,24,0.9); }
.block-container { padding-top: 2rem; max-width: 1450px; }
.eyebrow { color:#67d6c3; letter-spacing:.14em; font-size:.72rem; font-weight:700; }
.alert-box { border:1px solid #e16d64; background:#2b171c; border-radius:12px; padding:18px; }
[data-testid="stMetricValue"] { color:#e7f0f5; }
[data-testid="stMetricLabel"] { color:#8ca6b3; }
</style>
""", unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def demo_data(seed, baseline_f, shifted_f):
    return simulate_batch(60, bridge_freq=baseline_f, seed=seed), simulate_batch(60, bridge_freq=shifted_f, seed=seed + 100)

def dark_layout(height=360):
    return dict(height=height, template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=45, r=20, t=30, b=45), legend=dict(orientation="h", y=1.08), hovermode="x unified")

st.markdown('<div class="eyebrow">QIANPULSE / 黔脉</div>', unsafe_allow_html=True)
st.title("把营运车辆变成桥梁的移动感知网络")
st.caption("用移动感知筛查桥梁动态响应变化 · 本地离线黑客松演示")

with st.sidebar:
    st.header("演示控制")
    mode = st.radio("数据来源", ["模拟数据 · 演示", "真实数据 · Sensor Logger"], index=0)
    baseline_f = st.slider("基线桥梁脉冲（Hz）", 5.0, 10.0, 7.8, 0.1)
    shifted_f = st.slider("当前结构响应（Hz）", 5.0, 10.0, 7.2, 0.1)
    n = st.slider("融合穿越次数", 1, 50, 30, 1)
    seed = st.number_input("固定随机种子", 0, 9999, 42)
    replay = st.button("▶  播放黔脉演示", use_container_width=True, type="primary")
    upload = st.file_uploader("上传 Sensor Logger CSV 或 ZIP", type=["csv", "zip"]) if mode.startswith("真实") else None
    st.divider()
    st.caption("模拟演示数据" if mode.startswith("模拟") else "真实 Sensor Logger 数据")

if replay:
    progress = st.progress(0, text="正在启动桥梁感知演示…")
    for pct, label in [(12, "1 次穿越 · 信号很嘈杂"), (30, "5 次穿越 · 候选频率出现"), (52, "10 次穿越 · 共识逐渐形成"), (72, "20 次穿越 · 脉冲趋于稳定"), (88, "50 次穿越 · 建立历史基线"), (100, "当前状态 · 筛查响应变化")]:
        progress.progress(pct, text=label)
        time.sleep(0.18)
    progress.empty()

baseline_all, shifted_all = demo_data(int(seed), baseline_f, shifted_f)
data_note = "模拟演示数据"
if mode.startswith("真实") and upload is not None:
    suffix = Path(upload.name).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix) as handle:
        handle.write(upload.getvalue())
        handle.flush()
        real_crossings = load_sensorlogger_export(handle.name)
    if real_crossings:
        baseline_all = real_crossings
        shifted_all = real_crossings
        data_note = f"真实 Sensor Logger · {len(real_crossings)} 次穿越"
    else:
        st.warning("没有找到包含 x/y/z 加速度列的文件，当前展示模拟数据。")

baseline, shifted = baseline_all[:n], shifted_all[:n]
base_fused, shift_fused = fuse_crossings(baseline), fuse_crossings(shifted)
boot = bootstrap_baseline_divergence(baseline_all[:40], seed=int(seed) + 8)
threshold = boot["threshold95"]
div = fingerprint_divergence(base_fused["fingerprint"], shift_fused["fingerprint"])
is_shift = bool(np.isfinite(threshold) and div > threshold and abs(shifted_f - baseline_f) >= 0.2)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("融合穿越次数", n)
c2.metric("基线桥梁脉冲", f"{base_fused['dominant_frequency']:.2f} Hz")
c3.metric("当前桥梁脉冲", f"{shift_fused['dominant_frequency']:.2f} Hz")
c4.metric("脉冲稳定度", f"{base_fused['pulse_stability'] * 100:.0f}%")
c5.metric("指纹差异", f"{div:.3f}", f"阈值 {threshold:.3f}")
st.caption(f"数据模式：**{data_note}**")

st.divider()
st.markdown("### 01 · 单辆车的信号很嘈杂")
st.caption("单次穿越 · 证据不足，不能据此判断桥梁状态")
left, right = st.columns(2)
with left:
    fig = go.Figure(go.Scatter(x=baseline[0]["t"], y=baseline[0]["acc"], mode="lines", line=dict(color="#67d6c3", width=1.2), name="原始加速度"))
    fig.update_layout(**dark_layout(), xaxis_title="时间（秒）", yaxis_title="加速度（相对值）")
    st.plotly_chart(fig, use_container_width=True)
with right:
    single = crossing_to_peaks(baseline[0])
    fig = go.Figure(go.Scatter(x=single["f"], y=single["pxx"], mode="lines", line=dict(color="#f4b860"), name="单次 PSD"))
    fig.update_layout(**dark_layout(), xaxis_title="频率（Hz）", yaxis_title="功率谱密度")
    st.plotly_chart(fig, use_container_width=True)

st.divider()
st.markdown("### 02 · 桥梁脉冲从人群数据中浮现")
st.caption("多次穿越通过 KDE / 共识融合：车辆自身的随机峰逐渐减弱，共同的桥梁频率最终占据主导。")
fig = go.Figure()
for count in [1, 5, 10, 20, 30, 50]:
    if count <= len(baseline_all):
        fused = fuse_crossings(baseline_all[:count])
    fig.add_trace(go.Scatter(x=fused["grid"], y=fused["fingerprint"], mode="lines", name=f"{count} 次", visible=True if count == n else "legendonly"))
fig.add_vline(x=base_fused["dominant_frequency"], line_dash="dash", line_color="#67d6c3", annotation_text=f"桥梁脉冲 {base_fused['dominant_frequency']:.2f} Hz")
fig.update_layout(**dark_layout(430), xaxis_title="频率（Hz）", yaxis_title="归一化共识密度")
st.plotly_chart(fig, use_container_width=True)

conv = convergence_curve(baseline_all, counts=[1, 5, 10, 20, 30, 50])
cc1, cc2 = st.columns([1.25, 1])
with cc1:
    fig = go.Figure(go.Scatter(x=[x["n"] for x in conv], y=[x["dominant_frequency"] for x in conv], mode="lines+markers", line=dict(color="#67d6c3", width=3), name="桥梁脉冲"))
    fig.add_hline(y=baseline_f, line_dash="dot", line_color="#8ca6b3")
    fig.update_layout(**dark_layout(280), xaxis_title="融合穿越次数（N）", yaxis_title="估计脉冲（Hz）")
    st.plotly_chart(fig, use_container_width=True)
with cc2:
    vehicle = [c.get("vehicle_freq", np.nan) for c in baseline_all[:50]]
    fig = go.Figure(go.Scatter(x=list(range(1, len(vehicle) + 1)), y=vehicle, mode="markers", marker=dict(color="#f4b860", size=7), name="车辆自身频率"))
    fig.add_hline(y=base_fused["dominant_frequency"], line_dash="dash", line_color="#67d6c3")
    fig.update_layout(**dark_layout(280), xaxis_title="车辆编号", yaxis_title="车辆自身频率（Hz）")
    st.plotly_chart(fig, use_container_width=True)

st.divider()
st.markdown("### 03 · 历史基线与当前状态对比")
fig = go.Figure()
fig.add_trace(go.Scatter(x=base_fused["grid"], y=base_fused["fingerprint"], mode="lines", line=dict(color="#67d6c3", width=3), name=f"历史基线 · {base_fused['dominant_frequency']:.2f} Hz"))
fig.add_trace(go.Scatter(x=shift_fused["grid"], y=shift_fused["fingerprint"], mode="lines", line=dict(color="#f46d63", width=3), name=f"当前状态 · {shift_fused['dominant_frequency']:.2f} Hz"))
fig.update_layout(**dark_layout(380), xaxis_title="频率（Hz）", yaxis_title="归一化动态指纹")
st.plotly_chart(fig, use_container_width=True)

if is_shift:
    st.markdown(f'<div class="alert-box"><div class="eyebrow" style="color:#ff9b91">检测到结构响应发生持续偏移</div><p>当前脉冲相对基线变化 <b>{shift_fused["dominant_frequency"] - base_fused["dominant_frequency"]:+.2f} Hz</b> · 指纹差异 <b>{div:.3f}</b> 超过基线 95% 正常波动阈值 <b>{threshold:.3f}</b>。</p><p><b>建议优先进行专业工程检查。</b></p></div>', unsafe_allow_html=True)
else:
    st.success(f"处于历史基线正常波动范围 · 指纹差异 {div:.3f}，阈值 {threshold:.3f}")
st.info("黔脉只筛查桥梁相对自身历史基线的动态响应变化，不做结构损伤诊断，也不能替代专业桥梁检测。")
