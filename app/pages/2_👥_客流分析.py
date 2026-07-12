"""客流分析 —— 时空热力图 + 天气 × 楼层 + 节假日 × 楼层"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.utils import load_csv
from app.models import build_traffic_heatmap, analyze_weather_impact, analyze_holiday_effect
from app.date_filter import filter_traffic, get_date_range
from app.viz_theme import (
    PALETTE, themed_heatmap, stat_card_html, kpi_grid_html,
    inject_global_css, mobile_notice_html, current_palette, apply_theme, chart_config,
)
from app.agent import generate_traffic_profile
from app.llm_client import is_llm_ready

st.set_page_config(page_title="客流分析", layout="wide")
inject_global_css()
P = current_palette()
from app.date_filter import render_date_filter as _rdf
_rdf()  # 侧边栏时间段筛选器(每个页面都渲染,保证全页面可切换)


@st.cache_data(ttl=3600)
def load_data():
    return load_csv("foot_traffic_2023.csv", "raw")


traffic = load_data()
traffic = filter_traffic(traffic)
_dr_start, _dr_end = get_date_range()
_dr_label = f"{_dr_start.date()} ~ {_dr_end.date()}"

st.title("👥 客流分析")
st.markdown(mobile_notice_html(), unsafe_allow_html=True)
st.caption(f"📅 当前分析时段:**{_dr_label}**(左侧侧边栏可切换)")

# ===== 7×24 热力图 =====
st.subheader("🕐 客流时空热力图")
matrix, peaks = build_traffic_heatmap(traffic)
weekday_labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
hours = [f"{h}:00" for h in range(24)]
fig = themed_heatmap(matrix.tolist(), hours, weekday_labels, height=380)
fig.update_xaxes(side="bottom", title_text="时段")
fig.update_yaxes(title_text="星期")
st.plotly_chart(fig, config=chart_config(), width="stretch")

# Top3 峰值
peak_str = "、".join([f"{weekday_labels[p[0]]} {p[1]}:00(客流 {p[2]:,.0f})" for p in peaks])
st.info(f"🔥 **客流 Top3 峰值**:{peak_str}")

# ===== KPI 行 =====
weather = analyze_weather_impact(traffic)
holiday = analyze_holiday_effect(traffic)
rain_drop = 100 - weather["晴雨比"] * 100 if weather["晴雨比"] else 0
hol_boost = (holiday["节假日倍数"] - 1) * 100 if holiday["节假日倍数"] else 0
# 时段内无节假日/工作日时 None 兜底(选近7天可能遇到)
_hol_val = holiday["节假日"] if holiday["节假日"] else 0
_work_val = holiday["工作日"] if holiday["工作日"] else 0
_hol_note = "↑ 节假日增 {:.0f}%".format(hol_boost) if _hol_val else "本期无节假日"

kpi = (
    stat_card_html("晴天均客流", f"{weather['晴']:,.0f}", "↑ 高于雨天",
                   delta_good=True, accent=P["cat_aqua"])
    + stat_card_html("雨天均客流", f"{weather['雨']:,.0f}",
                     f"↓ 雨天下降 {rain_drop:.0f}%", delta_good=False,
                     accent=P["cat_red"])
    + stat_card_html("节假日均客流", f"{_hol_val:,.0f}",
                     _hol_note, delta_good=True,
                     accent=P["cat_gold"])
    + stat_card_html("工作日均客流", f"{_work_val:,.0f}", "基准线",
                     delta_good=True, accent=P["cat_blue"])
)
st.markdown(kpi_grid_html(kpi, cols=4), unsafe_allow_html=True)

# ===== 天气影响 × 楼层(分组柱状图)=====
st.subheader("🌤️ 天气对客流的影响(按楼层)")
st.caption("晴/阴/雨天 × 各楼层的平均客流对比,看哪些楼层受天气影响最大")

weather_floor = traffic.groupby(["weather", "floor"])["visitor_count"].mean().reset_index()
weather_floor["floor"] = weather_floor["floor"].astype(int)
weather_list = ["晴", "阴", "雨"]
weather_color = {"晴": P["cat_aqua"], "阴": P["cat_violet"], "雨": P["cat_red"]}
floors = sorted(weather_floor["floor"].unique())

fig2 = go.Figure()
for w in weather_list:
    vals = []
    for f in floors:
        row = weather_floor[(weather_floor["weather"] == w) & (weather_floor["floor"] == f)]
        vals.append(row["visitor_count"].values[0] if len(row) else 0)
    fig2.add_trace(go.Bar(
        name=w, x=[f"{f}F" for f in floors], y=vals,
        marker_color=weather_color[w], width=0.22,
        text=[f"{v:,.0f}" for v in vals], textposition="inside",
        textfont=dict(color="#ffffff", size=9, family="system-ui"),
        hovertemplate=f"{w} %{{x}}<br>均客流 %{{y:,.0f}}<extra></extra>",
    ))
fig2.update_layout(barmode="group", bargap=0.5, bargroupgap=0.15)
fig2.update_yaxes(title_text="平均客流")
apply_theme(fig2, height=400)
st.plotly_chart(fig2, config=chart_config(), width="stretch")

# ===== 节假日效应 × 楼层(分组柱状图)=====
st.subheader("🎉 节假日效应(按楼层)")
st.caption("工作日/周末/节假日 × 各楼层的平均客流对比,看哪些楼层节假日增益最大")

# 构造三类:工作日/周末/节假日
td = traffic.copy()
td["day_type"] = "工作日"
td.loc[td["is_weekend"] & ~td["is_holiday"], "day_type"] = "周末"
td.loc[td["is_holiday"], "day_type"] = "节假日"

hol_floor = td.groupby(["day_type", "floor"])["visitor_count"].mean().reset_index()
hol_floor["floor"] = hol_floor["floor"].astype(int)
day_list = ["工作日", "周末", "节假日"]
day_color = {"工作日": P["cat_blue"], "周末": P["cat_aqua"], "节假日": P["cat_gold"]}

fig3 = go.Figure()
for d in day_list:
    vals = []
    for f in floors:
        row = hol_floor[(hol_floor["day_type"] == d) & (hol_floor["floor"] == f)]
        vals.append(row["visitor_count"].values[0] if len(row) else 0)
    fig3.add_trace(go.Bar(
        name=d, x=[f"{f}F" for f in floors], y=vals,
        marker_color=day_color[d], width=0.22,
        text=[f"{v:,.0f}" for v in vals], textposition="inside",
        textfont=dict(color="#ffffff", size=9, family="system-ui"),
        hovertemplate=f"{d} %{{x}}<br>均客流 %{{y:,.0f}}<extra></extra>",
    ))
fig3.update_layout(barmode="group", bargap=0.5, bargroupgap=0.15)
fig3.update_yaxes(title_text="平均客流")
apply_theme(fig3, height=400)
st.plotly_chart(fig3, config=chart_config(), width="stretch")

# ===== 天气×节假日交叉:雨天节假日 vs 晴天工作日 =====
st.subheader("📊 极端场景对比")
st.caption("最差(雨天工作日) vs 最优(晴天节假日) × 各楼层,量化天气+节假日的叠加效应")

worst = td[(td["weather"] == "雨") & (td["day_type"] == "工作日")].groupby("floor")["visitor_count"].mean()
best = td[(td["weather"] == "晴") & (td["day_type"] == "节假日")].groupby("floor")["visitor_count"].mean()

fig4 = go.Figure()
fig4.add_trace(go.Bar(
    name="🌧️ 雨天工作日", x=[f"{f}F" for f in floors],
    y=[worst.get(f, 0) for f in floors],
    marker_color=P["cat_red"], width=0.3,
    text=[f"{worst.get(f,0):,.0f}" for f in floors], textposition="inside",
    textfont=dict(color="#ffffff", size=10),
    hovertemplate="雨天工作日 %{x}<br>%{y:,.0f}<extra></extra>",
))
fig4.add_trace(go.Bar(
    name="☀️ 晴天节假日", x=[f"{f}F" for f in floors],
    y=[best.get(f, 0) for f in floors],
    marker_color=P["cat_gold"], width=0.3,
    text=[f"{best.get(f,0):,.0f}" for f in floors], textposition="inside",
    textfont=dict(color="#ffffff", size=10),
    hovertemplate="晴天节假日 %{x}<br>%{y:,.0f}<extra></extra>",
))
fig4.update_layout(barmode="group", bargap=0.5, bargroupgap=0.15)
fig4.update_yaxes(title_text="平均客流")
apply_theme(fig4, height=340)
st.plotly_chart(fig4, config=chart_config(), width="stretch")

# 倍数总结
worst_total = worst.sum()
best_total = best.sum()
ratio = best_total / worst_total if worst_total else 0
st.markdown(f'<div style="background:{P["surface"]};border:1px solid {P["border"]};'
            f'border-radius:10px;padding:12px 18px;margin:10px 0">'
            f'<span style="color:{P["text_muted"]};font-size:0.85rem">晴天节假日 vs 雨天工作日总客流比</span><br>'
            f'<span style="color:{P["cat_gold"]};font-size:1.6rem;font-weight:700">{ratio:.1f}×</span>'
            f' <span style="color:{P["text_secondary"]};font-size:0.85rem">({best_total:,.0f} vs {worst_total:,.0f})</span>'
            f'</div>', unsafe_allow_html=True)

# ===== AI 客流人群画像(痛点①:不知来商场的人是谁 → 识人)=====
st.markdown("---")
st.subheader("🧠 AI 客流人群画像")
st.caption("基于客流时空规律,AI 生成'识人'总结:什么样的客群、何时来、如何转化")

# 构造画像输入
import numpy as np
mat = np.asarray(matrix)
peak_idx = mat.argmax()
peak_wd, peak_h = divmod(peak_idx, mat.shape[1]) if mat.ndim == 2 else (0, 0)
floor_traffic = traffic.groupby("floor")["visitor_count"].mean()
profile_summary = {
    "peak_weekday": weekday_labels[peak_wd] if peak_wd < 7 else "周末",
    "peak_hour": f"{peak_h}:00",
    "floor_top": f"{floor_traffic.idxmax()}F",
    "floor_distribution": {int(f): int(v) for f, v in floor_traffic.items()},
    "weather_ratio": round(weather["晴雨比"], 2) if weather["晴雨比"] else 1.0,
    "holiday_boost": round(holiday["节假日倍数"], 2) if holiday["节假日倍数"] else 1.0,
    "total_traffic": int(traffic["visitor_count"].sum()),
    "avg_daily": int(traffic.groupby("date")["visitor_count"].sum().mean()),
}

if st.button("生成客流人群画像", type="primary", key="gen_profile"):
    with st.spinner("AI 生成客流画像中..." if is_llm_ready() else None):
        profile_result = generate_traffic_profile(profile_summary, use_llm=is_llm_ready())
    profile = profile_result.get("text", "") if isinstance(profile_result, dict) else profile_result
    source = "AI 生成" if (isinstance(profile_result, dict) and "llm" in profile_result.get("_source", "")) else "规则兜底"
    st.markdown(f'<div style="background:linear-gradient(135deg, rgba(57,135,229,0.10), {P["surface"]});'
                f'border:1px solid rgba(57,135,229,0.35);border-radius:10px;padding:16px 20px;margin:10px 0">'
                f'<div style="color:{P["text_muted"]};font-size:0.72rem;margin-bottom:8px">客流人群画像 · {source}</div>'
                f'<div style="color:{P["text_primary"]};font-size:0.92rem;line-height:1.8;white-space:pre-line">{profile}</div></div>',
                unsafe_allow_html=True)
