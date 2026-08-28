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
        --paper:#f0ede4; --paper-deep:#e6e1d5; --ink:#202624; --muted:#737a74;
        --rule:#c8c3b7; --indigo:#142438; --indigo-2:#1b3048; --silver:#b9c1c2;
        --qian-red:#a13e35; --moss:#678176; --ochre:#b58d56;
    }
    html, body, [class*="css"] { font-family:"PingFang SC","Microsoft YaHei",sans-serif; }
    .stApp { background:var(--paper); color:var(--ink); }
    [data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer { display:none !important; }
    .block-container { max-width:1240px; padding:1.55rem 2rem 5rem; }
    div[data-testid="stPlotlyChart"] { margin:0; }
    div[data-testid="stPopover"] button {
        border:1px solid var(--rule); background:transparent; color:#505854; border-radius:0;
        min-height:34px; padding:0 13px; font-size:.72rem; box-shadow:none;
    }
    div[data-testid="stPopover"] button:hover { border-color:var(--indigo); color:var(--indigo); }
    [data-baseweb="popover"] { background:#f7f4ed !important; border:1px solid var(--rule) !important; color:var(--ink) !important; }
    [data-baseweb="input"], [data-baseweb="base-input"], input { background:#e7e2d7 !important; color:var(--ink) !important; }
    [data-testid="stFileUploaderDropzone"] { background:#e7e2d7; border-color:var(--rule); }
    .stButton button[kind="primary"] { background:var(--qian-red); color:white; border:0; border-radius:0; font-weight:650; }
    .stButton button[kind="primary"] p { color:white !important; }

    .mast { display:grid; grid-template-columns:auto 1fr auto; align-items:center; gap:18px; padding:2px 0 13px; border-bottom:1px solid var(--rule); }
    .seal { width:34px; height:34px; background:var(--qian-red); color:#f4efe4; display:grid; place-items:center; font-family:"Songti SC","STSong",serif; font-size:1rem; }
    .brand-line { display:flex; align-items:baseline; gap:10px; }
    .brand-cn { font-family:"Songti SC","STSong",serif; font-size:1.24rem; font-weight:700; letter-spacing:.15em; }
    .brand-en { font-family:Georgia,serif; color:#626b66; font-size:.6rem; letter-spacing:.2em; }
    .mast-meta { color:#777e78; font-size:.66rem; margin-top:3px; }
    .run-meta { text-align:right; color:#737a75; font-size:.65rem; line-height:1.7; }

    .bridge-plate { background:var(--indigo); color:#edf0eb; margin-top:22px; display:grid; grid-template-columns:220px 1fr 220px; min-height:340px; overflow:hidden; }
    .bridge-file { padding:26px 24px; border-right:1px solid rgba(198,207,207,.18); display:flex; flex-direction:column; justify-content:space-between; }
    .file-no { color:#91a1a6; font-family:Georgia,serif; font-size:.65rem; letter-spacing:.13em; }
    .file-title { font-family:"Songti SC","STSong",serif; font-size:1.42rem; line-height:1.45; margin-top:13px; }
    .file-sub { color:#9da9aa; font-size:.67rem; line-height:1.8; margin-top:10px; }
    .file-table { border-top:1px solid rgba(198,207,207,.2); margin-top:28px; }
    .file-row { display:flex; justify-content:space-between; border-bottom:1px solid rgba(198,207,207,.14); padding:8px 0; font-size:.63rem; color:#98a4a5; }
    .file-row b { color:#e0e5e1; font-weight:500; }
    .bridge-art { position:relative; min-height:340px; }
    .bridge-art svg { width:100%; height:100%; display:block; }
    .bridge-result { padding:26px 24px; border-left:1px solid rgba(198,207,207,.18); display:flex; flex-direction:column; justify-content:center; }
    .result-kicker { color:#9aa6a7; font-size:.62rem; letter-spacing:.08em; }
    .result-title { font-family:"Songti SC","STSong",serif; font-size:1.32rem; line-height:1.4; margin:12px 0 20px; }
    .result-shift { color:#e0786f; font-family:Georgia,serif; font-size:2.5rem; line-height:1; }
    .result-shift span { color:#9eabad; font-family:"PingFang SC",sans-serif; font-size:.65rem; margin-left:4px; }
    .result-rule { height:1px; background:rgba(198,207,207,.2); margin:20px 0 15px; }
    .result-note { color:#aeb8b8; font-size:.66rem; line-height:1.85; }
    .result-action { border-left:3px solid #d36b62; padding-left:10px; color:#edf0eb; font-size:.68rem; line-height:1.6; margin-top:18px; }

    .crowd-ribbon { display:grid; grid-template-columns:145px repeat(5,1fr); border:1px solid var(--rule); border-top:0; min-height:124px; }
    .ribbon-intro { padding:18px 17px; background:var(--paper-deep); border-right:1px solid var(--rule); }
    .ribbon-title { font-family:"Songti SC","STSong",serif; font-weight:700; font-size:.88rem; line-height:1.45; }
    .ribbon-copy { color:#7a817c; font-size:.61rem; line-height:1.55; margin-top:8px; }
    .pulse-stage { position:relative; padding:13px 12px 9px; border-right:1px solid var(--rule); }
    .pulse-stage:last-child { border-right:0; }
    .pulse-stage svg { width:100%; height:55px; display:block; }
    .stage-top { display:flex; justify-content:space-between; color:#727a75; font-size:.59rem; }
    .stage-n { color:var(--ink); font-family:Georgia,serif; font-size:.84rem; }
    .stage-note { color:#8b918d; font-size:.56rem; margin-top:3px; }

    .brief-head { display:grid; grid-template-columns:75px 250px 1fr; align-items:end; gap:16px; margin:48px 0 14px; padding-bottom:11px; border-bottom:1px solid var(--rule); }
    .brief-no { color:var(--qian-red); font-family:Georgia,serif; font-size:.73rem; }
    .brief-title { font-family:"Songti SC","STSong",serif; font-size:1.13rem; font-weight:700; }
    .brief-copy { color:#767d78; font-size:.68rem; line-height:1.7; text-align:right; }
    .chart-caption { color:#5f6762; font-size:.66rem; font-weight:600; margin:2px 0 -8px; }
    .side-note { background:var(--paper-deep); border-top:3px solid var(--indigo); padding:20px 21px; min-height:300px; }
    .side-label { color:#747c77; font-size:.61rem; letter-spacing:.06em; }
    .side-title { font-family:"Songti SC","STSong",serif; font-size:1.13rem; font-weight:700; margin:13px 0 18px; line-height:1.45; }
    .side-row { display:flex; justify-content:space-between; align-items:baseline; padding:9px 0; border-top:1px solid var(--rule); color:#747c77; font-size:.65rem; }
    .side-row strong { color:var(--ink); font-family:Georgia,serif; font-size:.86rem; font-weight:500; }
    .side-action { color:var(--qian-red); font-size:.68rem; line-height:1.65; padding-left:10px; border-left:3px solid var(--qian-red); margin-top:18px; }
    .method-boundary { margin-top:48px; padding-top:13px; border-top:1px solid var(--rule); color:#777e78; font-size:.64rem; line-height:1.8; }
    @media(max-width:900px) {
        .block-container { padding:1rem; }
        .bridge-plate { grid-template-columns:1fr; }
        .bridge-file, .bridge-result { border:0; }
        .bridge-art { min-height:260px; }
        .crowd-ribbon { grid-template-columns:1fr; }
        .pulse-stage, .ribbon-intro { border-right:0; border-bottom:1px solid var(--rule); }
        .brief-head { grid-template-columns:45px 1fr; }
        .brief-copy { display:none; }
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


def chart_layout(height=300, show_y=True):
    return dict(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family='"PingFang SC",sans-serif', color="#717873", size=10),
        margin=dict(l=44 if show_y else 16, r=16, t=30, b=40),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.1, x=0, font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showgrid=False, zeroline=False, linecolor="#bbb7ac", tickcolor="#bbb7ac"),
        yaxis=dict(showgrid=True, showticklabels=show_y, gridcolor="#d9d5ca", zeroline=False, linecolor="#bbb7ac"),
    )


def show_chart(fig):
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})


def brief_head(number, title, copy):
    st.markdown(
        f'<div class="brief-head"><div class="brief-no">{number}</div><div class="brief-title">{title}</div>'
        f'<div class="brief-copy">{copy}</div></div>', unsafe_allow_html=True,
    )


def svg_path(values, width=140, height=55, pad=5):
    values = np.asarray(values, dtype=float)
    if not len(values) or np.max(values) <= 0:
        return ""
    xs = np.linspace(pad, width - pad, len(values))
    ys = height - pad - (values / np.max(values)) * (height - 2 * pad)
    return "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))


brand_col, state_col, settings_col = st.columns([7, 1.45, 1.05], vertical_alignment="center")
with brand_col:
    st.markdown(
        '<div class="mast"><div class="seal">黔</div><div><div class="brand-line">'
        '<span class="brand-cn">黔脉</span><span class="brand-en">QIANPULSE</span></div>'
        '<div class="mast-meta">贵州山地桥梁移动感知 · 演示档案 QP-01</div></div></div>',
        unsafe_allow_html=True,
    )
with settings_col:
    with st.popover("演示设置"):
        mode = st.radio("数据源", ["模拟演示", "Sensor Logger"], horizontal=True)
        baseline_f = st.slider("基线频率 / Hz", 5.0, 10.0, 7.8, 0.1)
        current_f = st.slider("当前频率 / Hz", 5.0, 10.0, 7.2, 0.1)
        n = st.slider("融合样本 / 次", 1, 50, 30, 1)
        seed = st.number_input("随机种子", 0, 9999, 42)
        replay = st.button("运行演示流程", type="primary", use_container_width=True)
        upload = st.file_uploader("导入 CSV / ZIP", type=["csv", "zip"]) if mode == "Sensor Logger" else None

if replay:
    progress = st.progress(0, text="读取车辆穿越信号")
    for pct, label in [(20, "读取车辆穿越信号"), (48, "聚合车群频谱"), (74, "建立桥梁自身基线"), (100, "完成响应偏移筛查")]:
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
sample_counts = [1, 5, 10, 20, 50]
conv = convergence_curve(baseline_all, counts=[1, 5, 10, 20, 30, 50], seed=int(seed) + 11)
stability = min(conv, key=lambda item: abs(item["n"] - count))["stability"] * 100

with state_col:
    st.markdown(f'<div class="run-meta">{data_note}<br>本机离线分析</div>', unsafe_allow_html=True)

bridge_svg = """
<svg viewBox="0 0 660 340" preserveAspectRatio="none" aria-label="贵州山地桥梁移动观测示意">
  <g fill="none" stroke="#294058" stroke-width="1" opacity=".72">
    <path d="M0 72 C100 30 155 52 230 30 S400 14 660 58"/><path d="M0 91 C100 49 158 73 236 48 S410 32 660 78"/>
    <path d="M0 111 C95 70 164 92 241 68 S420 53 660 99"/><path d="M0 132 C100 91 168 114 248 89 S430 74 660 120"/>
  </g>
  <path d="M0 253 C90 214 128 190 188 230 C230 258 258 280 315 249 C372 218 408 197 463 232 C520 268 572 226 660 206 L660 340 L0 340Z" fill="#0d1c2d"/>
  <path d="M0 277 C78 247 131 222 188 255 C242 286 272 303 326 275 C391 241 420 225 476 256 C531 287 582 250 660 231" fill="none" stroke="#31475b" stroke-width="1"/>
  <g stroke="#b8c3c4" fill="none">
    <path d="M65 155 L595 155" stroke-width="3"/><path d="M97 151 L563 151" opacity=".45"/>
    <path d="M170 155 L170 250 M180 155 L180 254 M475 155 L475 249 M485 155 L485 245" stroke-width="2"/>
    <path d="M170 250 L180 254 M475 249 L485 245" opacity=".55"/>
  </g>
  <g fill="#d4dad7">
    <rect x="118" y="143" width="18" height="7"/><circle cx="122" cy="151" r="2"/><circle cx="133" cy="151" r="2"/>
    <rect x="267" y="143" width="22" height="7"/><circle cx="272" cy="151" r="2"/><circle cx="285" cy="151" r="2"/>
    <rect x="397" y="143" width="19" height="7"/><circle cx="401" cy="151" r="2"/><circle cx="413" cy="151" r="2"/>
    <rect x="526" y="143" width="20" height="7"/><circle cx="530" cy="151" r="2"/><circle cx="542" cy="151" r="2"/>
  </g>
  <g stroke="#d46a61" fill="none" stroke-width="2">
    <path d="M318 151 L318 126 L324 126 L330 104 L337 137 L343 119 L349 151"/>
  </g>
  <g fill="#82949a" font-family="PingFang SC" font-size="10"><text x="65" y="181">车辆穿越</text><text x="293" y="92">共享桥梁频率</text><text x="515" y="181">车群采样</text></g>
  <g stroke="#536a7d" stroke-width="1"><path d="M128 158 L128 172"/><path d="M337 146 L337 96"/><path d="M536 158 L536 172"/></g>
</svg>
"""

result_title = "响应偏移，建议复核" if is_shift else "响应处于基线范围"
result_action = "建议优先进行专业工程检查" if is_shift else "继续纳入常态化采集"
st.markdown(
    f'<div class="bridge-plate"><div class="bridge-file"><div><div class="file-no">BRIDGE FILE / QP-01</div>'
    f'<div class="file-title">贵州山地桥梁<br>移动观测场景</div><div class="file-sub">模拟演示场景，不对应任何真实桥梁。<br>采样率 100 Hz · 单次 8 秒。</div></div>'
    f'<div class="file-table"><div class="file-row"><span>数据批次</span><b>0828-A</b></div><div class="file-row"><span>穿越样本</span><b>{count} 次</b></div>'
    f'<div class="file-row"><span>分析频带</span><b>3–15 Hz</b></div></div></div>'
    f'<div class="bridge-art">{bridge_svg}</div>'
    f'<div class="bridge-result"><div class="result-kicker">本次筛查</div><div class="result-title">{result_title}</div>'
    f'<div class="result-shift">{shift_hz:+.2f}<span>Hz</span></div><div class="result-rule"></div>'
    f'<div class="result-note">基线 {base_fp["dominant_frequency"]:.2f} Hz<br>当前 {current_fp["dominant_frequency"]:.2f} Hz<br>指纹差异 {divergence:.3f}</div>'
    f'<div class="result-action">{result_action}</div></div></div>',
    unsafe_allow_html=True,
)

stages = []
for sample_n in sample_counts:
    fused = fuse_crossings(baseline_all[:sample_n])
    path = svg_path(fused["fingerprint"])
    note = "噪声主导" if sample_n == 1 else ("共识形成" if sample_n < 20 else "脉冲稳定")
    stages.append(
        f'<div class="pulse-stage"><div class="stage-top"><span><span class="stage-n">{sample_n}</span> 次</span><span>{fused["dominant_frequency"]:.2f} Hz</span></div>'
        f'<svg viewBox="0 0 140 55" preserveAspectRatio="none"><path d="M5 50 L135 50" stroke="#c7c2b7"/>'
        f'<path d="{path}" fill="none" stroke="#657f74" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>'
        f'<div class="stage-note">{note}</div></div>'
    )
st.markdown(
    '<div class="crowd-ribbon"><div class="ribbon-intro"><div class="ribbon-title">车流如何变成<br>桥梁脉冲</div>'
    '<div class="ribbon-copy">同一座桥<br>不同车辆<br>共同频率逐步显现</div></div>' + "".join(stages) + '</div>',
    unsafe_allow_html=True,
)

brief_head("01", "先看单辆车：证据很脏", "悬架、路面冲击与随机噪声共同主导单次观测；单辆车不用于桥梁状态判断。")
raw_col, psd_col = st.columns([1.18, 1], gap="large")
with raw_col:
    st.markdown('<div class="chart-caption">原始垂向加速度</div>', unsafe_allow_html=True)
    raw_fig = go.Figure(go.Scatter(x=baseline[0]["t"], y=baseline[0]["acc"], mode="lines", line=dict(color="#657f74", width=.9), name="原始信号"))
    raw_fig.update_layout(**chart_layout(275), xaxis_title="时间 / 秒", yaxis_title="加速度 / 相对值")
    show_chart(raw_fig)
with psd_col:
    st.markdown('<div class="chart-caption">单次穿越功率谱</div>', unsafe_allow_html=True)
    single = crossing_to_peaks(baseline[0])
    psd_fig = go.Figure(go.Scatter(x=single["f"], y=single["pxx"], mode="lines", line=dict(color="#b58d56", width=1.25), fill="tozeroy", fillcolor="rgba(181,141,86,.09)", name="功率谱"))
    psd_fig.update_layout(**chart_layout(275), xaxis_title="频率 / Hz", yaxis_title="功率谱密度")
    show_chart(psd_fig)

brief_head("02", "再看车群：桥梁频率留下来", "车辆自身频率持续变化；只有同一座桥共享的结构频率会在融合中稳定增强。")
fusion_col, vehicle_col = st.columns([1.45, .75], gap="large")
with fusion_col:
    st.markdown('<div class="chart-caption">多次穿越融合指纹</div>', unsafe_allow_html=True)
    fusion_fig = go.Figure()
    palette = ["#c1c4be", "#aeb5ad", "#929f96", "#788b7f", "#596f61"]
    for idx, sample_n in enumerate(sample_counts):
        fused = fuse_crossings(baseline_all[:sample_n])
        fusion_fig.add_trace(go.Scatter(x=fused["grid"], y=fused["fingerprint"], mode="lines", line=dict(color=palette[idx], width=1 + idx * .3), name=f"{sample_n} 次"))
    fusion_fig.add_vline(x=base_fp["dominant_frequency"], line_dash="dot", line_color="#596f61", annotation_text=f"桥梁脉冲 {base_fp['dominant_frequency']:.2f} Hz", annotation_font_color="#596f61", annotation_position="top right")
    fusion_fig.update_layout(**chart_layout(330), xaxis_title="频率 / Hz", yaxis_title="归一化共识密度")
    show_chart(fusion_fig)
with vehicle_col:
    st.markdown('<div class="chart-caption">车辆自身频率</div>', unsafe_allow_html=True)
    vehicle_freqs = [c.get("vehicle_freq", np.nan) for c in baseline_all[:50]]
    vehicle_fig = go.Figure(go.Scatter(x=list(range(1, len(vehicle_freqs) + 1)), y=vehicle_freqs, mode="markers", marker=dict(color="#b58d56", size=4.5, opacity=.72), name="车辆频率"))
    vehicle_fig.add_hline(y=base_fp["dominant_frequency"], line_dash="dot", line_color="#657f74", annotation_text="桥梁共识", annotation_font_color="#657f74")
    vehicle_fig.update_layout(**chart_layout(330), xaxis_title="车辆编号", yaxis_title="频率 / Hz")
    show_chart(vehicle_fig)

brief_head("03", "最后与桥梁自身历史比较", "从历史基线内部拆分估计自然波动；当前差异越过 95% 阈值后，才给出专业复核建议。")
hist_col, side_col = st.columns([1.35, .72], gap="large")
with hist_col:
    st.markdown('<div class="chart-caption">基线自然波动与当前差异</div>', unsafe_allow_html=True)
    hist_fig = go.Figure(go.Histogram(x=boot["values"], nbinsx=14, marker=dict(color="#829287", line=dict(color="#657f74", width=.5)), opacity=.88, name="基线自然波动"))
    hist_fig.add_vline(x=threshold, line_dash="dot", line_color="#b58d56", annotation_text=f"95% 阈值 {threshold:.3f}", annotation_font_color="#8d693b", annotation_position="top left")
    hist_fig.add_vline(x=divergence, line_color="#a13e35", line_width=2, annotation_text=f"当前差异 {divergence:.3f}", annotation_font_color="#a13e35", annotation_position="top right")
    hist_fig.update_layout(**chart_layout(310), xaxis_title="指纹差异", yaxis_title="出现次数", bargap=.12)
    show_chart(hist_fig)
with side_col:
    side_title = "超过自然波动范围" if is_shift else "处于自然波动范围"
    st.markdown(
        f'<div class="side-note"><div class="side-label">筛查记录 / 0828-A</div><div class="side-title">{side_title}</div>'
        f'<div class="side-row"><span>历史基线</span><strong>{base_fp["dominant_frequency"]:.2f} Hz</strong></div>'
        f'<div class="side-row"><span>当前状态</span><strong>{current_fp["dominant_frequency"]:.2f} Hz</strong></div>'
        f'<div class="side-row"><span>频率变化</span><strong>{shift_hz:+.2f} Hz</strong></div>'
        f'<div class="side-row"><span>指纹差异 / 阈值</span><strong>{divergence:.3f} / {threshold:.3f}</strong></div>'
        f'<div class="side-action">{result_action}</div></div>', unsafe_allow_html=True,
    )

st.markdown(
    '<div class="method-boundary">方法边界：黔脉只筛查桥梁相对自身历史基线的持续动态响应变化，不进行损伤类型识别、裂缝诊断或安全等级判断，也不能替代专业桥梁检测。页面所示为模拟演示数据。</div>',
    unsafe_allow_html=True,
)
