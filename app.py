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

st.set_page_config(page_title="QianPulse · 黔脉", page_icon="🌉", layout="wide")
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
st.caption("Mobile sensing for bridge-scale anomaly screening · 本地离线黑客松 Demo")

with st.sidebar:
    st.header("Demo Controls")
    mode = st.radio("Data source", ["SIMULATED · Demo data", "REAL · Sensor Logger"], index=0)
    baseline_f = st.slider("Baseline bridge pulse (Hz)", 5.0, 10.0, 7.8, 0.1)
    shifted_f = st.slider("Current response (Hz)", 5.0, 10.0, 7.2, 0.1)
    n = st.slider("Crossings fused", 1, 50, 30, 1)
    seed = st.number_input("Fixed seed", 0, 9999, 42)
    replay = st.button("▶  Run QianPulse Demo", use_container_width=True, type="primary")
    upload = st.file_uploader("Upload Sensor Logger CSV or ZIP", type=["csv", "zip"]) if mode.startswith("REAL") else None
    st.divider()
    st.caption("SIMULATED DEMO DATA" if mode.startswith("SIM") else "REAL SENSOR LOGGER INPUT")

if replay:
    progress = st.progress(0, text="Initializing bridge sensing replay…")
    for pct, label in [(12, "1 crossing · noisy evidence"), (30, "5 crossings · candidates appear"), (52, "10 crossings · consensus forming"), (72, "20 crossings · pulse stabilizing"), (88, "50 crossings · baseline established"), (100, "Current state · screening shift")]:
        progress.progress(pct, text=label)
        time.sleep(0.18)
    progress.empty()

baseline_all, shifted_all = demo_data(int(seed), baseline_f, shifted_f)
data_note = "SIMULATED DEMO DATA"
if mode.startswith("REAL") and upload is not None:
    suffix = Path(upload.name).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix) as handle:
        handle.write(upload.getvalue())
        handle.flush()
        real_crossings = load_sensorlogger_export(handle.name)
    if real_crossings:
        baseline_all = real_crossings
        shifted_all = real_crossings
        data_note = f"REAL SENSOR LOGGER · {len(real_crossings)} crossing(s)"
    else:
        st.warning("No accelerometer CSV with x/y/z columns found; showing simulated data instead.")

baseline, shifted = baseline_all[:n], shifted_all[:n]
base_fused, shift_fused = fuse_crossings(baseline), fuse_crossings(shifted)
boot = bootstrap_baseline_divergence(baseline_all[:40], seed=int(seed) + 8)
threshold = boot["threshold95"]
div = fingerprint_divergence(base_fused["fingerprint"], shift_fused["fingerprint"])
is_shift = bool(np.isfinite(threshold) and div > threshold and abs(shifted_f - baseline_f) >= 0.2)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Crossings fused", n)
c2.metric("Baseline Pulse", f"{base_fused['dominant_frequency']:.2f} Hz")
c3.metric("Current Pulse", f"{shift_fused['dominant_frequency']:.2f} Hz")
c4.metric("Pulse Stability", f"{base_fused['pulse_stability'] * 100:.0f}%")
c5.metric("Fingerprint Divergence", f"{div:.3f}", f"threshold {threshold:.3f}")
st.caption(f"Data mode: **{data_note}**")

st.divider()
st.markdown("### 01 · ONE VEHICLE IS NOISY")
st.caption("Single crossing — insufficient evidence")
left, right = st.columns(2)
with left:
    fig = go.Figure(go.Scatter(x=baseline[0]["t"], y=baseline[0]["acc"], mode="lines", line=dict(color="#67d6c3", width=1.2), name="raw acceleration"))
    fig.update_layout(**dark_layout(), xaxis_title="Time (s)", yaxis_title="Acceleration (a.u.)")
    st.plotly_chart(fig, use_container_width=True)
with right:
    single = crossing_to_peaks(baseline[0])
    fig = go.Figure(go.Scatter(x=single["f"], y=single["pxx"], mode="lines", line=dict(color="#f4b860"), name="single PSD"))
    fig.update_layout(**dark_layout(), xaxis_title="Frequency (Hz)", yaxis_title="Power spectral density")
    st.plotly_chart(fig, use_container_width=True)

