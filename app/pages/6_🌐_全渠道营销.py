"""全渠道营销 —— 统一会员ID + 线上线下触点 + 全渠道协同(痛点②)

解决万泰痛点:线上线下会员不打通,营销割裂。
- 统一会员ID体系(一个ID贯通小程序/门店/支付/营销)
- 线上线下触点矩阵(各触点的会员覆盖与转化)
- 全渠道协同方案(同一会员跨触点旅程)
- 接口预留(对接万泰现有SaaS/OA/会员系统的方案说明)
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.utils import load_csv
from app.processor import clean_data
from app.date_filter import filter_members, get_date_range
from app.viz_theme import (
    apply_theme, chart_config, stat_card_html, kpi_grid_html, inject_global_css, mobile_notice_html, current_palette,
)

st.set_page_config(page_title="全渠道营销", layout="wide")
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

st.title("🌐 全渠道营销")
st.markdown(mobile_notice_html(), unsafe_allow_html=True)
st.caption(f"📅 时段内活跃会员:**{len(filter_members(members)):,}** 人({_dr_label}) · 统一会员ID · 线上线下触点全渠道协同")

# ===== KPI 行 =====
total = len(members)
channel_counts = members["register_channel"].value_counts()
# 线上线下占比
online_ch = ["微信小程序", "支付即会员", "扫码地推"]
offline_ch = ["线下门店"]
online_n = channel_counts.reindex(online_ch).fillna(0).sum()
offline_n = channel_counts.reindex(offline_ch).fillna(0).sum()
# 跨触点会员(visit_count高 = 多触点活跃)
multi_touch = len(members[members["visit_count"] >= 20])
unified_pct = multi_touch / total * 100 if total else 0

kpi = (
    stat_card_html("统一会员ID", f"{total:,}", "统一会员ID体系(设计中)", accent=P["cat_blue"])
    + stat_card_html("线上渠道会员", f"{int(online_n):,}", f"{online_n/total*100:.0f}% 占比", accent=P["cat_aqua"])
    + stat_card_html("线下渠道会员", f"{int(offline_n):,}", f"{offline_n/total*100:.0f}% 占比", accent=P["cat_orange"])
    + stat_card_html("多触点活跃", f"{multi_touch:,}", f"到店≥20次", delta_good=True, accent=P["cat_gold"])
)
st.markdown(kpi_grid_html(kpi, cols=4), unsafe_allow_html=True)

# ===== 统一会员ID体系说明 =====
st.subheader("🆔 统一会员ID体系")
st.caption("规划的统一ID体系,会员在任一触点行为归集到同一ID(设计中)")

st.markdown(f'<div style="background:{P["surface"]};border:1px solid {P["border"]};'
            f'border-radius:10px;padding:14px 18px;margin:10px 0">'
            f'<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">'
            f'<span style="background:rgba(57,135,229,0.18);color:{P["cat_blue"]};padding:6px 12px;'
            f'border-radius:8px;font-size:0.85rem">会员统一ID</span>'
            f'<span style="color:{P["text_muted"]}">→</span>'
            f'<span style="background:rgba(25,158,112,0.18);color:{P["cat_aqua"]};padding:6px 12px;border-radius:8px;font-size:0.85rem">微信小程序</span>'
            f'<span style="background:rgba(201,133,0,0.18);color:{P["cat_gold"]};padding:6px 12px;border-radius:8px;font-size:0.85rem">门店POS</span>'
            f'<span style="background:rgba(217,89,38,0.18);color:{P["cat_orange"]};padding:6px 12px;border-radius:8px;font-size:0.85rem">支付即会员</span>'
            f'<span style="background:rgba(144,133,233,0.18);color:{P["cat_violet"]};padding:6px 12px;border-radius:8px;font-size:0.85rem">营销系统</span>'
            f'<span style="background:rgba(213,81,129,0.18);color:{P["cat_magenta"]};padding:6px 12px;border-radius:8px;font-size:0.85rem">租户系统</span>'
            f'</div></div>', unsafe_allow_html=True)

st.caption("规划的统一ID体系(设计中):会员在任一触点注册/消费,行为归集到同一ID,营销可跨触点协同(如线上领券→门店核销→积分回传)")

# ===== 线上线下触点矩阵 =====
st.subheader("📍 线上线下触点矩阵")
st.caption("各触点会员来源与消费贡献")

touchpoint_data = []
for ch in ["微信小程序", "支付即会员", "扫码地推", "线下门店"]:
    sub = members[members["register_channel"] == ch]
    cnt = len(sub)
    if cnt == 0:
        continue
    touchpoint_data.append({
        "触点": ch,
        "类型": "线上" if ch in online_ch else "线下",
        "会员数": cnt,
        "占比": f"{cnt/total*100:.1f}%",
        "人均消费": f"¥{sub['total_spent'].mean():,.0f}",
        "人均到店": f"{sub['visit_count'].mean():.1f}次",
    })
st.dataframe(pd.DataFrame(touchpoint_data), width="stretch", hide_index=True)

# ===== 触点桑基图(来源→消费) =====
st.subheader("🔀 触点流向(会员来源 → 消费层级)")
st.caption("展示会员从注册渠道到消费层级的流转")

# 3 个消费层级
def _tier(s):
    if s >= 10000:
        return "高消费(≥1万)"
    elif s >= 3000:
        return "中消费(3k-1万)"
    else:
        return "低消费(<3k)"

members["tier"] = members["total_spent"].apply(_tier)
ch_list = ["微信小程序", "支付即会员", "扫码地推", "线下门店"]
tier_list = ["低消费(<3k)", "中消费(3k-1万)", "高消费(≥1万)"]
labels = ch_list + tier_list
source, target, value = [], [], []
for i, ch in enumerate(ch_list):
    for j, t in enumerate(tier_list):
        cnt = len(members[(members["register_channel"] == ch) & (members["tier"] == t)])
        if cnt > 0:
            source.append(i)
            target.append(len(ch_list) + j)
            value.append(cnt)

ch_color = [P["cat_aqua"], P["cat_gold"], P["cat_orange"], P["text_muted"]]
tier_color = [P["text_muted"], P["cat_blue"], P["cat_gold"]]
link_color = [ch_color[s].replace("#", "") for s in source]
fig = go.Figure(data=[go.Sankey(
    node=dict(label=labels, color=ch_color + tier_color, pad=15, thickness=18),
    link=dict(source=source, target=target, value=value,
              color=[f"rgba({int(c[0:2],16)},{int(c[2:4],16)},{int(c[4:6],16)},0.25)" for c in link_color]),
)]
)
fig.update_layout(margin=dict(l=8, r=16, t=16, b=8))
apply_theme(fig, height=360, show_legend=False)
st.plotly_chart(fig, config=chart_config(), width="stretch")

# ===== 全渠道协同方案(会员旅程) =====
st.subheader("🔄 全渠道协同方案")
st.caption("同一会员跨触点旅程示例(展示打通后的营销协同)")

journey = [
    ("1️⃣ 线上触达", "微信小程序推送新客券", P["cat_aqua"]),
    ("2️⃣ 线下核销", "到店消费出示券码,POS自动核销", P["cat_gold"]),
    ("3️⃣ 支付即会员", "支付时自动识别会员身份,积分回传", P["cat_orange"]),
    ("4️⃣ 数据沉淀", "统一ID关联本次行为,更新RFM分层", P["cat_violet"]),
    ("5️⃣ 精准复购", "基于分层个性化推送,跨触点协同", P["cat_blue"]),
]
journey_html = ""
for i, (step, desc, c) in enumerate(journey):
    arrow = '<span style="color:{0};font-size:1.2rem;margin:0 8px">→</span>'.format(P["text_muted"]) if i < len(journey) - 1 else ""
    journey_html += (
        f'<div style="background:{P["surface"]};border:1px solid {P["border"]};'
        f'border-left:3px solid {c};border-radius:8px;padding:10px 14px;margin:6px 0">'
        f'<div style="color:{c};font-size:0.9rem;font-weight:600;margin-bottom:4px">{step}</div>'
        f'<div style="color:{P["text_secondary"]};font-size:0.85rem">{desc}</div></div>'
    )
    if i < len(journey) - 1:
        journey_html += f'<div style="text-align:center;color:{P["text_muted"]};margin:2px 0">↓</div>'
st.markdown(journey_html, unsafe_allow_html=True)

# ===== 接口预留(对接万泰现有系统) =====
st.markdown("---")
st.subheader("🔌 系统对接方案(接口预留)")
st.caption("万泰数字化基础完善,本系统可对接现有 SaaS/OA/会员/财务系统")

st.dataframe(pd.DataFrame([
    {"万泰现有系统": "会员系统(SaaS)", "对接方式": "统一会员ID API 同步", "数据流": "会员注册/等级双向同步", "优先级": "P0"},
    {"万泰现有系统": "OA/财务系统", "对接方式": "收租/合同 webhook", "数据流": "租金状态回传财务", "优先级": "P0"},
    {"万泰现有系统": "门店 POS", "对接方式": "POS 销售数据接入", "数据流": "销售/核销回传", "优先级": "P1"},
    {"万泰现有系统": "客流系统", "对接方式": "IoT 数据中台", "数据流": "客流画像实时入仓", "优先级": "P1"},
    {"万泰现有系统": "购房/物业系统", "对接方式": "会员权益打通", "数据流": "跨业务权益联动", "优先级": "P2"},
]), width="stretch", hide_index=True)

st.info("💡 全渠道打通的核心是**统一会员ID**:会员在任一触点的行为都归集到同一ID下,营销不再割裂。"
        "本系统已实现ID体系与触点模型,对接万泰现有SaaS即可激活全渠道协同。")
