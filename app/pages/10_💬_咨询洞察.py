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
from app.date_filter import filter_consultations, get_date_range
from app.viz_theme import (
    apply_theme, chart_config, stat_card_html, kpi_grid_html, inject_global_css, mobile_notice_html, current_palette,
)
from app.agent import analyze_consultations, generate_consult_reply
from app.llm_client import is_llm_ready

st.set_page_config(page_title="咨询洞察", layout="wide")
inject_global_css()
P = current_palette()
from app.date_filter import render_date_filter as _rdf
_rdf()  # 侧边栏时间段筛选器(每个页面都渲染,保证全页面可切换)


@st.cache_data(ttl=3600)
def load_data():
    return load_csv("consultations_2023.csv", "raw")


df = load_data()
df = filter_consultations(df)
_dr_start, _dr_end = get_date_range()
_dr_label = f"{_dr_start.date()} ~ {_dr_end.date()}"

st.title("💬 客户咨询洞察")
st.markdown(mobile_notice_html(), unsafe_allow_html=True)
st.caption(f"📅 当前分析时段:**{_dr_label}**(左侧侧边栏可切换) · 把沉睡的咨询数据变成可行动的运营动作")

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
st.plotly_chart(fig1, config=chart_config(), width="stretch")

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
    st.plotly_chart(fig2, config=chart_config(), width="stretch")

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
    st.plotly_chart(fig3, config=chart_config(), width="stretch")

# ===== 热点问题月度趋势 =====
st.subheader("📈 热点问题趋势")
top5_types = type_counts.head(5).index.tolist()
_dt = pd.to_datetime(df["date"], errors="coerce")
# 时段跨度≤31天 → 按日聚合;否则按月(避免短时段只剩小点)
_span_days = (_dt.max() - _dt.min()).days if _dt.notna().any() and _dt.max() > _dt.min() else 365
if _span_days <= 31:
    df["period"] = _dt.dt.strftime("%m-%d")
    _x_label = "日期"
    _x_vals = sorted(df["period"].dropna().unique())
else:
    df["period"] = _dt.dt.month
    _x_label = "月份"
    _x_vals = list(range(1, 13))
monthly = df[df["consult_type"].isin(top5_types)].groupby(["period", "consult_type"]).size().unstack(fill_value=0)
fig4 = go.Figure()
colors5 = [P["cat_blue"], P["cat_aqua"], P["cat_gold"], P["cat_green"], P["cat_violet"]]
for i, t in enumerate(top5_types):
    vals = [int(monthly.loc[x, t]) if (t in monthly.columns and x in monthly.index) else 0 for x in _x_vals]
    fig4.add_trace(go.Scatter(
        x=_x_vals, y=vals, name=t, mode="lines+markers",
        line=dict(color=colors5[i], width=2.5),
        marker=dict(size=8, color=colors5[i]),
        hovertemplate=f"{t}<br>%{{x}}: %{{y}} 条<extra></extra>",
    ))
fig4.update_xaxes(title_text=_x_label)
fig4.update_yaxes(title_text="咨询数")
apply_theme(fig4, height=360)
st.plotly_chart(fig4, config=chart_config(), width="stretch")

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
    st.session_state["consult_insight_result"] = result
    st.session_state["consult_insight_source"] = "AI 生成" if "llm" in result.get("_source", "") else "规则兜底"

# 从 session_state 取洞察结果(跨 rerun 保留,供导出/转任务使用)
result = st.session_state.get("consult_insight_result")
if result:
    source = st.session_state.get("consult_insight_source", "规则兜底")

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
            for i, im in enumerate(imp):
                st.markdown(f'<div style="background:{P["surface"]};border:1px solid {P["border"]};'
                            f'border-left:3px solid {P["cat_gold"]};border-radius:8px;padding:8px 12px;margin:5px 0">'
                            f'<span style="color:{P["text_secondary"]};font-size:0.88rem">✅ {im}</span></div>',
                            unsafe_allow_html=True)
                if st.button("📌 转任务", key=f"to_task_{i}", help="将此改进建议转为待办任务"):
                    tasks = st.session_state.setdefault("consult_tasks", [])
                    if im not in [t["content"] for t in tasks]:
                        tasks.append({"content": im, "source": "咨询洞察·改进建议"})
                        st.toast("已转入任务清单", icon="📌")
                    else:
                        st.toast("该建议已在任务清单中", icon="ℹ️")

    # 导出洞察报告(markdown)
    if insights or hq or imp:
        md_lines = ["# 万泰新天地 · 咨询洞察报告", ""]
        md_lines.append(f"> 数据来源:{source} | 咨询总量 {total:,} 条 | 生成时间由系统自动记录")
        md_lines.append("")
        if insights:
            md_lines.append("## 数据洞察")
            md_lines.append("")
            for ins in insights:
                md_lines.append(f"- {ins}")
            md_lines.append("")
        if hq:
            md_lines.append("## 客户最关心的问题")
            md_lines.append("")
            for q in hq:
                md_lines.append(f"- {q}")
            md_lines.append("")
        if imp:
            md_lines.append("## 改进建议")
            md_lines.append("")
            for im in imp:
                md_lines.append(f"- {im}")
            md_lines.append("")
        report_md = "\n".join(md_lines)
        st.download_button(
            "📥 导出洞察报告",
            data=report_md,
            file_name="咨询洞察报告.md",
            mime="text/markdown",
            help="下载 insights / hot_questions / improvements 的 Markdown 报告",
        )

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
        reply_result = generate_consult_reply(consult, use_llm=is_llm_ready())
    reply = reply_result.get("text", "") if isinstance(reply_result, dict) else reply_result
    source = "AI 生成" if (isinstance(reply_result, dict) and "llm" in reply_result.get("_source", "")) else "规则兜底"
    st.session_state["consult_reply_text"] = reply
    st.session_state["consult_reply_source"] = source
    st.session_state["consult_reply_content"] = sel
    st.session_state["consult_reply_meta"] = {
        "type": row["consult_type"], "channel": row["channel"], "sentiment": row["sentiment"],
    }

