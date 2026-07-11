"""数据采集 —— 采集覆盖率看板 + 缺失预警 + AI 采集建议(痛点④)

解决万泰痛点:商铺经营数据采集不到,客流/销售数据缺失。
- 采集覆盖率(整体/按楼层/按业态/按主力店)
- 缺失预警(低采集率商铺清单)
- 数据资产盘点(客流/销售/会员/合同 各类数据采集状态)
- AI 采集建议(基于低覆盖商铺生成可执行采集方案)
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.utils import load_csv
from app.viz_theme import (
    apply_theme, stat_card_html, kpi_grid_html, inject_global_css, current_palette,
)
from app.agent import generate_collection_advice
from app.llm_client import is_llm_ready

st.set_page_config(page_title="数据采集", layout="wide")
inject_global_css()
P = current_palette()


@st.cache_data(ttl=3600)
def load_data():
    return load_csv("shops_master.csv", "raw")


shops = load_data()

st.title("📡 数据采集")
st.caption("采集覆盖率 · 缺失预警 · 数据资产盘点 · AI 采集建议 —— 补齐商铺经营数据盲区")

# ===== KPI 行 =====
total = len(shops)
avg_rate = shops["collection_rate"].mean()
low_count = len(shops[shops["collection_rate"] < 0.7])
high_count = len(shops[shops["collection_rate"] >= 0.9])
anchor_rate = shops.loc[shops["is_anchor"], "collection_rate"].mean()

kpi = (
    stat_card_html("采集商铺数", f"{total}", f"{shops['name'].nunique()} 个品牌", accent=P["cat_blue"])
    + stat_card_html("平均采集率", f"{avg_rate*100:.0f}%",
                     "客流+销售+转化+租金", delta_good=avg_rate > 0.75, accent=P["cat_gold"])
    + stat_card_html("低采集(<70%)", f"{low_count}",
                     "需优先补采", delta_good=False, accent=P["cat_red"])
    + stat_card_html("高采集(≥90%)", f"{high_count}",
                     f"主力店 {anchor_rate*100:.0f}%", delta_good=True, accent=P["cat_aqua"])
)
st.markdown(kpi_grid_html(kpi, cols=4), unsafe_allow_html=True)

# ===== 采集覆盖率分布(直方图)=====
st.subheader("📊 采集覆盖率分布")
fig = go.Figure()
fig.add_trace(go.Histogram(
    x=shops["collection_rate"], nbinsx=20,
    marker_color=P["cat_blue"], marker_line_color=P["surface"], marker_line_width=2,
    hovertemplate="采集率 %{x:.2f}<br>商铺数 %{y}<extra></extra>",
))
fig.add_vline(x=0.7, line_dash="dash", line_color=P["warning"],
              annotation_text="预警线 70%", annotation_font_color=P["warning"])
fig.update_layout(bargap=0.1)
fig.update_xaxes(title_text="采集率", range=[0, 1], tickformat=".0%")
fig.update_yaxes(title_text="商铺数")
apply_theme(fig, height=320)
st.plotly_chart(fig, width="stretch")

# ===== 楼层 vs 业态 采集率 =====
col1, col2 = st.columns(2)

with col1:
    st.subheader("🏢 各楼层采集率")
    floor_rate = shops.groupby("floor")["collection_rate"].mean().round(3)
    fig1 = go.Figure()
    for f, r in zip(floor_rate.index, floor_rate.values):
        c = P["good"] if r >= 0.85 else (P["warning"] if r >= 0.7 else P["critical"])
        fig1.add_trace(go.Bar(
            x=[f"{int(f)}F"], y=[r * 100], name=f"{int(f)}F",
            marker_color=c, width=0.55,
            text=[f"{r*100:.0f}%"], textposition="outside",
            textfont=dict(color=P["text_secondary"], size=12),
            hovertemplate=f"{int(f)}F<br>采集率 %{{y:.0f}}%<extra></extra>",
        ))
    fig1.update_layout(bargap=0.4, showlegend=False)
    fig1.update_yaxes(title_text="采集率%", range=[0, 100])
    apply_theme(fig1, height=320)
    st.plotly_chart(fig1, width="stretch")

with col2:
    st.subheader("🏷️ 各业态采集率")
    cat_rate = shops.groupby("category")["collection_rate"].mean().round(3).sort_values()
    fig2 = go.Figure()
    for c, r in zip(cat_rate.index, cat_rate.values):
        col = P["good"] if r >= 0.85 else (P["warning"] if r >= 0.7 else P["critical"])
        fig2.add_trace(go.Bar(
            y=[c], x=[r * 100], orientation="h", name=c,
            marker_color=col, width=0.55,
            text=[f"{r*100:.0f}%"], textposition="outside",
            textfont=dict(color=P["text_secondary"], size=12),
            hovertemplate=f"{c}<br>采集率 %{{x:.0f}}%<extra></extra>",
        ))
    fig2.update_layout(bargap=0.4, showlegend=False)
    fig2.update_xaxes(title_text="采集率%", range=[0, 100])
    apply_theme(fig2, height=320)
    st.plotly_chart(fig2, width="stretch")

# ===== 缺失预警表 =====
st.subheader("⚠️ 采集缺失预警")
st.caption("采集率 < 70% 的商铺,按采集率升序,需优先补采")
low = shops[shops["collection_rate"] < 0.7].sort_values("collection_rate").copy()
if len(low):
    low_display = low[["name", "floor", "category", "collection_rate", "monthly_sales", "is_anchor"]].copy()
    low_display.columns = ["商铺", "楼层", "业态", "采集率", "月销售额", "主力店"]
    # 模拟缺失字段提示(基于采集率推断缺失哪些)
    def _missing_fields(r):
        miss = []
        if r["collection_rate"] < 0.6:
            miss.extend(["客流", "销售"])
        if r["collection_rate"] < 0.7:
            miss.append("转化率")
        return "、".join(miss) if miss else "部分时段"
    low_display["缺失字段"] = low.apply(_missing_fields, axis=1)
    low_display["采集率"] = low_display["采集率"].map(lambda x: f"{x*100:.0f}%")
    st.dataframe(low_display, width="stretch", hide_index=True,
                 column_config={"月销售额": st.column_config.NumberColumn("月销售额", format="¥%,.0f")})
else:
    st.success("✅ 所有商铺采集率均达 70% 以上")

# ===== 数据资产盘点 =====
st.subheader("🗂️ 数据资产盘点")
st.caption("各类数据采集状态与接入方式")
asset_data = [
    {"数据类型": "客流数据", "采集方式": "IoT客流计数器+入口热成像", "覆盖": f"{total}/{total} 商铺", "状态": "✅ 全覆盖", "更新": "小时级"},
    {"数据类型": "销售数据", "采集方式": "POS系统对接/月度申报", "覆盖": f"{int(avg_rate*total)}/{total} 商铺", "状态": f"覆盖率{avg_rate*100:.0f}%", "更新": "日级"},
    {"数据类型": "会员数据", "采集方式": "全渠道统一ID(小程序+门店+支付)", "覆盖": "5000 会员", "状态": "✅ 全覆盖", "更新": "实时"},
    {"数据类型": "合同数据", "采集方式": "租户管理系统录入", "覆盖": f"{total}/{total} 商铺", "状态": "✅ 全覆盖", "更新": "月级"},
    {"数据类型": "转化数据", "采集方式": "客流×会员匹配计算", "覆盖": f"{int(avg_rate*total)}/{total} 商铺", "状态": f"覆盖率{avg_rate*100:.0f}%", "更新": "日级"},
]
st.dataframe(pd.DataFrame(asset_data), width="stretch", hide_index=True)

# ===== AI 采集建议 =====
st.markdown("---")
st.subheader("🤖 AI 采集建议")
st.caption("基于低采集率商铺,Agent 生成可执行的数据采集方案")

if len(low):
    low_shops_for_ai = low.head(10)[["name", "category", "collection_rate"]].to_dict("records")
    for s in low_shops_for_ai:
        s["collection_rate"] = f"{s['collection_rate']:.2f}"
        s["missing_fields"] = "客流/销售/转化"

    if st.button("生成采集建议", type="primary", key="gen_collect"):
        with st.spinner("AI 生成数据采集建议中..." if is_llm_ready() else None):
            advice = generate_collection_advice(low_shops_for_ai, use_llm=is_llm_ready())
        source = "AI 生成" if is_llm_ready() else "规则兜底"
        advice_html = "".join(
            f'<div style="background:{P["surface"]};border:1px solid {P["border"]};'
            f'border-left:3px solid {P["cat_aqua"]};border-radius:8px;padding:10px 14px;margin:8px 0">'
            f'<span style="color:{P["text_secondary"]};font-size:0.9rem;line-height:1.5">'
            f'{["💡","📡","🎯"][i%3]} {a}</span></div>'
            for i, a in enumerate(advice)
        )
        st.markdown(f'<div style="color:{P["text_muted"]};font-size:0.72rem;margin-bottom:6px">采集建议 · {source}</div>'
                    f'{advice_html}', unsafe_allow_html=True)
else:
    st.success("✅ 采集覆盖率良好,无需额外建议。")
