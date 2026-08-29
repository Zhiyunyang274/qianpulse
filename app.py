import asyncio
import base64
import json
import mimetypes
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from qianpulse.engine import (
    bootstrap_baseline_divergence,
    crossing_to_peaks,
    fingerprint_divergence,
    fuse_crossings,
    fuse_peaks,
    noise_residual,
)
from qianpulse.scale_simulation import run_scale_simulation
from qianpulse.simulate import simulate_batch
from qianpulse.ui import (
    CHART_COLORS,
    inject_styles,
    metric,
    page_head,
    plotly_theme,
    show_chart,
    topbar,
)


st.set_page_config(
    page_title="黔脉 QianPulse",
    page_icon="🌉",
    layout="wide",
    initial_sidebar_state="collapsed",
)


INTRO_ROOT = Path(__file__).resolve().parent / "assets" / "intro"

# MapLibre GL 自托管（assets/vendor/），内联进地图 iframe：
# unpkg/jsdelivr 等公共 CDN 在大陆访问不稳定，且挂起时无 onerror，地图会永远停在加载态。
import functools


@functools.lru_cache(maxsize=1)
def _vendor_lib():
    root = Path(__file__).resolve().parent / "assets" / "vendor"
    js = (root / "maplibre-gl.js").read_text().replace("</script", "<\\/script")
    css = (root / "maplibre-gl.css").read_text().replace("</style", "<\\/style")
    return js, css


# =============================================================================
# Story Intro（六步叙事 Modal）
# =============================================================================

def _intro_media(step):
    # 第 4 步（转向车流的铺垫）使用程序化桥景 SVG（带行驶车辆动画）
    stems = {1: "story_01", 2: "story_02", 3: "story_03", 5: "story_04", 6: "reveal"}
    stem = stems.get(step)
    if stem is None:
        return _intro_bridge_svg(step)
    for suffix in (".mp4", ".webm", ".jpg", ".jpeg", ".png", ".webp"):
        path = INTRO_ROOT / f"{stem}{suffix}"
        if path.exists():
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            payload = base64.b64encode(path.read_bytes()).decode("ascii")
            if suffix in (".mp4", ".webm"):
                return f'<video class="intro-media" autoplay muted loop playsinline><source src="data:{mime};base64,{payload}" type="{mime}"></video>'
            return f'<div class="intro-media" style="background-image:url(data:{mime};base64,{payload})"></div>'
    return _intro_bridge_svg(step)


def _intro_bridge_svg(step):
    vehicle_dots = "" if step != 4 else '<circle cx="350" cy="235" r="5"/><circle cx="500" cy="235" r="5"/><circle cx="650" cy="235" r="5"/>'
    return f'''<div class="intro-media intro-fallback"><svg viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#63747a"/><stop offset=".55" stop-color="#31464d"/><stop offset="1" stop-color="#142127"/></linearGradient><filter id="blur"><feGaussianBlur stdDeviation="18"/></filter></defs><rect width="1440" height="900" fill="url(#sky)"/><path d="M0 520 C150 370 260 400 390 510 C510 610 610 375 770 485 C910 580 1010 345 1180 470 C1290 550 1360 490 1440 430 V900 H0Z" fill="#2b4249"/><path d="M0 610 C180 470 300 540 455 625 C620 715 755 500 930 595 C1080 675 1240 500 1440 570 V900 H0Z" fill="#193039"/><g stroke="#d0d8d3" stroke-width="5" fill="none" opacity=".78"><path d="M240 245 H1200"/><path d="M350 245 V565 M1090 245 V555"/><path d="M365 245 V570 M1075 245 V560"/></g><g fill="#8ecfc6" opacity=".95">{vehicle_dots}</g><g filter="url(#blur)" opacity=".26"><ellipse cx="850" cy="230" rx="450" ry="125" fill="#d5e2df"/></g></svg></div>'''


def _story_content(step):
    if step == 1:
        return '''<div class="intro-eyebrow">01 / 万桥贵州</div><h1>世界的桥梁看中国，<br/>中国的桥梁看贵州</h1><div class="intro-metrics"><div><strong>32,000+</strong><span>已建和在建桥梁</span></div><div><strong>Top 100</strong><span>世界高桥近一半在贵州</span></div></div><p>九成山地、河谷深切——桥，是贵州人写给群山的回信，也是这片土地持续发展的基础设施底座</p><a class="source-chip" href="https://jt.guizhou.gov.cn/" target="_blank">贵州省交通运输厅 · 2025 ↗</a>'''
    if step == 2:
        return '''<div class="intro-eyebrow">02 / 从建设到长期服役</div><h1>通车那天，只是这座桥<br/>五十年故事的开始</h1><p>从通车起，风、雨、车流与极端天气就在日复一日地作用于结构——真正的考验，都在通车之后</p><div class="life-line"><span>建成</span><i></i><span>通行</span><i></i><span>巡查</span><i></i><span>长期养护</span></div><div class="event-note"><b>REAL EVENT · 2025 · 猴子河大桥</b><span>极端降雨诱发滑坡，官方巡查及时发现了变形并提前管制——但下一个「等不到巡查日」的变化，靠什么发现？</span><a href="https://jt.guizhou.gov.cn/" target="_blank">查看案例 →</a></div>'''
    if step == 3:
        return '''<div class="intro-eyebrow">03 / 真正的缺口</div><h1>检查等不起，<br/>监测装不起</h1><p>面对漫长的服役期，现实只有两条路：人工检查按「年」计——封道、登高、组织队伍，两次检查之间的变化无人知晓；监测系统按「千万」计——注定只能覆盖极少数重点桥</p><div class="intro-metrics"><div><strong>32,000+</strong><span>需要长期看护的桥梁</span></div><div><strong>极少数</strong><span>装得起监测系统的重点桥</span></div></div><div class="turning-point">三万座桥，被留在了两次检查之间<small>问题，从不挑检查日出现</small></div><a class="source-chip" href="https://www.gzhighway.com/" target="_blank">贵州高速集团 · 官方资料 ↗</a>'''
    if step == 4:
        return '''<div class="intro-eyebrow">04 / 换一个角度</div><h1>那么，桥上每天<br/>最不缺的是什么？</h1><p>把目光从桥身移开，看向桥面——清晨的公交、跨城的物流、定线的巡检车……在贵州，每一座桥每天都有成百上千次穿越</p><div class="vehicle-row"><span>公交</span><span>出租</span><span>物流</span><span>巡检车辆</span></div><div class="bridge-motion"><i></i><b class="car c1"></b><b class="car c2"></b><b class="car c3"></b></div><p class="key-line">如果观测这座桥的，不必是巡检队，也不必是固定传感器呢？</p>'''
    if step == 5:
        return '''<div class="intro-eyebrow">05 / 核心洞察</div><h1>答案是：车。而且早就<br/>装好了传感器</h1><p>每一辆驶过桥面的车，都载着惯性测量单元——每一次通过，都是一次对桥梁的「测量」。只是这些测量从未被记录，过完桥，就随风而去</p><div class="turning-point">车流，是一张被浪费的观测网<small>观测一直都在发生，只是从未被留下</small></div><p class="key-line">把它留下来，就是免费的日常体检</p>'''
    return '''<div class="intro-reveal"><div class="intro-eyebrow">06 / QIANPULSE REVEAL</div><h1><span>黔脉</span><small>QianPulse</small></h1><svg class="reveal-pulse" viewBox="0 0 216 24" aria-hidden="true"><path d="M0 12 H66 L76 4 L88 20 L98 9 L106 12 H216"/></svg><h2>不新增一个传感器，把观测密度从「按年」提到「按天」</h2><p>让日常车流成为桥梁的脉搏记录者：单次各不相同，千百次之后，属于桥的响应自然显现——让有限的检查资源，先投向真正偏移的那座桥</p><div class="reveal-boundary"><b>筛查，不是诊断</b><span>帮助养护人员决定哪座桥值得优先检查</span></div></div>'''


def render_story_mode():
    # 所有叙事步骤都放在同一个浏览器组件里，由 JS 切换，
    # 推进叙事不会触发 Streamlit rerun，无闪烁。
    st.markdown("""<style>
    #MainMenu,header,footer,[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stSidebar"],[data-testid="stSidebarNav"]{display:none!important}
    .stApp{background:#0a1310!important}.block-container{max-width:none!important;padding:0!important}
    iframe[data-testid="stIFrame"]{display:block!important;margin-top:-16px!important;height:calc(100vh + 16px)!important}
    </style>""", unsafe_allow_html=True)
    steps = [_story_content(i) for i in range(1, 7)]
    media = [_intro_media(i) for i in range(1, 7)]
    payload = json.dumps({"steps": steps, "media": media}, ensure_ascii=False).replace("</", "<\\/")
    host = st.context.headers.get("host", "localhost:8501")
    proto = st.context.headers.get("x-forwarded-proto", "http")
    app_origin = f"{proto}://{host}"
    html = f'''<!doctype html><html><head><meta charset="utf-8"><style>
    *{{box-sizing:border-box}} html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:#0a1310;color:#e9f1ec;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}}
    .scene{{position:relative;width:100%;height:100vh;min-height:680px;overflow:hidden;background:#0a1310}} .bg{{position:absolute;inset:0;opacity:0;transition:opacity .8s ease;background-size:cover;background-position:center}} .bg.active{{opacity:1}} .bg::after{{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(5,10,13,.3),rgba(5,10,13,.78)),radial-gradient(circle at 50% 42%,transparent 0,rgba(4,9,12,.35) 78%)}} .bg svg{{width:100%;height:100%;filter:saturate(.65) contrast(1.08)}}
    .scrim{{position:absolute;inset:0;background:rgba(6,12,15,.05)}} .bg .intro-media{{position:absolute!important;inset:0!important;width:100%!important;height:100%!important;z-index:0!important;background-size:cover;background-position:center}} .bg .intro-media:after{{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(5,10,13,.12),rgba(5,10,13,.52)),radial-gradient(circle at 50% 42%,transparent 0,rgba(4,9,12,.18) 78%)}} .bg .intro-fallback svg{{width:100%;height:100%;display:block;filter:saturate(.78) contrast(1.08)}} .panel{{position:absolute;z-index:2;left:50%;top:50%;transform:translate(-50%,-50%);width:min(920px,82vw);min-height:500px;padding:28px 58px 28px;border:1px solid rgba(111,216,197,.16);border-radius:24px;background:rgba(10,19,16,.88);box-shadow:0 34px 110px rgba(0,0,0,.56),0 0 0 1px rgba(255,255,255,.03) inset;backdrop-filter:blur(17px);display:flex;flex-direction:column}} .panel-header{{display:flex;justify-content:flex-end;min-height:25px}} .skip{{border:0;background:none;color:#84988e;font-size:.72rem;cursor:pointer;padding:5px 0}} .skip:hover{{color:#e9f1ec}} .content{{flex:1;display:flex;flex-direction:column;justify-content:center;overflow:hidden}} .step{{display:none;animation:.42s ease both}} .step.current{{display:block}} .step.out{{animation-name:out}} .step.in{{animation-name:in}} @keyframes in{{from{{opacity:0;transform:translateY(12px)}}to{{opacity:1;transform:none}}}} @keyframes out{{from{{opacity:1;transform:none}}to{{opacity:0;transform:translateY(-10px)}}}} .reveal-boundary{{display:flex;gap:16px;align-items:center;justify-content:center;border-top:1px solid rgba(111,216,197,.16);margin:24px auto 0;padding-top:16px;color:#84988e;font-size:.74rem}} .reveal-boundary b{{color:#9ee8da;font-weight:650}} .reveal-boundary span{{color:#5f7469}}
    h1{{font-family:"Songti SC","Noto Serif SC","STSong",Georgia,serif;font-size:clamp(2rem,3.25vw,2.85rem);line-height:1.25;letter-spacing:.01em;font-weight:700;margin:12px 0 17px;max-width:780px;color:#e9f1ec}} p{{font-size:1rem;line-height:1.7;color:#aebcB4;max-width:700px;margin:11px 0}} .intro-eyebrow{{color:#6fd8c5;font-size:.68rem;letter-spacing:.16em;font-weight:750}} .intro-metrics{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:18px 0}} .intro-metrics div{{border:1px solid rgba(111,216,197,.14);background:rgba(111,216,197,.04);padding:14px 18px;border-radius:12px}} .intro-metrics strong{{display:block;color:#9ee8da;font:600 1.8rem Georgia,serif}} .intro-metrics span{{color:#84988e;font-size:.76rem}} .source-chip{{display:inline-block;padding:7px 10px;border-radius:999px;background:rgba(255,255,255,.06);color:#b9c8c0;text-decoration:none;font-size:.68rem}} .life-line{{display:flex;align-items:center;gap:10px;margin:28px 0;color:#d5ddd8;font-size:.78rem}} .life-line i{{height:1px;flex:1;background:#2a4536}} .event-note{{border-top:1px solid rgba(255,255,255,.1);padding-top:13px;display:grid;grid-template-columns:1fr 2fr auto;gap:14px;align-items:center;color:#84988e;font-size:.66rem}} .event-note b{{color:#b9c8c0}} .event-note a{{color:#6fd8c5}} .capability-grid{{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin:20px 0}} .capability-grid span,.vehicle-row span{{padding:11px 14px;border:1px solid rgba(255,255,255,.1);border-radius:9px;color:#c9d4ce;background:rgba(255,255,255,.025)}} .turning-point{{border-left:2px solid #6fd8c5;padding:11px 16px;margin:18px 0;color:#e3ebe6;font-size:1.05rem}} .turning-point small{{display:block;color:#84988e;font-size:.83rem;margin-top:5px}} .vehicle-row{{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin:19px 0}} .bridge-motion{{height:50px;position:relative;margin:13px 0}} .bridge-motion i{{position:absolute;left:3%;right:3%;top:27px;height:2px;background:#2a4536}} .car{{position:absolute;top:18px;width:20px;height:9px;border-radius:3px;background:#6fd8c5;animation:drive 5s linear infinite}} .c1{{animation-delay:-1s}} .c2{{animation-delay:-2.8s}} .c3{{animation-delay:-4.2s}} @keyframes drive{{from{{left:4%}}to{{left:92%}}}} .key-line{{color:#e9f1ec!important;font-size:1.2rem!important}} .intro-reveal{{text-align:center}} .intro-reveal h1{{margin-left:auto;margin-right:auto}} .intro-reveal h1 span{{display:block;font-size:1.55em;letter-spacing:.16em;margin-right:-.16em;background:linear-gradient(100deg,#8fe3d0 0%,#6fd8c5 26%,#f2fffb 50%,#6fd8c5 74%,#3f9c88 100%);background-size:200% 100%;-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;filter:drop-shadow(0 0 26px rgba(111,216,197,.36));animation:revealShimmer 3.4s linear infinite}} @keyframes revealShimmer{{to{{background-position:-200% 0}}}} .reveal-pulse{{width:216px;height:22px;margin:6px auto 0;display:block}} .reveal-pulse path{{fill:none;stroke:#6fd8c5;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:320;animation:revealDraw 3.8s ease-in-out infinite}} @keyframes revealDraw{{0%,10%{{stroke-dashoffset:320;opacity:.15}}45%,62%{{stroke-dashoffset:0;opacity:.95}}100%{{stroke-dashoffset:-320;opacity:.15}}}} .intro-reveal h1 small{{display:block;font:500 .32em Arial,sans-serif;letter-spacing:.22em;color:#84988e;margin-top:10px}} .intro-reveal h2{{font-size:1.45rem;font-weight:560;color:#dfe7e2}} .intro-reveal p{{margin-left:auto;margin-right:auto}}
    .footer{{display:flex;align-items:center;gap:18px;margin-top:18px}} .dots{{display:flex;gap:8px;flex:1}} .dot{{width:7px;height:7px;border-radius:50%;background:#2a4536;transition:all .3s}} .dot.on{{background:#6fd8c5;transform:scale(1.2)}} .count{{color:#5f7469;font-size:.68rem;font-family:ui-monospace,Menlo,monospace}} .actions{{display:flex;justify-content:space-between;align-items:center;margin-top:16px}} button{{font:inherit;cursor:pointer}} .back,.next,.enter{{border-radius:999px;padding:11px 21px;border:1px solid rgba(255,255,255,.16);background:rgba(255,255,255,.055);color:#e9f1ec;font-size:.78rem;text-decoration:none;display:inline-block}} .back{{visibility:hidden}} .back.visible{{visibility:visible}} .next,.enter{{background:#6fd8c5;border-color:#6fd8c5;color:#06110e;font-weight:700}} .enter{{padding:12px 28px}} .panel.exit{{animation:panelExit .45s ease forwards}} @keyframes panelExit{{to{{opacity:0;transform:translate(-50%,-50%) scale(.98)}}}} @media(max-width:760px){{.panel{{width:90vw;min-height:550px;padding:23px 24px 25px;border-radius:19px}}h1{{font-size:clamp(1.9rem,8.5vw,2.65rem)}}.vehicle-row{{grid-template-columns:1fr 1fr}}.event-note{{grid-template-columns:1fr}}.life-line{{gap:6px;font-size:.65rem}}}}
    </style></head><body><main class="scene"><div id="bgs"></div><div class="scrim"></div><section class="panel" id="panel"><header class="panel-header"><button class="skip" id="skip">跳过介绍</button></header><div class="content" id="content"></div><div class="footer"><div class="dots" id="dots"></div><span class="count" id="count"></span></div><div class="actions"><button class="back" id="back">← 返回</button><button class="next" id="next">继续 →</button></div></section></main><script>
    // 组件 iframe 被 sandbox 限制（无 allow-top-navigation），直接改 parent.location 会被静默拦截。
    // 借助 allow-same-origin 的 DOM 权限：向父文档动态注入脚本，在父页面上下文中执行导航。
    function nav(url){{try{{const s=parent.document.createElement('script');s.textContent='window.location.href='+JSON.stringify(url);parent.document.head.appendChild(s);}}catch(e){{}}}}
    const data={payload}; const content=document.getElementById('content'), bgs=document.getElementById('bgs'), dots=document.getElementById('dots'), count=document.getElementById('count'), back=document.getElementById('back'), next=document.getElementById('next'), panel=document.getElementById('panel'); let idx=0;
    data.media.forEach((m,i)=>{{const el=document.createElement('div');el.className='bg'+(i===0?' active':'');el.innerHTML=m;bgs.appendChild(el)}}); data.steps.forEach((s)=>{{const el=document.createElement('article');el.className='step';el.innerHTML=s;content.appendChild(el)}}); data.steps.forEach((_,i)=>{{const d=document.createElement('span');d.className='dot'+(i===0?' on':'');d.onclick=()=>go(i);dots.appendChild(d)}});
    function paint(){{document.querySelectorAll('.step').forEach((e,i)=>e.classList.toggle('current',i===idx));document.querySelectorAll('.bg').forEach((e,i)=>e.classList.toggle('active',i===idx));document.querySelectorAll('.dot').forEach((e,i)=>e.classList.toggle('on',i===idx));count.textContent=`${{idx+1}} / ${{data.steps.length}}`;back.classList.toggle('visible',idx>0);next.style.display=idx===data.steps.length-1?'none':'inline-block';document.querySelector('.enter')?.remove();if(idx===data.steps.length-1){{const e=document.createElement('button');e.className='enter';e.textContent='进入黔脉 →';e.onclick=()=>{{nav('/?view=console')}};document.querySelector('.actions').appendChild(e)}}}}
    function go(n){{if(n===idx)return; const old=document.querySelector('.step.current'); old?.classList.add('out'); idx=n; paint(); const cur=document.querySelector('.step.current');cur.classList.add('in');setTimeout(()=>old?.classList.remove('out'),430)}} function skip(){{nav('/?view=console')}} next.onclick=()=>go(Math.min(idx+1,data.steps.length-1)); back.onclick=()=>go(Math.max(idx-1,0)); document.getElementById('skip').onclick=skip; paint();
    window.addEventListener('keydown',e=>{{if(e.key==='ArrowRight'||e.key===' '){{e.preventDefault();go(Math.min(idx+1,data.steps.length-1))}}else if(e.key==='ArrowLeft'){{e.preventDefault();go(Math.max(idx-1,0))}}else if(e.key==='Escape'){{skip()}}}});
    </script></body></html>'''
    components.html(html, height=900, scrolling=False)


