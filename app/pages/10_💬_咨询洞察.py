"""客户咨询洞察 —— 用上数据弹药③:客户咨询记录

解决万泰痛点:客户咨询记录此前未被利用,本页将其转化为可行动洞察。
- 咨询分类分布(商铺位置/会员权益/活动促销/品牌商品/停车/营业时间/投诉/租户合作)
- 渠道分布(小程序/前台/电话/公众号/扫码)
- 情感与处理状态(负面占比/待处理占比)
- 热点问题趋势(按月)
- AI 咨询洞察(数据洞察+热点问题+改进建议)
- AI 自动回复建议(选单条咨询生成话术)
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
from app.agent import analyze_consultations, generate_consult_reply
from app.llm_client import is_llm_ready

st.set_page_config(page_title="咨询洞察", layout="wide")
inject_global_css()
P = current_palette()


@st.cache_data(ttl=3600)
def load_data():
    return load_csv("consultations_2023.csv", "raw")


df = load_data()

st.title("💬 客户咨询洞察")
st.caption("客户咨询记录 → 数据洞察 → 改进建议 —— 把沉睡的咨询数据变成可行动的运营动作")

# ===== KPI 行 =====
total = len(df)
negative_pct = len(df[df["sentiment"] == "负面"]) / total * 100
pending_pct = len(df[df["status"] == "待处理"]) / total * 100
top_type = df["consult_type"].value_counts().index[0]
peak_hour = df["hour"].mode().iloc[0]

kpi = (
    stat_card_html("咨询总量", f"{total:,}", "全年累计", accent=P["cat_blue"])
    + stat_card_html("最热类型", top_type, f"{df['consult_type'].value_counts().iloc[0]:,} 条", accent=P["cat_gold"])
    + stat_card_html("负面咨询", f"{negative_pct:.1f}%", "需重点跟进", delta_good=negative_pct < 10, accent=P["cat_red"])
    + stat_card_html("待处理", f"{pending_pct:.1f}%", f"高峰 {peak_hour}:00", delta_good=pending_pct < 15, accent=P["cat_orange"])
)
st.markdown(kpi_grid_html(kpi, cols=4), unsafe_allow_html=True)

# ===== 咨询分类分布 =====
st.subheader("📋 咨询分类分布")
type_counts = df["consult_type"].value_counts()
fig1 = go.Figure()
for i, (t, c) in enumerate(zip(type_counts.index, type_counts.values)):
    colors = [P["cat_blue"], P["cat_aqua"], P["cat_gold"], P["cat_green"], P["cat_violet"],
              P["cat_orange"], P["cat_red"], P["cat_magenta"]]
    fig1.add_trace(go.Bar(
        y=[t], x=[c], orientation="h", name=t,
        marker_color=colors[i % len(colors)], width=0.6,
        text=[f"{c:,} ({c/total*100:.0f}%)"], textposition="outside",
        textfont=dict(color=P["text_secondary"], size=11),
        hovertemplate=f"{t}<br>%{{x:,}} 条<extra></extra>",
    ))
fig1.update_layout(bargap=0.4, showlegend=False)
fig1.update_xaxes(title_text="咨询数")
apply_theme(fig1, height=380)
st.plotly_chart(fig1, width="stretch")

# ===== 渠道分布 + 情感 =====
col1, col2 = st.columns(2)

with col1:
    st.subheader("📱 咨询渠道分布")
    ch_counts = df["channel"].value_counts()
    fig2 = go.Figure()
    for i, (ch, c) in enumerate(zip(ch_counts.index, ch_counts.values)):
        fig2.add_trace(go.Bar(
            x=[ch], y=[c], name=ch,
            marker_color=[P["cat_aqua"], P["cat_gold"], P["cat_violet"], P["cat_orange"], P["cat_magenta"]][i % 5],
            width=0.5,
            text=[f"{c:,}"], textposition="outside",
            textfont=dict(color=P["text_secondary"], size=11),
            hovertemplate=f"{ch}<br>%{{y:,}} 条<extra></extra>",
        ))
    fig2.update_layout(bargap=0.4, showlegend=False)
    fig2.update_yaxes(title_text="咨询数")
    apply_theme(fig2, height=320)
    st.plotly_chart(fig2, width="stretch")

with col2:
    st.subheader("😊 情感与处理状态")
    sent_counts = df["sentiment"].value_counts().reindex(["正面", "中性", "负面"]).fillna(0)
    status_counts = df["status"].value_counts().reindex(["已回复", "待处理"]).fillna(0)
    fig3 = go.Figure()
    sent_color = {"正面": P["good"], "中性": P["text_muted"], "负面": P["critical"]}
    for s, c in zip(sent_counts.index, sent_counts.values):
        fig3.add_trace(go.Bar(
            x=[f"情感:{s}"], y=[c], name=s,
            marker_color=sent_color[s], width=0.4,
            text=[f"{int(c):,}"], textposition="outside",
            textfont=dict(color=P["text_secondary"], size=11),
        ))
    status_color = {"已回复": P["good"], "待处理": P["warning"]}
    for s, c in zip(status_counts.index, status_counts.values):
        fig3.add_trace(go.Bar(
            x=[f"状态:{s}"], y=[c], name=s,
            marker_color=status_color[s], width=0.4,
            text=[f"{int(c):,}"], textposition="outside",
            textfont=dict(color=P["text_secondary"], size=11),
        ))
    fig3.update_layout(bargap=0.4, showlegend=False)
    fig3.update_yaxes(title_text="咨询数")
    apply_theme(fig3, height=320)
    st.plotly_chart(fig3, width="stretch")

# ===== 热点问题月度趋势 =====
st.subheader("📈 热点问题月度趋势")
df["month"] = pd.to_datetime(df["date"], errors="coerce").dt.month
top5_types = type_counts.head(5).index.tolist()
monthly = df[df["consult_type"].isin(top5_types)].groupby(["month", "consult_type"]).size().unstack(fill_value=0)
fig4 = go.Figure()
colors5 = [P["cat_blue"], P["cat_aqua"], P["cat_gold"], P["cat_green"], P["cat_violet"]]
for i, t in enumerate(top5_types):
    vals = monthly[t].values if t in monthly.columns else [0] * 12
    fig4.add_trace(go.Scatter(
        x=list(range(1, 13)), y=vals, name=t, mode="lines+markers",
        line=dict(color=colors5[i], width=2.5),
        marker=dict(size=7, color=colors5[i]),
        hovertemplate=f"{t}<br>第%{{x}}月: %{{y}} 条<extra></extra>",
    ))
fig4.update_xaxes(title_text="月份", dtick=1)
fig4.update_yaxes(title_text="咨询数")
apply_theme(fig4, height=360)
st.plotly_chart(fig4, width="stretch")

# ===== AI 咨询洞察 =====
st.markdown("---")
st.subheader("🤖 AI 咨询洞察")
st.caption("基于咨询数据,Agent 生成数据洞察 + 热点问题 + 改进建议")

consult_stats = {
    "total": total,
    "top_types": [(t, int(c)) for t, c in type_counts.head(8).items()],
    "top_channels": [(ch, int(c)) for ch, c in ch_counts.head(5).items()],
    "negative_pct": negative_pct,
    "pending_pct": pending_pct,
    "peak_hour": int(peak_hour),
    "sample_contents": df["content"].dropna().sample(min(20, len(df)), random_state=42).tolist(),
}

if st.button("生成咨询洞察", type="primary", key="gen_consult_insight"):
    with st.spinner("AI 分析咨询数据中..." if is_llm_ready() else None):
        result = analyze_consultations(consult_stats, use_llm=is_llm_ready())
    source = "AI 生成" if "llm" in result.get("_source", "") else "规则兜底"

    # 洞察
    insights = result.get("insights", [])
    if insights:
        st.markdown(f'<div style="color:{P["text_muted"]};font-size:0.82rem;margin-bottom:8px">数据洞察 · {source}</div>',
                    unsafe_allow_html=True)
        for ins in insights:
            st.markdown(f'<div style="background:{P["surface"]};border:1px solid {P["border"]};'
                        f'border-left:3px solid {P["cat_blue"]};border-radius:8px;padding:10px 14px;margin:6px 0">'
                        f'<span style="color:{P["text_secondary"]};font-size:0.9rem">💡 {ins}</span></div>',
                        unsafe_allow_html=True)

    # 热点问题 + 改进建议 两列
    hq = result.get("hot_questions", [])
    imp = result.get("improvements", [])
    hc, ic = st.columns(2)
    with hc:
        if hq:
            st.markdown(f'<div style="color:{P["text_muted"]};font-size:0.82rem;margin-bottom:8px">客户最关心的问题</div>',
                        unsafe_allow_html=True)
            for q in hq:
                st.markdown(f'<div style="background:{P["surface"]};border:1px solid {P["border"]};'
                            f'border-radius:8px;padding:8px 12px;margin:5px 0">'
                            f'<span style="color:{P["text_secondary"]};font-size:0.88rem">❓ {q}</span></div>',
                            unsafe_allow_html=True)
    with ic:
        if imp:
            st.markdown(f'<div style="color:{P["text_muted"]};font-size:0.82rem;margin-bottom:8px">改进建议</div>',
                        unsafe_allow_html=True)
            for im in imp:
                st.markdown(f'<div style="background:{P["surface"]};border:1px solid {P["border"]};'
                            f'border-left:3px solid {P["cat_gold"]};border-radius:8px;padding:8px 12px;margin:5px 0">'
                            f'<span style="color:{P["text_secondary"]};font-size:0.88rem">✅ {im}</span></div>',
                            unsafe_allow_html=True)

# ===== AI 自动回复建议 =====
st.markdown("---")
st.subheader("🤖 AI 自动回复建议")
st.caption("选择一条咨询,Agent 生成可直接回复的话术")

neg_pending = df[df["status"] == "待处理"].head(50)
if len(neg_pending) == 0:
    neg_pending = df.head(50)
sel = st.selectbox("选择咨询", options=neg_pending["content"].head(30).tolist(), key="reply_sel")
if sel and st.button("生成回复话术", type="primary", key="gen_reply"):
    row = df[df["content"] == sel].iloc[0]
    consult = {"content": sel, "type": row["consult_type"], "channel": row["channel"], "sentiment": row["sentiment"]}
    with st.spinner("AI 生成回复话术..." if is_llm_ready() else None):
        reply = generate_consult_reply(consult, use_llm=is_llm_ready())
    source = "AI 生成" if is_llm_ready() else "规则兜底"
    st.markdown(f'<div style="background:linear-gradient(135deg, rgba(201,133,0,0.12), {P["surface"]});'
                f'border:1px solid rgba(201,133,0,0.35);border-radius:10px;padding:14px 18px;margin:10px 0">'
                f'<div style="color:{P["text_muted"]};font-size:0.72rem;margin-bottom:6px">回复话术 · {source}</div>'
                f'<div style="color:{P["text_primary"]};font-size:0.95rem;line-height:1.6">{reply}</div></div>',
                unsafe_allow_html=True)
