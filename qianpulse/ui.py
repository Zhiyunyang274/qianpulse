"""QianPulse 视觉系统：深色编辑排版（editorial），非仪表盘堆砌。

原则：
- 展示层用衬线（Songti/Noto Serif）大标题，正文系统无衬线
- 数字用 serif + tabular-nums，不滥用等宽终端体
- 标签克制：小字号、宽字距、中文为主，不用全大写英文黑话
- 用分割线和留白组织信息，少用圆角卡片框
"""
import streamlit as st
import streamlit.components.v1 as components


TOKENS_CSS = """
<style>
:root{
  --qp-bg:#0b1512; --qp-bg-deep:#081010; --qp-panel:#0f1b16; --qp-panel-2:#12221b;
  --qp-line:#1c3129; --qp-line-soft:#152721;
  --qp-text:#e9f1ec; --qp-dim:#b9c8c0; --qp-muted:#7f948a; --qp-faint:#5c7168;
  --qp-accent:#6fd8c5; --qp-accent-deep:#2f8d7c;
  --qp-shift:#e07a62; --qp-watch:#d9b46e; --qp-normal:#7fb89a;
  --qp-serif:"Songti SC","Noto Serif SC","STSong",Georgia,serif;
}
html,body,[class*="css"]{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}
/* 背景深度：黔地暮色 + 页底雾中山影（渐隐烘焙进图，与底色同色系衔接） */
.stApp{background:
  radial-gradient(ellipse 1200px 640px at 50% -10%,rgba(111,216,197,.05),transparent 60%),
  radial-gradient(ellipse 1000px 560px at 92% 115%,rgba(36,66,84,.075),transparent 55%),
  __FOOTER_MIST__
  linear-gradient(180deg,#0c1613 0%,#0a1411 52%,#080f0e 100%)!important;color:var(--qp-text)}
.stApp>.main>.block-container{background:transparent!important}
#MainMenu,header,footer,[data-testid="stHeader"],[data-testid="stToolbar"],
[data-testid="stSidebarNav"]{display:none!important}
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp h5,.stApp h6{color:var(--qp-text)!important}
.stApp [data-testid="stCaptionContainer"] p{color:var(--qp-muted)!important}
.stApp [data-testid="stMarkdownContainer"] a{color:var(--qp-accent)!important}
.block-container{max-width:1400px!important;padding:0 48px 80px!important}

/* ---------- 顶部 ---------- */
.qp-topbar{height:64px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--qp-line);position:relative;z-index:5}
.qp-topbar::after{content:"";position:absolute;left:0;right:0;bottom:-1px;height:1px;background:linear-gradient(90deg,transparent,rgba(111,216,197,.22) 30%,rgba(111,216,197,.22) 70%,transparent);pointer-events:none}
.qp-brand{display:flex;align-items:center;padding-right:24px;border-right:1px solid var(--qp-line-soft);height:38px}
/* 字标：衬线「黔脉」+ 微型脉搏线 + 极小拼音注 */
.qp-wordmark{display:flex;flex-direction:column;gap:3px;white-space:nowrap}
.qp-wordmark b{font-family:var(--qp-serif);font-size:22px;font-weight:700;letter-spacing:.34em;color:var(--qp-text);line-height:1;margin-right:-.34em}
.qp-logo-pulse{width:64px;height:11px;display:block}
.qp-logo-pulse path{stroke-dasharray:120;animation:qp-logo-draw 3.2s ease-in-out infinite}
@keyframes qp-logo-draw{0%,12%{stroke-dashoffset:120}55%,70%{stroke-dashoffset:0}100%{stroke-dashoffset:-120}}
.qp-nav{display:flex;gap:34px;align-items:center;flex:1;justify-content:center}
.qp-nav a{color:var(--qp-muted)!important;text-decoration:none!important;font-size:13.5px;letter-spacing:.02em;padding:20px 1px 17px;position:relative;transition:color .18s}
.qp-nav a::after{content:"";position:absolute;left:-2px;right:-2px;bottom:0;height:2px;border-radius:2px;background:linear-gradient(90deg,var(--qp-accent-deep),var(--qp-accent));transform:scaleX(0);transform-origin:center;transition:transform .22s ease}
.qp-nav a:hover{color:var(--qp-dim)}
.qp-nav a.active{color:var(--qp-text)!important}
.qp-nav a.active::after{transform:scaleX(1)}
.qp-nav a.active::before{content:"";position:absolute;left:-8px;top:50%;width:3px;height:3px;border-radius:50%;background:var(--qp-accent);transform:translateY(-50%);box-shadow:0 0 6px var(--qp-accent)}
.qp-tag{font-size:11px;color:var(--qp-faint);letter-spacing:.14em;display:flex;align-items:center;gap:8px}
.qp-tag i{width:6px;height:6px;border-radius:50%;background:var(--qp-accent);display:inline-block;box-shadow:0 0 8px rgba(111,216,197,.8);animation:qp-tag-breathe 3s ease-in-out infinite}
@keyframes qp-tag-breathe{0%,100%{opacity:.7}50%{opacity:1}}

/* ---------- 页头 ---------- */
.qp-pagehead{padding:56px 0 34px;border-bottom:1px solid var(--qp-line);display:flex;justify-content:space-between;align-items:flex-end;gap:24px}
.qp-kicker{font-size:11.5px;letter-spacing:.24em;color:var(--qp-accent);font-weight:600;display:flex;align-items:center;gap:10px}
.qp-kicker::before{content:"";width:22px;height:1px;background:linear-gradient(90deg,var(--qp-accent),transparent)}
.qp-title{font-family:var(--qp-serif);font-size:38px;line-height:1.22;letter-spacing:.015em;margin:14px 0 12px;font-weight:600;color:var(--qp-text)}
.qp-subtitle{font-size:14px;color:var(--qp-muted);line-height:1.9}
.qp-headnote{flex-shrink:0;padding-bottom:6px}

/* ---------- 结构 ---------- */
.qp-card{background:linear-gradient(170deg,rgba(255,255,255,.028),rgba(255,255,255,.007) 45%),var(--qp-panel);border:1px solid rgba(111,216,197,.12);border-radius:12px;padding:26px;box-shadow:0 16px 44px rgba(0,0,0,.36),0 1px 0 rgba(255,255,255,.05) inset;position:relative}
.qp-card::before{content:"";position:absolute;top:0;left:8%;right:8%;height:1px;background:linear-gradient(90deg,transparent,rgba(233,241,236,.13),transparent);pointer-events:none}
.qp-card-title{font-size:17px;font-weight:700;color:var(--qp-text);margin:4px 0 6px}
.qp-note{color:var(--qp-muted);font-size:13px;line-height:1.9}
.qp-action{border-left:2px solid var(--qp-shift);padding-left:14px;color:var(--qp-dim);font-size:13.5px;line-height:1.7}

/* ---------- 徽章（仅限数据真实性标注） ---------- */
.qp-badge{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:4.5px 11px;font-size:10.5px;font-weight:650;letter-spacing:.1em;border:1px solid transparent;white-space:nowrap;box-shadow:0 1px 0 rgba(255,255,255,.05) inset}
.qp-badge.sim{background:rgba(127,148,138,.08);color:#95a89e;border-color:rgba(127,148,138,.22)}
.qp-badge.real{background:rgba(111,216,197,.08);color:var(--qp-accent);border-color:rgba(111,216,197,.3);text-shadow:0 0 12px rgba(111,216,197,.4)}
.qp-badge.shift{background:rgba(224,122,98,.1);color:#eda28d;border-color:rgba(224,122,98,.34);text-shadow:0 0 12px rgba(224,122,98,.35)}
.qp-badge.watch{background:rgba(217,180,110,.08);color:#e3c584;border-color:rgba(217,180,110,.28)}
.qp-badge.normal{background:rgba(127,184,154,.08);color:#9ecbb0;border-color:rgba(127,184,154,.24)}

/* ---------- 指标：悬浮玻璃卡 ---------- */
.qp-metric{padding:22px 24px 20px;border:1px solid rgba(111,216,197,.18);border-radius:12px;background:linear-gradient(168deg,rgba(111,216,197,.085),#142520 46%,#101d17);box-shadow:0 22px 48px rgba(0,0,0,.5),0 2px 0 rgba(255,255,255,.05) inset,0 0 0 1px rgba(4,9,7,.7);position:relative;overflow:hidden;transition:transform .22s ease,box-shadow .22s ease,border-color .22s ease;backdrop-filter:blur(6px)}
.qp-metric::before{content:"";position:absolute;top:0;left:6%;right:6%;height:1.5px;background:linear-gradient(90deg,transparent,rgba(159,232,218,.5),transparent)}
.qp-metric:hover{transform:translateY(-3px);border-color:rgba(111,216,197,.5);box-shadow:0 28px 60px rgba(0,0,0,.58),0 2px 0 rgba(255,255,255,.07) inset,0 0 32px rgba(111,216,197,.1)}
.qp-metric span{display:block;color:var(--qp-muted);font-size:11px;letter-spacing:.16em;margin-bottom:12px}
.qp-metric strong{font-family:Georgia,serif;font-size:34px;font-weight:500;font-variant-numeric:tabular-nums;letter-spacing:0;color:var(--qp-text);display:block;line-height:1}
.qp-metric em{font-style:normal;font-size:12px;color:var(--qp-faint);margin-left:6px;font-weight:500}
.qp-metric.alert strong{color:var(--qp-shift);text-shadow:0 0 24px rgba(224,122,98,.3)}
.qp-metric.alert::before{content:"";position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,rgba(224,122,98,.55),transparent)}

/* ---------- 章节 ---------- */
.qp-section-label{font-size:11.5px;letter-spacing:.24em;color:var(--qp-accent);font-weight:600;margin:56px 0 12px;display:flex;align-items:center;gap:10px}
.qp-section-label::before{content:"";width:22px;height:1px;background:linear-gradient(90deg,var(--qp-accent),transparent)}
.qp-section-title{font-family:var(--qp-serif);font-size:27px;font-weight:600;color:var(--qp-text);line-height:1.35;margin-bottom:12px;letter-spacing:.01em}
.qp-section-copy{color:var(--qp-muted);font-size:13.5px;line-height:1.95;margin-bottom:24px;max-width:760px}

/* ---------- 原生组件深色化 ---------- */
.stButton button{border-radius:6px!important;border:1px solid var(--qp-line)!important;background:var(--qp-panel-2)!important;color:var(--qp-text)!important;min-height:40px}
.stButton button p{color:var(--qp-text)!important}
.stButton button[kind="primary"]{background:var(--qp-accent-deep)!important;border-color:var(--qp-accent-deep)!important;color:#eafff9!important}
.stButton button[kind="primary"] p{color:#eafff9!important}
.stButton button:hover{border-color:var(--qp-accent)!important}
[data-testid="stTable"]{background:var(--qp-panel)!important;border:1px solid var(--qp-line-soft);border-radius:6px;overflow:hidden}
[data-testid="stTable"] table{border-color:var(--qp-line-soft)!important;color:var(--qp-dim)!important;background:transparent!important}
[data-testid="stTable"] thead th{background:var(--qp-panel-2)!important;color:var(--qp-muted)!important;border-color:var(--qp-line-soft)!important;font-weight:650}
[data-testid="stTable"] tbody td{border-color:var(--qp-line-soft)!important}
[data-testid="stTable"] tbody tr:hover{background:rgba(111,216,197,.04)!important}
.stApp div[data-testid="stAlert"]{background:var(--qp-panel);border:1px solid var(--qp-line);color:var(--qp-dim);border-radius:6px}
.stApp div[data-testid="stAlert"] p{color:var(--qp-dim)}
[data-baseweb="popover"],[data-baseweb="menu"]{background:var(--qp-panel-2)!important;border:1px solid var(--qp-line)!important;color:var(--qp-text)!important}
[data-baseweb="input"],[data-baseweb="base-input"],input{background:var(--qp-bg-deep)!important;color:var(--qp-text)!important;border-color:var(--qp-line)!important}
[data-testid="stFileUploaderDropzone"]{background:var(--qp-bg-deep);border-color:var(--qp-line);border-radius:6px}
[data-testid="stFileUploaderDropzone"] span,[data-testid="stFileUploaderDropzone"] small{color:var(--qp-muted)!important}
.stTabs [data-baseweb="tab-list"]{gap:6px;border-bottom:1px solid var(--qp-line)}
.stTabs [data-baseweb="tab"]{color:var(--qp-muted)!important;background:transparent!important}
.stTabs [aria-selected="true"]{color:var(--qp-accent)!important}
code{background:var(--qp-panel-2)!important;color:var(--qp-dim)!important}
hr{border-color:var(--qp-line)!important}

@media(max-width:900px){
  .block-container{padding:0 20px 60px!important}
  .qp-topbar{gap:12px;height:auto;min-height:56px;flex-wrap:wrap;padding:8px 0}
  .qp-nav{order:3;width:100%;gap:16px;overflow-x:auto;justify-content:flex-start}
  .qp-nav a{padding:4px 0 8px;white-space:nowrap}
  .qp-tag{margin-left:auto}
  .qp-pagehead{flex-direction:column;align-items:flex-start;padding-top:32px}
  .qp-title{font-size:29px}
}
</style>
"""