view = st.query_params.get("view", "intro")
if "story_entered" not in st.session_state:
    st.session_state.story_entered = False
if view in {"console", "overview", "bridge", "method", "evidence", "arch", "sources"}:
    st.session_state.story_entered = True
if not st.session_state.story_entered:
    render_story_mode()
    st.stop()


# =============================================================================
# 数据
# =============================================================================

@st.cache_data(show_spinner=False)
def demo_data(seed, baseline_f, current_f):
    return (
        simulate_batch(100, bridge_freq=baseline_f, seed=seed),
        simulate_batch(100, bridge_freq=current_f, seed=seed + 100),
    )


@st.cache_data(show_spinner=False)
def _dominant_frequency(seed, freq):
    return float(fuse_crossings(simulate_batch(100, bridge_freq=freq, seed=seed))["dominant_frequency"])


@st.cache_data(show_spinner=False)
def _gz017_metrics():
    """GZ-017 全站统一指标：融合脉搏 + bootstrap 阈值 + JS 差异（重计算缓存）。"""
    base, current = demo_data(48, 7.81, 7.22)
    fb, fc = fuse_crossings(base), fuse_crossings(current)
    threshold = bootstrap_baseline_divergence(base[:50], seed=50)["threshold95"]
    js = fingerprint_divergence(fb["fingerprint"], fc["fingerprint"])
    return fb, fc, threshold, js


@st.cache_data(show_spinner=False)
def _network_queue():
    """总览优先队列三座桥的指标：同一管线计算，杜绝硬编码数字。

    GZ-042 用小偏移制造"略超阈值"的持续观察语义；
    GZ-008 用几乎不变的频率制造"低于阈值"的稳定语义。
    """
    out = []
    for seed, base_f, cur_f in ((48, 7.81, 7.22), (58, 9.06, 9.14), (68, 6.47, 6.49)):
        base, cur = simulate_batch(100, bridge_freq=base_f, seed=seed), simulate_batch(100, bridge_freq=cur_f, seed=seed + 100)
        fb, fc = fuse_crossings(base), fuse_crossings(cur)
        th = bootstrap_baseline_divergence(base[:50], seed=50)["threshold95"]
        js = fingerprint_divergence(fb["fingerprint"], fc["fingerprint"])
        out.append({"base_hz": fb["dominant_frequency"], "cur_hz": fc["dominant_frequency"],
                    "js": js, "threshold": th})
    return out


@st.cache_data(show_spinner=False)
def _physical_summary():
    """总览页"真实实验"卡片的数字：直接从真实 ZIP 管线重算，不写死。

    与 /Physical_Validation 页同源同码（gravity 投影），数据重采后自动更新。
    """
    from qianpulse.io_sensorlogger import discover_physical_runs
    from qianpulse.physical_validation import analyse_physical_experiment

    root = Path(__file__).resolve().parent / "data" / "physical_validation"
    discovered = discover_physical_runs(root)
    result = analyse_physical_experiment(discovered)
    fs = float(np.median([r["fs"] for r in result["baseline"] + result["perturbed"]]))
    return {
        "base_hz": float(result["baseline_group"]["dominant_frequency"]),
        "pert_hz": float(result["perturbed_group"]["dominant_frequency"]),
        "shift_pct": float(result["shift_percent"]),
        "fs": fs,
    }


# =============================================================================
# 总览：全出血地图 + 编辑式板块
# =============================================================================

OVERVIEW_CSS = """
<style>
/* ---------- 全出血地图 hero ---------- */
.ov-hero{position:relative;height:74vh;min-height:560px;margin:0 -48px;border-bottom:1px solid #1c3129;overflow:hidden;background:#081010}
.ov-hero .ov-map-frame{position:absolute;inset:0}
.ov-hero .ov-map-frame iframe{position:absolute;inset:0;width:100%;height:100%;border:0;display:block}
.ov-hero .ov-shade{position:absolute;inset:0;pointer-events:none;background:linear-gradient(180deg,rgba(8,16,16,.5),transparent 24%,transparent 46%,rgba(8,16,16,.55) 88%,rgba(8,16,16,.92) 100%),linear-gradient(90deg,rgba(7,14,12,.88) 0%,rgba(7,14,12,.55) 24%,rgba(7,14,12,.12) 48%,transparent 66%)}
.ov-copy{position:absolute;left:60px;bottom:44px;z-index:3;max-width:660px}
.ov-kicker{font-size:12px;letter-spacing:.26em;color:#9ee8da;font-weight:600;display:flex;align-items:center;gap:12px}
.ov-kicker::before{content:"";width:26px;height:1px;background:linear-gradient(90deg,#6fd8c5,transparent)}
.ov-title{font-family:"Songti SC","Noto Serif SC","STSong",serif;font-size:clamp(32px,4.6vw,56px);line-height:1.18;font-weight:600;color:#eef6f2;margin:18px 0 14px;letter-spacing:.01em;text-shadow:0 2px 30px rgba(0,0,0,.7),0 0 80px rgba(8,16,16,.5)}
.ov-sub{font-size:15px;color:#b3c4bb;line-height:1.85;text-shadow:0 1px 14px rgba(0,0,0,.85)}
.ov-legend{position:absolute;right:60px;bottom:44px;z-index:3;text-align:right;font-size:12px;color:#a9bcb2;line-height:2.1;text-shadow:0 1px 10px rgba(0,0,0,.8)}
.ov-legend i{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:8px;vertical-align:middle}
.ov-net{position:absolute;top:20px;right:60px;z-index:3;font-size:11.5px;letter-spacing:.16em;color:#7f948a}
.ov-net b{color:#9ee8da;font-weight:600}

/* ---------- 板块 ---------- */
/* 板块实际由 st.columns 渲染：间距打在 Streamlit 列容器上（页内仅此一组列） */
[data-testid="stHorizontalBlock"]{margin-top:96px}
.ov-board{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(300px,1fr);gap:56px;margin-top:96px}
.ov-h{font-family:"Songti SC","Noto Serif SC",serif;font-size:24px;font-weight:700;color:#e9f1ec;margin:0 0 4px}
.ov-h-sub{font-size:12.5px;color:#7f948a;margin:0 0 18px}
.ov-row{display:grid;grid-template-columns:44px minmax(0,1fr) auto;gap:18px;align-items:baseline;padding:24px 14px 22px 16px;border-top:1px solid #152721;position:relative;transition:background .18s,border-color .18s}
.ov-row::before{content:"";position:absolute;left:0;top:22px;bottom:20px;width:2.5px;border-radius:2px;background:linear-gradient(180deg,var(--row-c,#6fd8c5),transparent 90%)}
.ov-row:hover{background:rgba(111,216,197,.035)}
.ov-row:last-child{border-bottom:1px solid #152721}
.ov-num{font-family:Georgia,serif;font-size:15px;color:#5c7168;font-variant-numeric:tabular-nums}
.ov-id{font-size:16.5px;font-weight:700;color:#e9f1ec;display:flex;align-items:center;gap:10px;letter-spacing:.01em}
.ov-id i{width:8px;height:8px;border-radius:50%;flex-shrink:0;box-shadow:0 0 8px currentColor}
.ov-data{font-family:Georgia,serif;font-variant-numeric:tabular-nums;font-size:14px;color:#7f948a;margin-top:9px;line-height:1.9}
.ov-data b{color:#b9c8c0;font-weight:500}
.ov-data b.alert{color:#eda28d}
.ov-act{font-size:13px;color:#7f948a;text-align:right;white-space:nowrap;opacity:.85}
.ov-act a{color:#6fd8c5;text-decoration:none;margin-left:14px;font-size:12.5px;transition:text-shadow .18s}
.ov-act a:hover{text-shadow:0 0 14px rgba(111,216,197,.6)}

/* 真实证据栏 */
.ov-evi-label{font-size:11.5px;letter-spacing:.2em;color:#7f948a;font-weight:600;margin-bottom:8px}
.ov-evi-big{font-family:Georgia,serif;font-variant-numeric:tabular-nums;font-size:clamp(34px,3.1vw,46px);font-weight:500;color:#eef6f2;line-height:1.15;margin:18px 0 10px;letter-spacing:.01em}
.ov-evi-big i{font-style:normal;color:#5c7168;font-size:.5em;margin:0 12px;vertical-align:.14em}
.ov-evi-big .down{color:#eda28d}
.ov-evi-note{font-size:12.5px;color:#7f948a;line-height:1.9;margin-bottom:22px}
.ov-evi-link{color:#6fd8c5!important;text-decoration:none;font-size:13px}
.ov-bound{border-top:1px solid #152721;padding-top:18px;margin-top:6px}
.ov-bound-t{font-size:15px;font-weight:650;color:#e9f1ec;margin-bottom:6px}
.ov-stat{display:grid;grid-template-columns:1fr 1fr;border-top:1px solid #1c3129;margin-top:64px}
.ov-stat div{padding:30px 20px 30px 0}
.ov-stat div:last-child{border-left:1px solid #152721;padding-left:44px}
.ov-stat span{display:block;font-size:11px;letter-spacing:.2em;color:#7f948a;margin-bottom:14px}
.ov-stat b{display:block;font-family:Georgia,serif;font-variant-numeric:tabular-nums;font-size:38px;font-weight:500;color:#e9f1ec;line-height:1;letter-spacing:.01em}
.ov-foot{margin-top:56px;border-top:1px solid #1c3129;padding-top:18px;display:flex;justify-content:space-between;gap:30px;flex-wrap:wrap}
.ov-foot p{font-size:12.5px;color:#5c7168;line-height:1.9;margin:0;max-width:680px}
.ov-foot a{color:#7f948a!important;text-decoration:none;font-size:12.5px;white-space:nowrap}

/* ---------- 入场动效 ---------- */
@keyframes ov-rise{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:none}}
@keyframes ov-fade{from{opacity:0}to{opacity:1}}
.ov-hero{animation:ov-fade .9s ease both}
.ov-copy .ov-kicker{animation:ov-rise .7s .2s cubic-bezier(.22,1,.36,1) both}
.ov-title{animation:ov-rise .8s .35s cubic-bezier(.22,1,.36,1) both}
.ov-sub{animation:ov-rise .8s .55s cubic-bezier(.22,1,.36,1) both}
.ov-net{animation:ov-fade .8s .7s ease both}
.ov-legend{animation:ov-fade .8s .85s ease both}
.ov-board .ov-h{animation:ov-rise .7s .2s cubic-bezier(.22,1,.36,1) both}
.ov-board .ov-h-sub{animation:ov-rise .7s .3s cubic-bezier(.22,1,.36,1) both}
.ov-evi-label{animation:ov-rise .7s .4s cubic-bezier(.22,1,.36,1) both}
.ov-evi-big{animation:ov-rise .8s .55s cubic-bezier(.22,1,.36,1) both}

@media(max-width:960px){
  .ov-hero{margin:0 -20px;height:64vh}
  .ov-copy{left:22px;right:22px;bottom:30px}
  .ov-legend{display:none}
  .ov-net{right:22px}
  .ov-board{grid-template-columns:1fr;gap:40px}
  .ov-act{grid-column:2;text-align:left}
}
</style>
"""


