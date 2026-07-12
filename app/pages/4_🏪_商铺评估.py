"""商铺评估 —— 排行 + 业态雷达 + 楼层 + 坪效散点"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.utils import load_csv
from app.models import calculate_shop_score
from app.viz_theme import (
    categorical_colors, seq_bluescale, apply_theme, chart_config, themed_scatter,
    stat_card_html, kpi_grid_html, MARK_RING_WIDTH, MARK_LINE_WIDTH,
    inject_global_css, mobile_notice_html, current_palette,
)

st.set_page_config(page_title="商铺评估", layout="wide")
inject_global_css()
P = current_palette()
from app.date_filter import render_date_filter as _rdf
_rdf()  # 侧边栏时间段筛选器(每个页面都渲染,保证全页面可切换)


@st.cache_data(ttl=3600)
def load_data():
    shops = load_csv("shops_master.csv", "raw")
    return calculate_shop_score(shops)


shops = load_data()

st.title("🏪 商铺评估")
st.markdown(mobile_notice_html(), unsafe_allow_html=True)
st.caption("ℹ️ 商铺主数据为存量信息(合同/租金/坪效),不随时段筛选变化")

# ===== KPI 行 =====
top = shops.nsmallest(1, "rank").iloc[0]
low = shops.nlargest(1, "rank").iloc[0]
avg_score = shops["score"].mean()
kpi = (
    stat_card_html("商铺总数", f"{len(shops)}", f"{shops['category'].nunique()} 个业态",
                   accent=P["cat_blue"])
    + stat_card_html("榜首商铺", top["name"], f"{top['score']:.1f} 分 · {top['category']}",
                     accent=P["cat_gold"])
    + stat_card_html("末位商铺", low["name"], f"{low['score']:.1f} 分 · {low['category']}",
                     accent=P["cat_red"])
    + stat_card_html("平均评分", f"{avg_score:.1f}", "0-100 制", accent=P["cat_aqua"])
)
st.markdown(kpi_grid_html(kpi, cols=4), unsafe_allow_html=True)

# ===== 商铺排行榜(表格 + 评分进度条列)=====
st.subheader("🏆 商铺综合评分排行")

# 筛选器(65 行真实商户,需筛选提升可用性)
fcol1, fcol2, fcol3 = st.columns(3)
with fcol1:
    floor_sel = st.multiselect("楼层", options=sorted(shops["floor"].unique()),
                               default=sorted(shops["floor"].unique()), key="shop_floor")
with fcol2:
    cat_sel = st.multiselect("业态", options=sorted(shops["category"].unique()),
                             default=sorted(shops["category"].unique()), key="shop_cat")
with fcol3:
    anchor_only = st.checkbox("仅看主力店", value=False, key="shop_anchor")

mask = shops["floor"].isin(floor_sel) & shops["category"].isin(cat_sel)
if anchor_only:
    mask = mask & shops["is_anchor"]
shops_view = shops[mask].copy()
st.caption(f"当前筛选:{len(shops_view)} / {len(shops)} 家商铺")

display_cols = ["name", "category", "floor", "area_sqm", "monthly_sales", "monthly_traffic", "score", "rank", "is_anchor"]
display_names = ["商铺名", "业态", "楼层", "面积(㎡)", "月销售额", "月客流量", "综合评分", "排名", "主力店"]
df_display = shops_view[display_cols].copy()
df_display.columns = display_names
df_display = df_display.sort_values("排名").reset_index(drop=True)

# 评分用 ProgressColumn 列渲染为进度条
st.dataframe(df_display, width="stretch", hide_index=True,
             column_config={
                 "综合评分": st.column_config.ProgressColumn(
                     "综合评分", help="0-100 综合评分", format="%.1f",
                     min_value=0, max_value=100),
                 "月销售额": st.column_config.NumberColumn("月销售额", format="¥%,.0f"),
                 "月客流量": st.column_config.NumberColumn("月客流量", format="%,.0f"),
             })

# ===== 业态对比(雷达图,固定分类色 + ring 分离)=====
col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 业态对比")
    cat_stats = shops.groupby("category").agg({
        "score": "mean", "monthly_sales": "mean",
        "monthly_traffic": "mean", "member_conversion_rate": "mean",
    }).round(2)
    cat_stats.columns = ["综合评分", "月销售额", "月客流量", "转化率"]
    # 归一化到 0-100
    for col in cat_stats.columns:
        lo, hi = cat_stats[col].min(), cat_stats[col].max()
        cat_stats[col] = (cat_stats[col] - lo) / (hi - lo) * 100 if hi != lo else 50

    categories = cat_stats.columns.tolist()
    fig = go.Figure()
    for i, cat in enumerate(cat_stats.index):
        vals = cat_stats.loc[cat].tolist()
        c = categorical_colors()[i % len(categorical_colors())]
        fig.add_trace(go.Scatterpolar(
            r=vals + [vals[0]], theta=categories + [categories[0]],
            name=cat, fill="toself", opacity=0.5,
            line=dict(color=c, width=MARK_LINE_WIDTH),
        ))
    fig.update_layout(
        polar=dict(
            bgcolor=P["surface"],
            radialaxis=dict(gridcolor=P["gridline"], gridwidth=1,
                            tickfont=dict(color=P["text_muted"], size=9),
                            linecolor=P["axis_line"], range=[0, 100]),
            angularaxis=dict(gridcolor=P["gridline"], gridwidth=1,
                             tickfont=dict(color=P["text_muted"], size=10),
                             linecolor=P["axis_line"]),
        ),
    )
    apply_theme(fig, height=400, show_legend=True)
    st.plotly_chart(fig, config=chart_config(), width="stretch")

# ===== 楼层平均评分(横条形 sequential 蓝,不用 color=数值)=====
with col2:
    st.subheader("🏢 楼层平均评分")
    floor_stats = shops.groupby("floor")["score"].mean().round(1)
    fig2 = go.Figure()
    for f, s in zip(floor_stats.index, floor_stats.values):
        # 按 score 在蓝色 ramp 上取色(值越大越亮),但仍属同一色相
        t = (s - floor_stats.min()) / (floor_stats.max() - floor_stats.min() + 1e-9)
        # ramp 从深到亮
        ramp = ["#184f95", "#256abf", "#3987e5", "#6da7ec"]
        idx = min(len(ramp) - 1, int(t * (len(ramp) - 1)))
        fig2.add_trace(go.Bar(
            y=[f"{f}F"], x=[s], orientation="h", name=f"{f}F",
            marker_color=ramp[idx], width=0.6,
            text=[f"{s:.1f}"], textposition="outside",
            textfont=dict(color=P["text_secondary"], size=12),
            hovertemplate=f"{f}F<br>%{{x:.1f}} 分<extra></extra>",
        ))
    fig2.update_layout(bargap=0.4, showlegend=False)
    fig2.update_xaxes(title_text="平均评分", range=[0, 100])
    apply_theme(fig2, height=400)
    st.plotly_chart(fig2, config=chart_config(), width="stretch")

# ===== 坪效散点(marker≥8px + 2px surface ring,业态固定分类色)=====
st.subheader("📈 坪效分析(面积 vs 销售额)")
# 业态固定色映射
cats = shops["category"].unique()
cat_color_map = {c: categorical_colors()[i % len(categorical_colors())] for i, c in enumerate(sorted(cats))}
fig3 = themed_scatter(
    x="area_sqm", y="monthly_sales", color_by="category", df=shops,
    hover_name="name", size="monthly_traffic",
    height=420, color_map=cat_color_map,
)
fig3.update_xaxes(title_text="面积(㎡)")
fig3.update_yaxes(title_text="月销售额")
st.plotly_chart(fig3, config=chart_config(), width="stretch")