CHART_COLORS = {
    "base": "#5f8a7a",
    "current": "#6fd8c5",
    "alert": "#e07a62",
    "watch": "#d9b46e",
    "grid": "rgba(233,241,236,.055)",
    "axis": "rgba(139,166,154,.35)",
    "text": "rgba(139,166,154,.9)",
}


# Streamlit 强制 markdown 链接 target="_blank"（点一个按钮开一个新标签页）。
# 此同源组件持续移除站内链接的 target，让导航在同一标签页内完成。
_NAV_FIX = """
<script>
(function(){
  function fix(){
    try{
      parent.document.querySelectorAll('a[href^="/"]').forEach(function(a){
        // 只移除 Streamlit 强加的 _blank；保留 _parent（intro 全屏组件的跳出链接依赖它）
        if (a.target === '_blank') a.removeAttribute('target');
      });
    }catch(e){}
  }
  fix();
  try{
    new MutationObserver(fix).observe(parent.document.body, {childList:true, subtree:true});
  }catch(e){}
})();
</script>
"""


def _footer_mist_layer():
    """页底雾中山影：专为深色背景生成的喀斯特夜雾图（纯青绿色调），
    轻模糊 + 渐隐烘焙进像素，作为 .stApp 背景一层贴在页面最底部。"""
    import base64
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "assets" / "bg" / "footer_mist.jpg"
    try:
        uri = "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")
    except OSError:
        return ""
    return f'url("{uri}") center bottom/100% 480px no-repeat,'