GUIZHOU_BOUNDS = (103.8, 24.7, 108.9, 28.9)  # lon_min, lat_min, lon_max, lat_max


_RIVERS = ["北盘江", "清水江", "乌江", "六冲河", "三岔河", "猫跳河", "舞阳河", "重安江",
           "洛泽河", "洪渡河", "芙蓉江", "打邦河", "羊昌河", "南明河", "偏岩河", "都柳江",
           "樟江", "蒙江", "格凸河", "响水河", "巴拉河", "锦江", "瓮安河", "草海河"]
_ROUTES = ["G60 沪昆通道", "G75 兰海通道", "G76 厦蓉通道", "G56 杭瑞通道", "G69 银百通道", "G6921 都香通道"]
# (桥型, 主跨范围 m, 权重)——悬索/斜拉稀少，普通梁桥占多数，符合真实构成
_BRIDGE_TYPES = [("悬索桥", (600, 1400), 2), ("斜拉桥", (300, 620), 3),
                 ("拱桥", (180, 450), 8), ("连续刚构", (120, 300), 20), ("箱梁桥", (60, 130), 40)]


def _bridge_meta(rng, status, on_road, road_idx):
    """确定性生成一座桥的档案：名称 / 桥型 / 主跨 / 通车年 / 脉冲 / 穿越次数。"""
    types, weights = [t[0] for t in _BRIDGE_TYPES], [t[2] for t in _BRIDGE_TYPES]
    tname, (lo, hi), _ = _BRIDGE_TYPES[rng.choice(len(types), p=np.array(weights) / sum(weights))]
    span = int(round(rng.uniform(lo, hi), 0))
    river = _RIVERS[int(rng.integers(len(_RIVERS)))]
    name = f"{river}{'特大桥' if span >= 300 else '大桥'}"
    freq = round(rng.uniform(3.5, 12.0), 2)
    crossings = int(rng.integers(18, 96)) if status == "shift" else int(rng.integers(6, 64))
    return {
        "name": name, "type": tname, "span_m": span,
        "year": int(rng.integers(1996, 2024)),
        "route": _ROUTES[road_idx] if on_road else "省道联络线",
        "freq": freq, "crossings30d": crossings,
    }


def _densify_road(pts, seg=26, wobble=0.022, seed=0):
    """Catmull-Rom 样条加密 + 低频蜿蜒扰动：稀疏控制点干线 → 自然弯折的山地公路。"""
    rng = np.random.default_rng(seed)
    p = np.asarray(pts, dtype=float)
    ext = np.vstack([p[0] + (p[0] - p[1]), p, p[-1] + (p[-1] - p[-2])])
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for t in np.linspace(0.0, 1.0, seg, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append([
                0.5 * (2 * p1[0] + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3),
                0.5 * (2 * p1[1] + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3),
            ])
    a = np.asarray(out + [p[-1].tolist()])
    tang = np.gradient(a, axis=0)
    norm = np.stack([-tang[:, 1], tang[:, 0]], axis=1)
    ln = np.linalg.norm(norm, axis=1, keepdims=True)
    norm = np.divide(norm, ln, out=np.zeros_like(norm), where=ln > 0)
    for k in (2, 3, 5):  # 多频正弦蜿蜒，模拟喀斯特山地展线
        amp = wobble / (k ** 0.5)
        a = a + norm * (np.sin(np.linspace(0, 2 * np.pi * k, len(a)) + rng.uniform(0, 2 * np.pi)) * amp)[:, None]
    return [[round(x, 4), round(y, 4)] for x, y in a]


@st.cache_data(show_spinner=False)
def _map_data():
    """确定性生成 128 座桥的模拟感知网络（11 偏移 / 21 观察 / 96 稳定）与 6 条干线。

    seed 固定，结果确定 → 整体缓存，rerun 不重算。
    每座桥带完整档案（名称/桥型/主跨/通车年/脉冲频率/近30日穿越），
    供地图点击弹窗展示；三座重点桥用真实贵州名桥。
    """
    rng = np.random.default_rng(2026)
    roads = [
        [[104.5, 25.6], [105.3, 26.0], [106.1, 26.5], [106.9, 26.9], [107.7, 27.2], [108.6, 27.0]],
        [[105.6, 27.9], [106.0, 27.3], [106.5, 26.7], [107.0, 26.1], [107.4, 25.5]],
        [[104.7, 26.7], [105.5, 26.4], [106.3, 26.1], [107.1, 25.8], [107.9, 25.5]],
        [[104.3, 27.3], [105.1, 27.0], [105.9, 26.7], [106.7, 26.4], [107.5, 26.1]],
        [[104.9, 25.0], [105.7, 25.2], [106.5, 25.4], [107.3, 25.6], [108.1, 25.4]],
        [[106.2, 28.3], [106.6, 27.7], [107.0, 27.1], [107.4, 26.5], [107.8, 25.9]],
    ]
    features = [
        {"type": "Feature", "properties": {
            "id": "GZ-017", "status": "shift", "name": "坝陵河大桥", "type": "悬索桥",
            "span_m": 1088, "year": 2009, "route": "G60 沪昆通道", "freq": 7.22, "crossings30d": 87},
         "geometry": {"type": "Point", "coordinates": [106.92, 26.56]}},
        {"type": "Feature", "properties": {
            "id": "GZ-042", "status": "watch", "name": "六广河大桥", "type": "斜拉桥",
            "span_m": 480, "year": 2002, "route": "G75 兰海通道", "freq": 9.14, "crossings30d": 46},
         "geometry": {"type": "Point", "coordinates": [106.71, 27.02]}},
        {"type": "Feature", "properties": {
            "id": "GZ-008", "status": "normal", "name": "乌江特大桥", "type": "连续刚构",
            "span_m": 288, "year": 1998, "route": "G76 厦蓉通道", "freq": 6.49, "crossings30d": 31},
         "geometry": {"type": "Point", "coordinates": [105.98, 26.25]}},
    ]
    taken = {8, 17, 42}
    n = 0
    for status, count in (("shift", 10), ("watch", 20), ("normal", 95)):
        for _ in range(count):
            n += 1
            while n in taken:
                n += 1
            on_road = rng.random() < 0.72  # 多数桥梁沿干线分布
            road_idx = int(rng.integers(len(roads)))
            if on_road:
                road = roads[road_idx]
                seg = int(rng.integers(len(road) - 1))
                u = rng.uniform(0.06, 0.94)
                lon = road[seg][0] + (road[seg + 1][0] - road[seg][0]) * u + rng.normal(0, 0.07)
                lat = road[seg][1] + (road[seg + 1][1] - road[seg][1]) * u + rng.normal(0, 0.07)
            else:
                lon = rng.uniform(104.2, 108.6)
                lat = rng.uniform(25.0, 28.5)
            props = {"id": f"GZ-{n:03d}", "status": status}
            props.update(_bridge_meta(rng, status, on_road, road_idx))
            features.append({
                "type": "Feature", "properties": props,
                "geometry": {"type": "Point", "coordinates": [round(lon, 3), round(lat, 3)]},
            })
    bridges_fc = {"type": "FeatureCollection", "features": features}
    roads_fc = {"type": "FeatureCollection",
                "features": [{"type": "Feature", "geometry": {"type": "LineString", "coordinates": _densify_road(r, seed=i)}}
                             for i, r in enumerate(roads)]}
    return bridges_fc, roads_fc


def _fallback_dots(bridges_fc):
    """离线 SVG：把全部桥梁按经纬度投影进 900x480 画布。"""
    lon0, lat0, lon1, lat1 = GUIZHOU_BOUNDS
    parts = []
    for f in bridges_fc["features"]:
        lon, lat = f["geometry"]["coordinates"]
        x = (lon - lon0) / (lon1 - lon0) * 860 + 20
        y = (lat1 - lat) / (lat1 - lat0) * 430 + 25
        status = f["properties"]["status"]
        color = {"shift": "#e07a62", "watch": "#d9b46e", "normal": "#6fd8c5"}[status]
        key = f["properties"]["id"] in ("GZ-017", "GZ-042", "GZ-008")
        parts.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{5 if key else 3}" fill="{color}" '
                     f'opacity="{".95" if key or status != "normal" else ".5"}"/>')
        if status == "shift":
            parts.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="10" fill="none" stroke="#e07a62" '
                         f'stroke-width="1.2" opacity=".45"/>')
    return "".join(parts)