# 展示生成的回复(跨 rerun 保留)
reply = st.session_state.get("consult_reply_text")
if reply:
    source = st.session_state.get("consult_reply_source", "")
    sel_content = st.session_state.get("consult_reply_content", "")
    st.markdown(f'<div style="background:linear-gradient(135deg, rgba(201,133,0,0.12), {P["surface"]});'
                f'border:1px solid rgba(201,133,0,0.35);border-radius:10px;padding:14px 18px;margin:10px 0">'
                f'<div style="color:{P["text_muted"]};font-size:0.72rem;margin-bottom:6px">回复话术 · {source}</div>'
                f'<div style="color:{P["text_primary"]};font-size:0.95rem;line-height:1.6">{reply}</div></div>',
                unsafe_allow_html=True)
    # 复制回复(st.code 自带复制按钮)
    st.markdown(f'<div style="color:{P["text_muted"]};font-size:0.78rem;margin:8px 0 2px">📋 复制回复(点右侧图标复制)</div>',
                unsafe_allow_html=True)
    st.code(reply, language="text")
    # 标记已回复
    replied = st.session_state.setdefault("replied_consults", [])
    already = any(r.get("content") == sel_content for r in replied)
    if already:
        st.markdown(f'<span style="color:{P["good"]};font-size:0.85rem">✅ 该咨询已标记为已回复</span>',
                    unsafe_allow_html=True)
    else:
        if st.button("📨 标记已回复", key="mark_replied", help="记录到回复台账"):
            meta = st.session_state.get("consult_reply_meta", {})
            replied.append({
                "content": sel_content,
                "reply": reply,
                "type": meta.get("type", ""),
                "channel": meta.get("channel", ""),
                "sentiment": meta.get("sentiment", ""),
                "source": source,
            })
            st.toast("已标记并写入回复台账", icon="📨")
            st.rerun()

# ===== 回复台账 =====
replied = st.session_state.get("replied_consults", [])
if replied:
    st.markdown("---")
    st.subheader("📝 回复台账")
    st.caption(f"已回复咨询 {len(replied)} 条")
    ledger_df = pd.DataFrame(replied)
    # 列顺序与中文名
    col_map = {"content": "咨询内容", "reply": "回复话术", "type": "类型",
               "channel": "渠道", "sentiment": "情感", "source": "来源"}
    ledger_df = ledger_df[[c for c in col_map if c in ledger_df.columns]]
    ledger_df = ledger_df.rename(columns=col_map)
    st.dataframe(ledger_df, width="stretch", hide_index=True)
    st.download_button(
        "📥 导出台账",
        data=ledger_df.to_csv(index=False).encode("utf-8-sig"),
        file_name="咨询回复台账.csv",
        mime="text/csv",
    )

# ===== 任务清单 =====
tasks = st.session_state.get("consult_tasks", [])
if tasks:
    st.markdown("---")
    st.subheader("📌 改进任务清单")
    st.caption(f"待办任务 {len(tasks)} 条(来自咨询洞察·改进建议)")
    for i, t in enumerate(tasks):
        tc, btn_c = st.columns([8, 2])
        with tc:
            st.markdown(f'<div style="background:{P["surface"]};border:1px solid {P["border"]};'
                        f'border-left:3px solid {P["cat_violet"]};border-radius:8px;padding:8px 12px;margin:4px 0">'
                        f'<span style="color:{P["text_secondary"]};font-size:0.9rem">{i+1}. {t["content"]}</span>'
                        f'<span style="color:{P["text_muted"]};font-size:0.72rem;margin-left:8px">[{t.get("source","")}]</span></div>',
                        unsafe_allow_html=True)
        with btn_c:
            if st.button("完成", key=f"done_task_{i}", help="移除该任务"):
                tasks.pop(i)
                st.rerun()