st.divider()
st.markdown("### 02 · THE BRIDGE EMERGES FROM THE CROWD")
st.caption("Multi-crossing KDE / consensus fusion: random vehicle peaks fade, the shared bridge pulse remains.")
fig = go.Figure()
for count in [1, 5, 10, 20, 30, 50]:
    if count <= len(baseline_all):
        fused = fuse_crossings(baseline_all[:count])
        fig.add_trace(go.Scatter(x=fused["grid"], y=fused["fingerprint"], mode="lines", name=f"N={count}", visible=True if count == n else "legendonly"))
fig.add_vline(x=base_fused["dominant_frequency"], line_dash="dash", line_color="#67d6c3", annotation_text=f"Bridge Pulse {base_fused['dominant_frequency']:.2f} Hz")
fig.update_layout(**dark_layout(430), xaxis_title="Frequency (Hz)", yaxis_title="Normalized consensus density")
st.plotly_chart(fig, use_container_width=True)

conv = convergence_curve(baseline_all, counts=[1, 5, 10, 20, 30, 50])
cc1, cc2 = st.columns([1.25, 1])
with cc1:
    fig = go.Figure(go.Scatter(x=[x["n"] for x in conv], y=[x["dominant_frequency"] for x in conv], mode="lines+markers", line=dict(color="#67d6c3", width=3), name="pulse"))
    fig.add_hline(y=baseline_f, line_dash="dot", line_color="#8ca6b3")
    fig.update_layout(**dark_layout(280), xaxis_title="Crossings fused (N)", yaxis_title="Estimated pulse (Hz)")
    st.plotly_chart(fig, use_container_width=True)
with cc2:
    vehicle = [c.get("vehicle_freq", np.nan) for c in baseline_all[:50]]
    fig = go.Figure(go.Scatter(x=list(range(1, len(vehicle) + 1)), y=vehicle, mode="markers", marker=dict(color="#f4b860", size=7), name="vehicle frequency"))
    fig.add_hline(y=base_fused["dominant_frequency"], line_dash="dash", line_color="#67d6c3")
    fig.update_layout(**dark_layout(280), xaxis_title="Vehicle #", yaxis_title="Vehicle frequency (Hz)")
    st.plotly_chart(fig, use_container_width=True)

st.divider()
st.markdown("### 03 · BASELINE vs CURRENT")
fig = go.Figure()
fig.add_trace(go.Scatter(x=base_fused["grid"], y=base_fused["fingerprint"], mode="lines", line=dict(color="#67d6c3", width=3), name=f"Baseline · {base_fused['dominant_frequency']:.2f} Hz"))
fig.add_trace(go.Scatter(x=shift_fused["grid"], y=shift_fused["fingerprint"], mode="lines", line=dict(color="#f46d63", width=3), name=f"Current · {shift_fused['dominant_frequency']:.2f} Hz"))
fig.update_layout(**dark_layout(380), xaxis_title="Frequency (Hz)", yaxis_title="Normalized fingerprint")
st.plotly_chart(fig, use_container_width=True)

if is_shift:
    st.markdown(f'<div class="alert-box"><div class="eyebrow" style="color:#ff9b91">STRUCTURAL RESPONSE SHIFT DETECTED</div><p>Current pulse shifted <b>{shift_fused["dominant_frequency"] - base_fused["dominant_frequency"]:+.2f} Hz</b> · divergence <b>{div:.3f}</b> exceeds baseline 95% variability threshold <b>{threshold:.3f}</b>.</p><p><b>Recommend targeted engineering inspection.</b></p></div>', unsafe_allow_html=True)
else:
    st.success(f"WITHIN BASELINE VARIABILITY · divergence {div:.3f} vs threshold {threshold:.3f}")
st.info("QianPulse detects persistent changes in a bridge's dynamic response relative to its own historical baseline. It does not diagnose structural damage and does not replace professional bridge inspection.")