TOKENS_CSS = TOKENS_CSS.replace("__FOOTER_MIST__", _footer_mist_layer())


def inject_styles(dark=True, sidebar=False):
    """注入全局设计系统。

    sidebar=False（默认）时彻底隐藏 Streamlit 默认侧边栏与折叠按钮：
    导航职责完全交给编辑式 topbar，避免双导航系统的模板感。
    需要侧边栏控件（如真实实验页）的页面显式传 sidebar=True。
    """
    css = TOKENS_CSS
    if not sidebar:
        css += """
<style>
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],
[data-testid="stSidebarExpandButton"],section[data-testid="stSidebar"]{display:none!important}
</style>
"""
    st.markdown(css, unsafe_allow_html=True)
    components.html(_NAV_FIX, height=0)


def plotly_theme(height=320, show_y=True):
    """统一的 Plotly 深色布局，所有图表必须经过这里。

    精修要点：网格极细虚线、隐藏轴线框、只保留水平网格、
    轴文字低透明度——摆脱默认模板感。
    """
    return dict(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family='"PingFang SC",sans-serif', color=CHART_COLORS["text"], size=11),
        margin=dict(l=44 if show_y else 16, r=16, t=8, b=38),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#12221b", bordercolor="#2a4536",
                        font=dict(color="#e9f1ec", size=11), align="left"),
        legend=dict(orientation="h", y=1.08, x=0, font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showgrid=False, zeroline=False, showline=False,
                   tickcolor="rgba(139,166,154,.35)", title=dict(font=dict(size=10))),
        yaxis=dict(showgrid=True, showticklabels=show_y, gridcolor=CHART_COLORS["grid"],
                   griddash="dot", zeroline=False, showline=False,
                   title=dict(font=dict(size=10))),
    )


