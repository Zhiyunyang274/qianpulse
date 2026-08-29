"""证据 03 · 车载过桥试点：drive-by ZIP → 桥窗提取 → 候选峰 → 融合脉搏。

数据目录 data/drive_by_pilot/ 下每个 ZIP 是一次完整行车记录；
无数据时页面自动回退到「计划中」状态，绝不展示伪造结果。

当前目录同时包含：
- 真实外场采集（a*.zip 正向 / b*.zip 反向，iPhone 15 · 100 Hz，无桥窗标注
  → 按「全程窗口」处理），页面标注 REAL FIELD DATA；
- 模拟采集演练（sim_drive_*.zip，带 manifest）→ SIMULATED，作为管线验证。
两类数据分层展示，不混淆。
"""

from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from qianpulse.engine import crossing_to_peaks, fuse_peaks, noise_residual
from qianpulse.io_driveby import discover_driveby_runs, load_driveby_run
from qianpulse.ui import CHART_COLORS, inject_styles, page_head, plotly_theme, show_chart, topbar

ROOT = Path(__file__).resolve().parents[1] / "data" / "drive_by_pilot"

st.set_page_config(page_title="黔脉 · 车载过桥试点", page_icon="🚗", layout="wide")
inject_styles()
topbar("evidence")

_paths = discover_driveby_runs(ROOT)
_has_data = bool(_paths)


def _render_scheduled():
    page_head("证据 03 · 车载实测", "车载过桥试点",
              "下一步验证：使用日常车辆采集真实过桥数据。",
              '<span class="qp-badge watch">计划中</span>')
    st.markdown(
        '<div class="qp-card" style="margin-top:24px;padding:30px">'
        '<div class="qp-kicker">方案已就绪</div>'
        '<div style="font-size:22px;font-weight:700;color:#e9f1ec;margin:10px 0 8px">尚未开始采集</div>'
        '<p class="qp-note" style="max-width:640px">当前未完成真实车载采集，因此不展示任何假结果或已完成状态。</p>'
        '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:20px">'
        '<div style="border:1px solid #1f342b;border-radius:10px;padding:14px"><span class="qp-note">真实车辆</span></div>'
        '<div style="border:1px solid #1f342b;border-radius:10px;padding:14px"><span class="qp-note">真实桥梁</span></div>'
        '<div style="border:1px solid #1f342b;border-radius:10px;padding:14px"><span class="qp-note">iPhone ~100 Hz IMU · GPS</span></div>'
        '<div style="border:1px solid #1f342b;border-radius:10px;padding:14px"><span class="qp-note">重复过桥 · 道路控制段</span></div>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="qp-note" style="border-left:2px solid #6fd8c5;padding:2px 0 2px 14px;margin-top:20px">'
        '状态由有效数据目录决定：检测到 data/drive_by_pilot/ 下有效 ZIP 后自动切换为已接入。</div>',
        unsafe_allow_html=True,
    )


def _direction_label(source):
    """按文件名前缀给出行驶方向（a=正向去程 / b=反向回程）。"""
    name = Path(source).name.lower()
    if name.startswith("a"):
        return "正向 · 去程"
    if name.startswith("b"):
        return "反向 · 回程"
    return ""


