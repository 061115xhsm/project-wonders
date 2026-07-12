"""数字化获客 —— 获客漏斗 + 渠道ROI对比 + AI 拉新方案(痛点③)

解决万泰痛点:会员拉新靠传统方式,数字化获客不知道怎么做。
- 获客渠道分布(微信小程序/支付即会员/扫码地推/线下门店)
- 获客漏斗(触达→注册→首单→复购)
- 渠道 ROI 对比(单客成本 vs 客单价)
- AI 拉新方案(选渠道,Agent 生成裂变/券码/地推方案)
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import sys
import json as _json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.utils import load_csv
from app.processor import clean_data, mask_sensitive_data
from app.date_filter import filter_members, get_date_range
from app.viz_theme import (
    apply_theme, chart_config, stat_card_html, kpi_grid_html, inject_global_css, mobile_notice_html, current_palette,
)
from app.agent import generate_acquisition_plan
from app.llm_client import is_llm_ready

st.set_page_config(page_title="数字化获客", layout="wide")
inject_global_css()
P = current_palette()
from app.date_filter import render_date_filter as _rdf
_rdf()  # 侧边栏时间段筛选器(每个页面都渲染,保证全页面可切换)


@st.cache_data(ttl=3600)
def load_data():
    members = load_csv("members_2023.csv", "raw")
    return clean_data(members)


members = load_data()
_dr_start, _dr_end = get_date_range()
_dr_label = f"{_dr_start.date()} ~ {_dr_end.date()}"

st.title("📣 数字化获客")
st.markdown(mobile_notice_html(), unsafe_allow_html=True)
st.caption(f"📅 时段内活跃会员:**{len(filter_members(members)):,}** 人({_dr_label}) · 获客渠道/漏斗/ROI/AI拉新方案")

# ===== KPI 行 =====
total = len(members)
channel_counts = members["register_channel"].value_counts()
digital_channels = ["微信小程序", "支付即会员", "扫码地推"]
digital_count = channel_counts.reindex(digital_channels).fillna(0).sum()
digital_pct = digital_count / total * 100 if total else 0
new_recent = len(members[pd.to_datetime(members["register_date"], errors="coerce") >= "2023-01-01"])
avg_spent = members["total_spent"].mean()

kpi = (
    stat_card_html("会员总数", f"{total:,}", f"数字化获客 {digital_pct:.0f}%", accent=P["cat_blue"])
    + stat_card_html("数字化渠道占比", f"{digital_pct:.0f}%",
                     f"{int(digital_count):,} 人来自线上", delta_good=digital_pct > 50, accent=P["cat_gold"])
    + stat_card_html("今年新增", f"{new_recent:,}", "2023年新增", accent=P["cat_aqua"])
    + stat_card_html("人均累计消费", f"¥{avg_spent:,.0f}", "全体均值", accent=P["cat_violet"])
)
st.markdown(kpi_grid_html(kpi, cols=4), unsafe_allow_html=True)

# ===== 获客渠道分布 =====
col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("📊 获客渠道分布")
    ch_order = ["微信小程序", "支付即会员", "扫码地推", "线下门店"]
    ch_counts = channel_counts.reindex(ch_order).fillna(0)
    is_digital = {"微信小程序": True, "支付即会员": True, "扫码地推": True, "线下门店": False}
    fig1 = go.Figure()
    for ch, cnt in zip(ch_counts.index, ch_counts.values):
        c = P["cat_aqua"] if is_digital.get(ch) else P["text_muted"]
        fig1.add_trace(go.Bar(
            y=[ch], x=[cnt], orientation="h", name=ch,
            marker_color=c, width=0.55,
            text=[f"{int(cnt):,} ({cnt/total*100:.0f}%)"], textposition="outside",
            textfont=dict(color=P["text_secondary"], size=12),
            hovertemplate=f"{ch}<br>%{{x:,}} 人<extra></extra>",
        ))
    fig1.update_layout(bargap=0.4, showlegend=False)
    fig1.update_xaxes(title_text="人数")
    apply_theme(fig1, height=300)
    st.plotly_chart(fig1, config=chart_config(), width="stretch")

with col2:
    st.subheader("🎯 渠道质量")
    st.caption("各渠道人均消费(衡量获客质量)")
    ch_quality = members.groupby("register_channel")["total_spent"].mean().reindex(ch_order).fillna(0).round(0)
    fig2 = go.Figure()
    for ch, v in zip(ch_quality.index, ch_quality.values):
        c = P["cat_gold"] if v == ch_quality.max() else P["cat_blue"]
        fig2.add_trace(go.Bar(
            x=[ch], y=[v], name=ch,
            marker_color=c, width=0.55,
            text=[f"¥{v:,.0f}"], textposition="outside",
            textfont=dict(color=P["text_secondary"], size=11),
            hovertemplate=f"{ch}<br>人均 ¥%{{y:,.0f}}<extra></extra>",
        ))
    fig2.update_layout(bargap=0.4, showlegend=False)
    fig2.update_yaxes(title_text="人均消费")
    apply_theme(fig2, height=300)
    st.plotly_chart(fig2, config=chart_config(), width="stretch")

# ===== 获客漏斗 =====
st.subheader("🔻 数字化获客漏斗")
st.caption("触达 → 注册 → 首单 → 复购,定位流失环节")

# 漏斗各环节(基于真实会员数据 + 合理转化率)
visited = int(total / 0.35)  # 假设触达转化率35%(到店客流中扫码触达)
registered = total
first_order = len(members[members["visit_count"] >= 1])
repeat = len(members[members["visit_count"] >= 3])

funnel_stages = ["触达(扫码/曝光)", "注册会员", "首单消费", "复购(≥3次)"]
funnel_values = [visited, registered, first_order, repeat]
fig3 = go.Figure(go.Funnel(
    y=funnel_stages, x=funnel_values,
    marker_color=P["cat_blue"],
    textinfo="value+percent initial+percent previous",
    textfont=dict(color="#ffffff", size=13),
    connector=dict(line=dict(color=P["border"], width=1)),
))
fig3.update_layout(margin=dict(l=8, r=16, t=16, b=8))
apply_theme(fig3, height=340, show_legend=False)
st.plotly_chart(fig3, config=chart_config(), width="stretch")

# ===== 渠道 ROI 对比表 =====
st.subheader("💰 渠道 ROI 对比")
roi_data = []
# 行业基准单客获客成本(元)
channel_cost = {"微信小程序": 8, "支付即会员": 5, "扫码地推": 15, "线下门店": 25}
_activation_rate = 0.1  # 新客激活率(行业基准,实际需小批量AB测试校准)
for ch in ch_order:
    cnt = int(ch_counts.get(ch, 0))
    if cnt == 0:
        continue
    avg_s = members[members["register_channel"] == ch]["avg_spent"].mean()  # 人均客单价(非累计终身消费)
    cost = channel_cost[ch] * cnt
    # 预期增量营收 = 人均客单(用 avg_spent 代替) * 激活率 * 获客数
    # 而非把"累计终身消费"当获客营收(口径错配会导致 ROI 虚高至 10000x+)
    revenue = avg_s * _activation_rate * cnt
    # ROI 上限 6x(与 agent.py 约束一致),防数字渠道低成本导致 ROI 虚高
    roi = min(round(revenue / cost, 1) if cost else 0, 6.0)
    roi_data.append({"渠道": ch, "获客数": cnt, "单客成本(元)": channel_cost[ch],
                     "人均消费": round(avg_s, 0), "总成本": cost, "预期增量营收": int(revenue), "ROI": roi})
roi_df = pd.DataFrame(roi_data)
st.dataframe(roi_df, width="stretch", hide_index=True,
             column_config={
                 "人均消费": st.column_config.NumberColumn("人均消费", format="¥%,.0f"),
                 "总成本": st.column_config.NumberColumn("总成本", format="¥%,.0f"),
                 "预期增量营收": st.column_config.NumberColumn("预期增量营收", format="¥%,.0f"),
                 "ROI": st.column_config.NumberColumn("ROI", format="%.1fx"),
             })
st.caption("⚠️ ROI=预期增量营收/获客成本,基于行业基准(激活率10%),需小批量AB测试校准。"
           "增量营收=人均消费×激活率×获客数,非累计终身消费。")

# ===== AI 拉新方案生成 =====
st.markdown("---")
st.subheader("🤖 AI 拉新方案生成")
st.caption("选择获客渠道,Agent 生成裂变/券码/地推等可落地拉新方案")

ch_sel = st.selectbox("选择获客渠道", options=ch_order, key="acq_channel")
target_count = st.slider("目标拉新人数", 50, 500, 200, step=50, key="acq_target")

if st.button("生成拉新方案", type="primary", key="gen_acq"):
    ch_stats = {
        "new_members": target_count,
        "channel_pct": digital_pct,
        "cost_per": channel_cost[ch_sel],
        "avg_spent": float(members[members["register_channel"] == ch_sel]["total_spent"].mean()) if ch_sel in channel_counts.index else float(avg_spent),
        "target_segment": "新客",
    }
    with st.spinner("Agent 生成数字化获客方案中..." if is_llm_ready() else None):
        plan = generate_acquisition_plan(ch_sel, ch_stats, use_llm=is_llm_ready())
    source = "AI 生成" if "llm" in plan.get("_source", "") else "规则兜底"

    # 渲染方案
    st.markdown(f'<div style="color:{P["text_muted"]};font-size:0.72rem;margin-bottom:6px">获客方案 · {source}</div>',
                unsafe_allow_html=True)
    # 打法
    st.markdown(f'<div style="background:{P["surface"]};border:1px solid {P["border"]};'
                f'border-left:3px solid {P["cat_aqua"]};border-radius:8px;padding:12px 16px;margin:8px 0">'
                f'<div style="color:{P["text_muted"]};font-size:0.75rem;margin-bottom:4px">具体打法</div>'
                f'<div style="color:{P["text_secondary"]};font-size:0.9rem;line-height:1.5">{plan.get("tactic","")}</div></div>',
                unsafe_allow_html=True)
    # 话术
    st.markdown(f'<div style="background:linear-gradient(135deg, rgba(201,133,0,0.12), {P["surface"]});'
                f'border:1px solid rgba(201,133,0,0.35);border-radius:10px;padding:14px 18px;margin:10px 0">'
                f'<div style="color:{P["text_muted"]};font-size:0.72rem;margin-bottom:6px">投放话术</div>'
                f'<div style="color:{P["text_primary"]};font-size:0.95rem;line-height:1.6">{plan.get("copywriting","")}</div></div>',
                unsafe_allow_html=True)
    # ROI 网格
    est_cost = plan.get("est_cost", 0)
    est_new = plan.get("est_new_members", 0)
    est_rev = plan.get("est_revenue", 0)
    roi = plan.get("roi", 0)
    roi_cls = "good" if isinstance(roi, (int, float)) and roi >= 3 else ""
    roi_grid = (
        f'<div class="roi-grid">'
        f'<div class="roi-tile"><div class="roi-label">预估成本</div><div class="roi-value">¥{est_cost:,}</div></div>'
        f'<div class="roi-tile"><div class="roi-label">预计新增</div><div class="roi-value">{est_new:,}</div></div>'
        f'<div class="roi-tile"><div class="roi-label">预计增收</div><div class="roi-value">¥{est_rev:,}</div></div>'
        f'<div class="roi-tile"><div class="roi-label">ROI</div><div class="roi-value {roi_cls}">{roi}x</div></div>'
        f'</div>'
    )
    st.markdown(roi_grid, unsafe_allow_html=True)
    st.caption("⚠️ 合规提示:话术不含绝对化用语与虚假优惠,券码需明示使用门槛与有效期。")

    # ===== 执行出口:复制话术 / 导出方案 / 标记已执行 =====
    st.markdown(f'<div style="color:{P["text_muted"]};font-size:0.72rem;margin:14px 0 6px">执行出口</div>',
                unsafe_allow_html=True)
    ex_c1, ex_c2, ex_c3 = st.columns([2, 2, 2])
    with ex_c1:
        st.caption("📋 投放话术(可复制)")
        st.code(plan.get("copywriting", ""), language="text")
    with ex_c2:
        plan_export = {k: v for k, v in plan.items() if k != "_source"}
        plan_export["_channel_selected"] = ch_sel
        plan_export["_target_count"] = target_count
        plan_json = _json.dumps(plan_export, ensure_ascii=False, indent=2)
        st.caption("📥 导出拉新方案")
        st.download_button(
            "📥 导出拉新方案(JSON)",
            data=plan_json,
            file_name=f"拉新方案_{ch_sel}_{target_count}人.json",
            mime="application/json",
            key="dl_acq_plan",
        )
    with ex_c3:
        st.caption("✅ 标记方案已执行")
        if st.button("✅ 标记为已执行", key="mark_executed_acq", use_container_width=True):
            executed = st.session_state.setdefault("executed_acq", [])
            record = {
                "channel": ch_sel,
                "tactic": plan.get("tactic", ""),
                "copywriting": plan.get("copywriting", ""),
                "est_cost": plan.get("est_cost", 0),
                "est_new_members": plan.get("est_new_members", 0),
                "est_revenue": plan.get("est_revenue", 0),
                "roi": plan.get("roi", 0),
                "actual_new": None,
                "actual_cost": plan.get("est_cost", 0),
                "source": source,
                "executed_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
            }
            executed.append(record)
            st.session_state["executed_acq"] = executed
            st.toast("✅ 拉新方案已标记为已执行,可在底部执行台账录入实际数据", icon="✅")

# ===== 执行台账(底部展示已执行拉新方案) =====
st.markdown("---")
st.subheader("📒 执行台账")
st.caption("已执行的拉新方案,录入实际新增人数,回算真实获客成本并与预估对比")

executed = st.session_state.get("executed_acq", [])
if not executed:
    st.info("暂无已执行的拉新方案。生成方案后点击「✅ 标记为已执行」即可记录到台账。")
else:
    ledger_rows = []
    for i, rec in enumerate(executed):
        est_cost = rec.get("est_cost", 0) or 0
        est_new = rec.get("est_new_members", 0) or 0
        est_rev = rec.get("est_revenue", 0) or 0
        est_roi = rec.get("roi", 0)
        # 实际新增人数输入框
        cur_actual = rec.get("actual_new")
        actual_new_input = st.number_input(
            f"实际新增人数 · {rec.get('channel','')} · {rec.get('executed_at','')}",
            min_value=0, value=int(cur_actual) if cur_actual else 0, step=10,
            key=f"actual_new_{i}",
        )
        # 写回 session_state
        executed[i]["actual_new"] = actual_new_input
        # 实际成本(默认=预估成本,可后续扩展为输入)
        actual_cost = rec.get("actual_cost", est_cost) or est_cost
        # 真实获客成本 = 实际成本 / 实际新增
        real_cpa = round(actual_cost / actual_new_input, 1) if actual_new_input > 0 else None
        # 预估单客成本
        est_cpa = round(est_cost / est_new, 1) if est_new > 0 else None
        # 真实 ROI = 实际增收(按实际新增比例折算预估增收) / 实际成本
        actual_rev = int(est_rev * actual_new_input / est_new) if est_new > 0 else 0
        real_roi = round(actual_rev / actual_cost, 1) if actual_cost > 0 else 0
        ledger_rows.append({
            "渠道": rec.get("channel", ""),
            "执行时间": rec.get("executed_at", ""),
            "来源": rec.get("source", ""),
            "预估新增": est_new,
            "实际新增": actual_new_input,
            "预估成本(¥)": est_cost,
            "实际成本(¥)": actual_cost,
            "预估单客成本(¥)": est_cpa if est_cpa is not None else "—",
            "真实单客成本(¥)": real_cpa if real_cpa is not None else "—",
            "预估ROI": f"{est_roi}x",
            "真实ROI": f"{real_roi}x" if actual_new_input > 0 else "—",
        })
    st.session_state["executed_acq"] = executed
    ledger_df = pd.DataFrame(ledger_rows)
    st.dataframe(ledger_df, width="stretch", hide_index=True,
                 column_config={
                     "预估成本(¥)": st.column_config.NumberColumn("预估成本(¥)", format="¥%,.0f"),
                     "实际成本(¥)": st.column_config.NumberColumn("实际成本(¥)", format="¥%,.0f"),
                 })
    st.caption("💡 真实单客成本 = 实际成本 / 实际新增;真实ROI = 折算实际增收 / 实际成本。"
               "录入实际新增人数后自动回算,与预估值对比定位偏差。")