def _map_iframe():
    """MapLibre 深色地图（OpenFreeMap 矢量深色样式，免费无 key，任意缩放保持锐利）：128 座桥梁全网上图，离线时显示 SVG fallback。"""
    bridges_fc, roads_fc = _map_data()
    template = '''<!doctype html><html><head><meta charset="utf-8"><style>__MLGL_CSS__</style><style>html,body,#map{margin:0;width:100%;height:100%;background:#081010}.fallback{display:none;position:absolute;inset:0;padding:26px;background:#081010}
.pulse{width:16px;height:16px;border-radius:50%;border:2px solid #e07a62;opacity:.85;pointer-events:none}
@keyframes pulse{0%{transform:scale(.35);opacity:.9}100%{transform:scale(3.4);opacity:0}}
.pulse{animation:pulse 2.6s cubic-bezier(.2,.6,.4,1) infinite}
.zoomctl{position:absolute;top:16px;right:16px;z-index:5;display:flex;flex-direction:column;gap:6px}
.zoomctl button{width:34px;height:34px;border-radius:10px;border:1px solid rgba(111,216,197,.28);background:rgba(8,16,13,.85);color:#6fd8c5;font:400 19px/1 -apple-system,sans-serif;cursor:pointer;backdrop-filter:blur(8px);transition:all .15s;padding:0}
.zoomctl button:hover{background:rgba(111,216,197,.16);border-color:rgba(111,216,197,.55)}
.zoomctl button:active{transform:scale(.93)}
/* 点击桥梁点的档案弹窗（覆盖 MapLibre 默认白底） */
.maplibregl-popup-content{background:#0f1b16!important;border:1px solid #2a4536!important;border-radius:12px!important;box-shadow:0 18px 50px rgba(0,0,0,.6)!important;padding:14px 16px!important;color:#e9f1ec!important}
.maplibregl-popup-tip{border-top-color:#2a4536!important;border-bottom-color:#2a4536!important}
.maplibregl-popup-close-button{color:#7f948a!important;font-size:15px!important;right:6px!important;top:4px!important}
.pp{min-width:218px;font:12px/1.5 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}
.pp-head{display:flex;align-items:baseline;gap:8px;margin-bottom:3px}
.pp-head b{font-size:14.5px;color:#e9f1ec}
.pp-head span{font-size:10px;color:#7f948a;letter-spacing:.08em}
.pp-status{font-size:11px;font-weight:600;margin-bottom:9px}
.pp-grid{display:grid;grid-template-columns:auto 1fr auto 1fr;gap:4px 10px;font-size:11px}
.pp-grid span{color:#5c7168}
.pp-grid b{color:#b9c8c0;font-weight:600;text-align:right;font-variant-numeric:tabular-nums}
.pp-action{margin-top:9px;padding-top:8px;border-top:1px solid #1c3129;color:#8ba69a;font-size:10.5px}
.pp-link{display:block;margin-top:9px;padding-top:8px;border-top:1px solid #1c3129;color:#6fd8c5!important;text-decoration:none;font-size:11px;font-weight:600;letter-spacing:.02em}
.pp-link:hover{color:#9ee8da}
/* 弹窗必须浮在暗角之上 */
.maplibregl-popup{z-index:8!important}
/* 桥梁标签徽章化：深色胶囊 + 青绿描边 + 微光 */
.blab{display:inline-flex;align-items:center;gap:5px;padding:3.5px 9px 3px 6.5px;border-radius:999px;background:rgba(8,16,13,.88);border:1px solid rgba(111,216,197,.42);backdrop-filter:blur(4px);pointer-events:none;white-space:nowrap;box-shadow:0 2px 12px rgba(0,0,0,.55),0 0 14px rgba(111,216,197,.14),0 1px 0 rgba(233,241,236,.12) inset}
.blab i{width:5px;height:5px;border-radius:50%;flex:none;box-shadow:0 0 6px currentColor}
.blab b{font:600 10.5px -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;letter-spacing:.1em;color:#eef6f2;text-shadow:0 0 8px rgba(0,0,0,.6)}
/* 通道名标注：细字 + 虚线引导 */
.rlab{font:500 10px -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;color:#7fa598;letter-spacing:.14em;text-shadow:0 0 6px rgba(0,0,0,.9);pointer-events:none;white-space:nowrap;opacity:.85}
/* 加载态：接入感知网络 */
.boot{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;background:#081010;z-index:9;transition:opacity .5s}
.boot.off{opacity:0;pointer-events:none}
.boot .ring{width:44px;height:44px;border-radius:50%;border:2px solid rgba(111,216,197,.18);border-top-color:#6fd8c5;animation:spin 1s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.boot span{font:600 11px -apple-system,sans-serif;letter-spacing:.3em;color:#7f948a}
/* 首次操作引导：运镜结束后浮现，数秒后自动淡出，任何交互立即消失 */
.hint{position:absolute;left:50%;bottom:18px;transform:translateX(-50%) translateY(6px);z-index:6;display:flex;gap:16px;padding:9px 18px;border-radius:999px;background:rgba(8,16,13,.8);border:1px solid rgba(111,216,197,.22);backdrop-filter:blur(10px);box-shadow:0 8px 26px rgba(0,0,0,.45);opacity:0;pointer-events:none;transition:opacity .6s ease,transform .6s ease;font:500 11px -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;color:#a9bcb2;white-space:nowrap}
.hint.show{opacity:1;transform:translateX(-50%) translateY(0)}
.hint span{display:flex;align-items:center;gap:6px}
.hint svg{width:13px;height:13px;flex:none;stroke:#6fd8c5;fill:none;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
@media(max-width:900px){.hint{gap:9px;padding:7px 13px;font-size:10px;max-width:calc(100% - 40px)}}
/* 状态筛选条：顶部悬浮玻璃（避开 hero 左下文案区） */
.fbar{position:absolute;left:50%;top:16px;transform:translateX(-50%);z-index:6;display:flex;gap:8px;padding:8px 10px;border-radius:14px;background:rgba(8,16,13,.82);border:1px solid rgba(111,216,197,.2);backdrop-filter:blur(10px);box-shadow:0 10px 34px rgba(0,0,0,.5)}
.fbtn{display:flex;align-items:center;gap:7px;padding:7px 13px;border-radius:9px;border:1px solid transparent;background:transparent;color:#a9bcb2;font:600 11.5px -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;cursor:pointer;transition:all .18s;white-space:nowrap}
.fbtn i{width:7px;height:7px;border-radius:50%;background:var(--c);box-shadow:0 0 8px var(--c);transition:opacity .18s}
.fbtn b{font-weight:650;color:#e9f1ec;font-variant-numeric:tabular-nums}
.fbtn small{color:#5c7168;font-size:10px}
.fbtn:hover{background:rgba(255,255,255,.05)}
.fbtn.on{background:rgba(255,255,255,.055);border-color:rgba(255,255,255,.14)}
.fbtn:not(.on) i{opacity:.25;box-shadow:none}
.fbtn:not(.on){color:#5c7168}
.fbtn:not(.on) b{color:#7f948a}
/* 图例计数徽章 + 实时穿越动态（左上信息区） */
.mcount{position:absolute;left:18px;top:16px;z-index:5;font:600 10.5px -apple-system,sans-serif;letter-spacing:.18em;color:#7f948a;text-shadow:0 1px 8px rgba(0,0,0,.95)}
.feed{position:absolute;left:18px;top:38px;z-index:5;max-width:264px}
.feed-it{display:flex;align-items:center;gap:10px;padding:8px 13px;border-radius:10px;background:rgba(8,16,13,.76);border:1px solid rgba(111,216,197,.16);backdrop-filter:blur(8px);box-shadow:0 6px 22px rgba(0,0,0,.45);animation:feedin .55s cubic-bezier(.22,1,.36,1) both}
.feed-it i{width:6px;height:6px;border-radius:50%;flex:none;box-shadow:0 0 8px currentColor}
.feed-it b{display:block;font:650 11px -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;color:#dfe7e2;letter-spacing:.02em}
.feed-it span{display:block;font:400 9.5px -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;color:#7f948a;margin-top:1px;letter-spacing:.03em}
@keyframes feedin{from{opacity:0;transform:translateY(7px)}to{opacity:1;transform:none}}
/* 电影感：边缘暗角 + 上下雾化，让地图与页面暮色背景融为一体 */
#vig{position:absolute;inset:0;pointer-events:none;z-index:4;background:radial-gradient(130% 95% at 50% 42%,transparent 52%,rgba(5,11,9,.5) 100%),linear-gradient(180deg,rgba(5,11,9,.4),transparent 19%,transparent 76%,rgba(5,11,9,.6))}
/* 城市锚点：细环 + 细字，省会略放大 */
.city{display:flex;align-items:center;gap:6px;pointer-events:none;white-space:nowrap}
.city i{width:5px;height:5px;border-radius:50%;border:1px solid #8ba69a;background:rgba(20,34,29,.9);box-shadow:0 0 9px rgba(139,166,154,.4);flex:none}
.city b{font:500 10px -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;color:#93a89d;letter-spacing:.16em;text-shadow:0 0 8px rgba(0,0,0,.95)}
.city.cap i{width:7px;height:7px;border-color:#c3d4cb}
.city.cap b{font-size:11.5px;color:#c9d6ce;letter-spacing:.22em}
/* 车辆：带航向的流光胶囊 */
.veh{width:3.5px;height:11px;border-radius:2px;background:linear-gradient(180deg,#eef8f3,#9fe8d8);box-shadow:0 0 10px 2px rgba(111,216,197,.5);pointer-events:none}
/* 悬停迷你档案 */
.tip .maplibregl-popup-content{background:rgba(9,17,14,.94)!important;border:1px solid rgba(111,216,197,.3)!important;border-radius:9px!important;box-shadow:0 10px 30px rgba(0,0,0,.55)!important;padding:6px 11px!important}
.tip .maplibregl-popup-tip{border:none!important;background:transparent!important}
.tip-in{display:flex;align-items:center;gap:8px;font:650 11px -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;color:#e5eee9;white-space:nowrap}
.tip-in i{width:6px;height:6px;border-radius:50%;flex:none;box-shadow:0 0 7px currentColor}
.tip-in span{color:#7f948a;font-weight:500;font-size:10px;letter-spacing:.06em}
.attrib{position:absolute;right:18px;bottom:18px;z-index:5;font:400 9.5px -apple-system,sans-serif;color:#46585033;text-shadow:0 1px 6px rgba(0,0,0,.8)}
.attrib a{color:#4d6058;text-decoration:none}
.attrib a:hover{color:#7f948a}
@media(max-width:900px){.fbar{top:10px;gap:4px;padding:6px 8px;max-width:calc(100% - 84px);flex-wrap:wrap;justify-content:center;border-radius:11px}.fbtn{padding:5px 9px;font-size:10.5px;gap:5px}.fbtn small{display:none}.feed{display:none}}
</style></head><body><div id="map"></div><div id="vig"></div><div class="boot" id="boot"><div class="ring"></div><span>正在接入感知网络</span></div><div class="zoomctl" id="zoomctl" style="display:none"><button id="zin" aria-label="放大">+</button><button id="zout" aria-label="缩小">−</button></div><div class="fbar" id="fbar" style="display:none"><button class="fbtn on" data-st="shift" style="--c:#e07a62"><i></i>响应偏移 <b>11</b></button><button class="fbtn on" data-st="watch" style="--c:#d9b46e"><i></i>持续观察 <b>21</b></button><button class="fbtn on" data-st="normal" style="--c:#6fd8c5"><i></i>状态稳定 <b>96</b></button></div><div class="mcount" id="mcount" style="display:none">感知网络 · 128 桥在线</div><div class="feed" id="feed" style="display:none"></div><div class="hint" id="hint"><span><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 8v.01M12 11v5"/></svg>悬停看桥名</span><span><svg viewBox="0 0 24 24"><path d="M9 11.5V21l3-2 3 2v-9.5a5.5 5.5 0 1 0-6 0z"/></svg>点击看档案</span><span><svg viewBox="0 0 24 24"><path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="1.8" fill="#e07a62"/><circle cx="15" cy="12" r="1.8" fill="#d9b46e"/><circle cx="7" cy="18" r="1.8" fill="#6fd8c5"/></svg>顶部按状态筛选</span><span><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3M11 8v6M8 11h6"/></svg>右侧按钮缩放</span></div><div class="attrib" id="attrib" style="display:none"><a href="https://openfreemap.org" target="_blank">© OpenFreeMap</a></div><div class="fallback"><b style="color:#6fd8c5;font:600 11px -apple-system,sans-serif;letter-spacing:.2em">贵州桥梁动态感知网络 · 离线示意 · 128 座</b><svg viewBox="0 0 900 480" style="width:100%;height:calc(100% - 30px);margin-top:10px"><path d="M70 70 L210 30 360 62 500 20 690 70 820 145 770 300 650 390 470 450 290 410 120 330z" fill="#0f1b16" stroke="#1c3129"/><path d="M105 110 C260 40 420 100 565 55 S760 100 795 175 S690 300 550 275 S280 340 115 255 M120 145 C285 80 410 145 545 100 S720 135 760 195 S660 265 535 245 S300 305 145 220" fill="none" stroke="#1c3129"/><path d="M95 300 C205 260 280 170 400 190 S560 300 690 235 S780 160 840 130 M160 90 C260 145 330 195 420 190 S600 130 770 170" fill="none" stroke="#3f7a67" stroke-width="1.6" stroke-dasharray="5 6"/><path d="M120 350 C250 310 290 235 390 255 S520 350 610 300 S720 210 820 225" fill="none" stroke="#275244" stroke-width="2"/>__FALLBACK_DOTS__<circle cx="170" cy="278" r="4" fill="#e9f1ec"><animateMotion dur="7s" repeatCount="indefinite" path="M0,0 C40,-30 120,-60 260,-88"/></circle><circle cx="260" cy="143" r="4" fill="#e9f1ec"><animateMotion dur="9s" begin="-3s" repeatCount="indefinite" path="M0,0 C60,20 140,35 300,47"/></circle><circle cx="360" cy="280" r="4" fill="#e9f1ec"><animateMotion dur="8s" begin="-5s" repeatCount="indefinite" path="M0,0 C80,-20 180,-55 320,-85"/></circle></svg></div><script>__MLGL_JS__</script><script>
const bridges=__BRIDGES__;
const roads=__ROADS__;
// 状态计数从数据实时统计，不写死
const COUNTS=bridges.features.reduce((m,f)=>{const s=f.properties.status;m[s]=(m[s]||0)+1;return m},{});
const TOTAL=bridges.features.length;
const colors={shift:"#e07a62",watch:"#d9b46e",normal:"#6fd8c5"};
const KEYS=new Set(["GZ-017","GZ-042","GZ-008"]);
const CITIES=[["贵阳",106.63,26.65,1],["遵义",106.93,27.73,0],["六盘水",104.83,26.60,0],["安顺",105.93,26.25,0],["毕节",105.29,27.28,0],["兴义",104.90,25.09,0],["都匀",107.52,26.26,0],["凯里",107.98,26.58,0],["铜仁",109.19,27.72,0]];
function killBoot(){const b=document.getElementById('boot');if(b)b.classList.add('off')}
function fallback(){killBoot();document.querySelector('.fallback').style.display='block';document.getElementById('map').style.display='none';document.getElementById('zoomctl').style.display='none'}
function init(){if(!window.maplibregl){fallback();return}
// 样式预检：先 fetch 样式 JSON（拿不到/CORS 失败立即降级），成功后以样式对象建图（省一次请求）。
// 瓦片偶发失败不再触发降级——底图能画多少画多少，总比整体回退到示意图强。
fetch('__STYLE_URL__').then(function(r){if(!r.ok)throw new Error('style '+r.status);return r.json()})
.then(function(st){
const map=new maplibregl.Map({container:'map',center:[106.92,26.56],zoom:7.2,attributionControl:false,style:st});
window.__map=map;
const styleTimer=setTimeout(fallback,15000); // 样式已就绪后仍长时间无渲染才降级
map.on('styledata',function(){clearTimeout(styleTimer)}); // 样式验证通过即认为底图会渲染
map.scrollZoom.disable();
document.getElementById('zin').onclick=()=>map.zoomIn({duration:320});
document.getElementById('zout').onclick=()=>map.zoomOut({duration:320});
map.on('load',()=>{
clearTimeout(styleTimer);
document.getElementById('map').style.display='block';document.querySelector('.fallback').style.display='none';
document.getElementById('zoomctl').style.display='flex';
document.getElementById('fbar').style.display='flex';
// 徽章计数与总数字从注入数据回填，与 _map_data 永远一致
document.querySelectorAll('.fbtn').forEach(btn=>{const b=btn.querySelector('b');if(b)b.textContent=COUNTS[btn.dataset.st]||0});
document.getElementById('mcount').textContent='感知网络 · '+TOTAL+' 桥在线';
document.getElementById('mcount').style.display='block';
document.getElementById('feed').style.display='block';
document.getElementById('attrib').style.display='block';
setTimeout(killBoot,350);
// 底图品牌化：背景/水体统一为青绿暮色系
try{
map.setPaintProperty('background','background-color','#0a1210');
map.setPaintProperty('water','fill-color','#0c2019');
map.setPaintProperty('waterway','line-color','#143128');
}catch(e){}
// 隐藏底图自带地名（改用自绘城市锚点体系，字体与全站设计语言一致）
['place_city_large','place_city','place_town','place_village','place_suburb','place_other','place_state','place_country_other','place_country_minor','place_country_major','water_name'].forEach(id=>{try{map.setLayoutProperty(id,'visibility','none')}catch(e){}});
// 城市锚点：细环 + 细字，省会略放大
CITIES.forEach(c=>{
const el=document.createElement('div');el.className='city'+(c[3]?' cap':'');
el.innerHTML='<i></i><b>'+c[0]+'</b>';
const m=new maplibregl.Marker({element:el}).setLngLat([c[1],c[2]]).addTo(map);
el.style.transform='translate(7px,-50%)'});
// ---- 开场自动导览：地图自己"演"一遍全部交互，评委零操作也能看到 ----
const hintEl=document.getElementById('hint');
const hintKill=()=>hintEl.classList.remove('show');
const ALL=['shift','watch','normal'];
const baseOpacity=['match',['get','status'],'shift',1,'watch',.95,.8];
const tourPopup=new maplibregl.Popup({closeButton:false,offset:10,maxWidth:"300px"});
let tourAlive=true;
function killTour(){
if(!tourAlive)return;tourAlive=false;
tourPopup.remove();
try{applyFilter()}catch(e){setStatusFilter(ALL)} // 与当前筛选按钮的实际状态对齐
try{map.setPaintProperty('bridge-points','circle-opacity',baseOpacity)}catch(e){}
}
map.on('mousedown',killTour);
map.on('dragstart',killTour);
map.on('wheel',killTour);
document.getElementById('zin').addEventListener('click',killTour);
document.getElementById('zout').addEventListener('click',killTour);
document.querySelectorAll('.fbtn').forEach(btn=>btn.addEventListener('click',killTour));
const step=(ms,fn)=>setTimeout(()=>{if(tourAlive)fn()},ms);
// 幕一：拉出全省 + 桥梁三波点亮（稳定 → 观察 → 偏移）
map.fitBounds([[103.8,24.9],[108.9,28.8]],{padding:12,duration:3000,easing:t=>1-Math.pow(1-t,3)});
setStatusFilter([]);
step(400,()=>setStatusFilter(['normal']));
step(1150,()=>setStatusFilter(['normal','watch']));
step(1950,()=>setStatusFilter(ALL));
// 幕二：聚焦坝陵河大桥，自动弹出档案，其余桥暗化为背景
step(3400,()=>map.flyTo({center:[106.92,26.56],zoom:8.7,duration:1500}));
step(5000,()=>{
try{map.setPaintProperty('bridge-points','circle-opacity',.15)}catch(e){}
const f=bridges.features.filter(x=>x.properties.id==='GZ-017')[0];
tourPopup.setLngLat(f.geometry.coordinates).setHTML(bridgePopupHTML(f.properties)).addTo(map)});
step(8600,()=>{
tourPopup.remove();
try{map.setPaintProperty('bridge-points','circle-opacity',baseOpacity)}catch(e){}
map.fitBounds([[103.8,24.9],[108.9,28.8]],{padding:12,duration:1100})});
// 幕三：自动演示筛选——96 座稳定桥淡出，只剩需要关注的桥
step(10100,()=>{
stateOn.normal=false;
document.querySelector('.fbtn[data-st="normal"]').classList.remove('on');
applyFilter()});
step(12400,()=>{
stateOn.normal=true;
document.querySelector('.fbtn[data-st="normal"]').classList.add('on');
applyFilter()});
// 收尾：全部能力演完，操作提示最后浮现兜底
step(13200,()=>hintEl.classList.add('show'));
setTimeout(hintKill,23000);
map.addSource('roads',{type:'geojson',data:roads});
// 路网三层：宽发光晕 → 亮主线 → 节奏虚线，"光脉"感
map.addLayer({id:'roads-glow',type:'line',source:'roads',paint:{'line-color':'#6fd8c5','line-width':10,'line-opacity':.13,'line-blur':4}});
map.addLayer({id:'roads-glow2',type:'line',source:'roads',paint:{'line-color':'#8fe3d0','line-width':4.5,'line-opacity':.14,'line-blur':1.5}});
map.addLayer({id:'roads-base',type:'line',source:'roads',paint:{'line-color':'#4a9683','line-width':2.2,'line-opacity':.55}});
map.addLayer({id:'roads',type:'line',source:'roads',paint:{'line-color':'#a9f0e0','line-width':1.2,'line-opacity':.9,'line-dasharray':[2.5,2.5]}});
// 光脉流动：虚线相位循环推进，路网像血管一样输送"脉搏"
const dashSeq=[[0,4,3],[0.5,4,2.5],[1,4,2],[1.5,4,1.5],[2,4,1],[2.5,4,0.5],[3,4,0],[0,0.5,3,3.5],[0,1,3,3],[0,1.5,3,2.5],[0,2,3,2],[0,2.5,3,1.5],[0,3,3,1],[0,3.5,3,0.5]];
let dashIdx=0;
setInterval(()=>{dashIdx=(dashIdx+1)%dashSeq.length;try{map.setPaintProperty('roads','line-dasharray',dashSeq[dashIdx])}catch(e){}},70);
map.addSource('bridges',{type:'geojson',data:bridges});
map.addLayer({id:'bridge-halo',type:'circle',source:'bridges',filter:['==',['get','status'],'shift'],paint:{'circle-radius':14,'circle-color':'#e07a62','circle-opacity':.14}});
map.addLayer({id:'bridge-glow',type:'circle',source:'bridges',paint:{'circle-radius':7,'circle-color':['match',['get','status'],'shift','#e07a62','watch','#d9b46e','#6fd8c5'],'circle-opacity':.22,'circle-blur':1}});
map.addLayer({id:'bridge-ring',type:'circle',source:'bridges',filter:['in',['get','status'],['literal',['shift','watch']]],paint:{'circle-radius':8.5,'circle-color':'transparent','circle-stroke-color':['match',['get','status'],'shift','#e07a62','#d9b46e'],'circle-stroke-width':1.5,'circle-stroke-opacity':.5}});
map.addLayer({id:'bridge-points',type:'circle',source:'bridges',paint:{'circle-radius':['match',['get','status'],'shift',5,'watch',4.2,3.4],'circle-color':['match',['get','status'],'shift','#e07a62','watch','#d9b46e','#6fd8c5'],'circle-opacity':['match',['get','status'],'shift',1,'watch',.95,.8],'circle-stroke-color':'#081010','circle-stroke-width':1.5}});
// 状态筛选状态先声明（标签可见性依赖它）
const stateOn={shift:true,watch:true,normal:true};
function refreshLabels(){
const show=map.getZoom()>=7.6; // 高缩放渐进披露：其余偏移桥桥名逐一点亮
document.querySelectorAll('.blab').forEach(el=>{
const zoomable=el.classList.contains('zoomable');
el.style.visibility=(stateOn[el.dataset.st]&&(!zoomable||show))?'visible':'hidden'});
document.querySelectorAll('.pulse').forEach(el=>{
el.style.visibility=stateOn[el.dataset.st]?'visible':'hidden'});
}
// 重点桥徽章常显；其余偏移桥徽章随缩放渐进出现
bridges.features.forEach(f=>{
const p=f.properties;
const wantLabel=KEYS.has(p.id)||p.status==='shift';
if(!wantLabel)return;
const el=document.createElement('div');el.className='blab'+(KEYS.has(p.id)?'':' zoomable');el.dataset.st=p.status;
el.innerHTML='<i style="background:'+colors[p.status]+'"></i><b>'+p.name+'</b>';
new maplibregl.Marker({element:el}).setLngLat(f.geometry.coordinates).addTo(map);
el.style.transform='translate(14px,-50%)'});
refreshLabels();
map.on('zoomend',refreshLabels);
bridges.features.forEach(f=>{
if(f.properties.status!=='shift')return;
const p=document.createElement('div');p.className='pulse';p.dataset.st='shift';
new maplibregl.Marker({element:p}).setLngLat(f.geometry.coordinates).addTo(map)});
// 通道名标注：每条干线中点放一枚细字标签
const routeNames=["G60 沪昆","G75 兰海","G76 厦蓉","G56 杭瑞","G69 银百","G6921 都香"];
roads.features.forEach((f,i)=>{
const c=f.geometry.coordinates,mid=c[Math.floor(c.length/2)];
const el=document.createElement('div');el.className='rlab';el.textContent=routeNames[i]||'';
new maplibregl.Marker({element:el}).setLngLat(mid).addTo(map)});
// 状态筛选：按状态过滤桥点/光晕/环层/辉光 + 徽章 & 脉冲 marker
function setStatusFilter(list){
const f=list.length?['in',['get','status'],['literal',list]]:['==',['get','status'],'__none__'];
map.setFilter('bridge-points',f);
map.setFilter('bridge-glow',f);
map.setFilter('bridge-ring',['all',f,['in',['get','status'],['literal',['shift','watch']]]]);
map.setFilter('bridge-halo',['all',f,['==',['get','status'],'shift']]);
}
function applyFilter(){
setStatusFilter(Object.keys(stateOn).filter(k=>stateOn[k]));
const vis=Object.keys(stateOn).filter(k=>stateOn[k]);
const total=vis.reduce((s,k)=>s+(COUNTS[k]||0),0);
document.getElementById('mcount').textContent='感知网络 · '+total+' 桥在线';
refreshLabels()}
document.querySelectorAll('.fbtn').forEach(btn=>{
btn.onclick=()=>{const st=btn.dataset.st;stateOn[st]=!stateOn[st];btn.classList.toggle('on',stateOn[st]);applyFilter()}});
// 实时穿越动态：左上角滚动播报"车流即观测网"的现场感
const feedEl=document.getElementById('feed');
const feedPool=bridges.features.flatMap(f=>f.properties.status==='shift'?[f,f,f]:f.properties.status==='watch'?[f,f]:[f]);
let feedIdx=0;
function pushFeed(){
const p=feedPool[feedIdx++%feedPool.length].properties,c=colors[p.status];
feedEl.innerHTML='<div class="feed-it"><i style="background:'+c+';color:'+c+'"></i><div><b>'+p.name+'</b><span>刚刚完成穿越 · 30日累计 '+p.crossings30d+' 次</span></div></div>'}
pushFeed();setInterval(pushFeed,3400);
// 呼吸光晕：偏移桥的 halo 半径/透明度正弦呼吸
map.setPaintProperty('bridge-halo','circle-radius',14);
let h0=null;
function breathe(ts){
if(h0===null)h0=ts;
const u=(Math.sin((ts-h0)/1600)+1)/2; // 0→1→0
try{
map.setPaintProperty('bridge-halo','circle-radius',10+u*8);
map.setPaintProperty('bridge-halo','circle-opacity',.08+u*.14);
}catch(e){}
requestAnimationFrame(breathe)}
requestAnimationFrame(breathe);
const lerp=(a,b,u)=>a+(b-a)*u;
function addVehicle(road,dur,delay){
const dot=document.createElement('div');dot.className='veh';
const v=new maplibregl.Marker({element:dot,rotationAlignment:'map'}).setLngLat(road[0]).addTo(map);
let t0=null;function step(ts){if(!t0)t0=ts+delay;const total=road.length-1,u=(Math.max(ts-t0,0)%dur)/dur,p=u*total,i=Math.min(Math.floor(p),total-1),f=p-i;
v.setLngLat([lerp(road[i][0],road[i+1][0],f),lerp(road[i][1],road[i+1][1],f)]);
v.setRotation(Math.atan2(road[i+1][0]-road[i][0],road[i+1][1]-road[i][1])*180/Math.PI);
requestAnimationFrame(step)}
requestAnimationFrame(step)}
addVehicle(roads.features[0].geometry.coordinates,11000,0);
addVehicle(roads.features[0].geometry.coordinates,15000,-6000);
addVehicle(roads.features[0].geometry.coordinates,17000,-11000);
addVehicle(roads.features[1].geometry.coordinates,12500,-3000);
addVehicle(roads.features[1].geometry.coordinates,16000,-9000);
addVehicle(roads.features[2].geometry.coordinates,14000,-8000);
addVehicle(roads.features[2].geometry.coordinates,17500,-2000);
addVehicle(roads.features[3].geometry.coordinates,13000,-4500);
addVehicle(roads.features[4].geometry.coordinates,15500,-7000);
addVehicle(roads.features[5].geometry.coordinates,14500,-5000);
// 点击桥梁光点 → 档案弹窗；悬停放大 + 迷你档案
const tip=new maplibregl.Popup({closeButton:false,closeOnClick:false,offset:12,className:'tip'});
const stText={shift:"响应偏移",watch:"持续观察",normal:"状态稳定"};
function bridgePopupHTML(p){
const st=stText[p.status];
const act={shift:"脉搏差异超出阈值，建议优先工程复核",watch:"脉搏差异略超阈值，持续采样观察",normal:"脉搏差异低于阈值，维持常规监测"}[p.status];
const link=p.id==="GZ-017"?'<a class="pp-link" href="__APP_ORIGIN__/?view=bridge&bridge=GZ-017" target="_parent">查看完整证据链 →</a>':"";
return '<div class="pp"><div class="pp-head"><b>'+p.name+'</b><span>'+p.id+'</span></div>'+
'<div class="pp-status" style="color:'+colors[p.status]+'">● '+st+' · '+p.route+'</div>'+
'<div class="pp-grid">'+
'<span>桥型</span><b>'+p.type+'</b><span>主跨</span><b>'+p.span_m+' m</b>'+
'<span>通车</span><b>'+p.year+' 年</b><span>桥梁脉冲</span><b>'+p.freq.toFixed(2)+' Hz</b>'+
'<span>近30日穿越</span><b>'+p.crossings30d+' 次</b><span>状态</span><b>'+st+'</b>'+
'</div><div class="pp-action">'+act+'</div>'+link+'</div>'}
map.on('mousemove','bridge-points',e=>{
if(e.features.length){map.getCanvas().style.cursor='pointer';
map.setPaintProperty('bridge-points','circle-radius',['match',['get','status'],'shift',6.4,'watch',5.4,4.4]);
const p=e.features[0].properties,c=colors[p.status];
tip.setLngLat(e.lngLat).setHTML('<div class="tip-in"><i style="background:'+c+';color:'+c+'"></i>'+p.name+'<span>'+stText[p.status]+'</span></div>').addTo(map)}});
map.on('mouseleave','bridge-points',()=>{
map.getCanvas().style.cursor='';
map.setPaintProperty('bridge-points','circle-radius',['match',['get','status'],'shift',5,'watch',4.2,3.4]);
tip.remove()});
map.on('click','bridge-points',e=>{
tip.remove();
const p=e.features[0].properties;
new maplibregl.Popup({closeButton:true,offset:10,maxWidth:"300px"}).setLngLat(e.lngLat).setHTML(bridgePopupHTML(p)).addTo(map)});
});
}).catch(function(){fallback()})}
// 库已内联（自托管），直接初始化；样式获取失败由 Promise catch 降级
init();
</script></body></html>'''
    # 弹窗内链接需要绝对地址（地图是 data: iframe，相对 URL 无法解析）
    try:
        host = st.context.headers.get("host", "localhost:8501")
        proto = st.context.headers.get("x-forwarded-proto", "http")
    except Exception:
        host, proto = "localhost:8501", "http"
    # 底图瓦片走本站同源代理（生产）；本地开发直连 OpenFreeMap
    if host.startswith("localhost") or host.startswith("127."):
        style_url = "https://tiles.openfreemap.org/styles/dark"
    else:
        style_url = f"{proto}://{host}/tiles/styles/dark"
    mlgl_js, mlgl_css = _vendor_lib()
    map_html = (
        template
        .replace("__MLGL_JS__", mlgl_js)
        .replace("__MLGL_CSS__", mlgl_css)
        .replace("__STYLE_URL__", style_url)
        .replace("__BRIDGES__", json.dumps(bridges_fc, separators=(",", ":")))
        .replace("__ROADS__", json.dumps(roads_fc, separators=(",", ":")))
        .replace("__FALLBACK_DOTS__", _fallback_dots(bridges_fc))
        .replace("__APP_ORIGIN__", f"{proto}://{host}")
    )
    return "data:text/html;base64," + base64.b64encode(map_html.encode()).decode()


