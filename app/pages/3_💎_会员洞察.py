"""会员洞察 —— 等级分布 + RFM 分层 + 年龄 + 群体消费对比"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.utils import load_csv
from app.processor import clean_data, mask_sensitive_data
from app.models import RFMModel
from app.date_filter import filter_members, get_date_range
from app.viz_theme import (
    apply_theme, chart_config, segment_colors, SEGMENT_ORDER, level_colors,
    stat_card_html, kpi_grid_html, MARK_LINE_WIDTH, MARK_GAP, inject_global_css, mobile_notice_html, current_palette,
)

st.set_page_config(page_title="会员洞察", layout="wide")
inject_global_css()
P = current_palette()
from app.date_filter import render_date_filter as _rdf
_rdf()  # 侧边栏时间段筛选器(每个页面都渲染,保证全页面可切换)


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
# 时段内活跃会员(last_visit_date 落在选定范围) —— 用于"近期活跃"统计
members_active = filter_members(members)
_dr_start, _dr_end = get_date_range()
_dr_label = f"{_dr_start.date()} ~ {_dr_end.date()}"

st.title("💎 会员洞察")
st.markdown(mobile_notice_html(), unsafe_allow_html=True)
st.caption(f"📅 时段内活跃会员:**{len(members_active):,}** 人({_dr_label}) · 下方 RFM 分群基于全量会员存量结构")

# ===== KPI 行 =====
total = len(members)
vip = len(members[members["segment"] == "高价值"])
sleep = len(members[members["segment"] == "沉睡"])
avg_spend = members["total_spent"].mean()
kpi = (
    stat_card_html("会员总数", f"{total:,}", f"时段活跃 {len(members_active):,}", accent=P["cat_blue"])
    + stat_card_html("高价值会员", f"{vip:,}", f"{vip/total*100:.1f}% 占比",
                     accent=P["cat_gold"])
    + stat_card_html("沉睡会员", f"{sleep:,}", f"{sleep/total*100:.1f}% 待激活",
                     accent=P["cat_red"])
    + stat_card_html("人均累计消费", f"¥{avg_spend:,.0f}", "全体均值",
                     accent=P["cat_aqua"])
)
st.markdown(kpi_grid_html(kpi, cols=4), unsafe_allow_html=True)

# ===== 等级分布(饼图→横条形,part-to-whole 用条形)=====
col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 会员等级分布")
    level_counts = members["level"].value_counts().reindex(["黑金", "金卡", "银卡", "普通"]).dropna()
    fig1 = go.Figure()
    for lvl, cnt in zip(level_counts.index, level_counts.values):
        c = level_colors().get(lvl, P["cat_blue"])
        fig1.add_trace(go.Bar(
            y=[lvl], x=[cnt], orientation="h", name=lvl,
            marker_color=c, width=0.6,
            text=[f"{cnt:,} ({cnt/total*100:.1f}%)"], textposition="outside",
            textfont=dict(color=P["text_secondary"], size=12),
            hovertemplate=f"{lvl}<br>%{{x:,}} 人<extra></extra>",
        ))
    fig1.update_layout(bargap=0.4, showlegend=False)
    fig1.update_xaxes(title_text="人数")
    apply_theme(fig1, height=380)
    st.plotly_chart(fig1, config=chart_config(), width="stretch")

# ===== RFM 分层(固定色,颜色跟随实体)=====
with col2:
    st.subheader("🎯 RFM 分层结果")
    seg_counts = members["segment"].value_counts().reindex(SEGMENT_ORDER).dropna()
    fig2 = go.Figure()
    for seg, cnt in zip(seg_counts.index, seg_counts.values):
        c = segment_colors().get(seg, P["cat_blue"])
        fig2.add_trace(go.Bar(
            x=[seg], y=[cnt], name=seg,
            marker_color=c, width=0.55,
            text=[f"{cnt:,}"], textposition="outside",
            textfont=dict(color=P["text_secondary"], size=12),
            hovertemplate=f"{seg}<br>%{{y:,}} 人<extra></extra>",
        ))
    fig2.update_layout(bargap=0.4, showlegend=False)
    fig2.update_yaxes(title_text="人数")
    apply_theme(fig2, height=380)
    st.plotly_chart(fig2, config=chart_config(), width="stretch")

# ===== 年龄分布(按 segment 堆叠,2px surface gap)=====
st.subheader("👤 会员年龄分布(按分层堆叠)")
fig3 = px.histogram(
    members, x="age", color="segment", nbins=30,
    color_discrete_map=segment_colors(),
    category_orders={"segment": SEGMENT_ORDER},
)
fig3.update_traces(marker_line_width=MARK_GAP, marker_line_color=P["surface"])
fig3.update_layout(bargap=0.1)
apply_theme(fig3, height=340, show_legend=True)
fig3.update_xaxes(title_text="年龄")
fig3.update_yaxes(title_text="人数")
st.plotly_chart(fig3, config=chart_config(), width="stretch")

# ===== 各群体消费对比(表格条带)=====
st.subheader("💰 各群体消费对比")
seg_stats = members.groupby("segment").agg(
    平均总消费=("total_spent", "mean"),
    平均到店次数=("visit_count", "mean"),
    平均客单价=("avg_spent", "mean"),
).round(0)
seg_stats = seg_stats.reindex(SEGMENT_ORDER).dropna()
seg_stats = seg_stats.astype(int)
st.dataframe(seg_stats, width="stretch")

# ===== 流失风险预警(痛点②延伸:识别高价值会员长期未到店)=====
st.markdown("---")
st.subheader("🚨 流失风险预警")
st.caption("高价值/金卡/黑金会员中,30天以上未到店 = 流失风险,需主动挽回")

members["last_visit_date"] = pd.to_datetime(members["last_visit_date"], errors="coerce")
from app.config import DATA_TODAY
TODAY = pd.Timestamp(DATA_TODAY)
members["days_since_visit"] = (TODAY - members["last_visit_date"]).dt.days

# 高价值且长期未到店
risk_members = members[
    (members["segment"].isin(["高价值", "潜力"]))
    & (members["days_since_visit"] > 30)
].sort_values("days_since_visit", ascending=False)

risk_count = len(risk_members)
high_value_total = len(members[members["segment"] == "高价值"])
risk_pct = risk_count / len(members) * 100 if len(members) else 0

rk = (
    stat_card_html("风险会员数", f"{risk_count:,}", f"占全体 {risk_pct:.1f}%", delta_good=False, accent=P["critical"])
    + stat_card_html("最高未到店", f"{int(members['days_since_visit'].max())} 天", "最久未到店", accent=P["warning"])
    + stat_card_html("高价值流失", f"{len(risk_members[risk_members['segment']=='高价值']):,}",
                     f"高价值共 {high_value_total} 人", delta_good=False, accent=P["cat_gold"])
    + stat_card_html("平均未到店", f"{risk_members['days_since_visit'].mean():.0f} 天", "风险会员均值", accent=P["cat_orange"])
)
st.markdown(kpi_grid_html(rk, cols=4), unsafe_allow_html=True)

# 风险会员表(脱敏)
if risk_count:
    risk_display = risk_members.head(20)[["member_id", "name", "level", "segment", "total_spent", "visit_count", "days_since_visit"]].copy()
    risk_display.columns = ["会员ID", "姓名", "等级", "分群", "累计消费", "到店次数", "未到店天数"]
    st.dataframe(risk_display, width="stretch", hide_index=True,
                 column_config={"累计消费": st.column_config.NumberColumn("累计消费", format="¥%,.0f")})
    st.warning(f"⚠️ {risk_count} 位高价值/潜力会员存在流失风险,建议立即启动挽回:专属客服回访 + 大额满减券 + 到店即赠礼。")
else:
    st.success("✅ 暂无流失风险会员")
