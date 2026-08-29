"""工作原理页的规范入口是 /?view=method（app.py render_method，含 1000 条轨迹互动演示）。

此 multipage 路由已无内部链接指向（来源页已改指规范入口），
保留旧版 50 条轨迹的简化实现会与新页漂移；这里直接重定向。
"""
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="黔脉 · 原理演示", page_icon="◌", layout="wide")
components.html(
    '<script>window.parent.location.replace("/?view=method");</script>',
    height=0,
)