def render_overview():
    live_pulse = _dominant_frequency(148, 7.22)
    # 数字可追溯：全网近30日穿越总数由 128 座桥的档案汇总，不硬编码
    _bfc, _ = _map_data()
    crossings_30d = sum(f["properties"]["crossings30d"] for f in _bfc["features"])
    st.markdown(OVERVIEW_CSS, unsafe_allow_html=True)

    # 全出血地图 hero：标题直接压在地图上
    st.markdown(
        f'<section class="ov-hero">'
        f'<div class="ov-map-frame"><iframe src="{_map_iframe()}" title="贵州桥梁动态感知地图"></iframe></div>'
        f'<div class="ov-shade"></div>'
        f'<div class="ov-net"><b>128</b> 座纳入感知 · <b>32,000+</b> 座贵州桥梁总数</div>'
        f'<div class="ov-copy"><div class="ov-kicker">贵州桥梁动态感知网络</div>'
        f'<h1 class="ov-title">今天，哪些桥<br>值得优先关注？</h1>'
        f'<div class="ov-sub">把车辆的日常通行，转化为桥梁网络的持续动态观测</div></div>'
        f'<div class="ov-legend">'
        f'<div><i style="background:#e07a62"></i>响应偏移 · 11 座</div>'
        f'<div><i style="background:#d9b46e"></i>持续观察 · 21 座</div>'
        f'<div><i style="background:#6fd8c5"></i>状态稳定 · 96 座</div></div>'
        f'</section>',
        unsafe_allow_html=True,
    )

    # 编辑式板块：左优先队列，右真实证据
    q17, q42, q008 = _network_queue()
    left, right = st.columns([1.6, 1], gap="large")
    with left:
        st.markdown(
            '<div class="ov-h">优先检查队列</div>'
            '<div class="ov-h-sub">有限的检查资源，应优先投向哪里 · 按响应偏移程度排序</div>'
            f'<div class="ov-row" style="--row-c:#e07a62"><div class="ov-num">01</div><div>'
            f'<div class="ov-id">GZ-017 · 坝陵河大桥 <i style="background:#e07a62"></i></div>'
            f'<div class="ov-data">历史 <b>{q17["base_hz"]:.2f} Hz</b> → 当前 <b class="alert">{q17["cur_hz"]:.2f} Hz</b> · '
            f'脉搏差异 <b>{q17["js"]:.3f}</b> / 阈值 <b>{q17["threshold"]:.3f}</b></div></div>'
            f'<div class="ov-act">建议优先工程复核<a href="/?view=bridge&bridge=GZ-017" target="_self">查看证据 →</a></div></div>'
            f'<div class="ov-row" style="--row-c:#d9b46e"><div class="ov-num">02</div><div>'
            f'<div class="ov-id">GZ-042 · 六广河大桥 <i style="background:#d9b46e"></i></div>'
            f'<div class="ov-data">历史 <b>{q42["base_hz"]:.2f} Hz</b> → 当前 <b>{q42["cur_hz"]:.2f} Hz</b> · '
            f'脉搏差异 <b>{q42["js"]:.3f}</b> / 阈值 <b>{q42["threshold"]:.3f}</b></div></div>'
            f'<div class="ov-act">脉搏差异略超阈值，持续采样观察是否保持偏移</div></div>'
            f'<div class="ov-row" style="--row-c:#6fd8c5"><div class="ov-num">03</div><div>'
            f'<div class="ov-id">GZ-008 · 乌江特大桥 <i style="background:#6fd8c5"></i></div>'
            f'<div class="ov-data">历史 <b>{q008["base_hz"]:.2f} Hz</b> → 当前 <b>{q008["cur_hz"]:.2f} Hz</b> · '
            f'脉搏差异 <b>{q008["js"]:.3f}</b> / 阈值 <b>{q008["threshold"]:.3f}</b></div></div>'
            f'<div class="ov-act">低于阈值，维持常规监测</div></div>',
            unsafe_allow_html=True,
        )
    with right:
        try:
            phys = _physical_summary()
            evi_big = (f'<div class="ov-evi-big">{phys["base_hz"]:.3f}<i>→</i>'
                       f'<span class="down">{phys["pert_hz"]:.3f} Hz</span></div>')
            direction = "下移" if phys["shift_pct"] <= 0 else "上移"
            evi_note = (f'同一结构、同一手机位置，仅改变附加质量：主导频率{direction} {abs(phys["shift_pct"]):.1f}%。'
                        f'数据来自真实 iPhone 15 IMU（{phys["fs"]:.1f} Hz），由页面实时重算。')
        except (ValueError, OSError):
            evi_big = '<div class="ov-evi-big">—<i>→</i><span class="down">— Hz</span></div>'
            evi_note = '真实实验数据未接入（data/physical_validation/ 为空）。'
        st.markdown(
            '<div class="ov-evi-label">真实实验 · 缩尺结构受控验证</div>'
            + evi_big +
            '<div class="ov-evi-note">' + evi_note + '</div>'
            '<a class="ov-evi-link" href="/Physical_Validation">查看实验分析 →</a>'
            '<div class="ov-bound"><div class="ov-bound-t">数据边界</div>'
            '<div class="ov-evi-note" style="margin:0">本页网络态势为模拟演示；真实实验数据单独标注，不与模拟网络混用。</div></div>',
            unsafe_allow_html=True,
        )

    # 网络现状一行统计 + 方法边界
    st.markdown(
        f'<div class="ov-stat">'
        f'<div><span>近30日全网穿越（模拟）</span><b>{crossings_30d:,}</b></div>'
        f'<div><span>GZ-017 当前脉冲</span><b>{live_pulse:.2f}<em>Hz</em></b></div></div>'
        '<div class="ov-foot">'
        '<p>黔脉筛查桥梁相对自身历史基线的持续动态响应变化，不进行损伤诊断，也不能替代专业桥梁检测；'
        '输出仅为"建议优先工程检查"。一辆车很吵，很多辆车才能看见桥——'
        '反复穿越后，属于桥梁的共同响应会从车流噪声中浮现。</p>'
        '<a href="/?view=method" target="_self">了解工作原理 →</a></div>',
        unsafe_allow_html=True,
    )


