"""万泰新天地智能运营中台 - Streamlit 主入口

仅负责:页面配置、全局主题 CSS、侧边栏品牌区与全局筛选器、AI 就绪状态。
业务内容(首页 KPI/趋势/Top5/AI日报)见 pages/1_首页概览.py。
"""
import streamlit as st
import os
import sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import MALL_NAME, MALL_CITY, DATA_END, DATA_TODAY
from app.viz_theme import build_global_css, current_palette, brand_header_html
from app.llm_client import is_llm_ready

# 页面配置(layout=wide 在手机端 Streamlit 会自动转单列;sidebar 手机默认收起)
st.set_page_config(
    page_title=f"{MALL_NAME}智能运营中台",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="auto",  # 手机端默认收起,桌面端展开
)

# 注入全局 CSS(按当前主题动态生成,明暗都正确)
st.markdown(build_global_css(), unsafe_allow_html=True)

# 移动端防误触JS:阻止双指缩放(gesturestart)+ 双击缩放 + 多指触摸
# iOS Safari 的 CSS user-zoom:fixed 不完全可靠,需 JS 兜底
_anti_zoom_js = """
<script>
(function(){
  if (window.__noZoomBound) return; window.__noZoomBound = true;
  // 阻止双指缩放手势(iOS)
  document.addEventListener('gesturestart', function(e){ e.preventDefault(); }, {passive:false});
  document.addEventListener('gesturechange', function(e){ e.preventDefault(); }, {passive:false});
  document.addEventListener('gestureend', function(e){ e.preventDefault(); }, {passive:false});
  // 阻止双击缩放:最后一次 touchend 后 300ms 内的再次 touchend 视为双击
  var lastTouchEnd = 0;
  document.addEventListener('touchend', function(e){
    var now = Date.now();
    if (now - lastTouchEnd <= 350) { e.preventDefault(); }
    lastTouchEnd = now;
  }, {passive:false});
  // 阻止双指 touchmove(安卓部分浏览器绕过 gesture 事件)
  document.addEventListener('touchmove', function(e){
    if (e.touches && e.touches.length > 1) { e.preventDefault(); }
  }, {passive:false});
  // 强制 viewport meta 禁用缩放(覆盖 Streamlit 默认)
  var meta = document.querySelector('meta[name="viewport"]');
  if (meta) { meta.setAttribute('content', 'width=device-width, initial-scale=1, maximum-scale=1, minimum-scale=1, user-scalable=no, viewport-fit=cover'); }
})();
</script>
"""
st.markdown(_anti_zoom_js, unsafe_allow_html=True)

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

    # 全局筛选器(时间段,各页面侧边栏也会渲染同一组件)
    from app.date_filter import render_date_filter
    render_date_filter()

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
