"""首页概览 —— 全景视图"""
import streamlit as st
import pandas as pd
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.utils import load_csv
from app.processor import clean_data, mask_sensitive_data
from app.models import RFMModel, calculate_shop_score
from app.viz_theme import (
    themed_line, stat_card_html, kpi_grid_html, hero_figure_html,
    segment_colors, insights_html, inject_global_css, current_palette,
)
from app.agent import generate_daily_digest, chat_operation
from app.llm_client import is_llm_ready

st.set_page_config(page_title="首页概览", layout="wide")
inject_global_css()
P = current_palette()


@st.cache_data(ttl=3600)
def load_all_data():
    traffic = load_csv("foot_traffic_2023.csv", "raw")
    members = load_csv("members_2023.csv", "raw")
    shops = load_csv("shops_master.csv", "raw")
    members_clean = clean_data(members)
    members_masked = mask_sensitive_data(members_clean)
    rfm = RFMModel()
    labels = rfm.fit(members_masked)
    members_masked["segment"] = labels
    scored = calculate_shop_score(shops)
    return traffic, members_masked, scored


traffic, members, shops_scored = load_all_data()

st.title("🏠 首页概览")

# ===== Hero 区:年度总营收 =====
total_revenue = shops_scored["monthly_sales"].sum() * 12
vip_count = len(members[members["segment"] == "高价值"])
st.markdown(
    hero_figure_html(
        "年度总营收(估)", f"¥{total_revenue/1e6:,.1f}M",
        subtitle=f"基于 {shops_scored['name'].nunique()} 个真实品牌 · 高价值会员 {vip_count:,} 人 · 数据已脱敏",
        accent=P["cat_gold"],
    ),
    unsafe_allow_html=True,
)

# ===== KPI 行 =====
today_traffic = traffic["visitor_count"].sum()
total_members = len(members)
vip_ratio = vip_count / total_members * 100 if total_members else 0

kpi = (
    stat_card_html("年度总客流", f"{today_traffic/1e4:,.1f}万", "↑ 完整年度",
                   delta_good=True, accent=P["cat_blue"])
    + stat_card_html("会员总数", f"{total_members:,}",
                     f"高价值 {vip_count:,} 人", delta_good=True,
                     accent=P["cat_aqua"])
    + stat_card_html("高价值会员占比", f"{vip_ratio:.1f}%",
                     f"共 {vip_count:,} 人", delta_good=True,
                     accent=P["cat_gold"])
    + stat_card_html("商铺数", f"{len(shops_scored)}",
                     f"覆盖 {shops_scored['category'].nunique()} 个业态",
                     delta_good=True, accent=P["cat_violet"])
)
st.markdown(kpi_grid_html(kpi, cols=4), unsafe_allow_html=True)

# ===== AI 运营日报(Agent 基于全局统计生成 3 条洞察)=====
overview = {
    "total_traffic": int(today_traffic),
    "total_revenue": int(total_revenue),
    "total_members": int(total_members),
    "vip_count": int(vip_count),
    "vip_ratio": round(vip_ratio, 1),
    "shop_count": int(len(shops_scored)),
    "category_count": int(shops_scored["category"].nunique()),
    "top_peak": "周末 19:00",
    "holiday_boost": 2.0,
    "rain_drop_pct": 20,
}
llm_ok = is_llm_ready()
with st.spinner("AI 运营分析师生成日报中..." if llm_ok else None):
    @st.cache_data(ttl=600)
    def _digest(traffic, revenue, members_n, vip, vip_r, shops_n, cats, peak, hol, rain, ok):
        return generate_daily_digest(
            {"total_traffic": traffic, "total_revenue": revenue, "total_members": members_n,
             "vip_count": vip, "vip_ratio": vip_r, "shop_count": shops_n,
             "category_count": cats, "top_peak": peak, "holiday_boost": hol, "rain_drop_pct": rain},
            use_llm=ok,
        )
    insights = _digest(
        overview["total_traffic"], overview["total_revenue"], overview["total_members"],
        overview["vip_count"], overview["vip_ratio"], overview["shop_count"],
        overview["category_count"], overview["top_peak"], overview["holiday_boost"],
        overview["rain_drop_pct"], llm_ok,
    )
st.markdown(insights_html(insights), unsafe_allow_html=True)

# ===== 近 30 天客流趋势 =====
st.subheader("📈 近 30 天客流趋势")
recent = traffic[traffic["date"] >= "2023-12-01"].copy()
recent["date"] = pd.to_datetime(recent["date"])
daily = recent.groupby("date")["visitor_count"].sum().reset_index()
fig = themed_line(daily["date"], daily["visitor_count"],
                  name="日客流", color=P["cat_blue"], height=320)