# =============================================================================
# 桥梁详情
# =============================================================================

@st.cache_data(show_spinner=False)
def _gz017_timeline():
    """GZ-017 滑动窗口融合主频：前 100 次为基线期，后 100 次为当前期。

    每个点是 20 次穿越窗口的融合主导频率，展示"从哪次穿越开始偏移"。
    """
    base = simulate_batch(100, bridge_freq=7.81, seed=48)
    cur = simulate_batch(100, bridge_freq=7.22, seed=148)
    seq = base + cur
    xs, ys = [], []
    for start in range(0, 181, 10):
        xs.append(start + 10)
        ys.append(float(fuse_crossings(seq[start:start + 20])["dominant_frequency"]))
    return xs, ys


def render_bridge():
    bridge_id = st.query_params.get("bridge", "")
    if bridge_id == "GZ-017":
        _render_bridge_detail()
        return

    # ---- 桥梁网络总表 ----
    bridges_fc, _ = _map_data()
    feats = [f["properties"] for f in bridges_fc["features"]]
    order = {"shift": 0, "watch": 1, "normal": 2}
    key_rank = {"GZ-017": 0, "GZ-042": 1, "GZ-008": 2}
    feats.sort(key=lambda p: (order[p["status"]], key_rank.get(p["id"], 9), -p["crossings30d"]))
    counts = {s: sum(1 for p in feats if p["status"] == s) for s in ("shift", "watch", "normal")}
    shown = [p for p in feats if p["status"] in ("shift", "watch")]

    page_head(
        "桥梁网络",
        "一百二十八座桥，今天各自的脉搏",
        f"按响应状态排序 · 响应偏移 {counts['shift']} 座 / 持续观察 {counts['watch']} 座 / 状态稳定 {counts['normal']} 座",
        '<span class="qp-badge sim">模拟网络数据</span>',
    )

    st.markdown(
        '<style>'
        '.bn-head{display:grid;grid-template-columns:64px minmax(140px,1.2fr) 96px 110px 72px 56px 130px 84px 76px;'
        'gap:12px;padding:10px 2px 9px;border-bottom:1px solid #1c3129;font-size:11px;letter-spacing:.1em;color:#5c7168}'
        '.bn-row{display:grid;grid-template-columns:64px minmax(140px,1.2fr) 96px 110px 72px 56px 130px 84px 76px;'
        'gap:12px;align-items:baseline;padding:15px 2px 14px;border-bottom:1px solid #152721;'
        'font-size:13px;transition:background .15s}'
        '.bn-row:hover{background:rgba(111,216,197,.03)}'
        '.bn-id{font-family:Georgia,serif;font-size:12.5px;color:#5c7168;font-variant-numeric:tabular-nums}'
        '.bn-name{color:#e9f1ec;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}'
        '.bn-name a{color:inherit!important;text-decoration:none;border-bottom:1px solid rgba(111,216,197,.35)}'
        '.bn-name a:hover{border-bottom-color:#6fd8c5}'
        '.bn-key .bn-name::after{content:"重点桥";font-size:9.5px;color:#6fd8c5;letter-spacing:.14em;'
        'border:1px solid rgba(111,216,197,.3);border-radius:2px;padding:1.5px 5px;margin-left:9px;vertical-align:1.5px}'
        '.bn-st{font-size:11px;font-weight:600}'
        '.bn-cell{color:#9aa8a0;font-variant-numeric:tabular-nums;white-space:nowrap}'
        '.bn-cell b{color:#cdd9d3;font-weight:600}'
        '@media(max-width:1000px){.bn-head,.bn-row{grid-template-columns:56px 1fr 84px 70px 60px;gap:8px}'
        '.bn-hide{display:none}}'
        '</style>'
        '<div class="qp-section-label" style="margin-top:8px">响应偏移 · 持续观察 · 共 '
        f'{len(shown)} 座在册关注</div>'
        '<div class="qp-note" style="margin-bottom:6px">其余 '
        f'{counts["normal"]} 座脉搏差异低于阈值、维持常规监测，未列入下表。'
        '每行的脉搏频率来自该桥历史穿越的融合估计。</div>'
        '<div class="bn-head"><span>编号</span><span>桥名</span><span>状态</span><span class="bn-hide">桥型</span>'
        '<span class="bn-hide">主跨</span><span class="bn-hide">通车</span><span class="bn-hide">所属通道</span>'
        '<span>脉搏</span><span class="bn-hide">近30日穿越</span></div>',
        unsafe_allow_html=True,
    )
    st_map = {"shift": ("响应偏移", "#eda28d"), "watch": ("持续观察", "#e3c584")}
    rows = []
    for p in shown:
        st_label, st_color = st_map[p["status"]]
        is_key = p["id"] in key_rank
        name = (f'<a href="/?view=bridge&bridge={p["id"]}" target="_self" title="查看完整证据链">{p["name"]}</a>'
                if p["id"] == "GZ-017" else p["name"])
        rows.append(
            f'<div class="bn-row{" bn-key" if is_key else ""}">'
            f'<span class="bn-id">{p["id"]}</span><span class="bn-name">{name}</span>'
            f'<span class="bn-st" style="color:{st_color}">● {st_label}</span>'
            f'<span class="bn-cell bn-hide">{p["type"]}</span>'
            f'<span class="bn-cell bn-hide"><b>{p["span_m"]}</b> m</span>'
            f'<span class="bn-cell bn-hide">{p["year"]}</span>'
            f'<span class="bn-cell bn-hide" style="overflow:hidden;text-overflow:ellipsis">{p["route"]}</span>'
            f'<span class="bn-cell"><b>{p["freq"]:.2f}</b> Hz</span>'
            f'<span class="bn-cell bn-hide">{p["crossings30d"]}</span></div>'
        )
    st.markdown("".join(rows), unsafe_allow_html=True)
    st.markdown(
        '<div class="qp-note" style="margin-top:18px">仅 GZ-017 坝陵河大桥开放完整证据链详情；'
        '其余桥梁的穿越数据在当前演示规模下未达到详情页所需的融合样本量。</div>',
        unsafe_allow_html=True,
    )


def _render_bridge_detail():
    # 原生按钮 + 编程式导航：彻底杜绝新标签页
    if st.button("← 返回桥梁网络", help="回到 128 座桥的网络总表"):
        st.query_params["view"] = "bridge"
        if "bridge" in st.query_params:
            del st.query_params["bridge"]
        st.rerun()
    page_head(
        "桥梁详情",
        "GZ-017 · 坝陵河大桥",
        "贵州山地桥梁网络 · 最近 200 次穿越（前 100 次为历史基线期）",
        '<span class="qp-badge sim">模拟网络数据</span>',
    )
    # 与总览页同一份模拟网络数据：历史 7.81 Hz → 当前 7.22 Hz
    fb, fc, threshold, js = _gz017_metrics()
    shift_pct = (fc["dominant_frequency"] - fb["dominant_frequency"]) / fb["dominant_frequency"] * 100

    st.markdown(
        '<div style="margin:24px 0;padding:24px;border-radius:6px;border:1px solid rgba(224,122,98,.3);'
        'background:rgba(224,122,98,.06)">'
        '<span class="qp-badge shift">响应偏移</span>'
        '<h2 style="margin:14px 0 6px;font-size:24px;color:#e9f1ec">建议优先工程检查</h2>'
        '<p style="color:#b9c8c0;margin:0;font-size:13.5px">当前动态响应已持续偏离这座桥自己的历史状态；黔脉不判断损伤，只帮助工程师决定先检查哪里。</p></div>',
        unsafe_allow_html=True,
    )
    cols = st.columns(4)
    data = [
        ("历史脉冲", f"{fb['dominant_frequency']:.2f}", "Hz", False),
        ("当前脉冲", f"{fc['dominant_frequency']:.2f}", "Hz", True),
        ("脉搏差异", f"{js:.3f}", "JS", True),
        ("历史阈值", f"{threshold:.3f}", "JS", False),
    ]
    for col, (label, val, unit, alert) in zip(cols, data):
        with col:
            metric(label, val, unit, alert=alert)
    st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=fb["grid"], y=fb["fingerprint"], name="历史基线",
                             line=dict(color=CHART_COLORS["base"], width=2)))
    fig.add_trace(go.Scatter(x=fc["grid"], y=fc["fingerprint"], name="当前状态",
                             line=dict(color=CHART_COLORS["alert"], width=2)))
    fig.update_layout(**plotly_theme(360), xaxis_title="频率 / Hz", yaxis_title="归一化频谱")
    st.markdown(
        f'<div class="qp-card"><div class="qp-kicker">核心证据</div>'
        f'<div class="qp-card-title" style="margin-top:6px">主导频率 {shift_pct:+.1f}% · 脉搏差异 {js:.3f}，超过历史波动阈值 {threshold:.3f}</div>',
        unsafe_allow_html=True,
    )
    show_chart(fig)
    st.markdown('</div>', unsafe_allow_html=True)

    # ---- 取证时间线：偏移从哪次穿越开始、是否持续 ----
    xs, ys = _gz017_timeline()
    base_hz, cur_hz = fb["dominant_frequency"], fc["dominant_frequency"]
    tl = go.Figure()
    tl.add_hrect(y0=cur_hz - 0.12, y1=cur_hz + 0.12, fillcolor="rgba(224,122,98,.07)",
                 line_width=0)
    tl.add_trace(go.Scatter(
        x=xs, y=ys, mode="lines+markers",
        line=dict(color=CHART_COLORS["current"], width=1.8),
        marker=dict(color=[CHART_COLORS["base"] if x <= 100 else "#e07a62" for x in xs],
                    size=6, line=dict(color="#081010", width=1.5)),
        hovertemplate="第 %{x} 次穿越 · 融合主频 %{y:.2f} Hz<extra></extra>",
    ))
    tl.add_vline(x=100, line=dict(color="#7f948a", dash="dash", width=1), opacity=.6)
    tl.add_annotation(x=100, y=1.06, text="基线期 → 当前期", showarrow=False,
                      font=dict(color="#7f948a", size=10), yref="paper", xanchor="left", xshift=6)
    tl.update_layout(**plotly_theme(300), xaxis_title="累计穿越次数（20 次窗口）",
                      yaxis_title="窗口融合主频 / Hz")
    st.markdown(
        '<div class="qp-kicker" style="margin-top:44px">取证时间线</div>'
        '<div class="qp-card-title">从第 100 次穿越开始持续下移，且不再回到历史区间</div>'
        '<div class="qp-note" style="max-width:760px;margin-bottom:4px">'
        '每个点是连续 20 次穿越的融合主导频率。前 100 次始终停在历史区间；'
        '进入当前期后下移并保持——持续性排除了单次异常的可能。</div>',
        unsafe_allow_html=True,
    )
    show_chart(tl)


# =============================================================================
# 工作原理
# =============================================================================

@st.cache_data(show_spinner=False)
def _trajectory_bank(seed=42, freq=7.8, n_total=1000):
    """一次性预生成并解析全部穿越轨迹：工作原理页"百千轨迹"的数据源。

    返回统一频率网格、逐条轨迹的频谱矩阵（每行一辆车，行内归一化），
    以及每条轨迹提出的候选峰——后续任意规模的融合都不再重算频谱。
    """
    cs = simulate_batch(n_total, bridge_freq=freq, seed=seed)
    fine = np.linspace(3.0, 13.0, 500)
    specs, peaks = [], []
    for c in cs:
        r = crossing_to_peaks(c)
        f, pxx = r["f"], r["pxx"]
        mask = (f >= 3.0) & (f <= 13.0)
        row = np.maximum(np.interp(fine, f[mask], pxx[mask]), 0.0)
        # γ=0.5 提升中强度：让真实频率处的条纹从随机噪声里显影
        row = np.sqrt(row / (row.max() + 1e-12))
        specs.append(row)
        peaks.append(r["peaks"])
    return fine, np.vstack(specs), peaks


