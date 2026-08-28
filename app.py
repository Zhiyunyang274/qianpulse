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


st.set_page_config(
    page_title="黔脉 QianPulse",
    page_icon="🌉",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root {
        --bg:#05080d; --surface:#091019; --surface2:#0c151f; --line:#182633;
        --text:#eef4f6; --muted:#708493; --soft:#a6b5be;
        --cyan:#4de1cd; --cyan2:#1baea1; --amber:#eab661; --red:#ff6373;
    }
    html, body, [class*="css"] { font-family: Inter, "PingFang SC", "Microsoft YaHei", sans-serif; }
    .stApp {
        color:var(--text);
        background:
            radial-gradient(circle at 78% 2%, rgba(38,118,115,.13), transparent 29%),
            radial-gradient(circle at 18% 44%, rgba(22,66,87,.10), transparent 25%),
            var(--bg);
    }
    [data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer { display:none !important; }
    .block-container { max-width:1280px; padding:1.7rem 2.2rem 5rem; }
    div[data-testid="stPopover"] button {
        border:1px solid #233442; background:rgba(10,18,27,.86); color:#c4d0d6;
        border-radius:999px; min-height:36px; padding:0 16px; font-size:.76rem;
    }
    div[data-testid="stPopover"] button:hover { border-color:#477064; color:#fff; }
    div[data-testid="stPlotlyChart"] { margin:0; }
    .masthead { display:flex; align-items:center; gap:13px; padding:2px 0 5px; }
    .logo-mark { display:flex; align-items:flex-end; gap:3px; width:24px; height:23px; }
    .logo-mark i { width:3px; border-radius:3px; background:var(--cyan); display:block; box-shadow:0 0 14px rgba(77,225,205,.25); }
    .logo-mark i:nth-child(1), .logo-mark i:nth-child(5) { height:8px; opacity:.45; }
    .logo-mark i:nth-child(2), .logo-mark i:nth-child(4) { height:15px; opacity:.7; }
    .logo-mark i:nth-child(3) { height:23px; }
    .brand-cn { font-size:1.22rem; font-weight:800; letter-spacing:.17em; }
    .brand-en { color:var(--cyan); font-size:.61rem; font-weight:750; letter-spacing:.24em; margin-left:2px; }
    .mode-chip { display:inline-flex; align-items:center; gap:7px; color:#8497a4; font-size:.68rem; white-space:nowrap; padding-top:8px; }
    .mode-chip b { width:6px; height:6px; display:inline-block; border-radius:50%; background:var(--cyan); box-shadow:0 0 10px rgba(77,225,205,.65); }
    .hairline { height:1px; background:linear-gradient(90deg,var(--line),transparent); margin:12px 0 27px; }
    .hero-copy { padding:28px 8px 10px 0; min-height:365px; display:flex; flex-direction:column; justify-content:center; }
    .overline { color:#6d8492; font-size:.64rem; font-weight:750; letter-spacing:.19em; margin-bottom:16px; }
    .hero-title { color:var(--text); font-size:1.86rem; font-weight:680; letter-spacing:.035em; line-height:1.25; margin-bottom:18px; }
    .hero-shift { font-size:3.55rem; line-height:1; font-weight:720; letter-spacing:-.04em; color:var(--red); }
    .hero-unit { color:#a0afb8; font-size:.84rem; margin-left:8px; letter-spacing:.02em; }
    .hero-detail { color:#8194a1; font-size:.76rem; line-height:1.8; margin-top:20px; max-width:340px; }
    .hero-action { color:#e6edef; font-size:.76rem; margin-top:19px; padding-left:12px; border-left:2px solid var(--red); }
    .plot-label { color:#8fa0aa; font-size:.66rem; font-weight:650; letter-spacing:.1em; margin:2px 0 -10px; position:relative; z-index:2; }
    .kpi-strip { display:grid; grid-template-columns:repeat(5,1fr); border-top:1px solid var(--line); border-bottom:1px solid var(--line); margin:7px 0 50px; }
    .kpi { padding:16px 18px 15px 0; margin-right:18px; border-right:1px solid var(--line); }
    .kpi:last-child { border-right:0; margin-right:0; }
    .kpi-label { color:#647887; font-size:.64rem; letter-spacing:.08em; margin-bottom:8px; }
    .kpi-value { color:#e9f0f3; font-size:1.24rem; font-weight:660; }
    .kpi-value em { color:#8495a0; font-size:.67rem; font-style:normal; margin-left:4px; }
    .kpi-note { color:#4f6573; font-size:.61rem; margin-top:5px; }
    .story-head { display:flex; align-items:flex-end; justify-content:space-between; gap:28px; margin:46px 0 18px; }
    .story-index { color:var(--cyan); font-size:.6rem; font-weight:800; letter-spacing:.22em; margin-bottom:7px; }
    .story-title { font-size:1.12rem; font-weight:680; letter-spacing:.035em; }
    .story-copy { color:#718492; font-size:.72rem; line-height:1.75; max-width:560px; text-align:right; }
    .chart-shell { border-top:1px solid var(--line); padding-top:14px; }
    .decision { min-height:320px; background:linear-gradient(145deg,rgba(19,29,40,.82),rgba(8,14,21,.76)); border:1px solid var(--line); padding:27px 28px; display:flex; flex-direction:column; justify-content:center; }
    .decision-label { color:#687d8b; font-size:.62rem; letter-spacing:.16em; margin-bottom:19px; }
    .decision-title { font-size:1.34rem; font-weight:680; margin-bottom:20px; }
    .decision-row { display:flex; align-items:baseline; justify-content:space-between; border-top:1px solid var(--line); padding:12px 0; color:#7e919e; font-size:.7rem; }
    .decision-row strong { color:#edf3f5; font-size:.92rem; font-weight:650; }
    .decision-rec { margin-top:21px; color:#e8edef; font-size:.74rem; padding-left:12px; border-left:2px solid var(--red); }
    .boundary { color:#506573; border-top:1px solid var(--line); margin-top:50px; padding-top:14px; font-size:.67rem; line-height:1.8; }
    [data-testid="stFileUploaderDropzone"] { background:#09111a; border-color:#22333f; }
    [data-baseweb="popover"] { background:#0b131c !important; border:1px solid #233442 !important; }
    [data-baseweb="input"], [data-baseweb="base-input"], input { background:#091019 !important; }
    .stButton button[kind="primary"] { background:var(--cyan); color:#03100e; border:0; font-weight:750; }
    .stButton button[kind="primary"] p { color:#03100e !important; }
    @media(max-width:900px) {
        .block-container { padding:1.2rem 1rem 3rem; }
        .kpi-strip { grid-template-columns:repeat(2,1fr); }
        .story-copy { display:none; }
        .hero-copy { min-height:auto; padding-top:15px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def demo_data(seed, baseline_f, current_f):
    return (
        simulate_batch(60, bridge_freq=baseline_f, seed=seed),
        simulate_batch(60, bridge_freq=current_f, seed=seed + 100),
    )


def layout(height=320, show_y=True):
    return dict(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family='Inter, "PingFang SC", sans-serif', color="#708493", size=10),
        margin=dict(l=42 if show_y else 14, r=15, t=31, b=38),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.11, x=0, font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showgrid=False, zeroline=False, linecolor="#20313e", tickcolor="#20313e"),
        yaxis=dict(showgrid=True, showticklabels=show_y, gridcolor="#14212c", zeroline=False, linecolor="#20313e"),
    )


def show(fig):
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})


def story(index, title, copy):
    st.markdown(
        f'<div class="story-head"><div><div class="story-index">{index}</div><div class="story-title">{title}</div></div>'
        f'<div class="story-copy">{copy}</div></div>',
        unsafe_allow_html=True,
    )


top_brand, top_mode, top_settings = st.columns([7, 1.5, 1.1], vertical_alignment="center")
with top_brand:
    st.markdown(
        '<div class="masthead"><span class="logo-mark"><i></i><i></i><i></i><i></i><i></i></span>'
        '<span class="brand-cn">黔脉</span><span class="brand-en">QIANPULSE</span></div>',
        unsafe_allow_html=True,
    )
with top_settings:
    with st.popover("演示设置"):
        mode = st.radio("数据源", ["模拟演示", "Sensor Logger"], horizontal=True)
        baseline_f = st.slider("基线频率 / Hz", 5.0, 10.0, 7.8, 0.1)
        current_f = st.slider("当前频率 / Hz", 5.0, 10.0, 7.2, 0.1)
        n = st.slider("融合样本 / 次", 1, 50, 30, 1)
        seed = st.number_input("随机种子", 0, 9999, 42)
        replay = st.button("运行演示流程", type="primary", use_container_width=True)
        upload = st.file_uploader("导入 CSV / ZIP", type=["csv", "zip"]) if mode == "Sensor Logger" else None

if replay:
    progress = st.progress(0, text="正在读取单次穿越信号")
    for pct, label in [(18, "正在读取单次穿越信号"), (46, "正在融合多车辆频谱"), (72, "正在估计基线自然波动"), (100, "正在完成当前状态筛查")]:
        progress.progress(pct, text=label)
        time.sleep(.17)
    progress.empty()

baseline_all, current_all = demo_data(int(seed), baseline_f, current_f)
data_note = "模拟数据"
if mode == "Sensor Logger" and upload is not None:
    with tempfile.NamedTemporaryFile(suffix=Path(upload.name).suffix) as handle:
        handle.write(upload.getvalue())
        handle.flush()
        real = load_sensorlogger_export(handle.name)
    if real:
        baseline_all, current_all = real, real
        data_note = f"实测数据 · {len(real)} 次"
    else:
        st.warning("未识别到有效三轴加速度数据，已回退至模拟数据。")

count = min(n, len(baseline_all), len(current_all))
baseline, current = baseline_all[:count], current_all[:count]
base_fp, current_fp = fuse_crossings(baseline), fuse_crossings(current)
boot = bootstrap_baseline_divergence(baseline_all[:40], seed=int(seed) + 8)
threshold = boot["threshold95"]
divergence = fingerprint_divergence(base_fp["fingerprint"], current_fp["fingerprint"])
shift_hz = current_fp["dominant_frequency"] - base_fp["dominant_frequency"]
is_shift = bool(np.isfinite(threshold) and divergence > threshold and abs(current_f - baseline_f) >= .2)
counts = [1, 5, 10, 20, 30, 50]
conv = convergence_curve(baseline_all, counts=counts, seed=int(seed) + 11)
stability = min(conv, key=lambda item: abs(item["n"] - count))["stability"] * 100

with top_mode:
    st.markdown(f'<div class="mode-chip"><b></b>{data_note} · 本机分析</div>', unsafe_allow_html=True)
st.markdown('<div class="hairline"></div>', unsafe_allow_html=True)

hero_copy, hero_plot = st.columns([.72, 1.55], gap="large")
with hero_copy:
    title = "检测到响应偏移" if is_shift else "响应处于基线范围"
    action = "建议优先安排专业工程检查" if is_shift else "继续纳入常态化采集"
    st.markdown(
        f'<div class="hero-copy"><div class="overline">当前筛查结论</div><div class="hero-title">{title}</div>'
        f'<div><span class="hero-shift">{shift_hz:+.2f}</span><span class="hero-unit">Hz</span></div>'
        f'<div class="hero-detail">当前桥梁脉冲为 {current_fp["dominant_frequency"]:.2f} Hz，历史基线为 {base_fp["dominant_frequency"]:.2f} Hz。'
        f'动态指纹差异 {divergence:.3f}，基线自然波动阈值 {threshold:.3f}。</div>'
        f'<div class="hero-action">{action}</div></div>',
        unsafe_allow_html=True,
    )
with hero_plot:
    st.markdown('<div class="plot-label">桥梁动态指纹 / 历史基线与当前状态</div>', unsafe_allow_html=True)
    hero_fig = go.Figure()
    for width, opacity in [(13, .035), (7, .055)]:
        hero_fig.add_trace(go.Scatter(x=base_fp["grid"], y=base_fp["fingerprint"], mode="lines", line=dict(color="#4de1cd", width=width), opacity=opacity, showlegend=False, hoverinfo="skip"))
        hero_fig.add_trace(go.Scatter(x=current_fp["grid"], y=current_fp["fingerprint"], mode="lines", line=dict(color="#ff6373", width=width), opacity=opacity, showlegend=False, hoverinfo="skip"))
    hero_fig.add_trace(go.Scatter(x=base_fp["grid"], y=base_fp["fingerprint"], mode="lines", line=dict(color="#4de1cd", width=2.4), fill="tozeroy", fillcolor="rgba(77,225,205,.035)", name=f"历史基线 {base_fp['dominant_frequency']:.2f} Hz"))
    hero_fig.add_trace(go.Scatter(x=current_fp["grid"], y=current_fp["fingerprint"], mode="lines", line=dict(color="#ff6373", width=2.4), fill="tozeroy", fillcolor="rgba(255,99,115,.03)", name=f"当前状态 {current_fp['dominant_frequency']:.2f} Hz"))
    hero_fig.update_layout(**layout(390, show_y=False), xaxis_title="频率 / Hz", yaxis_title="")
    show(hero_fig)

st.markdown(
    f'<div class="kpi-strip">'
    f'<div class="kpi"><div class="kpi-label">融合样本</div><div class="kpi-value">{count}<em>次</em></div><div class="kpi-note">多车辆穿越</div></div>'
    f'<div class="kpi"><div class="kpi-label">历史基线</div><div class="kpi-value">{base_fp["dominant_frequency"]:.2f}<em>Hz</em></div><div class="kpi-note">桥梁脉冲</div></div>'
    f'<div class="kpi"><div class="kpi-label">当前状态</div><div class="kpi-value">{current_fp["dominant_frequency"]:.2f}<em>Hz</em></div><div class="kpi-note">最新融合结果</div></div>'
    f'<div class="kpi"><div class="kpi-label">融合稳定度</div><div class="kpi-value">{stability:.0f}<em>%</em></div><div class="kpi-note">自助采样估计</div></div>'
    f'<div class="kpi"><div class="kpi-label">指纹差异 / 阈值</div><div class="kpi-value">{divergence:.3f}<em>/ {threshold:.3f}</em></div><div class="kpi-note">基线 95% 波动边界</div></div>'
    f'</div>',
    unsafe_allow_html=True,
)

story("01 / 原始证据", "单次穿越不足以判断", "车辆悬架、路面冲击和随机噪声共同主导单次观测。黔脉不使用单辆车作出桥梁状态结论。")
raw_col, psd_col = st.columns([1.18, 1], gap="large")
with raw_col:
    st.markdown('<div class="chart-shell"><div class="plot-label">原始垂向加速度</div>', unsafe_allow_html=True)
    raw_fig = go.Figure(go.Scatter(x=baseline[0]["t"], y=baseline[0]["acc"], mode="lines", line=dict(color="#67cfc2", width=.9), name="原始信号"))
    raw_fig.update_layout(**layout(275), xaxis_title="时间 / 秒", yaxis_title="加速度 / 相对值")
    show(raw_fig)
    st.markdown('</div>', unsafe_allow_html=True)
with psd_col:
    st.markdown('<div class="chart-shell"><div class="plot-label">单次穿越功率谱</div>', unsafe_allow_html=True)
    single = crossing_to_peaks(baseline[0])
    psd_fig = go.Figure(go.Scatter(x=single["f"], y=single["pxx"], mode="lines", line=dict(color="#eab661", width=1.35), fill="tozeroy", fillcolor="rgba(234,182,97,.045)", name="功率谱"))
    psd_fig.update_layout(**layout(275), xaxis_title="频率 / Hz", yaxis_title="功率谱密度")
    show(psd_fig)
    st.markdown('</div>', unsafe_allow_html=True)

story("02 / 群体共识", "桥梁脉冲从多车数据中浮现", "不同车辆的自身频率持续变化；只有桥梁共享频率会在多次穿越融合中不断增强并稳定收敛。")
st.markdown('<div class="chart-shell"><div class="plot-label">融合规模与动态指纹收敛</div>', unsafe_allow_html=True)
fusion_fig = go.Figure()
palette = ["#283a46", "#334c58", "#3b5d66", "#3d7978", "#43b5a8", "#4de1cd"]
for idx, sample_n in enumerate(counts):
    if sample_n <= len(baseline_all):
        fused = fuse_crossings(baseline_all[:sample_n])
        fusion_fig.add_trace(go.Scatter(x=fused["grid"], y=fused["fingerprint"], mode="lines", line=dict(color=palette[idx], width=1.1 + idx * .22), name=f"{sample_n} 次"))
fusion_fig.add_vline(x=base_fp["dominant_frequency"], line_dash="dot", line_color="#79e7d8", annotation_text=f"共识脉冲 {base_fp['dominant_frequency']:.2f} Hz", annotation_font_color="#87d9ce", annotation_position="top right")
fusion_fig.update_layout(**layout(370), xaxis_title="频率 / Hz", yaxis_title="归一化共识密度")
show(fusion_fig)
st.markdown('</div>', unsafe_allow_html=True)

small_left, small_right = st.columns([1, 1], gap="large")
with small_left:
    st.markdown('<div class="chart-shell"><div class="plot-label">桥梁脉冲收敛轨迹</div>', unsafe_allow_html=True)
    conv_fig = go.Figure(go.Scatter(x=[x["n"] for x in conv], y=[x["dominant_frequency"] for x in conv], mode="lines+markers", line=dict(color="#4de1cd", width=2), marker=dict(size=6, color="#05080d", line=dict(color="#4de1cd", width=1.7)), name="桥梁脉冲"))
    conv_fig.add_hline(y=baseline_f, line_dash="dot", line_color="#3b4c58")
    conv_fig.update_layout(**layout(255), xaxis_title="融合样本 / 次", yaxis_title="频率 / Hz")
    show(conv_fig)
    st.markdown('</div>', unsafe_allow_html=True)
with small_right:
    st.markdown('<div class="chart-shell"><div class="plot-label">车辆自身频率离散分布</div>', unsafe_allow_html=True)
    vehicle_freqs = [c.get("vehicle_freq", np.nan) for c in baseline_all[:50]]
    vehicle_fig = go.Figure(go.Scatter(x=list(range(1, len(vehicle_freqs) + 1)), y=vehicle_freqs, mode="markers", marker=dict(color="#eab661", size=4.5, opacity=.72), name="车辆频率"))
    vehicle_fig.add_hline(y=base_fp["dominant_frequency"], line_dash="dot", line_color="#4de1cd")
    vehicle_fig.update_layout(**layout(255), xaxis_title="车辆编号", yaxis_title="频率 / Hz")
    show(vehicle_fig)
    st.markdown('</div>', unsafe_allow_html=True)

story("03 / 统计闭环", "异常结论来自桥梁自身基线", "将历史穿越数据反复拆分并比较，得到自然波动分布与 95% 阈值；当前差异只有越过该阈值才触发复核建议。")
hist_col, decision_col = st.columns([1.35, .82], gap="large")
with hist_col:
    st.markdown('<div class="chart-shell"><div class="plot-label">历史基线内部差异分布</div>', unsafe_allow_html=True)
    hist_fig = go.Figure(go.Histogram(x=boot["values"], nbinsx=14, marker=dict(color="#315c60", line=dict(color="#4a7c7c", width=.5)), opacity=.86, name="自然波动"))
    hist_fig.add_vline(x=threshold, line_dash="dot", line_color="#eab661", annotation_text=f"95% 阈值 {threshold:.3f}", annotation_font_color="#d5ab69", annotation_position="top left")
    hist_fig.add_vline(x=divergence, line_color="#ff6373", line_width=2, annotation_text=f"当前差异 {divergence:.3f}", annotation_font_color="#ff8893", annotation_position="top right")
    hist_fig.update_layout(**layout(320), xaxis_title="指纹差异", yaxis_title="出现次数", bargap=.12)
    show(hist_fig)
    st.markdown('</div>', unsafe_allow_html=True)
with decision_col:
    decision_title = "超过自然波动阈值" if is_shift else "未超过自然波动阈值"
    recommendation = "建议优先进行专业工程检查" if is_shift else "继续积累常态化穿越数据"
    st.markdown(
        f'<div class="decision"><div class="decision-label">筛查判定</div><div class="decision-title">{decision_title}</div>'
        f'<div class="decision-row"><span>当前指纹差异</span><strong>{divergence:.3f}</strong></div>'
        f'<div class="decision-row"><span>基线 95% 阈值</span><strong>{threshold:.3f}</strong></div>'
        f'<div class="decision-row"><span>频率变化</span><strong>{shift_hz:+.2f} Hz</strong></div>'
        f'<div class="decision-rec">{recommendation}</div></div>',
        unsafe_allow_html=True,
    )

st.markdown(
    '<div class="boundary">方法边界：黔脉仅筛查桥梁相对自身历史基线的持续动态响应变化，不进行损伤类型识别、裂缝诊断或安全等级判断，也不能替代专业桥梁检测。</div>',
    unsafe_allow_html=True,
)
