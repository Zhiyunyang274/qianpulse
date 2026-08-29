"""来源页的规范入口是 /?view=sources（app.py render_sources）。

此 multipage 路由已无内部链接指向，保留双份实现会漂移；
这里直接重定向到规范入口，保证评委从任何路径看到的是同一份页面。
"""
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="黔脉 · 来源与证据", page_icon="📚", layout="wide")
components.html(
    '<script>window.parent.location.replace("/?view=sources");</script>',
    height=0,
)