@st.cache_data(show_spinner=False)
def _fused_at(seed, freq, n):
    """前 n 条轨迹的候选峰融合（等权投票 KDE）。"""
    _, _, peaks = _trajectory_bank(seed=seed, freq=freq)
    parts = [p for p in peaks[:n] if len(p)]
    votes = np.concatenate(parts) if parts else np.array([])
    grid, density, dominant = fuse_peaks(votes)
    fingerprint = density / np.max(density) if np.max(density) > 0 else density
    return grid, fingerprint, dominant, votes


@st.cache_data(show_spinner=False)
def _collapse_profile(seed, freq, milestones):
    """噪声坍缩轨迹：在里程碑规模上重算融合，看残余随轨迹数下降。"""
    _, _, peaks = _trajectory_bank(seed=seed, freq=freq)
    residual = []
    for m in milestones:
        parts = [p for p in peaks[:m] if len(p)]
        votes = np.concatenate(parts) if parts else np.array([])
        _, density, _ = fuse_peaks(votes)
        fp = density / np.max(density) if np.max(density) > 0 else density
        residual.append(noise_residual(fp))
    return residual


def render_method():
    page_head("工作原理", "桥一直都在说话，只是从来没人听",
              "每辆过桥的车，都在无意间「测量」这座桥。黔脉把千百次被丢弃的测量，坍缩成一条清晰的桥梁脉搏。")

    # ---- 核心洞察：角度之妙，先声夺人 ----
    st.markdown('''
    <style>
    .qp-aha{margin-top:40px;border-top:1px solid var(--qp-line);border-bottom:1px solid var(--qp-line);padding:36px 0 32px}
    .qp-aha h2{font-family:var(--qp-serif);font-size:clamp(24px,2.6vw,32px);font-weight:700;color:#e9f1ec;line-height:1.45;margin:12px 0 14px;max-width:880px}
    .qp-aha h2 em{font-style:normal;color:#6fd8c5;text-shadow:0 0 26px rgba(111,216,197,.35)}
    .qp-aha p{color:var(--qp-muted);font-size:14px;line-height:2;max-width:780px;margin:0}
    .qp-aha-nums{display:flex;margin-top:26px;flex-wrap:wrap}
    .qp-aha-nums div{flex:1;min-width:190px;padding:2px 28px;border-left:1px solid var(--qp-line)}
    .qp-aha-nums div:first-child{border-left:0;padding-left:0}
    .qp-aha-nums b{display:block;font-family:Georgia,"Songti SC",serif;font-size:29px;font-weight:500;color:#9ee8da}
    .qp-aha-nums span{display:block;font-size:12px;color:var(--qp-faint);margin-top:7px;letter-spacing:.05em}
    </style>
    <div class="qp-aha">
      <div class="qp-kicker">核心洞察</div>
      <h2>监测桥梁的传感器，<em>每天都在桥上跑</em>——只是从来没人记录</h2>
      <p>一套结构健康监测系统造价千万，注定只能覆盖极少数重点桥。但每天驶过桥面的车流——公交、出租、物流、巡检——
      每一辆都载着惯性传感器，每一次穿越都在无意间「测量」这座桥。观测数据其实一直在产生，
      只是过完桥就随风而去。黔脉做的事只有一件：把这些被丢弃的测量存下来、读出来，汇成桥的脉搏。</p>
      <div class="qp-aha-nums">
        <div><b>¥0</b><span>新增传感器投入</span></div>
        <div><b>千万级</b><span>传统监测系统造价</span></div>
        <div><b>按年 → 按天</b><span>观测密度的量级跃迁</span></div>
      </div>
    </div>
    ''', unsafe_allow_html=True)

    # ---- 互动演示：从 1 条轨迹拖到 1,000 条，看噪声坍缩成桥梁脉搏 ----
    TRUE_FREQ = 7.8
    MILESTONES = (1, 2, 3, 5, 10, 20, 30, 50, 100, 200, 300, 500, 700, 1000)
    st.markdown(
        '<div class="qp-kicker" style="margin-top:48px">互动演示 · 拖动滑块</div>'
        '<div style="font-family:var(--qp-serif);font-size:27px;font-weight:700;color:#e9f1ec;margin:9px 0 5px">一千条车辙，坍缩成一次脉搏</div>'
        '<div class="qp-note" style="max-width:760px;margin-bottom:6px">热图里每行是一辆车过桥时的原始频谱——'
        '悬架、路面、冲击各说各话，单看任何一条都找不到桥。但它们经过的是同一座桥：拖动滑块，'
        '从 1 条一路汇集到 1,000 条，看真实频率处的候选峰逐条堆积、噪声相互抵消，'
        '最终坍缩成一条明确的桥梁脉搏。</div>',
        unsafe_allow_html=True,
    )
    n = st.slider("参与融合的穿越次数", 1, 1000, 1)
    fine, specs, _peaks = _trajectory_bank(42, TRUE_FREQ)
    grid, fingerprint, dominant, votes = _fused_at(42, TRUE_FREQ, n)
    left, right = st.columns([2.15, 1], gap="large")
    with left:
        # 图一：百千条轨迹的原始频率图——桥梁条纹在噪声里逐条显影
        fig0 = go.Figure(go.Heatmap(
            z=specs[:n], x=fine, y=np.arange(1, n + 1),
            colorscale=[(0, "#0c1712"), (0.5, "#153a2c"), (0.8, "#319786"), (1, "#c8f5e6")],
            showscale=False, zsmooth="best", hoverinfo="skip",
        ))
        fig0.add_vline(x=TRUE_FREQ, line=dict(color="#eef6f2", dash="dash", width=1.1), opacity=.8)
        fig0.add_annotation(x=TRUE_FREQ, y=1.0, text=f"桥梁真实频率 {TRUE_FREQ:.1f} Hz",
                            showarrow=False, font=dict(color="#dfe7e2", size=10.5),
                            yref="paper", xanchor="left", xshift=8)
        fig0.update_layout(
            height=340, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family='"PingFang SC",sans-serif', color=CHART_COLORS["text"], size=11),
            margin=dict(l=46, r=16, t=10, b=36),
            xaxis=dict(title="频率 / Hz", range=[3, 13], showgrid=False, zeroline=False,
                       showline=False, tickcolor="rgba(139,166,154,.35)"),
            # y 轴固定满刻度 1→1000：拖动滑块时轨迹行从顶部逐行生长，视觉反馈明确
            yaxis=dict(title="穿越轨迹（每行一辆车）", autorange="reversed", range=[1000, 1],
                       showgrid=False, zeroline=False, showline=False,
                       tickcolor="rgba(139,166,154,.35)",
                       tickvals=[1, 250, 500, 750, 1000]),
        )
        st.markdown('<div class="qp-kicker" style="margin-bottom:2px">原始轨迹 · 百千张频率图</div>',
                    unsafe_allow_html=True)
        show_chart(fig0)

        # 图二：候选峰"投票"散点（噪声随机散布，桥的真值反复堆积）+ 融合脉搏
        fig = go.Figure()
        if len(votes):
            rng = np.random.default_rng(7)
            fig.add_trace(go.Scatter(
                x=votes, y=rng.uniform(0.012, 0.045, size=len(votes)), mode="markers",
                marker=dict(color="#7fb89a", size=4.5, opacity=.5), name="候选峰投票",
                hovertemplate="%{x:.2f} Hz<extra>候选峰</extra>",
            ))
        fig.add_trace(go.Scatter(
            x=grid, y=fingerprint, mode="lines", name="融合脉搏",
            line=dict(color=CHART_COLORS["current"], width=2.2),
            fill="tozeroy", fillcolor="rgba(111,216,197,.055)",
            hovertemplate="%{x:.2f} Hz<extra></extra>",
        ))
        if np.isfinite(dominant):
            peak_i = int(np.argmin(np.abs(grid - dominant)))
            fig.add_trace(go.Scatter(
                x=[dominant], y=[fingerprint[peak_i]], mode="markers",
                marker=dict(color="#eef6f2", size=9, line=dict(color=CHART_COLORS["current"], width=2)),
                name="主导频率", hovertemplate="主导频率 %{x:.2f} Hz<extra></extra>",
            ))
        fig.add_vline(x=TRUE_FREQ, line=dict(color=CHART_COLORS["base"], dash="dash", width=1.2), opacity=.65)
        fig.add_annotation(x=TRUE_FREQ, y=1.0, text=f"桥梁真实频率 {TRUE_FREQ:.2f} Hz", showarrow=False,
                           font=dict(color="#7f948a", size=10), yref="paper", xanchor="left", xshift=6)
        fig.update_layout(**plotly_theme(300), xaxis_title="频率 / Hz", yaxis_title="归一化脉搏密度",
                          xaxis_range=[3, 13], yaxis_range=[0, 1.08])
        st.markdown('<div class="qp-kicker" style="margin:16px 0 2px">候选峰投票 → 融合脉搏</div>',
                    unsafe_allow_html=True)
        show_chart(fig)
    with right:
        err = abs(dominant - TRUE_FREQ)
        residual = noise_residual(fingerprint)
        converged = "已收敛" if (err < 0.15 and residual < 0.35) else ("接近收敛" if (err < 0.4 or residual < 0.6) else "仍被噪声主导")
        metric("已汇集轨迹", f"{n:,}", "条穿越")
        metric("候选峰票数", f"{len(votes):,}", "等权投票")
        metric("脉搏主频", f"{dominant:.2f}", "Hz")
        metric("与真实频率偏差", f"±{err:.2f}", "Hz", alert=err > 0.4)
        metric("噪声残余", f"{residual:.0%}", "次峰/主峰", alert=residual > 0.6)
        metric("融合状态", converged, f"{n} 条轨迹")
        profile = _collapse_profile(42, TRUE_FREQ, MILESTONES)
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=list(MILESTONES), y=profile, mode="lines",
            line=dict(color="#d9b46e", width=1.8), fill="tozeroy",
            fillcolor="rgba(217,180,110,.08)", name="噪声残余",
            hovertemplate="%{x} 条轨迹 · 残余 %{y:.0%}<extra></extra>",
        ))
        fig2.add_trace(go.Scatter(
            x=[n], y=[residual], mode="markers",
            marker=dict(color="#eef6f2", size=8, line=dict(color="#d9b46e", width=2)),
            hovertemplate="当前 · 残余 %{y:.0%}<extra></extra>",
        ))
        fig2.update_layout(**plotly_theme(230), xaxis_title="轨迹数", yaxis_title="噪声残余",
                           yaxis_range=[0, 1.05], xaxis_type="log",
                           xaxis_tickvals=[m for m in MILESTONES if m >= 10], showlegend=False)
        st.markdown('<div class="qp-kicker" style="margin:18px 0 2px">噪声坍缩轨迹 · 1 → 1,000 条</div>',
                    unsafe_allow_html=True)
        show_chart(fig2)

    # ---- 三步解释（紧凑）----
    st.markdown(
        '<div class="qp-section-label" style="margin-top:44px">三步原理</div>', unsafe_allow_html=True,
    )
    steps = [
        ("01", "一辆车", "单次穿越不能代表桥——悬架、路面、车辆本身与随机冲击混在一起。"),
        ("02", "很多辆车", "穿越次数越多，属于桥梁的共同响应越稳定，车辆各自的噪声相互抵消。"),
        ("03", "持续比较", "当前脉搏持续偏离这座桥自己的历史波动范围时，推荐优先工程检查。"),
    ]
    s1, s2, s3 = st.columns(3, gap="medium")
    for col, (k, t, body) in zip([s1, s2, s3], steps):
        with col:
            st.markdown(
                f'<div class="qp-card" style="height:100%"><div class="qp-kicker">{k}</div>'
                f'<div style="font-family:var(--qp-serif);font-size:20px;font-weight:700;color:#e9f1ec;margin:8px 0 8px">{t}</div>'
                f'<div class="qp-note">{body}</div></div>',
                unsafe_allow_html=True,
            )

    # ---- 与筛查决策的衔接（带内下移偏移，方向与真实实验一致）----
    base, current = demo_data(7, 13.4, 10.6)
    bp, cp = fuse_crossings(base), fuse_crossings(current)
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(x=bp["grid"], y=bp["fingerprint"], name="历史脉搏",
                              line=dict(color=CHART_COLORS["base"], width=2)))
    fig3.add_trace(go.Scatter(x=cp["grid"], y=cp["fingerprint"], name="当前脉搏",
                              line=dict(color=CHART_COLORS["alert"], width=2)))
    fig3.update_layout(**plotly_theme(300), xaxis_title="频率 / Hz", yaxis_title="脉搏强度")
    st.markdown(
        '<div class="qp-card" style="padding:20px;margin-top:44px"><div class="qp-kicker">筛查结论</div>'
        '<div style="font-size:17px;color:#e9f1ec;margin:8px 0 4px">人的脉搏变了，会去看医生；桥的脉搏变了，该去看桥</div>'
        '<div class="qp-note" style="margin-bottom:10px">同一座桥的历史脉搏与当前脉搏：主导频率持续下移并越过历史波动范围——'
        '黔脉不诊断损伤，只回答「哪座桥值得先看」。</div>',
        unsafe_allow_html=True,
    )
    show_chart(fig3)
    st.markdown('</div>', unsafe_allow_html=True)


# =============================================================================
# 系统架构
# =============================================================================

# 与 qianpulse/scale_simulation.architecture_snapshot 的七站流水线一一对应
ARCH_STAGES = [
    ("01", "车辆 · 边缘采集", "一辆车过桥，手机 IMU 落盘一段原始加速度窗口——观测从这里开始。", "qianpulse/simulate.py"),
    ("02", "质量门禁", "短窗、非有限值、采样率异常直接拒绝——脏数据永远进不了桥的脉搏。", "qianpulse/pipeline.py"),
    ("03", "特征包 FeaturePacket", "原始信号压缩成 800 点谱特征包：主导频率、候选峰、质量分，原始数据只留抽样。", "qianpulse/pipeline.py"),
    ("04", "桥级分区", "按 bridge_id 哈希分区入队，单桥状态串行更新，多桥互不污染。", "qianpulse/scale_simulation.py"),
    ("05", "增量桥态", "BridgePulseState 收包即 O(1) 更新——永不重扫历史穿越。", "qianpulse/pipeline.py"),
    ("06", "持久化", "桥级状态快照落 SQLite，进程重启即恢复；原始数据分层保留。", "qianpulse/scale_simulation.py"),
    ("07", "筛查边界", "与历史基线比较 JS 散度，越过 bootstrap 阈值才建议优先检查。", "qianpulse/engine.py"),
]

ARCH_MODULES = [
    ("qianpulse/engine.py", "信号处理内核：去趋势、带通、Welch、候选峰、KDE 融合、JS 散度"),
    ("qianpulse/pipeline.py", "生产边界：质量门禁 + FeaturePacket + 增量桥态"),
    ("qianpulse/scale_simulation.py", "本地规模模拟：asyncio 分区队列 + SQLite 持久化 + 分层保留"),
    ("qianpulse/io_sensorlogger.py", "真实 iPhone Sensor Logger ZIP 解析：列名自适应、时间轴重建"),
    ("qianpulse/physical_validation.py", "受控实验分析：等面积归一化、组间散度矩阵"),
    ("qianpulse/simulate.py", "刻意「脏」的模拟穿越：单次必须看不出桥"),
    ("qianpulse/ui.py", "视觉系统：深色编辑排版与统一图表主题"),
    ("tests/test_qianpulse.py", "9 个单元测试：收敛、误报、分区、增量、持久化"),
]


