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
from app.agent import generate_marketing_plan_react
from app.date_filter import filter_members, get_date_range
from app.viz_theme import (
    segment_colors, SEGMENT_ORDER, apply_theme, chart_config,
    stat_card_html, kpi_grid_html, hero_figure_html, marketing_plan_html,
    inject_global_css, mobile_notice_html, current_palette,
)

st.set_page_config(page_title="营销助手", layout="wide")
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
_dr_start, _dr_end = get_date_range()
_dr_label = f"{_dr_start.date()} ~ {_dr_end.date()}"

st.title("📢 营销助手")
st.markdown(mobile_notice_html(), unsafe_allow_html=True)
st.caption(f"📅 时段内活跃会员:**{len(filter_members(members)):,}** 人({_dr_label}) · RAG 知识库 + 大模型 Agent 自动生成可落地方案(RFM 分群基于全量存量)")


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

with st.spinner(f"ReAct Agent 正在自主调工具收集信息 + 生成 {segment} 群体方案..." if use_llm
                else "生成方案中..."):
    # 方案按群体+统计指纹缓存(统计变才重算)
    @st.cache_data(ttl=600)
    def _gen(seg, count, avg_spent, avg_visit, avg_order, use_llm_flag):
        s = {"count": count, "pct": 0, "avg_spent": avg_spent,
             "avg_visit": avg_visit, "avg_order": avg_order}
        return generate_marketing_plan_react(seg, s, use_llm=use_llm_flag)

    plan = _gen(segment, int(stats["count"]), float(stats["avg_spent"]),
                float(stats["avg_visit"]), float(stats["avg_order"]), use_llm)

# ===== Agent 思考轨迹(展示ReAct工具调用过程,评审亮点)=====
trace = plan.get("_trace", [])
if trace:
    with st.expander(f"🧠 Agent 思考轨迹({len(trace)}步工具调用)", expanded=False):
        st.caption("ReAct Agent 自主决定调哪些工具收集信息,而非硬编码流程。这是真Agent行为。")
        for t in trace:
            tool_name = t.get("tool", "")
            tool_args = t.get("args", {})
            result_preview = t.get("result_preview", "")
            st.markdown(
                f'<div style="background:{P["surface"]};border:1px solid {P["border"]};'
                f'border-left:3px solid {P["cat_violet"]};border-radius:8px;padding:10px 14px;margin:8px 0">'
                f'<div style="color:{P["cat_violet"]};font-size:0.82rem;font-weight:600;margin-bottom:4px">'
                f'步{t["step"]}: 🔧 {tool_name}</div>'
                f'<div style="color:{P["text_muted"]};font-size:0.78rem;margin-bottom:4px">参数: {tool_args}</div>'
                f'<div style="color:{P["text_secondary"]};font-size:0.8rem;font-family:monospace;white-space:pre-wrap;word-break:break-all">'
                f'{result_preview}...</div></div>',
                unsafe_allow_html=True,
            )

# 渲染分块方案
st.markdown(marketing_plan_html(plan), unsafe_allow_html=True)

# ===== 执行出口:把方案从"只读卡片"变"可执行" =====
import json as _json
from datetime import datetime

st.markdown("---")
st.subheader("🚀 执行出口")
st.caption("把方案转化为动作:复制话术 / 导出方案 / 导出名单 / 标记已执行")

exec_col1, exec_col2 = st.columns(2)
with exec_col1:
    if st.button("📋 复制投放话术", type="primary", key="btn_copy_cw", use_container_width=True):
        cw = plan.get("copywriting", "")
        st.code(cw, language="text")
        st.toast("投放话术已展开,点击右侧复制按钮即可复制", icon="📋")

with exec_col2:
    plan_json = _json.dumps(plan, ensure_ascii=False, indent=2)
    st.download_button(
        "📥 导出方案(JSON)",
        data=plan_json,
        file_name=f"营销方案_{segment}.json",
        mime="application/json",
        type="secondary",
        use_container_width=True,
    )

