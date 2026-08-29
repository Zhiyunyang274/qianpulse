from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from qianpulse.io_sensorlogger import discover_physical_runs
from qianpulse.physical_validation import analyse_physical_experiment
from qianpulse.ui import inject_styles, topbar


st.set_page_config(page_title="黔脉 · 真实实验验证", page_icon="📡", layout="wide")
inject_styles(sidebar=True)  # 本页使用侧边栏控件（垂向方法切换）
topbar("evidence")

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data" / "physical_validation"
BASE = "#6fd8c5"
PERT = "#e07a62"
GRID = "#182a22"

st.markdown(
    """
    <style>
    .eyebrow { color:#6fd8c5; font-size:.67rem; font-weight:800; letter-spacing:.2em; margin-bottom:13px; }
    .hero { font-family:"Songti SC","Noto Serif SC","STSong",Georgia,serif; font-size:2.45rem; line-height:1.15; font-weight:700; color:#e9f1ec; }
    .sub { color:#84988e; font-size:.88rem; margin:13px 0 24px; }
    .real-badge { display:inline-block; border:1px solid rgba(111,216,197,.35); color:#6fd8c5; background:rgba(111,216,197,.08); border-radius:99px; padding:7px 12px; font-size:.65rem; font-weight:800; letter-spacing:.13em; }
    .rule { height:1px; background:linear-gradient(90deg,#1f342b,transparent); margin:24px 0 36px; }
    .section { color:#6fd8c5; font-size:.63rem; font-weight:800; letter-spacing:.17em; margin:42px 0 8px; }
    .section-title { font-size:1.27rem; font-weight:680; margin-bottom:8px; color:#e9f1ec; }
    .section-copy { color:#84988e; font-size:.76rem; line-height:1.7; margin-bottom:18px; }
    .setup { display:grid; grid-template-columns:repeat(6,1fr); border-top:1px solid #1f342b; border-bottom:1px solid #1f342b; }
    .setup div { padding:17px 12px; border-right:1px solid #1f342b; color:#84988e; font-size:.68rem; }
    .setup div:last-child { border:0; } .setup b { display:block; color:#e9f1ec; font-size:.82rem; margin-bottom:5px; }
    .pulse-row { display:grid; grid-template-columns:1fr auto 1fr auto 1fr; gap:24px; align-items:center; border:1px solid #1f342b; background:#101d17; padding:24px 28px; margin:18px 0; border-radius:14px; }
    .pulse-label { color:#84988e; font-size:.66rem; letter-spacing:.09em; } .pulse-value { font-size:2rem; font-weight:600; margin-top:5px; color:#e9f1ec; font-family:Georgia,serif; font-variant-numeric:tabular-nums; }
    .arrow { color:#5f7469; font-size:1.5rem; } .shift { color:#e07a62; }
    .boundary { border-left:2px solid #6fd8c5; background:rgba(111,216,197,.05); padding:17px 20px; margin-top:34px; color:#b9c8c0; font-size:.76rem; line-height:1.8; border-radius:0 10px 10px 0; }
    .notes { color:#5f7469; border-top:1px solid #1f342b; margin-top:34px; padding-top:18px; font-size:.69rem; line-height:1.8; }
    /* 原生 dataframe / 侧边栏深色化 */
    [data-testid="stDataFrame"] { border:1px solid #1f342b; border-radius:6px; overflow:hidden; }
    [data-testid="stDataFrame"] * { font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif; }
    .stApp [data-testid="stSidebar"] { background:#0a1310; border-right:1px solid #1c3129; }
    .stApp [data-testid="stSidebar"] * { color:#b9c8c0; }
    .sb-kicker { font-size:11.5px; letter-spacing:.2em; color:#7f948a; font-weight:600; margin:8px 0 2px; }
    @media(max-width:900px) { .setup { grid-template-columns:repeat(2,1fr); } .pulse-row { grid-template-columns:1fr; } .arrow { transform:rotate(90deg); } }
    </style>
    """,
    unsafe_allow_html=True,
)


def plot_layout(height=330):
    return dict(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=48, r=20, t=38, b=45), hovermode="x unified",
        font=dict(family='"PingFang SC",sans-serif', color="#8ba69a", size=10),
        legend=dict(orientation="h", y=1.12, x=0, bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showgrid=False, linecolor=GRID, title="频率 / Hz"),
        yaxis=dict(showgrid=True, gridcolor=GRID, zeroline=False, title="归一化 PSD"),
    )


def show(fig):
    st.plotly_chart(fig, config={"displayModeBar": False})