@st.cache_data(show_spinner=False)
def _run_scale(crossings):
    """在本地真实运行一次规模模拟，所有指标实测而非硬编码。"""
    return asyncio.run(run_scale_simulation(fleet_size=100, crossings=crossings, workers=4))


@st.cache_data(show_spinner=False)
def _module_loc(rel):
    path = Path(__file__).resolve().parent / rel
    return sum(1 for _ in open(path, encoding="utf-8")) if path.exists() else 0


def render_architecture():
    page_head("系统架构", "一条穿越的七站旅程",
              "从手机里的一段原始窗口，到桥级脉搏的一次增量更新——每一站都是可测试的代码，不是示意图。")

    # ---- 七站流水线 ----
    rows = "".join(
        f'<div class="arch-row"><div class="arch-num">{n}</div>'
        f'<div class="arch-body"><div class="arch-title">{t}</div><div class="arch-note">{d}</div></div>'
        f'<code class="arch-mod">{m}</code></div>'
        for n, t, d, m in ARCH_STAGES
    )
    st.markdown(
        '<style>'
        '.arch-row{display:grid;grid-template-columns:52px minmax(0,1fr) auto;gap:20px;align-items:baseline;'
        'padding:20px 2px 18px;border-top:1px solid #152721;transition:background .15s}'
        '.arch-row:hover{background:rgba(111,216,197,.025)}'
        '.arch-row:last-of-type{border-bottom:1px solid #152721}'
        '.arch-num{font-family:Georgia,serif;font-size:15px;color:#5c7168}'
        '.arch-title{font-size:16.5px;font-weight:700;color:#e9f1ec}'
        '.arch-note{font-size:13px;color:#7f948a;line-height:1.9;margin-top:7px;max-width:680px}'
        '.arch-mod{font-size:11.5px;color:#5f8a7a;white-space:nowrap;background:transparent!important}'
        '.arch-cm{grid-template-columns:270px minmax(0,1fr) 58px;align-items:baseline;column-gap:26px}'
        '.arch-cm .arch-mod{overflow:hidden;text-overflow:ellipsis;max-width:270px}'
        '</style>'
        '<div class="qp-section-label" style="margin-top:8px">数据流 · 七站流水线</div>'
        f'<div style="margin-top:14px">{rows}</div>'
        '<div class="qp-note" style="margin-top:16px">七站对应 <code>architecture_snapshot()</code> 的阶段定义，'
        '由 <code>tests/test_qianpulse.py</code> 逐站验证——不是概念图，是跑在进程里的代码。</div>',
        unsafe_allow_html=True,
    )

    # ---- 现场演示：本地规模模拟（实测指标）----
    st.markdown(
        '<div class="qp-section-label" style="margin-top:56px">现场演示 · 本地规模模拟</div>'
        '<div style="font-family:var(--qp-serif);font-size:24px;font-weight:700;color:#e9f1ec;margin:6px 0 10px">一千次穿越，此刻在你机器上跑一遍</div>'
        '<div class="qp-note" style="max-width:760px">点击运行，在本机实时跑完整个七站流水线：asyncio 分区队列、'
        '质量门禁、增量桥态、SQLite 落盘。以下每个数字都是刚才实测的结果，不是预设的演示值。</div>',
        unsafe_allow_html=True,
    )
    col_run, col_placeholder = st.columns([1, 3])
    with col_run:
        if st.button("运行规模模拟", type="primary"):
            st.session_state["arch_ran"] = True
    if st.session_state.get("arch_ran"):
        crossings = st.slider("穿越事件数", 100, 1000, 300, step=10)
        with st.spinner("七站流水线运行中…"):
            result = _run_scale(crossings)
        m1, m2, m3 = st.columns(3, gap="medium")
        with m1:
            metric("实测吞吐", f"{result['throughput_events_per_sec']:.0f}", "事件 / 秒")
            metric("处理 / 拒绝", f"{result['processed_count']}", f"拒绝 {result['rejected_count']} 条")
        with m2:
            metric("桥态更新", f"{result['bridge_state_updates']}", f"覆盖 {result['bridges_in_sqlite']} 座桥")
            metric("原始数据保留", f"{result['raw_retention_ratio']:.0%}", "抽样留存")
        with m3:
            metric("全历史重扫", "无", "增量更新")
            metric("劣质窗口", f"{result['low_quality_generated']}", "已按比例注入")
        st.markdown(
            f'<div class="qp-note" style="margin-top:4px">车队规模 {result["fleet_size"]} 辆 · 生成 {result["generated_crossings"]} 次穿越 · '
            f'拒绝的 {result["rejected_count"]} 条中含 {result["rejected_debug_count"]} 条留档可查——'
            '门禁拒绝不是丢弃，是可追溯的拒绝。</div>',
            unsafe_allow_html=True,
        )

    # ---- 代码地图 ----
    mod_rows = "".join(
        f'<div class="arch-row arch-cm"><code class="arch-mod">{p}</code>'
        f'<div class="arch-body"><div class="arch-note" style="margin-top:0">{d}</div></div>'
        f'<div class="arch-num" style="text-align:right">{_module_loc(p)} 行</div></div>'
        for p, d in ARCH_MODULES
    )
    st.markdown(
        '<div class="qp-section-label" style="margin-top:56px">代码地图</div>'
        f'<div style="margin-top:14px">{mod_rows}</div>'
        '<div class="qp-note" style="margin-top:16px">行数为实时统计——这一页连自己的代码规模都在说真话。</div>',
        unsafe_allow_html=True,
    )

    # ---- 工程约束（每条都有测试背书）----
    guarantees = [
        ("增量", "桥态 O(1) 更新", "每次穿越只更新一个特征包的和式，从不重扫历史——一万次穿越后依然是常数时间。", "增量与持久化"),
        ("门禁", "脏数据止步于门口", "短窗、非有限值、采样率异常在进入桥态之前就被拒绝，永远污染不了脉搏。", "特征包与增量桥态"),
        ("分区", "一桥一账，互不污染", "错配 bridge_id 的特征包直接抛错，绝不静默写入别的桥的历史。", "分区强一致校验"),
        ("克制", "同态不误报", "同一状态对自身基线的散度必须落在历史波动范围内——安静的系统不许报警。", "基线波动范围"),
        ("敏感", "偏移必报警", "真实响应偏移必须超出历史波动范围——该响的时候绝不沉默。", "偏移超阈值"),
    ]
    g_cells = "".join(
        f'<div class="arch-g"><div class="arch-g-tag">{tag}</div>'
        f'<div class="arch-g-title">{t}</div><div class="arch-g-note">{d}</div>'
        f'<div class="arch-g-chip">✓ 测试背书 · {test}</div></div>'
        for tag, t, d, test in guarantees
    )
    st.markdown(
        '<style>'
        '.arch-g-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:1px;'
        'background:#152721;border:1px solid #152721;margin-top:18px}'
        '.arch-g{background:#0c1613;padding:26px 28px 24px;position:relative;transition:background .2s}'
        '.arch-g:hover{background:#101c17}'
        '.arch-g-tag{display:inline-block;font-size:10.5px;letter-spacing:.22em;color:#6fd8c5;'
        'border:1px solid rgba(111,216,197,.28);border-radius:2px;padding:3px 9px;margin-bottom:14px}'
        '.arch-g-title{font-family:var(--qp-serif);font-size:19px;font-weight:700;color:#e9f1ec;margin-bottom:10px}'
        '.arch-g-note{font-size:13px;color:#7f948a;line-height:1.95}'
        '.arch-g-chip{margin-top:16px;font-size:11px;color:#5f8a7a;letter-spacing:.04em}'
        '</style>'
        '<div class="qp-section-label" style="margin-top:56px">工程约束 · 五条硬保证</div>'
        '<div style="font-family:var(--qp-serif);font-size:24px;font-weight:700;color:#e9f1ec;margin:6px 0 6px">这些不是口头承诺，是测试套件里的断言</div>'
        f'<div class="arch-g-grid">{g_cells}</div>'
        '<div class="qp-note" style="margin-top:16px">架构图人人会画；能被单元测试钉死的架构，才是真的架构。</div>',
        unsafe_allow_html=True,
    )


# =============================================================================
# 真实证据
# =============================================================================

def render_evidence():
    page_head("证据层", "从模拟走向真实世界",
              "每一层都标注数据状态，不把计划中的实验包装成已完成。",
              '<span class="qp-badge real">真实证据可追溯</span>')
    rows = [
        ("01", "real", "已完成", "iPhone 实采 · 缩尺结构",
         "iPhone 15 · Sensor Logger · 实际采样率约 99.9 Hz。真实 ZIP → 解析 → 信号处理全流程，每条结果由页面实时重算。",
         "/Physical_Validation"),
        ("02", "real", "已完成", "受控物理验证",
         "同一缩尺结构、同一手机位置：基线 × 3、附加满水瓶质量状态 × 3。实时计算脉冲变化、脉搏差异与频谱迁移。",
         "/Physical_Validation"),
        ("03", "sim", "管线已验证", "车载过桥试点",
         "数据管线全流程跑通：ZIP → 桥窗切分 → 竖直向投影 → 候选峰 → 三次穿越融合出 7.81 Hz 桥频。当前为模拟采集演练数据，真实外场采集后原样替换。",
         "/Drive_by_Field_Pilot"),
    ]
    parts = [
        f'<div class="ev-row"><div class="ev-num">{n}</div>'
        f'<div><div class="ev-title">{title}<span class="qp-badge {cls}">{badge}</span></div>'
        f'<div class="ev-note">{body}</div></div>'
        f'<a class="ev-link" href="{link}">查看证据 →</a></div>'
        for n, cls, badge, title, body, link in rows
    ]
    st.markdown(
        '<style>'
        '.ev-row{display:grid;grid-template-columns:44px minmax(0,1fr) auto;gap:18px;align-items:baseline;'
        'padding:22px 2px 20px;border-top:1px solid #152721;transition:background .15s}'
        '.ev-row:hover{background:rgba(111,216,197,.025)}'
        '.ev-row:last-of-type{border-bottom:1px solid #152721}'
        '.ev-num{font-family:Georgia,serif;font-size:15px;color:#5c7168}'
        '.ev-title{display:flex;align-items:center;gap:12px;font-size:16.5px;font-weight:700;color:#e9f1ec}'
        '.ev-note{font-size:13px;color:#7f948a;line-height:1.9;margin-top:8px;max-width:760px}'
        '.ev-link{color:#6fd8c5;text-decoration:none;font-size:12.5px;white-space:nowrap}'
        '.ev-step{padding:12px 18px;border:1px solid #1f342b;border-radius:6px;font-size:13px;color:#e9f1ec;'
        'background:rgba(111,216,197,.03);white-space:nowrap}'
        '.ev-step small{display:block;font-size:10.5px;color:#7f948a;letter-spacing:.12em;margin-top:3px}'
        '.ev-step.done{border-color:rgba(111,216,197,.35)}'
        '.ev-step.plan{border-style:dashed;color:#b9c8c0;background:transparent}'
        '.ev-arrow{color:#5c7168;margin:0 10px;font-size:15px}'
        '</style>' + "".join(parts),
        unsafe_allow_html=True,
    )
    chain = [("模拟演示", "已完成", "done"), ("真实 iPhone 采集", "已完成", "done"),
             ("缩尺结构受控实验", "已完成", "done"), ("车载实测", "计划中", "plan"),
             ("车队规模验证", "展望", "plan")]
    steps = []
    for i, (name, state, cls) in enumerate(chain):
        if i:
            steps.append('<span class="ev-arrow">→</span>')
        steps.append(f'<div class="ev-step {cls}">{name}<small>{state}</small></div>')
    st.markdown(
        f'<div style="margin-top:56px"><div class="qp-kicker">验证路径</div>'
        f'<div style="display:flex;align-items:center;flex-wrap:wrap;margin-top:18px">{"".join(steps)}</div>'
        f'<div class="qp-note" style="margin-top:18px">每一步只在前一步成立后推进；未完成的一步如实标注，不提前渲染结论。</div></div>',
        unsafe_allow_html=True,
    )


# =============================================================================
# 来源
# =============================================================================

def render_sources():
    page_head("来源", "来源与证据边界",
              "真实事实、真实传感器数据与模拟演示数据在产品中明确区分。")
    sources = [
        ("贵州省交通运输厅", "贵州桥梁网络、桥梁养护与公开灾害通报相关信息。",
         "https://jt.guizhou.gov.cn/", "官方来源"),
        ("贵州高速集团", "省级高速公路数字化养护、GIS 与移动巡检相关公开信息。",
         "https://www.gzhighway.com/", "官方来源"),
        ("物理验证原始数据", "本地 data/physical_validation/ 下的真实 iPhone Sensor Logger ZIP；页面实时重算，不是硬编码结果。",
         "/Physical_Validation", "真实数据"),
        ("模拟演示数据", "离线可重复的模拟网络数据，用于展示多次过桥融合与优先检查逻辑，不代表真实运营网络。",
         "/?view=method", "模拟演示"),
    ]
    badge_cls = {"官方来源": "sim", "真实数据": "real", "模拟演示": "sim"}
    parts = [
        f'<div class="src-row"><div><div class="src-name">{name}</div>'
        f'<div class="src-note">{desc}</div>'
        f'<a class="src-link" href="{url}" target="_blank">打开来源 / 证据 ↗</a></div>'
        f'<span class="qp-badge {badge_cls[tag]}">{tag}</span></div>'
        for name, desc, url, tag in sources
    ]
    st.markdown(
        '<style>'
        '.src-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:20px;align-items:baseline;'
        'padding:22px 2px 20px;border-top:1px solid #152721;transition:background .15s}'
        '.src-row:hover{background:rgba(111,216,197,.025)}'
        '.src-row:last-of-type{border-bottom:1px solid #152721}'
        '.src-name{font-size:16.5px;font-weight:700;color:#e9f1ec}'
        '.src-note{font-size:13px;color:#7f948a;line-height:1.9;margin-top:8px;max-width:760px}'
        '.src-link{color:#6fd8c5;text-decoration:none;font-size:12.5px}'
        '</style>' + "".join(parts),
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="qp-note" style="margin-top:48px;border-top:1px solid #1f342b;padding-top:16px">'
        '方法边界：黔脉只筛查桥梁相对自身历史基线的持续动态响应变化，不进行损伤类型识别、裂缝诊断或安全等级判断，'
        '也不能替代专业桥梁检测；输出仅为"建议优先工程检查"。</div>',
        unsafe_allow_html=True,
    )


# =============================================================================
# 路由
# =============================================================================

inject_styles()
topbar(view)
if view == "bridge":
    render_bridge()
elif view == "method":
    render_method()
elif view == "evidence":
    render_evidence()
elif view == "arch":
    render_architecture()
elif view == "sources":
    render_sources()
else:
    render_overview()