# 端点直接标注(单序列 → 无图例框,标最后一个点)
last_row = daily.iloc[-1]
fig.add_annotation(
    x=last_row["date"], y=last_row["visitor_count"],
    text=f"{last_row['visitor_count']:,.0f}",
    showarrow=False, xanchor="left", xshift=8,
    font=dict(color=P["text_primary"], size=11),
)
fig.update_yaxes(title_text="客流")
st.plotly_chart(fig, width="stretch")

# ===== Top 5 商铺 =====
st.subheader("🏆 Top 5 商铺")
top5 = shops_scored.nsmallest(5, "rank")[["name", "category", "floor", "score", "rank"]].copy()
top5.columns = ["商铺名", "业态", "楼层", "综合评分", "排名"]
top5 = top5.sort_values("排名").reset_index(drop=True)
top5.index = top5.index + 1
top5.index.name = "序号"

st.dataframe(
    top5.style.format({"综合评分": "{:.1f}"}),
    width="stretch", hide_index=False,
)

st.caption(f"数据来源:真实商户({shops_scored['name'].nunique()} 品牌)· 2023 全年模拟运营 · 评分 = 0.4×销售 + 0.3×客流 + 0.2×租售比 + 0.1×转化率")

# ===== AI 运营对话(多轮)=====
st.markdown("---")
st.subheader("🤖 AI 运营助手")
st.caption("多轮对话 · AI 结合商场真实数据回答(客流/会员/商铺/营销/租户均可,可追问)")

# 初始化对话历史
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []


def _send_question(q: str):
    """发送问题:加入历史 → 调 AI → 加入回答 → rerun"""
    q = q.strip()
    if not q:
        return
    st.session_state["chat_history"].append({"role": "user", "content": q})
    with st.spinner("AI 思考中..." if is_llm_ready() else None):
        history = st.session_state["chat_history"][:-1]
        answer = chat_operation(q, history, use_llm=is_llm_ready())
    source = "AI 生成" if is_llm_ready() else "规则兜底"
    st.session_state["chat_history"].append({"role": "assistant", "content": answer, "source": source})


# 预设问题快捷按钮(点击即发送)
preset_qs = [
    "高价值会员有多少?",
    "沉睡会员怎么激活?",
    "L1有哪些主力店?",
    "周末客流是工作日几倍?",
    "哪些商铺租售比过高?",
    "怎么提升会员转化率?",
]
pq_cols = st.columns(3)
for i, q in enumerate(preset_qs):
    with pq_cols[i % 3]:
        if st.button(q, key=f"pq_{i}", use_container_width=True):
            _send_question(q)
            st.rerun()

# 渲染历史对话(聊天气泡)
chat_container = st.container()
with chat_container:
    for msg in st.session_state["chat_history"]:
        if msg["role"] == "user":
            st.markdown(f'<div style="display:flex;justify-content:flex-end;margin:8px 0">'
                        f'<div style="background:{P["cat_blue"]};color:#fff;padding:10px 16px;'
                        f'border-radius:14px 14px 4px 14px;max-width:80%;font-size:0.9rem;white-space:pre-line">{msg["content"]}</div></div>',
                        unsafe_allow_html=True)
        else:
            src = msg.get("source", "")
            src_badge = f'<span style="font-size:0.68rem;color:{P["text_muted"]};margin-right:6px">{src}</span>' if src else ""
            st.markdown(f'<div style="display:flex;justify-content:flex-start;margin:8px 0">'
                        f'<div style="background:{P["surface"]};border:1px solid {P["border"]};color:{P["text_primary"]};'
                        f'padding:10px 16px;border-radius:14px 14px 14px 4px;max-width:85%;font-size:0.9rem;line-height:1.7;white-space:pre-line">'
                        f'{src_badge}{msg["content"]}</div></div>',
                        unsafe_allow_html=True)

# 输入区(用 form 提交)
with st.form("chat_form", clear_on_submit=True):
    question = st.text_input(
        "你的问题",
        placeholder="例如:高价值会员有多少? → 再追问:他们平均消费多少? → 怎么提升留存?",
        label_visibility="collapsed",
    )
    submitted = st.form_submit_button("发送", type="primary", use_container_width=False)

if submitted and question.strip():
    _send_question(question)
    st.rerun()

# 清空对话按钮
if st.session_state["chat_history"]:
    if st.button("🗑️ 清空对话", key="clear_chat"):
        st.session_state["chat_history"] = []
        st.rerun()