def chart_layout(height=330, **overrides):
    configured = plot_layout(height)
    configured.update(overrides)
    return configured


def section(index, title, copy):
    st.markdown(
        f'<div class="section">{index}</div><div class="section-title">{title}</div>'
        f'<div class="section-copy">{copy}</div>', unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def _analyse(root_str, vertical_method):
    """真实 ZIP → 分析结果；同参数下缓存，侧边栏切换才重算。"""
    discovered = discover_physical_runs(Path(root_str), vertical_method=vertical_method)
    return analyse_physical_experiment(discovered)


with st.sidebar:
    st.markdown('<div class="sb-kicker">本页控制</div>', unsafe_allow_html=True)
    method_choice = st.radio(
        "垂向加速度方法", ["重力方向投影", "设备 Z 轴"],
        help="优先使用重力方向投影；设备 Z 轴作为可切换的回退方法。",
    )
    st.caption(f"数据自动发现目录\n\n`{DATA_ROOT}`")

vertical_method = "gravity" if method_choice == "重力方向投影" else "z"
try:
    result = _analyse(str(DATA_ROOT), vertical_method)
except (ValueError, OSError) as exc:
    st.error(f"无法分析真实实验数据：{exc}")
    st.info("请将 Sensor Logger ZIP 分别放入 data/physical_validation/baseline 和 perturbed。")
    st.stop()

baseline = result["baseline"]
perturbed = result["perturbed"]
base_group = result["baseline_group"]
pert_group = result["perturbed_group"]

st.markdown('<div class="eyebrow">真实实验 / 物理验证</div>', unsafe_allow_html=True)
st.markdown('<div class="hero">真实实验验证</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub">来自受控缩尺结构实验的真实 iPhone IMU 数据</div>'
    '<span class="real-badge">真实 iPhone 传感器数据</span><div class="rule"></div>',
    unsafe_allow_html=True,
)

section("01 / 实验设置", "受控缩尺结构实验",
        "手机始终位于桥面近似相同的位置，每次通过敲击桥面产生激励。扰动状态使用一整瓶密封水作为受控附加质量，放置在手机旁边但不与手机接触。")
st.markdown(
    f'<div class="setup"><div><b>同一结构</b>缩尺桥梁</div><div><b>同一手机位置</b>桥面固定 iPhone</div>'
    f'<div><b>同一分析管线</b>原始 ZIP → Welch PSD</div><div><b>{len(baseline)} 次实验</b>基线状态</div>'
    f'<div><b>{len(perturbed)} 次实验</b>扰动状态</div><div><b>约 100 Hz IMU</b>逐次实测采样率</div></div>',
    unsafe_allow_html=True,
)
st.caption("扰动条件：使用一整瓶密封水进行受控附加质量扰动。这是结构动力条件的受控改变，不是损伤模拟。")

section("02 / 原始实验数据", f"{len(baseline) + len(perturbed)} 条原始记录 · 本机实时分析",
        "以下信息由 Accelerometer.csv 时间戳计算。采样抖动表示采样间隔相对其中位数的均方根偏差。")
rows = []
for run in baseline + perturbed:
    rows.append({
        "文件": run["source"], "状态": "基线" if run["state"] == "baseline" else "扰动",
        "时长（秒）": round(run["duration"], 3), "样本数": run["sample_count"],
        "实际采样率（Hz）": round(run["fs"], 2), "采样抖动 RMS（ms）": round(run["sampling_jitter_ms"], 4),
        "垂向方法": "重力方向投影" if run["vertical_method"] == "Gravity projected" else "设备 Z 轴",
    })
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

section("03 / 单次功率谱", "逐次归一化频谱脉搏",
        "全部记录采用相同的 5–25 Hz 频率范围与信号处理参数；每条曲线均由对应的原始 ZIP 重新计算。")
left, right = st.columns(2, gap="large")
for column, runs, title, color, prefix in [
    (left, baseline, "基线状态", BASE, "B"), (right, perturbed, "扰动状态", PERT, "P")
]:
    with column:
        fig = go.Figure()
        for index, run in enumerate(runs, 1):
            fig.add_trace(go.Scatter(
                x=result["grid"], y=run["fingerprint"], mode="lines",
                line=dict(color=color, width=1.5), opacity=.45 + .5 * index / max(len(runs), 1),
                name=f"{prefix}{index} · {run['dominant_frequency']:.2f} Hz",
            ))
        fig.update_layout(**plot_layout(), title=dict(text=title, font=dict(size=13)))
        show(fig)

section("04 / 融合脉搏", "状态级动态响应偏移",
        "融合脉搏由各次实验的等面积归一化 PSD 取平均得到，其主导频率为融合曲线的最大值位置。")
fused = go.Figure()
fused.add_trace(go.Scatter(x=result["grid"], y=base_group["fingerprint"], mode="lines",
                           line=dict(color=BASE, width=2.5), fill="tozeroy", fillcolor="rgba(77,225,205,.04)", name="基线融合脉搏"))
fused.add_trace(go.Scatter(x=result["grid"], y=pert_group["fingerprint"], mode="lines",
                           line=dict(color=PERT, width=2.5), fill="tozeroy", fillcolor="rgba(255,138,102,.035)", name="扰动融合脉搏"))
fused.update_layout(**plot_layout(380))
show(fused)
st.markdown(
    f'<div class="pulse-row"><div><div class="pulse-label">基线脉冲</div><div class="pulse-value">{base_group["dominant_frequency"]:.2f} Hz</div></div>'
    f'<div class="arrow">→</div><div><div class="pulse-label">扰动脉冲</div><div class="pulse-value">{pert_group["dominant_frequency"]:.2f} Hz</div></div>'
    f'<div class="arrow">→</div><div><div class="pulse-label">响应偏移</div><div class="pulse-value shift">{result["shift_percent"]:+.1f}%</div>'
    f'<div class="pulse-label">融合 JS divergence：{result["fused_divergence"]:.3f}</div></div></div>', unsafe_allow_html=True,
)

section("05 / 状态分离", "同状态与跨状态差异比较",
        "Jensen–Shannon divergence 用于比较每一对 5–25 Hz 归一化 PSD；数值越低，表示动态响应脉搏越相似。")
div_left, div_right = st.columns([.8, 1.25], gap="large")
with div_left:
    categories = ["基线内部", "扰动内部", "跨状态"]
    values = [result["within_baseline"], result["within_perturbed"], result["cross_state"]]
    colors = [BASE, "#7faea8", PERT]
    box = go.Figure()
    for category, vals, color in zip(categories, values, colors):
        box.add_trace(go.Box(y=vals, name=category, boxpoints="all", jitter=.28, pointpos=0,
                             marker=dict(color=color, size=6), line=dict(color=color), fillcolor="rgba(0,0,0,0)"))
    box.update_layout(**chart_layout(
        360, showlegend=False,
        xaxis=dict(showgrid=False, linecolor=GRID),
        yaxis=dict(showgrid=True, gridcolor=GRID, title="JS 差异度", rangemode="tozero"),
    ))
    show(box)
with div_right:
    labels = [f"B{i}" for i in range(1, len(baseline) + 1)] + [f"P{i}" for i in range(1, len(perturbed) + 1)]
    heat = go.Figure(go.Heatmap(
        z=result["divergence_matrix"], x=labels, y=labels,
        colorscale=[[0, "#0d1a15"], [.35, "#2f8d7c"], [1, "#e07a62"]],
        text=np.round(result["divergence_matrix"], 3), texttemplate="%{text:.3f}",
        colorbar=dict(title="JS", thickness=10), zmin=0,
    ))
    heat.update_layout(**chart_layout(
        360, xaxis=dict(title="", side="top"), yaxis=dict(title="", autorange="reversed")
    ))
    show(heat)

section("06 / 频谱能量迁移", "主导频谱能量整体下移",
        "以下比例直接由两组融合归一化 PSD 在指定频率区间内积分得到。")
energy = go.Figure(go.Bar(
    x=["基线 · 11–16 Hz", "扰动 · 8–11 Hz"],
    y=[result["baseline_energy_11_16"] * 100, result["perturbed_energy_8_11"] * 100],
    marker_color=[BASE, PERT], text=[f"{result['baseline_energy_11_16']:.1%}", f"{result['perturbed_energy_8_11']:.1%}"],
    textposition="outside",
))
energy.update_layout(**chart_layout(
    300, xaxis=dict(title="", showgrid=False),
    yaxis=dict(title="选定频带能量占比 / %", showgrid=True, gridcolor=GRID, range=[0, 100]),
))
show(energy)

st.markdown(
    '<div class="boundary"><b>黔脉检测的是结构动态响应变化，不进行结构损伤诊断。</b><br>'
    '本实验验证的是传感与响应偏移检测能力，不是桥梁安全诊断。</div>'
    '<div class="notes"><b>技术边界。</b> 本次扰动通过在缩尺结构上放置一整瓶密封水引入，改变了系统的质量分布与动态响应。'
    '本实验展示的是响应偏移的可检测性，而不是结构损伤检测或桥梁状态的定量识别。</div>',
    unsafe_allow_html=True,
)