def _render_runs(runs, simulated):
    """渲染一组穿越记录。simulated=True 渲染模拟演练（管线验证），False 渲染真实外场采集。"""
    badge = ('<span class="qp-badge sim">SIMULATED DRIVE-BY DATA · 模拟采集演练</span>'
             if simulated else '<span class="qp-badge real">REAL FIELD DATA · 真实开车采集</span>')
    page_head("证据 03 · 车载实测", "车载过桥试点 · 数据已接入",
              "同一车辆、同一路线、同一座桥——把每一次过桥变成一次测量。",
              badge)

    n = len(runs)
    has_window = all(r["window"] is not None for r in runs)
    if simulated:
        method_note = (
            '驾驶员使用日常车辆多次通过目标桥梁，手机固定于车内并以约 100 Hz 记录 IMU 与 GPS；'
            'Bridge-Enter / Bridge-Exit 标注切出桥窗，重力投影提取竖直向加速度，'
            '对每次穿越做功率谱候选峰，再多票融合得到桥梁脉搏。'
            '<b style="color:#e3c584">本组三条记录为模拟采集演练数据（iPhone 传感器格式，数据集标注桥频 7.78 Hz），'
            '用于验证整条数据管线；不是真实外场测量。</b>')
    else:
        method_note = (
            '驾驶员使用日常车辆对同一座平桥完成 {} 次真实穿越（正向 {} 次 / 反向 {} 次），'
            '手机固定于车内以约 100 Hz 记录 IMU。本组采集未做桥窗标注、未开 GPS——'
            '系统按「全程窗口」处理：把整段行车记录当作一次穿越提取候选峰，'
            '引道路段的噪声候选随穿越轮换，只有桥梁响应会堆积。'
            '竖直向加速度由重力投影得到。'.format(n, sum(1 for r in runs if _direction_label(r["source"]) == "正向 · 去程"),
                                                   n - sum(1 for r in runs if _direction_label(r["source"]) == "正向 · 去程")))
    st.markdown(
        '<div class="qp-card" style="margin-top:24px;padding:24px 28px">'
        '<div class="qp-kicker">采集方案与真实边界</div>'
        '<p class="qp-note" style="max-width:860px;margin-top:10px">' + method_note + '</p></div>',
        unsafe_allow_html=True,
    )

    # ---- 指标行 ----
    fs_med = float(np.median([r["fs"] for r in runs]))
    dur_med = float(np.median([r["duration"] for r in runs]))
    votes = [crossing_to_peaks(r["bridge"] if r["bridge"] is not None else r["full"])["peaks"] for r in runs]
    all_votes = np.concatenate(votes)
    grid, density, dominant = fuse_peaks(all_votes)
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(
        '<div class="qp-metric"><span>有效穿越</span><strong>{}</strong><em>次 · 同桥同向</em></div>'.format(n),
        unsafe_allow_html=True)
    c2.markdown(
        '<div class="qp-metric"><span>采样率 / 时长</span><strong>{}<em> Hz</em> · {:.0f}<em> s</em></strong></div>'.format(
            round(fs_med), dur_med),
        unsafe_allow_html=True)
    c3.markdown(
        '<div class="qp-metric"><span>候选峰总票数</span><strong>{}</strong><em>来自 {} 次穿越</em></div>'.format(
            len(all_votes), n),
        unsafe_allow_html=True)
    c4.markdown(
        '<div class="qp-metric"><span>融合主频</span><strong>{}<em> Hz</em></strong></div>'.format(
            "—" if not np.isfinite(dominant) else f"{dominant:.2f}"),
        unsafe_allow_html=True)

    # ---- 逐次穿越：竖直向波形 + 桥窗标注 ----
    st.markdown(
        '<div class="qp-section-label" style="margin-top:44px">逐次穿越 · 竖直向加速度</div>'
        '<div class="qp-section-title">每一次过桥，都是一次独立测量</div>'
        '<div class="qp-section-copy">下图为重力投影竖直向加速度全程波形' +
        ('；阴影区为标注切出的桥窗，桥上振动肉眼可见地强于引道路段。' if has_window
         else '。本组采集无桥窗标注，整段记录按一次穿越处理。') + '</div>',
        unsafe_allow_html=True,
    )
    for r in runs:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=r["full"]["t"], y=r["full"]["acc"], mode="lines",
                                 line=dict(color=CHART_COLORS["base"], width=1),
                                 name="竖直向加速度（g）", hovertemplate="%{x:.1f}s · %{y:.4f}g<extra></extra>"))
        if r["window"] is not None:
            enter, exit_ = r["window"]
            fig.add_vrect(x0=enter, x1=exit_, fillcolor=CHART_COLORS["current"], opacity=.10,
                         line_width=0, annotation_text="桥窗 {:.1f}s–{:.1f}s".format(enter, exit_),
                         annotation_font=dict(size=10, color=CHART_COLORS["current"]))
        fig.update_layout(plotly_theme(height=210, show_y=False))
        fig.update_xaxes(title_text="行车时间（s）")
        direction = _direction_label(r["source"])
        dir_chip = ' · <b style="color:#6fd8c5">{}</b>'.format(direction) if direction else ""
        st.markdown(
            '<div class="qp-note" style="margin:6px 0 2px"><b>{}</b>{} · {} · {:.2f} km 路线</div>'.format(
                r["source"], dir_chip,
                "模拟数据" if r["simulated"] else "真实数据", r["route_km"]),
            unsafe_allow_html=True)
        show_chart(fig)

    # ---- 候选峰投票 + 融合 ----
    st.markdown(
        '<div class="qp-section-label" style="margin-top:44px">候选峰投票 · {} 次穿越</div>'.format(n)
        + '<div class="qp-section-title">单次各不相同，多次之后，属于桥的频率开始堆积</div>'
        '<div class="qp-section-copy">每次穿越的功率谱前若干候选峰各投一票（等权）：车辆与路面噪声的候选每次都换位置，'
        '只有桥梁自身的响应会在同一频率反复出现。灰色短线为各次穿越的原始候选，'
        '青色曲线为 KDE 融合密度（绝对带宽 0.15 Hz）。</div>',
        unsafe_allow_html=True,
    )
    fig = go.Figure()
    for i, (r, pk) in enumerate(zip(runs, votes)):
        jitter = np.full_like(pk, (i + 1) * 0.5)
        fig.add_trace(go.Scatter(x=pk, y=jitter, mode="markers",
                                 marker=dict(color=CHART_COLORS["watch"], size=9, opacity=.9,
                                             line=dict(width=1, color="rgba(0,0,0,.3)")),
                                 name="穿越 {} 候选峰".format(i + 1),
                                 hovertemplate="%{x:.2f} Hz<extra>穿越 " + str(i + 1) + "</extra>"))
        for f0 in pk:
            fig.add_shape(type="line", x0=f0, x1=f0, y0=jitter[0] - .22, y1=jitter[0] + .22,
                          line=dict(color="rgba(217,180,110,.35)", width=1))
    if np.any(density > 0):
        fig.add_trace(go.Scatter(x=grid, y=density / density.max() * 2.35, mode="lines",
                                 line=dict(color=CHART_COLORS["current"], width=2.6, shape="spline"),
                                 name="融合密度（归一化）", hovertemplate="%{x:.2f} Hz<extra></extra>"))
        if np.isfinite(dominant):
            fig.add_vline(x=dominant, line=dict(color=CHART_COLORS["alert"], width=1.6, dash="dot"))
            fig.add_annotation(x=dominant, y=2.5, text="融合主频 {:.2f} Hz".format(dominant),
                               showarrow=False, yanchor="bottom",
                               font=dict(color=CHART_COLORS["alert"], size=12))
    fig.update_layout(plotly_theme(height=330, show_y=False))
    fig.update_xaxes(title_text="频率（Hz）", range=[3, 15])
    fig.update_yaxes(showticklabels=False)
    show_chart(fig)

    # ---- 结论 ----
    residual = noise_residual(density) if np.any(density > 0) else float("nan")
    st.markdown(
        '<div class="qp-card" style="margin-top:28px">'
        '<div class="qp-kicker">融合结论</div>'
        '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-top:14px">'
        '<div><span class="qp-note">候选峰散布（单次）</span><div style="font-family:Georgia,serif;font-size:26px;color:#e9f1ec;margin-top:6px">{:.1f} Hz</div></div>'
        '<div><span class="qp-note">融合主频（同桥反复出现）</span><div style="font-family:Georgia,serif;font-size:26px;color:#6fd8c5;margin-top:6px">{} Hz</div></div>'
        '<div><span class="qp-note">噪声残余率</span><div style="font-family:Georgia,serif;font-size:26px;color:#e9f1ec;margin-top:6px">{:.0f}%</div></div>'
        '</div>'
        '<p class="qp-note" style="margin-top:16px;max-width:860px">车辆/路面噪声的候选峰随穿越轮换（噪声残余 {:.0f}% 的票落在主频 ±0.5 Hz 之外），'
        '而桥梁响应稳定堆积——这就是「筛查，不是诊断」的第一步：只用日常车流，就锁定了这座桥的脉搏。</p></div>'.format(
            float(np.ptp(all_votes)), "—" if not np.isfinite(dominant) else f"{dominant:.2f}",
            residual * 100, residual * 100),
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="qp-note" style="border-top:1px solid #1f342b;padding-top:16px;margin-top:34px">'
        '数据来源：data/drive_by_pilot/ · ' +
        ("SIMULATED DRIVE-BY（模拟采集演练，iPhone 传感器格式）· " if simulated else "") +
        '竖直向方法：{}。筛查结果不构成结构诊断。</div>'.format(
            " / ".join(sorted({r["vertical_method"] for r in runs}))),
        unsafe_allow_html=True,
    )


if _has_data:
    @st.cache_data(show_spinner=False)
    def _load_runs(paths_str):
        return [load_driveby_run(Path(p)) for p in paths_str]

    try:
        _all = _load_runs(tuple(str(p) for p in _paths))
    except (ValueError, KeyError, OSError) as exc:
        st.error(f"车载数据解析失败：{exc}")
        st.info("请检查 data/drive_by_pilot/ 下的 ZIP 是否完整（需含 Accelerometer.csv）。")
        st.stop()

    _real = [r for r in _all if not r["simulated"]]
    _sim = [r for r in _all if r["simulated"]]

    if _real:
        _render_runs(_real, simulated=False)
    if _sim:
        if _real:
            st.markdown(
                '<div class="qp-note" style="margin-top:56px;border-top:1px dashed #1f342b;padding-top:28px">'
                '以下为<b>模拟采集演练数据</b>（管线验证）：在真实外场数据接入前用于验证 ZIP → 桥窗 → '
                '候选峰 → 融合的完整链路，保留作对照。</div>',
                unsafe_allow_html=True,
            )
        _render_runs(_sim, simulated=True)
    if not _real and not _sim:
        _render_scheduled()
else:
    _render_scheduled()