# 导出 CSV 联动商户名单
products = plan.get("products") or []
if products:
    csv_lines = ["shop,reason"]
    for p in products:
        shop = str(p.get("shop", "")).replace(",", " ")
        reason = str(p.get("reason", "")).replace(",", " ")
        csv_lines.append(f"{shop},{reason}")
    csv_data = "\n".join(csv_lines)
    st.download_button(
        "📑 导出联动商户名单(CSV)",
        data=csv_data,
        file_name=f"联动商户_{segment}.csv",
        mime="text/csv",
        type="secondary",
        use_container_width=True,
    )

# 标记为已执行 → 写入 session_state 执行台账
if st.button("✅ 标记为已执行", type="primary", key="btn_mark_exec", use_container_width=True):
    if "executed_plans" not in st.session_state:
        st.session_state["executed_plans"] = []
    roi = plan.get("roi", {}) or {}
    record = {
        "segment": segment,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "objective": plan.get("objective", ""),
        "est_revenue": roi.get("est_revenue", 0),
        "cost": roi.get("cost", 0),
        "roi_ratio": roi.get("roi_ratio", 0),
        "actual_reach": None,
        "actual_revenue": None,
    }
    st.session_state["executed_plans"].append(record)
    st.toast("已记录到执行台账", icon="✅")

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
    st.plotly_chart(fig1, config=chart_config(), width="stretch")

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
    st.plotly_chart(fig2, config=chart_config(), width="stretch")

# ===== 执行台账(页面底部) =====
st.markdown("---")
st.subheader("📊 执行台账")
st.caption("已标记执行的方案列表;可录入实际触达/实际增收,回算真实 ROI 与预估对比")

executed = st.session_state.get("executed_plans", [])
if not executed:
    st.info("暂无已执行方案。点击上方「✅ 标记为已执行」即可记录到台账。")
else:
    for idx, rec in enumerate(executed):
        seg_name = rec.get("segment", "—")
        with st.expander(
            f"{idx + 1}. {seg_name} · {rec.get('time', '—')} · {rec.get('objective', '')[:30]}",
            expanded=False,
        ):
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("预估增量营收", f"¥{rec.get('est_revenue', 0):,.0f}")
            with m2:
                st.metric("预估投放成本", f"¥{rec.get('cost', 0):,.0f}")
            with m3:
                est_roi = rec.get("roi_ratio", 0)
                st.metric("预估 ROI", f"{est_roi}x")

            st.markdown(
                f'<div style="color:{P["text_secondary"]};font-weight:600;margin:8px 0 4px">录入实际效果</div>',
                unsafe_allow_html=True,
            )
            in1, in2 = st.columns(2)
            with in1:
                actual_reach = st.number_input(
                    "实际触达人数", min_value=0, value=0, step=1,
                    key=f"actual_reach_{idx}",
                )
            with in2:
                actual_rev = st.number_input(
                    "实际增收(元)", min_value=0, value=0, step=100,
                    key=f"actual_rev_{idx}",
                )
            # 回算真实 ROI(实际增收 / 投放成本)
            cost = rec.get("cost", 0) or 0
            real_roi = round(actual_rev / cost, 2) if cost > 0 else 0.0
            # 真实 vs 预估对比
            c1, c2 = st.columns(2)
            with c1:
                delta = round(real_roi - est_roi, 2) if isinstance(est_roi, (int, float)) else 0
                st.metric("真实 ROI", f"{real_roi}x", delta=f"{delta:+}x" if delta else None,
                          delta_color="inverse" if delta < 0 else "normal")
            with c2:
                rev_delta = actual_rev - rec.get("est_revenue", 0)
                st.metric("营收偏差", f"{rev_delta:+,.0f} 元",
                          delta_color="inverse" if rev_delta < 0 else "normal")

