"""营销助手 —— AI Agent 驱动的营销方案生成

工作流:选目标 RFM 群体 → 真实群体统计 → RAG 检索商户/方法论知识
       → 大模型生成结构化方案(目标/策略/选品/话术/ROI)→ 分块卡片渲染
大模型不可用时自动 fallback 规则引擎,保证 Demo 不崩。
"""
import streamlit as st
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.utils import load_csv
from app.processor import clean_data, mask_sensitive_data
from app.models import RFMModel
from app.agent import generate_marketing_plan
from app.viz_theme import (
    segment_colors, SEGMENT_ORDER, apply_theme,
    stat_card_html, kpi_grid_html, hero_figure_html, marketing_plan_html,
    inject_global_css, current_palette,
)

st.set_page_config(page_title="营销助手", layout="wide")
inject_global_css()
P = current_palette()


@st.cache_data(ttl=3600)
def load_data():
    members = load_csv("members_2023.csv", "raw")
    members_clean = clean_data(members)
    members_masked = mask_sensitive_data(members_clean)
    rfm = RFMModel()
    labels = rfm.fit(members_masked)
    members_masked["segment"] = labels
    return members_masked


members = load_data()

st.title("📢 营销助手")
st.caption("RAG 知识库 + 大模型 Agent · 自动生成可落地的会员营销方案")


# ===== 选择目标群体 =====
seg_col, gen_col = st.columns([2, 1])
with seg_col:
    segment = st.selectbox("选择目标会员群体", options=SEGMENT_ORDER, index=0,
                           help="基于 RFM 分层:高价值/潜力/新客/沉睡")
with gen_col:
    use_llm = st.toggle("启用 AI 生成", value=True,
                        help="关闭则用规则引擎兜底(无大模型调用)")
seg_data = members[members["segment"] == segment].copy()
seg_color = segment_colors().get(segment, P["cat_blue"])

# ===== KPI 行:群体真实统计 =====
total_seg = len(seg_data)
total_all = len(members)
stats = {
    "count": total_seg,
    "pct": total_seg / total_all * 100 if total_all else 0,
    "avg_spent": seg_data["total_spent"].mean(),
    "avg_visit": seg_data["visit_count"].mean(),
    "avg_order": seg_data["avg_spent"].mean(),
}
kpi = (
    stat_card_html("群体人数", f"{stats['count']:,}", f"{stats['pct']:.1f}% 占比",
                   accent=seg_color)
    + stat_card_html("平均累计消费", f"¥{stats['avg_spent']:,.0f}", "全体累计", accent=seg_color)
    + stat_card_html("平均到店", f"{stats['avg_visit']:.1f} 次", "累计", accent=seg_color)
    + stat_card_html("平均客单价", f"¥{stats['avg_order']:,.0f}", "单次", accent=seg_color)
)
st.markdown(kpi_grid_html(kpi, cols=4), unsafe_allow_html=True)

# ===== AI 营销方案生成 =====
st.markdown("---")
st.subheader("💡 智能营销方案")

with st.spinner(f"Agent 正在基于真实数据 + RAG 知识库生成 {segment} 群体方案..." if use_llm
                else "生成方案中..."):
    # 方案按群体+统计指纹缓存(统计变才重算)
    @st.cache_data(ttl=600)
    def _gen(seg, count, avg_spent, avg_visit, avg_order, use_llm_flag):
        s = {"count": count, "pct": 0, "avg_spent": avg_spent,
             "avg_visit": avg_visit, "avg_order": avg_order}
        return generate_marketing_plan(seg, s, use_llm=use_llm_flag)

    plan = _gen(segment, int(stats["count"]), float(stats["avg_spent"]),
                float(stats["avg_visit"]), float(stats["avg_order"]), use_llm)

# 渲染分块方案
st.markdown(marketing_plan_html(plan), unsafe_allow_html=True)

# ===== 群体画像(性别/品类偏好) =====
st.markdown("---")
st.subheader("👤 群体画像")
import plotly.graph_objects as go
col1, col2 = st.columns(2)

with col1:
    st.markdown(f'<div style="color:{P["text_secondary"]};font-weight:600;margin-bottom:8px">性别分布</div>',
                unsafe_allow_html=True)
    gender_counts = seg_data["gender"].value_counts()
    g_map = {"男": P["cat_blue"], "女": P["cat_magenta"]}
    fig1 = go.Figure()
    for g, cnt in zip(gender_counts.index, gender_counts.values):
        fig1.add_trace(go.Bar(
            y=[g], x=[cnt], orientation="h", name=g,
            marker_color=g_map.get(g, P["cat_blue"]), width=0.6,
            text=[f"{cnt:,} ({cnt/len(seg_data)*100:.0f}%)"], textposition="outside",
            textfont=dict(color=P["text_secondary"], size=12),
            hovertemplate=f"{g}<br>%{{x:,}} 人<extra></extra>",
        ))
    fig1.update_layout(bargap=0.4, showlegend=False)
    fig1.update_xaxes(title_text="人数")
    apply_theme(fig1, height=300)
    st.plotly_chart(fig1, width="stretch")

with col2:
    st.markdown(f'<div style="color:{P["text_secondary"]};font-weight:600;margin-bottom:8px">品类偏好</div>',
                unsafe_allow_html=True)
    cat_counts = seg_data["preferred_category"].value_counts()
    cats = list(cat_counts.index)
    c_map = {c: P["cat_aqua"] for c in cats}
    c_map[cats[0]] = P["cat_gold"]
    fig2 = go.Figure()
    for c, cnt in zip(cats, cat_counts.values):
        fig2.add_trace(go.Bar(
            y=[c], x=[cnt], orientation="h", name=c,
            marker_color=c_map.get(c, P["cat_aqua"]), width=0.6,
            text=[f"{cnt:,}"], textposition="outside",
            textfont=dict(color=P["text_secondary"], size=12),
            hovertemplate=f"{c}<br>%{{x:,}} 人<extra></extra>",
        ))
    fig2.update_layout(bargap=0.4, showlegend=False)
    fig2.update_xaxes(title_text="人数")
    apply_theme(fig2, height=300)
    st.plotly_chart(fig2, width="stretch")
