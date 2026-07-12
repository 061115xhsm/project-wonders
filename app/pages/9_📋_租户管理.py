"""租户管理 —— 合同到期提醒 + 收租进度 + 租售比预警 + AI 催租话术(痛点⑤)

解决万泰痛点:租户管理/合同管理繁琐,收租提醒靠人工。
- 合同到期看板(60天内到期 / 已逾期)
- 收租进度(已收/待收/逾期)
- 租售比预警(租金/销售额过高→经营压力大,红色预警)
- AI 催租话术(选逾期/待收商户,Agent 生成合规催缴话术)
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.utils import load_csv
from app.viz_theme import (
    apply_theme, chart_config, stat_card_html, kpi_grid_html, inject_global_css, mobile_notice_html, current_palette,
)
from app.agent import generate_rent_reminder
from app.llm_client import is_llm_ready

st.set_page_config(page_title="租户管理", layout="wide")
inject_global_css()
P = current_palette()
from app.date_filter import render_date_filter as _rdf
_rdf()  # 侧边栏时间段筛选器(每个页面都渲染,保证全页面可切换)

from app.config import DATA_TODAY
TODAY = pd.Timestamp(DATA_TODAY)


@st.cache_data(ttl=3600)
def load_data():
    return load_csv("shops_master.csv", "raw")


shops = load_data()
# 计算合同状态字段
shops = shops.copy()
shops["contract_end_ts"] = pd.to_datetime(shops["contract_end"], errors="coerce")
shops["days_to_end"] = (TODAY - shops["contract_end_ts"]).dt.days  # 正=已过期, 负=未来
shops["rent_sales_ratio"] = (shops["monthly_rent"] / shops["monthly_sales"]).round(3)

st.title("📋 租户管理")
st.markdown(mobile_notice_html(), unsafe_allow_html=True)
st.caption("ℹ️ 合同/收租为存量数据,不随时段筛选变化(基准日=今天) · 合同到期提醒 · 收租进度 · 租售比预警 · AI 催租话术")

# ===== KPI 行 =====
total = len(shops)
overdue = len(shops[shops["rent_status"] == "逾期"])
pending = len(shops[shops["rent_status"] == "待收"])
expiring_60 = len(shops[(shops["days_to_end"] < 0) & (shops["days_to_end"] > -60)])  # 60天内到期
collected_rent = shops.loc[shops["rent_status"] == "已收", "monthly_rent"].sum()
total_rent = shops["monthly_rent"].sum()
collection_rate = collected_rent / total_rent if total_rent else 0
high_ratio = len(shops[shops["rent_sales_ratio"] > 0.3])  # 租售比>30%预警

kpi = (
    stat_card_html("商铺总数", f"{total}", f"{shops['name'].nunique()} 个品牌", accent=P["cat_blue"])
    + stat_card_html("本月收租率", f"{collection_rate*100:.0f}%",
                     f"已收 ¥{collected_rent/1e4:,.0f}万 / 应收 ¥{total_rent/1e4:,.0f}万",
                     delta_good=collection_rate > 0.8, accent=P["cat_gold"])
    + stat_card_html("逾期/待收", f"{overdue+pending}",
                     f"逾期{overdue} · 待收{pending}", delta_good=False, accent=P["cat_red"])
    + stat_card_html("60天内到期", f"{expiring_60}", "需续约对接",
                     delta_good=expiring_60 < 5, accent=P["cat_orange"])
)
st.markdown(kpi_grid_html(kpi, cols=4), unsafe_allow_html=True)

# ===== 收租进度可视化 =====
st.subheader("💰 收租进度")
col1, col2 = st.columns([1, 2])

with col1:
    # 收租状态饼图(用条形更规范,但这里 part-to-whole 用甜甜圈展示进度更直观)
    status_counts = shops["rent_status"].value_counts().reindex(["已收", "待收", "逾期"]).fillna(0)
    fig1 = go.Figure()
    status_map = {"已收": P["good"], "待收": P["warning"], "逾期": P["critical"]}
    for s, cnt in zip(status_counts.index, status_counts.values):
        fig1.add_trace(go.Bar(
            x=[cnt], y=[s], orientation="h", name=s,
            marker_color=status_map.get(s, P["cat_blue"]), width=0.55,
            text=[f"{int(cnt)} 家"], textposition="outside",
            textfont=dict(color=P["text_secondary"], size=12),
            hovertemplate=f"{s}<br>%{{x}} 家<extra></extra>",
        ))
    fig1.update_layout(bargap=0.4, showlegend=False)
    fig1.update_xaxes(title_text="商铺数")
    apply_theme(fig1, height=260)
    st.plotly_chart(fig1, config=chart_config(), width="stretch")

with col2:
    # 各楼层收租率
    floor_rent = shops.groupby("floor").apply(
        lambda g: g.loc[g["rent_status"] == "已收", "monthly_rent"].sum() / g["monthly_rent"].sum() * 100
    ).round(0)
    fig2 = go.Figure()
    for f, rate in zip(floor_rent.index, floor_rent.values):
        c = P["good"] if rate >= 80 else (P["warning"] if rate >= 50 else P["critical"])
        fig2.add_trace(go.Bar(
            x=[f"{int(f)}F"], y=[rate], name=f"{int(f)}F",
            marker_color=c, width=0.55,
            text=[f"{rate:.0f}%"], textposition="outside",
            textfont=dict(color=P["text_secondary"], size=12),
            hovertemplate=f"{int(f)}F<br>收租率 %{{y:.0f}}%<extra></extra>",
        ))
    fig2.update_layout(bargap=0.4, showlegend=False)
    fig2.update_yaxes(title_text="收租率%", range=[0, 100])
    apply_theme(fig2, height=260)
    st.plotly_chart(fig2, config=chart_config(), width="stretch")

# ===== 合同到期提醒表 =====
st.subheader("📅 合同到期提醒")
st.caption("按到期日升序,60天内到期与已逾期需重点关注")

expiring = shops[shops["days_to_end"] > -60].copy()  # 未来60天内到期 + 已过期
expiring = expiring.sort_values("days_to_end")
expiring_display = expiring[["name", "floor", "category", "contract_start", "contract_end",
                              "days_to_end", "rent_status", "monthly_rent"]].copy()
expiring_display.columns = ["商铺", "楼层", "业态", "合同起始", "合同到期", "距今天数", "收租状态", "月租金"]
# 距今天数:正=已过期,负=未来;展示成更直观的
expiring_display["状态"] = expiring_display.apply(
    lambda r: "🟢 续约中" if r["收租状态"] == "已收" and r["距今天数"] > 0
    else ("🔴 逾期" if r["收租状态"] == "逾期" else "🟡 待收/临期"), axis=1)
expiring_display = expiring_display.drop(columns=["距今天数", "收租状态"])

st.dataframe(expiring_display, width="stretch", hide_index=True,
             column_config={
                 "月租金": st.column_config.NumberColumn("月租金", format="¥%,.0f"),
             })

# ===== 租售比预警 =====
st.subheader("⚠️ 租售比预警")
st.caption("租售比 = 月租金 / 月销售额,>30% 经营压力大,需营销扶持或租金谈判")
high_ratio_shops = shops[shops["rent_sales_ratio"] > 0.3].sort_values("rent_sales_ratio", ascending=False)
if len(high_ratio_shops):
    hr_display = high_ratio_shops[["name", "floor", "category", "monthly_rent", "monthly_sales", "rent_sales_ratio"]].copy()
    hr_display.columns = ["商铺", "楼层", "业态", "月租金", "月销售额", "租售比"]
    hr_display["租售比"] = hr_display["租售比"].map(lambda x: f"{x*100:.0f}%")
    st.dataframe(hr_display, width="stretch", hide_index=True,
                 column_config={
                     "月租金": st.column_config.NumberColumn("月租金", format="¥%,.0f"),
                     "月销售额": st.column_config.NumberColumn("月销售额", format="¥%,.0f"),
                 })
else:
    st.success("✅ 暂无租售比超 30% 的商铺")

# ===== AI 催租话术 =====
st.markdown("---")
st.subheader("🤖 AI 催租话术生成")
st.caption("选择逾期/待收商户,AI 生成合规、可直接发送的催缴话术")

# 选商户(仅逾期/待收)
candidates = shops[shops["rent_status"].isin(["逾期", "待收"])].copy()
if len(candidates) == 0:
    st.info("当前无逾期/待收商户,无需催租。")
else:
    candidates["label"] = candidates["name"] + " · " + candidates["floor"].astype(str) + "F · " + candidates["rent_status"]
    sel = st.selectbox("选择商户", options=candidates["label"].tolist())
    if sel:
        shop_row = candidates[candidates["label"] == sel].iloc[0]
        shop_info = {
            "name": shop_row["name"], "floor": int(shop_row["floor"]),
            "category": shop_row["category"], "monthly_rent": float(shop_row["monthly_rent"]),
            "rent_status": shop_row["rent_status"],
            "days_to_end": int(shop_row["days_to_end"]),
            "contract_end": str(shop_row["contract_end"]),
        }
        st.markdown(f'<div style="background:{P["surface"]};border:1px solid {P["border"]};'
                    f'border-radius:8px;padding:12px 16px;margin:10px 0">'
                    f'<span style="color:{P["text_muted"]};font-size:0.8rem">商户信息</span><br>'
                    f'<span style="color:{P["text_primary"]};font-weight:600">{shop_info["name"]}</span>'
                    f' <span style="color:{P["text_secondary"]};font-size:0.85rem">'
                    f'{shop_info["floor"]}F · {shop_info["category"]} · 月租 ¥{shop_info["monthly_rent"]:,.0f} · '
                    f'{shop_info["rent_status"]}</span></div>', unsafe_allow_html=True)

        if st.button("生成催租话术", type="primary", key="gen_rent"):
            with st.spinner("AI 生成合规催租话术中..." if is_llm_ready() else None):
                rent_result = generate_rent_reminder(shop_info, use_llm=is_llm_ready())
            msg = rent_result.get("text", "") if isinstance(rent_result, dict) else rent_result
            source = "AI 生成" if (isinstance(rent_result, dict) and "llm" in rent_result.get("_source", "")) else "规则兜底"
            st.session_state["last_rent_msg"] = msg
            st.session_state["last_rent_source"] = source
            st.session_state["last_rent_shop"] = shop_info["name"]
            st.markdown(f'<div style="background:linear-gradient(135deg, rgba(201,133,0,0.12), {P["surface"]});'
                        f'border:1px solid rgba(201,133,0,0.35);border-radius:10px;padding:14px 18px;margin:10px 0">'
                        f'<div style="color:{P["text_muted"]};font-size:0.72rem;margin-bottom:6px">催租话术 · {source}</div>'
                        f'<div style="color:{P["text_primary"]};font-size:0.95rem;line-height:1.6">{msg}</div>'
                        f'</div>', unsafe_allow_html=True)
            st.caption("⚠️ 合规提示:话术已遵守合同法,不含威胁/单方解约条款;发送前请核对欠费金额与期限。")

        # ===== 催租执行出口(复制 / 标记已发送 / 发送台账)=====
        if "last_rent_msg" in st.session_state and st.session_state.get("last_rent_shop") == shop_info["name"]:
            cur_msg = st.session_state["last_rent_msg"]
            cur_source = st.session_state.get("last_rent_source", "")
            st.markdown(f'<div style="background:linear-gradient(135deg, rgba(201,133,0,0.12), {P["surface"]});'
                        f'border:1px solid rgba(201,133,0,0.35);border-radius:10px;padding:14px 18px;margin:10px 0">'
                        f'<div style="color:{P["text_muted"]};font-size:0.72rem;margin-bottom:6px">催租话术 · {cur_source}</div>'
                        f'<div style="color:{P["text_primary"]};font-size:0.95rem;line-height:1.6">{cur_msg}</div>'
                        f'</div>', unsafe_allow_html=True)
            st.caption("⚠️ 合规提示:话术已遵守合同法,不含威胁/单方解约条款;发送前请核对欠费金额与期限。")

            st.markdown(f'<div style="color:{P["text_muted"]};font-size:0.8rem;margin:2px 0 6px">执行出口</div>',
                        unsafe_allow_html=True)
            ex_col1, ex_col2 = st.columns(2)
            with ex_col1:
                st.caption("📋 复制话术(点右上角复制按钮)")
                st.code(cur_msg, language="text")
            with ex_col2:
                st.caption("📨 标记为已发送")
                if st.button("标记已发送", key="mark_sent", help="记录到发送台账"):
                    st.session_state.setdefault("sent_reminders", []).append({
                        "shop": shop_info["name"],
                        "time": date.today().isoformat(),
                        "msg_summary": cur_msg[:30] + ("…" if len(cur_msg) > 30 else ""),
                        "paid": False,
                    })
                    st.toast(f"已标记 {shop_info['name']} 催租话术为已发送", icon="📨")

        # ===== 批量催租(可选增强)=====
        if len(candidates) > 1:
            st.markdown(f'<div style="color:{P["text_muted"]};font-size:0.8rem;margin:10px 0 4px">批量催租</div>',
                        unsafe_allow_html=True)
            if st.button("一键生成全部逾期商户话术", key="batch_gen", help="为所有逾期/待收商户生成话术"):
                st.session_state["batch_reminders"] = []
                prog = st.progress(0.0, text="批量生成中…")
                ready = is_llm_ready()
                for i, (_, row) in enumerate(candidates.iterrows()):
                    s_info = {
                        "name": row["name"], "floor": int(row["floor"]),
                        "category": row["category"], "monthly_rent": float(row["monthly_rent"]),
                        "rent_status": row["rent_status"],
                        "days_to_end": int(row["days_to_end"]),
                        "contract_end": str(row["contract_end"]),
                    }
                    r = generate_rent_reminder(s_info, use_llm=ready)
                    t = r.get("text", "") if isinstance(r, dict) else r
                    st.session_state["batch_reminders"].append({"shop": s_info["name"], "msg": t})
                    prog.progress((i + 1) / len(candidates), text=f"已生成 {i+1}/{len(candidates)}")
                st.toast(f"已为 {len(candidates)} 家商户生成催租话术", icon="✅")

# ===== 发送台账 =====
st.markdown("---")
st.subheader("📊 发送台账")
st.caption("已发送催租记录与回款标记")
sent = st.session_state.get("sent_reminders", [])
if not sent:
    st.info("暂无已发送催租记录。生成话术后点「标记已发送」即可入账。")
else:
    for i, rec in enumerate(sent):
        tag = "🟢 已回款" if rec["paid"] else "🟡 待回款"
        tag_color = P["good"] if rec["paid"] else P["warning"]
        st.markdown(f'<div style="background:{P["surface"]};border:1px solid {P["border"]};'
                    f'border-radius:8px;padding:10px 14px;margin:6px 0">'
                    f'<span style="color:{P["text_primary"]};font-weight:600">{rec["shop"]}</span>'
                    f' <span style="color:{tag_color};font-size:0.8rem">{tag}</span>'
                    f' <span style="color:{P["text_muted"]};font-size:0.75rem">{rec["time"]}</span><br>'
                    f'<span style="color:{P["text_secondary"]};font-size:0.85rem">{rec["msg_summary"]}</span>'
                    f'</div>', unsafe_allow_html=True)
        paid_key = f"paid_{i}"
        prev = st.session_state.get(paid_key, rec["paid"])
        if st.checkbox("已回款", value=prev, key=paid_key):
            if not rec["paid"]:
                rec["paid"] = True
                st.toast(f"{rec['shop']} 已标记回款", icon="🟢")
        else:
            if rec["paid"]:
                rec["paid"] = False
