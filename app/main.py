"""万泰新天地智能运营中台 - Streamlit 主入口

仅负责:页面配置、全局主题 CSS、侧边栏品牌区与全局筛选器、AI 就绪状态。
业务内容(首页 KPI/趋势/Top5/AI日报)见 pages/1_首页概览.py。
"""
import streamlit as st
import os
import sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import MALL_NAME, MALL_CITY
from app.viz_theme import build_global_css, current_palette, brand_header_html
from app.llm_client import is_llm_ready

# 页面配置
st.set_page_config(
    page_title=f"{MALL_NAME}智能运营中台",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 注入全局 CSS(按当前主题动态生成,明暗都正确)
st.markdown(build_global_css(), unsafe_allow_html=True)

# ===== 侧边栏 =====
with st.sidebar:
    P = current_palette()  # 当前主题 token(明/暗动态)
    st.markdown(brand_header_html(f"{MALL_NAME}", f"{MALL_CITY} · 智能运营中台 V2.0", "万"),
                unsafe_allow_html=True)
    st.markdown(f'<hr style="border-color:{P["border"]};margin:14px 0">',
                unsafe_allow_html=True)

    # AI 就绪状态指示
    llm_ok = is_llm_ready()
    status_color = P["good"] if llm_ok else P["warning"]
    status_text = "AI 引擎就绪" if llm_ok else "AI 引擎未就绪(降级规则)"
    st.markdown(
        f'<div style="background:{P["surface"]};border:1px solid {P["border"]};'
        f'border-radius:8px;padding:10px 12px;margin-bottom:12px">'
        f'<div style="display:flex;align-items:center;gap:8px">'
        f'<span style="width:8px;height:8px;border-radius:50%;background:{status_color};'
        f'display:inline-block;box-shadow:0 0 6px {status_color}"></span>'
        f'<span style="color:{P["text_secondary"]};font-size:0.85rem">{status_text}</span>'
        f'</div>'
        f'<div style="color:{P["text_muted"]};font-size:0.72rem;margin-top:4px">'
        f'大模型+RAG 营销 Agent</div></div>',
        unsafe_allow_html=True,
    )

    # 主题切换提示(Streamlit 原生:右上角菜单 → Settings → Theme)
    st.markdown(
        f'<div style="background:{P["surface"]};border:1px solid {P["border"]};'
        f'border-radius:8px;padding:8px 12px;margin-bottom:12px">'
        f'<div style="color:{P["text_secondary"]};font-size:0.78rem;font-weight:600;margin-bottom:2px">🎨 主题</div>'
        f'<div style="color:{P["text_muted"]};font-size:0.7rem">'
        f'右上角 ⚙️ → Settings → Theme 切换明/暗</div></div>',
        unsafe_allow_html=True,
    )

    # 全局筛选器
    st.markdown(f'<div style="color:{P["text_secondary"]};font-size:0.9rem;font-weight:600;margin-bottom:8px">📊 全局筛选</div>',
                unsafe_allow_html=True)
    date_range = st.date_input(
        "日期范围",
        value=(pd.Timestamp("2023-01-01").date(), pd.Timestamp("2023-12-31").date()),
        key="global_date_range",
    )
    floor_filter = st.multiselect(
        "楼层",
        options=[1, 2, 3, 4, 5],
        default=[1, 2, 3, 4, 5],
        key="global_floor",
    )

    st.markdown(f'<hr style="border-color:{P["border"]};margin:14px 0">',
                unsafe_allow_html=True)
    st.markdown(
        f'<div style="color:{P["text_muted"]};font-size:0.75rem">'
        f'© 2026 {MALL_NAME} · Project WONDERS</div>',
        unsafe_allow_html=True)

# 首页引导(Hero)
st.markdown(f"""
<div style="text-align:center;padding:48px 20px 32px 20px">
  <div style="font-size:2.4rem;font-weight:800;color:{P['text_primary']};margin-bottom:10px;letter-spacing:1px">
    🏪 {MALL_NAME} <span style="color:{P['cat_gold']}">智能运营中台</span>
  </div>
  <div style="color:{P['text_secondary']};font-size:1.05rem;margin-bottom:8px">
    AI 驱动的客流画像 · 会员分层 · 商铺评估 · 智能营销
  </div>
  <div style="color:{P['text_muted']};font-size:0.85rem;margin-bottom:28px">
    RAG 知识库 + 营销 Agent · 让商场从"凭经验"转向"看数据做决策"
  </div>
  <div style="color:{P['text_secondary']};font-size:0.9rem">
    👈 从左侧导航进入 <b style="color:{P['cat_blue']}">首页概览</b> 查看核心指标与 AI 运营日报
  </div>
</div>
""", unsafe_allow_html=True)