def show_chart(fig):
    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False, "scrollZoom": False})


def topbar(view=None, links=None):
    """渲染顶部 chrome。view 用于高亮当前导航项。"""
    if links is None:
        links = [("overview", "总览", "/?view=overview"), ("bridge", "桥梁", "/?view=bridge"),
                 ("method", "工作原理", "/?view=method"), ("evidence", "真实证据", "/?view=evidence"),
                 ("arch", "系统架构", "/?view=arch"), ("sources", "来源", "/?view=sources")]
    nav = "".join(
        f'<a class="{"active" if view == key else ""}" href="{url}" target="_self">{label}</a>'
        for key, label, url in links
    )
    logo = (
        '<div class="qp-brand">'
        '<span class="qp-wordmark"><b>黔脉</b>'
        '<svg class="qp-logo-pulse" viewBox="0 0 64 11" aria-hidden="true">'
        '<defs><linearGradient id="qpg" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0" stop-color="#2f8d7c"/><stop offset=".5" stop-color="#6fd8c5"/>'
        '<stop offset="1" stop-color="#2f8d7c"/></linearGradient></defs>'
        '<path d="M1 6 H14 L18 1.5 L25 10 L30 4.5 L34 6 H63" fill="none" '
        'stroke="url(#qpg)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg></span></div>'
    )
    st.markdown(
        f'<div class="qp-topbar">{logo}'
        f'<nav class="qp-nav">{nav}</nav>'
        f'<div class="qp-tag"><i></i>模拟网络与真实实验分层标注</div></div>',
        unsafe_allow_html=True,
    )


def page_head(kicker, title, subtitle="", badge_html=""):
    st.markdown(
        f'<div class="qp-pagehead"><div><div class="qp-kicker">{kicker}</div>'
        f'<div class="qp-title">{title}</div><div class="qp-subtitle">{subtitle}</div></div>'
        f'<div class="qp-headnote">{badge_html}</div></div>',
        unsafe_allow_html=True,
    )


def metric(label, value, unit="", alert=False):
    cls = "qp-metric alert" if alert else "qp-metric"
    st.markdown(
        f'<div class="{cls}"><span>{label}</span><strong>{value}</strong><em>{unit}</em></div>',
        unsafe_allow_html=True,
    )


# ---- 兼容旧 pages/ 的 API ------------------------------------------------

def chrome(title="总览", subtitle="桥梁动态响应筛查 · 操作台"):
    inject_styles()
    topbar()


def section(label, title, copy=""):
    st.markdown(
        f'<div class="qp-section-label">{label}</div><div class="qp-section-title">{title}</div>'
        f'<div class="qp-section-copy">{copy}</div>', unsafe_allow_html=True,
    )


def status(label, kind="normal"):
    return f'<span class="qp-badge {kind}">{label}</span>'
