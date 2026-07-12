"""时间段筛选 —— 侧边栏全局日期范围的统一读取与过滤

所有页面通过 filter_by_date(df, date_col) 应用筛选,避免每页各写一套。
商铺/租户等无时间维度的数据,过滤函数原样返回(无副作用)。

筛选范围来源:st.session_state["global_date_range"] = (start_date, end_date)
由 render_date_filter() 写入(每个页面侧边栏调用,保证全页面可见)。
未设置时默认近7天(基于 DATA_END)。
"""
import datetime as _dt
import pandas as pd
import streamlit as st

from app.config import DATA_END, DATA_TODAY

_DEFAULT_DAYS = 7  # 默认近7天


def render_date_filter():
    """在侧边栏渲染日期筛选器(快捷按钮 + 日期选择器)。

    每个页面调用一次即可,内容自动进入左侧侧边栏,
    确保用户在任何页面都能切换时间段。
    """
    _today = pd.Timestamp(DATA_END).date()
    _presets = [
        ("今天", _today, _today),
        ("近7天", _today - _dt.timedelta(days=6), _today),
        ("近30天", _today - _dt.timedelta(days=29), _today),
        ("本月", _today.replace(day=1), _today),
        ("全部", pd.Timestamp("2025-07-12").date(), _today),
    ]
    with st.sidebar:
        st.markdown("**📊 时间段筛选**")
        cols = st.columns(len(_presets))
        for col, (label, s, e) in zip(cols, _presets):
            if col.button(label, key=f"preset_{label}", use_container_width=True):
                st.session_state.global_date_range = (s, e)
                st.rerun()

        if "global_date_range" not in st.session_state:
            st.session_state.global_date_range = (_today - _dt.timedelta(days=6), _today)
        st.date_input("日期范围", key="global_date_range")
        st.caption("切换后本页数据自动重算")


def get_date_range() -> tuple:
    """返回 (start, end) pd.Timestamp。优先读 session_state,无则默认近7天。

    每次页面重跑都重新读取,使侧边栏改动立即生效。
    """
    dr = st.session_state.get("global_date_range")
    if dr is None or len(dr) != 2:
        end = pd.Timestamp(DATA_END)
        return end - pd.Timedelta(days=_DEFAULT_DAYS - 1), end
    start, end = dr
    return pd.Timestamp(start), pd.Timestamp(end)


def date_range_key() -> str:
    """缓存 key:把日期范围序列化成字符串,供 @st.cache_data 函数作参数。
    换日期 → key 变 → 触发重算。
    """
    s, e = get_date_range()
    return f"{s.date()}_{e.date()}"


def filter_by_date(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    """按全局日期范围过滤 df。

    df 无 date_col 列 → 原样返回(商铺/租户等无时间维度数据安全)。
    日期列解析失败 → 原样返回(不阻断页面)。
    范围内无数据 → 原样返回(由调用方决定空态展示,避免页面崩)。
    """
    if df is None or len(df) == 0 or date_col not in df.columns:
        return df
    start, end = get_date_range()
    dt = pd.to_datetime(df[date_col], errors="coerce")
    mask = (dt >= start) & (dt <= end)
    filtered = df[mask]
    # 空结果回退全量(保证页面不崩;调用方可另行提示)
    return filtered if len(filtered) else df


def filter_traffic(traffic: pd.DataFrame) -> pd.DataFrame:
    """客流:按 date 列过滤。"""
    return filter_by_date(traffic, "date")


def filter_members(members: pd.DataFrame) -> pd.DataFrame:
    """会员:按 last_visit_date 过滤(近期到店的会员)。"""
    return filter_by_date(members, "last_visit_date")


def filter_consultations(cons: pd.DataFrame) -> pd.DataFrame:
    """咨询:按 date 列过滤。"""
    return filter_by_date(cons, "date")
