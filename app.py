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
        --paper:#f5f3ee; --ink:#171b1a; --muted:#737975; --rule:#d3d0c8;
        --night:#111820; --night2:#1a242e; --white:#f5f6f2;
        --red:#c64d43; --green:#65796f; --gold:#b18a58;
    }
    html, body, [class*="css"] { font-family:"PingFang SC","Microsoft YaHei",sans-serif; }
    .stApp { background:var(--paper); color:var(--ink); }
    [data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer { display:none !important; }
    .block-container { max-width:1280px; padding:1.3rem 2.1rem 5rem; }
    div[data-testid="stPlotlyChart"] { margin:0; }
    div[data-testid="stPopover"] button {
        min-height:34px; padding:0 13px; color:#4c5350; background:transparent;
        border:1px solid #bbb8b0; border-radius:0; box-shadow:none; font-size:.71rem;
    }
    div[data-testid="stPopover"] button:hover { color:var(--ink); border-color:var(--ink); }
    [data-baseweb="popover"] { background:#faf8f3 !important; border:1px solid #bbb8b0 !important; color:var(--ink) !important; }
    [data-baseweb="input"], [data-baseweb="base-input"], input { background:#ece9e2 !important; color:var(--ink) !important; }
    [data-testid="stFileUploaderDropzone"] { background:#ece9e2; border-color:#bbb8b0; }
    .stButton button[kind="primary"] { background:var(--ink); color:white; border:0; border-radius:0; font-weight:650; }
    .stButton button[kind="primary"] p { color:white !important; }

    .topbar { display:flex; align-items:center; gap:13px; min-height:42px; }
    .wordmark { font-size:1.17rem; font-weight:750; letter-spacing:.15em; }
    .wordmark-en { font-family:Arial,sans-serif; font-size:.58rem; letter-spacing:.2em; color:#626a66; }
    .top-context { margin-left:9px; padding-left:15px; border-left:1px solid var(--rule); color:#787e7a; font-size:.64rem; }
    .data-state { color:#6b736f; font-size:.64rem; text-align:right; line-height:1.6; }
    .top-rule { height:1px; background:var(--rule); margin:9px 0 20px; }

    .hero { background:var(--night); color:var(--white); display:grid; grid-template-columns:38% 62%; min-height:470px; overflow:hidden; }
    .hero-copy { padding:52px 46px 42px; display:flex; flex-direction:column; justify-content:space-between; border-right:1px solid rgba(222,228,226,.14); }
    .hero-kicker { color:#94a1a3; font-size:.66rem; letter-spacing:.08em; }
    .hero-title { font-family:"Songti SC","STSong",serif; font-size:2.7rem; font-weight:700; line-height:1.23; letter-spacing:.025em; margin:22px 0; }
    .hero-desc { color:#9ca7a8; font-size:.73rem; line-height:1.9; max-width:320px; }
    .hero-status { border-top:1px solid rgba(222,228,226,.16); padding-top:18px; display:flex; justify-content:space-between; align-items:flex-end; }
    .status-label { color:#94a1a3; font-size:.61rem; margin-bottom:7px; }
    .status-text { font-size:.88rem; }
    .status-shift { color:#e16a61; font-family:Georgia,serif; font-size:2rem; line-height:1; }
    .status-shift span { color:#96a1a2; font-family:"PingFang SC",sans-serif; font-size:.62rem; margin-left:4px; }
    .hero-chart { position:relative; min-height:470px; padding:27px 31px 15px; display:flex; flex-direction:column; }
    .chart-overline { color:#8f9b9e; font-size:.62rem; letter-spacing:.06em; }
    .hero-chart svg { width:100%; flex:1; display:block; }
    .hero-legend { display:flex; gap:22px; color:#a9b2b3; font-size:.62rem; padding:0 3px 15px; }
    .legend-line { display:inline-block; width:21px; height:2px; margin-right:7px; vertical-align:middle; }

    .facts { display:grid; grid-template-columns:repeat(4,1fr); border-bottom:1px solid var(--rule); }
    .fact { padding:18px 22px 17px 0; margin-right:22px; border-right:1px solid var(--rule); }
    .fact:last-child { border-right:0; }
    .fact-label { color:#747b77; font-size:.61rem; margin-bottom:7px; }
    .fact-value { font-family:Georgia,serif; font-size:1.24rem; color:var(--ink); }
    .fact-value span { font-family:"PingFang SC",sans-serif; font-size:.63rem; color:#747b77; margin-left:4px; }

    .statement { margin:76px 0 28px; display:grid; grid-template-columns:58% 42%; align-items:end; }
    .statement-index { color:var(--red); font-family:Georgia,serif; font-size:.66rem; margin-bottom:10px; }
    .statement-title { font-family:"Songti SC","STSong",serif; font-size:2rem; font-weight:700; line-height:1.35; }
    .statement-copy { color:#727975; font-size:.71rem; line-height:1.9; max-width:430px; justify-self:end; }
    .chart-block { border-top:1px solid var(--rule); padding-top:14px; }
    .chart-name { color:#5d6561; font-size:.66rem; font-weight:600; margin-bottom:-7px; }

    .fusion-steps { display:grid; grid-template-columns:repeat(5,1fr); border-top:1px solid var(--rule); border-bottom:1px solid var(--rule); margin-top:30px; }
    .fusion-step { padding:16px 15px 14px 0; margin-right:15px; border-right:1px solid var(--rule); }
    .fusion-step:last-child { border-right:0; }
    .step-n { font-family:Georgia,serif; font-size:1.02rem; }
    .step-n span { color:#757c78; font-family:"PingFang SC",sans-serif; font-size:.59rem; margin-left:3px; }
    .step-bar { height:3px; background:#dbd7ce; margin:13px 0 8px; }
    .step-bar i { display:block; height:100%; background:var(--green); }
    .step-note { color:#7b827e; font-size:.59rem; }

    .conclusion { background:#e9e6de; border-top:4px solid var(--night); min-height:310px; padding:27px 28px; display:flex; flex-direction:column; justify-content:center; }
    .conclusion-label { color:#737a76; font-size:.61rem; }
    .conclusion-title { font-family:"Songti SC","STSong",serif; font-size:1.35rem; font-weight:700; line-height:1.45; margin:14px 0 19px; }
    .conclusion-row { display:flex; justify-content:space-between; padding:10px 0; border-top:1px solid #cbc7bd; color:#727975; font-size:.65rem; }
    .conclusion-row b { font-family:Georgia,serif; color:var(--ink); font-size:.88rem; font-weight:500; }
    .conclusion-action { color:var(--red); border-left:3px solid var(--red); padding-left:10px; font-size:.68rem; line-height:1.65; margin-top:17px; }
    .boundary { margin-top:56px; border-top:1px solid var(--rule); padding-top:14px; color:#767d79; font-size:.63rem; line-height:1.85; }
    @media(max-width:900px) {
        .block-container { padding:1rem; }
        .hero { grid-template-columns:1fr; }
        .hero-copy { border-right:0; padding:38px 27px; }
        .hero-chart { min-height:340px; }
        .facts, .fusion-steps { grid-template-columns:repeat(2,1fr); }
        .statement { grid-template-columns:1fr; }
        .statement-copy { justify-self:start; margin-top:15px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def demo_data(seed, baseline_f, current_f):
    return (
        simulate_batch(100, bridge_freq=baseline_f, seed=seed),
        simulate_batch(100, bridge_freq=current_f, seed=seed + 100),
    )


def chart_layout(height=300, show_y=True):
    return dict(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family='"PingFang SC",sans-serif', color="#717873", size=10),
        margin=dict(l=44 if show_y else 16, r=16, t=30, b=40), hovermode="x unified",
        legend=dict(orientation="h", y=1.1, x=0, font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showgrid=False, zeroline=False, linecolor="#bbb7ac", tickcolor="#bbb7ac"),
        yaxis=dict(showgrid=True, showticklabels=show_y, gridcolor="#ddd9d0", zeroline=False, linecolor="#bbb7ac"),
    )


def show_chart(fig):
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})


def svg_curve(x_values, y_values, width=690, height=330, pad_x=30, pad_y=35):
    x_values, y_values = np.asarray(x_values), np.asarray(y_values)
    xs = pad_x + (x_values - x_values.min()) / max(np.ptp(x_values), 1e-9) * (width - 2 * pad_x)
    ys = height - pad_y - y_values / max(np.max(y_values), 1e-9) * (height - 2 * pad_y)
    return "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))


def statement(number, title, copy):
    st.markdown(
        f'<div class="statement"><div><div class="statement-index">{number}</div><div class="statement-title">{title}</div></div>'
        f'<div class="statement-copy">{copy}</div></div>', unsafe_allow_html=True,
    )


brand_col, mode_col, settings_col = st.columns([7, 1.4, 1], vertical_alignment="center")
with brand_col:
    st.markdown(
        '<div class="topbar"><span class="wordmark">黔脉</span><span class="wordmark-en">QIANPULSE</span>'
        '<span class="top-context">贵州山地桥梁移动感知</span></div>', unsafe_allow_html=True,
    )
with settings_col:
    with st.popover("演示设置"):
        mode = st.radio("数据源", ["模拟演示", "Sensor Logger"], horizontal=True)
        baseline_f = st.slider("基线频率 / Hz", 5.0, 10.0, 7.8, 0.1)
        current_f = st.slider("当前频率 / Hz", 5.0, 10.0, 7.2, 0.1)
        n = st.slider("融合样本 / 次", 1, 100, 50, 1)
        seed = st.number_input("随机种子", 0, 9999, 42)
        replay = st.button("运行演示流程", type="primary", use_container_width=True)
        upload = st.file_uploader("导入 CSV / ZIP", type=["csv", "zip"]) if mode == "Sensor Logger" else None

if replay:
    progress = st.progress(0, text="读取车辆穿越信号")
    for pct, label in [(20, "读取车辆穿越信号"), (48, "融合多车辆频谱"), (75, "估计桥梁自然波动"), (100, "完成响应偏移筛查")]:
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
conv = convergence_curve(baseline_all, counts=[1, 5, 10, 20, 50, 100], seed=int(seed) + 11)
stability = min(conv, key=lambda item: abs(item["n"] - count))["stability"] * 100

with mode_col:
    st.markdown(f'<div class="data-state">{data_note}<br>本机离线分析</div>', unsafe_allow_html=True)
st.markdown('<div class="top-rule"></div>', unsafe_allow_html=True)

base_path = svg_curve(base_fp["grid"], base_fp["fingerprint"])
current_path = svg_curve(current_fp["grid"], current_fp["fingerprint"])
status_title = "检测到持续响应偏移" if is_shift else "响应处于基线范围"
status_action = "建议优先进行专业工程检查" if is_shift else "继续纳入常态化采集"
hero_svg = f"""
<svg viewBox="0 0 690 330" preserveAspectRatio="none" role="img" aria-label="历史基线与当前桥梁动态指纹">
  <g stroke="#27343f" stroke-width="1"><path d="M30 70 H660"/><path d="M30 135 H660"/><path d="M30 200 H660"/><path d="M30 265 H660"/></g>
  <path d="{base_path}" fill="none" stroke="#93a59c" stroke-width="2.2" vector-effect="non-scaling-stroke"/>
  <path d="{current_path}" fill="none" stroke="#e16a61" stroke-width="2.2" vector-effect="non-scaling-stroke"/>
  <path d="M30 295 H660" stroke="#53606a" stroke-width="1"/>
  <g fill="#7f8c90" font-family="PingFang SC" font-size="10"><text x="30" y="316">3 Hz</text><text x="328" y="316">9 Hz</text><text x="635" y="316">15 Hz</text></g>
</svg>
"""
st.markdown(
    f'<div class="hero"><div class="hero-copy"><div><div class="hero-kicker">贵州山地桥梁移动感知</div>'
    f'<div class="hero-title">桥的频率，<br>留在车流里。</div>'
    f'<div class="hero-desc">单辆车带来噪声。多辆车反复穿越后，共同的桥梁动态响应被保留下来，形成可持续比较的桥梁脉冲。</div></div>'
    f'<div class="hero-status"><div><div class="status-label">本次筛查</div><div class="status-text">{status_title}</div></div>'
    f'<div class="status-shift">{shift_hz:+.2f}<span>Hz</span></div></div></div>'
    f'<div class="hero-chart"><div class="chart-overline">桥梁动态指纹 · 同桥纵向比较</div>{hero_svg}'
    f'<div class="hero-legend"><span><i class="legend-line" style="background:#93a59c"></i>历史基线 {base_fp["dominant_frequency"]:.2f} Hz</span>'
    f'<span><i class="legend-line" style="background:#e16a61"></i>当前状态 {current_fp["dominant_frequency"]:.2f} Hz</span></div></div></div>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<div class="facts"><div class="fact"><div class="fact-label">融合样本</div><div class="fact-value">{count}<span>次穿越</span></div></div>'
    f'<div class="fact"><div class="fact-label">融合稳定度</div><div class="fact-value">{stability:.0f}<span>%</span></div></div>'
    f'<div class="fact"><div class="fact-label">指纹差异</div><div class="fact-value">{divergence:.3f}</div></div>'
    f'<div class="fact"><div class="fact-label">基线 95% 阈值</div><div class="fact-value">{threshold:.3f}</div></div></div>',
    unsafe_allow_html=True,
)

statement("01", "一辆车，是噪声。\n一百辆车，是桥。", "悬架、路面冲击与随机噪声共同主导单次穿越。只有来自不同车辆的重复观测，才有资格形成桥梁状态证据。")
raw_col, fusion_col = st.columns([.88, 1.32], gap="large")
with raw_col:
    st.markdown('<div class="chart-block"><div class="chart-name">单次穿越 · 原始加速度</div>', unsafe_allow_html=True)
    raw_fig = go.Figure(go.Scatter(x=baseline[0]["t"], y=baseline[0]["acc"], mode="lines", line=dict(color="#65796f", width=.85), name="原始信号"))
    raw_fig.update_layout(**chart_layout(305), xaxis_title="时间 / 秒", yaxis_title="加速度 / 相对值")
    show_chart(raw_fig)
    st.markdown('</div>', unsafe_allow_html=True)
with fusion_col:
    st.markdown('<div class="chart-block"><div class="chart-name">多次穿越 · 动态指纹收敛</div>', unsafe_allow_html=True)
    fusion_fig = go.Figure()
    sample_counts = [1, 5, 10, 20, 100]
    palette = ["#c6c9c4", "#acb5ae", "#919f96", "#778a80", "#536c60"]
    for idx, sample_n in enumerate(sample_counts):
        fused = fuse_crossings(baseline_all[:sample_n])
        fusion_fig.add_trace(go.Scatter(x=fused["grid"], y=fused["fingerprint"], mode="lines", line=dict(color=palette[idx], width=1 + idx * .25), name=f"{sample_n} 次"))
    fusion_fig.add_vline(x=base_fp["dominant_frequency"], line_dash="dot", line_color="#536c60", annotation_text=f"桥梁脉冲 {base_fp['dominant_frequency']:.2f} Hz", annotation_font_color="#536c60", annotation_position="top right")
    fusion_fig.update_layout(**chart_layout(305), xaxis_title="频率 / Hz", yaxis_title="归一化共识密度")
    show_chart(fusion_fig)
    st.markdown('</div>', unsafe_allow_html=True)

steps = []
for sample_n in [1, 5, 10, 20, 100]:
    conv_item = min(conv, key=lambda item: abs(item["n"] - sample_n))
    pct = 5 if sample_n == 1 else max(22, min(100, conv_item["stability"] * 100))
    note = "证据不足" if sample_n == 1 else ("共识形成" if sample_n < 20 else "脉冲稳定")
    steps.append(f'<div class="fusion-step"><div class="step-n">{sample_n}<span>次</span></div><div class="step-bar"><i style="width:{pct:.0f}%"></i></div><div class="step-note">{note}</div></div>')
st.markdown('<div class="fusion-steps">' + "".join(steps) + '</div>', unsafe_allow_html=True)

statement("02", "不同车辆在变，\n桥的共识不变。", "车辆自身频率分散在低频区间；车群共同指向的 7.8 Hz 响应持续存在，说明融合结果并非车辆自身频率。")
vehicle_col, conv_col = st.columns(2, gap="large")
with vehicle_col:
    st.markdown('<div class="chart-block"><div class="chart-name">车辆自身频率分布</div>', unsafe_allow_html=True)
    vehicle_freqs = [c.get("vehicle_freq", np.nan) for c in baseline_all[:100]]
    vehicle_fig = go.Figure(go.Scatter(x=list(range(1, len(vehicle_freqs) + 1)), y=vehicle_freqs, mode="markers", marker=dict(color="#b18a58", size=5, opacity=.75), name="车辆频率"))
    vehicle_fig.add_hline(y=base_fp["dominant_frequency"], line_dash="dot", line_color="#65796f", annotation_text="桥梁共识", annotation_font_color="#65796f")
    vehicle_fig.update_layout(**chart_layout(290), xaxis_title="车辆编号", yaxis_title="频率 / Hz")
    show_chart(vehicle_fig)
    st.markdown('</div>', unsafe_allow_html=True)
with conv_col:
    st.markdown('<div class="chart-block"><div class="chart-name">桥梁脉冲收敛轨迹</div>', unsafe_allow_html=True)
    conv_fig = go.Figure(go.Scatter(x=[x["n"] for x in conv], y=[x["dominant_frequency"] for x in conv], mode="lines+markers", line=dict(color="#65796f", width=1.8), marker=dict(size=6, color="#f5f3ee", line=dict(color="#65796f", width=1.4)), name="桥梁脉冲"))
    conv_fig.add_hline(y=baseline_f, line_dash="dot", line_color="#b7b3aa")
    conv_fig.update_layout(**chart_layout(290), xaxis_title="融合样本 / 次", yaxis_title="频率 / Hz")
    show_chart(conv_fig)
    st.markdown('</div>', unsafe_allow_html=True)

statement("03", "异常不是猜出来的。\n只和桥自己的历史比。", "历史穿越数据反复拆分，形成桥梁自身的自然波动分布。当前指纹只有越过 95% 阈值，才触发专业复核建议。")
hist_col, conclusion_col = st.columns([1.35, .72], gap="large")
with hist_col:
    st.markdown('<div class="chart-block"><div class="chart-name">基线自然波动与当前差异</div>', unsafe_allow_html=True)
    hist_fig = go.Figure(go.Histogram(x=boot["values"], nbinsx=14, marker=dict(color="#84948b", line=dict(color="#65796f", width=.5)), opacity=.88, name="自然波动"))
    hist_fig.add_vline(x=threshold, line_dash="dot", line_color="#b18a58", annotation_text=f"95% 阈值 {threshold:.3f}", annotation_font_color="#8b693d", annotation_position="top left")
    hist_fig.add_vline(x=divergence, line_color="#c64d43", line_width=2, annotation_text=f"当前差异 {divergence:.3f}", annotation_font_color="#a93d35", annotation_position="top right")
    hist_fig.update_layout(**chart_layout(310), xaxis_title="指纹差异", yaxis_title="出现次数", bargap=.12)
    show_chart(hist_fig)
    st.markdown('</div>', unsafe_allow_html=True)
with conclusion_col:
    conclusion_title = "超过自然波动范围" if is_shift else "处于自然波动范围"
    st.markdown(
        f'<div class="conclusion"><div class="conclusion-label">筛查结论</div><div class="conclusion-title">{conclusion_title}</div>'
        f'<div class="conclusion-row"><span>历史基线</span><b>{base_fp["dominant_frequency"]:.2f} Hz</b></div>'
        f'<div class="conclusion-row"><span>当前状态</span><b>{current_fp["dominant_frequency"]:.2f} Hz</b></div>'
        f'<div class="conclusion-row"><span>指纹差异 / 阈值</span><b>{divergence:.3f} / {threshold:.3f}</b></div>'
        f'<div class="conclusion-action">{status_action}</div></div>', unsafe_allow_html=True,
    )

st.markdown(
    '<div class="boundary">方法边界：黔脉只筛查桥梁相对自身历史基线的持续动态响应变化，不进行损伤类型识别、裂缝诊断或安全等级判断，也不能替代专业桥梁检测。当前页面使用模拟演示数据。</div>',
    unsafe_allow_html=True,
)
