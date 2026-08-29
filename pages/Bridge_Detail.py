"""桥梁详情的规范入口是 /?view=bridge（app.py render_bridge）。

此 multipage 路由已无内部链接指向，保留双份实现会漂移；
这里直接重定向到规范入口，保证评委从任何路径看到的是同一份页面。
"""
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="黔脉 · 桥梁详情", page_icon="🌉", layout="wide")
components.html(
    '<script>window.parent.location.replace("/?view=bridge");</script>',
    height=0,
)
