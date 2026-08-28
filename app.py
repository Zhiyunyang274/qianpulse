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

st.markdown(
    """
    <style>
    :root {
        --bg: #060b11;
        --panel: #0b131c;
        --panel-2: #0e1823;
        --line: #1b2a38;
        --text: #edf4f7;
        --muted: #718596;
        --cyan: #39d6c4;
        --amber: #f1b85b;
        --red: #ff6b78;
    }
    html, body, [class*="css"] { font-family: Inter, "PingFang SC", "Microsoft YaHei", sans-serif; }
    .stApp { background: var(--bg); color: var(--text); }
    [data-testid="stHeader"] { background: transparent; height: 0; }
    [data-testid="stToolbar"], #MainMenu, footer { display: none !important; }
    .block-container { max-width: 1320px; padding: 1.5rem 2rem 4rem; }
    [data-testid="stSidebar"] { background: #080e15; border-right: 1px solid var(--line); }
    [data-testid="stSidebar"] > div:first-child { padding-top: 1.4rem; }
    [data-testid="stSidebar"] * { color: #cbd8df; }
    [data-testid="stSidebar"] hr { border-color: var(--line); }
    [data-testid="stSidebar"] [data-baseweb="radio"] > div:first-child { background-color: var(--cyan); }
    [data-testid="stSidebar"] .stButton button {
        background: var(--cyan); border: 0; color: #03100f; font-weight: 750;
        min-height: 42px; border-radius: 7px;
    }
    [data-testid="stSidebar"] .stButton button:hover { background: #63e4d5; color: #03100f; }
    [data-testid="stSidebar"] .stButton button p { color: #03100f !important; font-weight: 750; }
    [data-testid="stSidebar"] [data-baseweb="input"],
    [data-testid="stSidebar"] [data-baseweb="base-input"],
    [data-testid="stSidebar"] input { background: var(--panel) !important; color: var(--text) !important; }
    [data-testid="stSidebar"] [role="slider"] { color: var(--cyan) !important; }
    [data-testid="stFileUploaderDropzone"] { background: var(--panel); border-color: var(--line); }
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: linear-gradient(180deg, rgba(14,24,35,.96), rgba(9,17,25,.96));
        border: 1px solid var(--line) !important; border-radius: 10px !important;
    }
    .brandbar { display:flex; align-items:center; justify-content:space-between; padding:4px 0 18px; }
    .brand { display:flex; align-items:baseline; gap:12px; }
    .brand-cn { font-size:1.35rem; font-weight:800; letter-spacing:.14em; color:var(--text); }
    .brand-en { font-size:.67rem; font-weight:700; letter-spacing:.24em; color:var(--cyan); }
    .brand-desc { color:var(--muted); font-size:.79rem; letter-spacing:.02em; }
    .live-chip { display:inline-flex; align-items:center; gap:8px; border:1px solid var(--line); background:var(--panel); padding:7px 11px; border-radius:999px; color:#9fb0bd; font-size:.72rem; }
    .live-dot { width:6px; height:6px; border-radius:50%; background:var(--cyan); box-shadow:0 0 10px var(--cyan); }
    .status-strip { display:flex; align-items:center; justify-content:space-between; gap:24px; background:linear-gradient(90deg,#0d1822,#101821); border:1px solid var(--line); border-left:3px solid var(--red); padding:18px 20px; border-radius:9px; margin-bottom:14px; }
    .status-strip.normal { border-left-color:var(--cyan); }
    .status-kicker { color:var(--muted); font-size:.67rem; letter-spacing:.18em; margin-bottom:5px; }
    .status-title { font-size:1.03rem; font-weight:750; letter-spacing:.04em; }
    .status-note { color:#8fa1af; font-size:.78rem; margin-top:4px; }
    .status-action { text-align:right; color:#dce7ec; font-size:.78rem; white-space:nowrap; }
    .metric-card { min-height:91px; background:var(--panel); border:1px solid var(--line); border-radius:9px; padding:14px 15px; }
    .metric-label { color:var(--muted); font-size:.68rem; letter-spacing:.08em; margin-bottom:8px; }
    .metric-value { color:var(--text); font-size:1.47rem; font-weight:690; line-height:1; }
    .metric-unit { color:#8fa1af; font-size:.72rem; margin-left:4px; }
    .metric-sub { color:#5e7586; font-size:.66rem; margin-top:7px; }
    .section-head { display:flex; align-items:flex-end; justify-content:space-between; gap:20px; margin:30px 0 12px; }
    .section-index { color:var(--cyan); font-size:.64rem; font-weight:800; letter-spacing:.2em; margin-bottom:5px; }
    .section-title { color:var(--text); font-size:.96rem; font-weight:720; letter-spacing:.04em; }
    .section-desc { color:var(--muted); font-size:.75rem; max-width:620px; text-align:right; }
    .panel-title { color:#a9bac5; font-size:.68rem; font-weight:650; letter-spacing:.08em; margin:2px 0 -6px; }
    .boundary { margin-top:24px; border-top:1px solid var(--line); padding-top:14px; color:#647887; font-size:.7rem; line-height:1.7; }
    div[data-testid="stPlotlyChart"] { margin-top:-6px; }
    @media (max-width: 900px) {
        .brand-desc, .section-desc { display:none; }
        .status-strip { align-items:flex-start; flex-direction:column; }
        .status-action { text-align:left; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def demo_data(seed, baseline_f, shifted_f):
    return (
        simulate_batch(60, bridge_freq=baseline_f, seed=seed),
        simulate_batch(60, bridge_freq=shifted_f, seed=seed + 100),
    )


def chart_layout(height=320):
    return dict(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family='Inter, "PingFang SC", sans-serif', color="#8194a3", size=11),
        margin=dict(l=44, r=18, t=24, b=42),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.10, x=0, font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showgrid=False, zeroline=False, linecolor="#263746", tickcolor="#263746"),
        yaxis=dict(showgrid=True, gridcolor="#172532", zeroline=False, linecolor="#263746"),
    )


def show_chart(fig):
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})


def section_header(index, title, description):
    st.markdown(
        f'<div class="section-head"><div><div class="section-index">{index}</div>'
        f'<div class="section-title">{title}</div></div>'
        f'<div class="section-desc">{description}</div></div>',
        unsafe_allow_html=True,
    )


def metric_card(label, value, unit="", sub=""):
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}<span class="metric-unit">{unit}</span></div>'
        f'<div class="metric-sub">{sub}</div></div>',
        unsafe_allow_html=True,
    )


with st.sidebar:
    st.markdown("### 控制台")
    mode = st.radio("数据源", ["模拟演示", "Sensor Logger"], index=0)
    st.markdown("---")
    baseline_f = st.slider("基线频率 / Hz", 5.0, 10.0, 7.8, 0.1)
    shifted_f = st.slider("当前频率 / Hz", 5.0, 10.0, 7.2, 0.1)
    n = st.slider("融合样本 / 次", 1, 50, 30, 1)
    seed = st.number_input("随机种子", 0, 9999, 42)
    replay = st.button("运行演示流程", use_container_width=True, type="primary")
    upload = st.file_uploader("导入 CSV / ZIP", type=["csv", "zip"]) if mode == "Sensor Logger" else None
    st.markdown("---")
    st.caption("本机计算 · 无需联网")

if replay:
    progress = st.progress(0, text="正在载入单次穿越信号")
    for pct, label in [
        (18, "正在载入单次穿越信号"),
        (42, "正在聚合多车辆频谱"),
        (67, "正在建立桥梁脉冲基线"),
        (86, "正在计算自然波动阈值"),
        (100, "正在完成当前状态筛查"),
    ]:
        progress.progress(pct, text=label)
        time.sleep(0.16)
    progress.empty()

baseline_all, shifted_all = demo_data(int(seed), baseline_f, shifted_f)
data_note = "模拟数据"
if mode == "Sensor Logger" and upload is not None:
    with tempfile.NamedTemporaryFile(suffix=Path(upload.name).suffix) as handle:
        handle.write(upload.getvalue())
        handle.flush()
        real_crossings = load_sensorlogger_export(handle.name)
    if real_crossings:
        baseline_all = real_crossings
        shifted_all = real_crossings
        data_note = f"Sensor Logger · {len(real_crossings)} 次"
    else:
        st.warning("未识别到有效的三轴加速度数据，已回退至模拟数据。")

available_n = min(n, len(baseline_all), len(shifted_all))
baseline, shifted = baseline_all[:available_n], shifted_all[:available_n]
base_fused, shift_fused = fuse_crossings(baseline), fuse_crossings(shifted)
boot = bootstrap_baseline_divergence(baseline_all[:40], seed=int(seed) + 8)
threshold = boot["threshold95"]
div = fingerprint_divergence(base_fused["fingerprint"], shift_fused["fingerprint"])
is_shift = bool(np.isfinite(threshold) and div > threshold and abs(shifted_f - baseline_f) >= 0.2)
counts = [1, 5, 10, 20, 30, 50]
conv = convergence_curve(baseline_all, counts=counts, seed=int(seed) + 11)
stability_item = min(conv, key=lambda item: abs(item["n"] - available_n))
stability = stability_item["stability"] * 100

status_class = "" if is_shift else " normal"
status_title = "响应偏移 · 建议复核" if is_shift else "响应稳定 · 基线范围内"
status_note = (
    f"当前脉冲较历史基线变化 {shift_fused['dominant_frequency'] - base_fused['dominant_frequency']:+.2f} Hz"
    if is_shift else "当前动态指纹未超过自然波动阈值"
)
status_action = "建议优先安排专业工程检查" if is_shift else "继续纳入常态化采集"

st.markdown(
    f'<div class="brandbar"><div class="brand"><span class="brand-cn">黔脉</span>'
    f'<span class="brand-en">QIANPULSE</span><span class="brand-desc">桥梁动态响应移动感知</span></div>'
    f'<span class="live-chip"><span class="live-dot"></span>{data_note} · 离线分析</span></div>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<div class="status-strip{status_class}"><div><div class="status-kicker">筛查状态</div>'
    f'<div class="status-title">{status_title}</div><div class="status-note">{status_note}</div></div>'
    f'<div class="status-action">{status_action}</div></div>',
    unsafe_allow_html=True,
)

m1, m2, m3, m4, m5 = st.columns(5, gap="small")
with m1:
    metric_card("融合样本", str(available_n), "次", "多车辆穿越")
with m2:
    metric_card("基线脉冲", f"{base_fused['dominant_frequency']:.2f}", "Hz", "历史动态指纹")
with m3:
    metric_card("当前脉冲", f"{shift_fused['dominant_frequency']:.2f}", "Hz", "当前观测状态")
with m4:
    metric_card("融合稳定度", f"{stability:.0f}", "%", "自助采样频率离散度")
with m5:
    metric_card("指纹差异", f"{div:.3f}", "", f"95% 阈值 {threshold:.3f}")

section_header("01 / 单次穿越", "单次穿越观测", "车辆、路面冲击与随机噪声相互叠加；单次信号仅用于展示原始证据，不用于状态判断。")
left, right = st.columns(2, gap="medium")
with left:
    with st.container(border=True):
        st.markdown('<div class="panel-title">原始垂向加速度</div>', unsafe_allow_html=True)
        raw_fig = go.Figure(go.Scatter(
            x=baseline[0]["t"], y=baseline[0]["acc"], mode="lines",
            line=dict(color="#39d6c4", width=1), name="加速度",
        ))
        raw_fig.update_layout(**chart_layout(300), xaxis_title="时间 / 秒", yaxis_title="加速度 / 相对值")
        show_chart(raw_fig)
with right:
    with st.container(border=True):
        st.markdown('<div class="panel-title">单次穿越功率谱</div>', unsafe_allow_html=True)
        single = crossing_to_peaks(baseline[0])
        psd_fig = go.Figure(go.Scatter(
            x=single["f"], y=single["pxx"], mode="lines",
            line=dict(color="#f1b85b", width=1.5), fill="tozeroy", fillcolor="rgba(241,184,91,.08)", name="PSD",
        ))
        psd_fig.update_layout(**chart_layout(300), xaxis_title="频率 / Hz", yaxis_title="功率谱密度")
        show_chart(psd_fig)

section_header("02 / 多车共识", "多车融合与收敛", "车辆自身频率随车辆变化，共同的桥梁频率在多次穿越共识中持续增强。")
with st.container(border=True):
    st.markdown('<div class="panel-title">桥梁动态指纹 · 样本规模对比</div>', unsafe_allow_html=True)
    fusion_fig = go.Figure()
    for count in counts:
        if count > len(baseline_all):
            continue
        fused = fuse_crossings(baseline_all[:count])
        is_selected = count == min(counts, key=lambda x: abs(x - available_n))
        fusion_fig.add_trace(go.Scatter(
            x=fused["grid"], y=fused["fingerprint"], mode="lines", name=f"{count} 次",
            line=dict(width=2.6 if is_selected else 1.1, color="#39d6c4" if is_selected else None),
            opacity=1 if is_selected else .42,
        ))
    fusion_fig.add_vline(
        x=base_fused["dominant_frequency"], line_dash="dot", line_color="#39d6c4",
        annotation_text=f"共识脉冲 {base_fused['dominant_frequency']:.2f} Hz",
        annotation_font_color="#8feadd", annotation_position="top right",
    )
    fusion_fig.update_layout(**chart_layout(390), xaxis_title="频率 / Hz", yaxis_title="归一化共识密度")
    show_chart(fusion_fig)

conv_left, conv_right = st.columns([1.15, 1], gap="medium")
with conv_left:
    with st.container(border=True):
        st.markdown('<div class="panel-title">桥梁脉冲收敛轨迹</div>', unsafe_allow_html=True)
        convergence_fig = go.Figure(go.Scatter(
            x=[x["n"] for x in conv], y=[x["dominant_frequency"] for x in conv],
            mode="lines+markers", line=dict(color="#39d6c4", width=2.4),
            marker=dict(size=7, color="#06100f", line=dict(color="#39d6c4", width=2)), name="估计脉冲",
        ))
        convergence_fig.add_hline(y=baseline_f, line_dash="dot", line_color="#526575")
        convergence_fig.update_layout(**chart_layout(270), xaxis_title="融合样本 / 次", yaxis_title="频率 / Hz")
        show_chart(convergence_fig)
with conv_right:
    with st.container(border=True):
        st.markdown('<div class="panel-title">车辆频率离散性验证</div>', unsafe_allow_html=True)
        vehicle = [c.get("vehicle_freq", np.nan) for c in baseline_all[:50]]
        vehicle_fig = go.Figure(go.Scatter(
            x=list(range(1, len(vehicle) + 1)), y=vehicle, mode="markers",
            marker=dict(color="#f1b85b", size=5, opacity=.76), name="车辆自身频率",
        ))
        vehicle_fig.add_hline(y=base_fused["dominant_frequency"], line_dash="dot", line_color="#39d6c4")
        vehicle_fig.update_layout(**chart_layout(270), xaxis_title="车辆编号", yaxis_title="频率 / Hz")
        show_chart(vehicle_fig)

section_header("03 / 漂移筛查", "基线漂移筛查", "使用历史基线内部自助采样波动建立 95% 阈值，再与当前动态指纹进行同桥纵向比较。")
with st.container(border=True):
    st.markdown('<div class="panel-title">历史基线 / 当前状态</div>', unsafe_allow_html=True)
    compare_fig = go.Figure()
    compare_fig.add_trace(go.Scatter(
        x=base_fused["grid"], y=base_fused["fingerprint"], mode="lines",
        line=dict(color="#39d6c4", width=2.7), fill="tozeroy", fillcolor="rgba(57,214,196,.06)",
        name=f"历史基线 · {base_fused['dominant_frequency']:.2f} Hz",
    ))
    compare_fig.add_trace(go.Scatter(
        x=shift_fused["grid"], y=shift_fused["fingerprint"], mode="lines",
        line=dict(color="#ff6b78", width=2.7), fill="tozeroy", fillcolor="rgba(255,107,120,.04)",
        name=f"当前状态 · {shift_fused['dominant_frequency']:.2f} Hz",
    ))
    compare_fig.update_layout(**chart_layout(360), xaxis_title="频率 / Hz", yaxis_title="归一化动态指纹")
    show_chart(compare_fig)

st.markdown(
    '<div class="boundary">方法边界：黔脉用于筛查桥梁相对自身历史基线的持续动态响应变化，不进行损伤类型识别、裂缝诊断或安全等级判断，也不能替代专业桥梁检测。</div>',
    unsafe_allow_html=True,
)
