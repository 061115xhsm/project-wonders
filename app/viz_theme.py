"""可视化主题层 —— 统一设计 token 与 Plotly 图表工厂,支持明暗双主题

依据 dataviz 方法论:颜色先算后用,标记规范固定,分类色按固定顺序分配。
调色板已用 validate_palette.js 在暗色 surface #1a1a19 上验证 PASS(CVD 8-12 floor band,
≥4 序列需配直接标签,调用方按此标注端点/极值)。

主题切换:通过 .streamlit/config.toml 定义 [theme.light]/[theme.dark],
用户在 Streamlit 右上角菜单切换;current_palette() 读 st.context.theme.type
动态返回对应 token,GLOBAL_CSS 与所有工厂函数随之响应。
"""
import plotly.graph_objects as go
import plotly.express as px

try:
    import streamlit as st
except Exception:  # 裸 import(非 Streamlit 运行时)
    st = None


# ===== 设计 token:暗色 =====
DARK_PALETTE = {
    # 表面
    "page_bg": "#0d0d0d",        # page plane
    "surface": "#1a1a19",        # chart surface / card
    "sidebar_bg": "#0d0d0d",
    "border": "rgba(255,255,255,0.10)",
    # 文字
    "text_primary": "#ffffff",
    "text_secondary": "#c3c2b7",
    "text_muted": "#898781",
    # 网格/轴
    "gridline": "#2c2c2a",       # 1px hairline
    "axis_line": "#383835",
    # 分类色(固定顺序,绝不循环)
    "cat_blue": "#3987e5",
    "cat_aqua": "#199e70",
    "cat_gold": "#c98500",
    "cat_green": "#008300",
    "cat_violet": "#9085e9",
    "cat_red": "#e66767",
    "cat_magenta": "#d55181",
    "cat_orange": "#d95926",
    # sequential 蓝(单一色相,浅=低,深=高)
    "seq": ["#1a1a19", "#104281", "#184f95", "#256abf", "#3987e5", "#6da7ec"],
    # 状态色
    "good": "#0ca30c",
    "warning": "#fab219",
    "critical": "#d03b3b",
}

# ===== 设计 token:亮色(白底金色专业风)=====
LIGHT_PALETTE = {
    # 表面
    "page_bg": "#f7f7f5",         # 暖白 page plane
    "surface": "#ffffff",         # 卡片/图表白底
    "sidebar_bg": "#f0efea",       # 侧边栏稍深暖白
    "border": "rgba(0,0,0,0.10)",
    # 文字
    "text_primary": "#1a1a1a",
    "text_secondary": "#4a4a4a",
    "text_muted": "#8a8a8a",
    # 网格/轴
    "gridline": "#e8e8e6",        # 1px hairline
    "axis_line": "#c8c8c6",
    # 分类色(亮色背景适配,略加深以保证对比度)
    "cat_blue": "#1f6feb",
    "cat_aqua": "#0a7d5a",
    "cat_gold": "#b87300",         # 金色主强调,白底可读
    "cat_green": "#1a7f37",
    "cat_violet": "#7250d8",
    "cat_red": "#cf222e",
    "cat_magenta": "#bf3989",
    "cat_orange": "#bc4a1c",
    # sequential 蓝(浅=低,深=高,白底版)
    "seq": ["#ffffff", "#dbeafe", "#a8c8f0", "#6da7ec", "#3987e5", "#1f6feb"],
    # 状态色
    "good": "#1a7f37",
    "warning": "#b88600",
    "critical": "#cf222e",
}

# 向后兼容:PALETTE 指向暗色(模块级常量供静态 import;运行时请用 current_palette())
PALETTE = DARK_PALETTE


def current_palette() -> dict:
    """运行时返回当前主题 token。读 st.context.theme.type;非 Streamlit 上下文返回暗色。"""
    if st is not None:
        try:
            if st.context.theme.type == "light":
                return LIGHT_PALETTE
        except Exception:
            pass
    return DARK_PALETTE


def current_theme_type() -> str:
    """当前主题类型 'light'/'dark'(供页面条件逻辑)"""
    if st is not None:
        try:
            return st.context.theme.type or "dark"
        except Exception:
            pass
    return "dark"


# 向后兼容 config.THEME(老页面 import 不致断链;运行时建议用 current_palette())
THEME = {
    "bg_color": DARK_PALETTE["page_bg"],
    "text_color": DARK_PALETTE["text_primary"],
    "accent_gold": DARK_PALETTE["cat_gold"],
    "accent_cyan": DARK_PALETTE["cat_blue"],
    "accent_green": DARK_PALETTE["cat_aqua"],
    "card_bg": DARK_PALETTE["surface"],
}


# 分类色固定顺序列表(按当前主题取)
def categorical_colors() -> list:
    p = current_palette()
    return [p["cat_blue"], p["cat_aqua"], p["cat_gold"], p["cat_green"],
            p["cat_violet"], p["cat_red"], p["cat_magenta"], p["cat_orange"]]


# 向后兼容静态常量(暗色默认)
CATEGORICAL = [DARK_PALETTE["cat_blue"], DARK_PALETTE["cat_aqua"], DARK_PALETTE["cat_gold"], DARK_PALETTE["cat_green"],
               DARK_PALETTE["cat_violet"], DARK_PALETTE["cat_red"], DARK_PALETTE["cat_magenta"], DARK_PALETTE["cat_orange"]]


# RFM 群体固定映射(颜色跟随实体,不跟随排名)
def segment_colors() -> dict:
    p = current_palette()
    return {
        "高价值": p["cat_gold"],
        "潜力": p["cat_blue"],
        "新客": p["cat_aqua"],
        "沉睡": p["cat_red"],
    }


# 向后兼容静态映射
SEGMENT_COLORS = {
    "高价值": DARK_PALETTE["cat_gold"],
    "潜力": DARK_PALETTE["cat_blue"],
    "新客": DARK_PALETTE["cat_aqua"],
    "沉睡": DARK_PALETTE["cat_red"],
}
SEGMENT_ORDER = ["高价值", "潜力", "新客", "沉睡"]


# 会员等级固定映射
def level_colors() -> dict:
    p = current_palette()
    return {
        "黑金": p["cat_gold"],
        "金卡": p["cat_orange"],
        "银卡": p["cat_blue"],
        "普通": p["text_muted"],
    }


LEVEL_COLORS = {
    "黑金": DARK_PALETTE["cat_gold"],
    "金卡": DARK_PALETTE["cat_orange"],
    "银卡": DARK_PALETTE["cat_blue"],
    "普通": DARK_PALETTE["text_muted"],
}


# Plotly 用的 sequential 色阶(单色相,从 surface 到亮色)
def seq_bluescale() -> list:
    p = current_palette()
    return [
        [0.0, p["surface"]],
        [0.2, "#104281" if p is DARK_PALETTE else "#dbeafe"],
        [0.4, "#184f95" if p is DARK_PALETTE else "#a8c8f0"],
        [0.6, "#256abf"],
        [0.8, "#3987e5"],
        [1.0, "#6da7ec" if p is DARK_PALETTE else "#1f6feb"],
    ]


def _hsl_to_rgb(h: float, s: float, l: float) -> str:
    """HSL→HEX。h=0~360, s=0~1, l=0~1"""
    import math
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2
    if h < 60:    r, g, b = c, x, 0
    elif h < 120: r, g, b = x, c, 0
    elif h < 180: r, g, b = 0, c, x
    elif h < 240: r, g, b = 0, x, c
    elif h < 300: r, g, b = x, 0, c
    else:         r, g, b = c, 0, x
    R = int((r + m) * 255 + 0.5)
    G = int((g + m) * 255 + 0.5)
    B = int((b + m) * 255 + 0.5)
    return f"#{R:02x}{G:02x}{B:02x}"


def chart_config() -> dict:
    """Plotly 图表 Streamlit config:桌面端滚轮缩放,手机端禁用触摸缩放(防误触过度缩放)。
    页面用法: st.plotly_chart(fig, config=chart_config(), width="stretch")"""
    return {
        "scrollZoom": False,         # 禁用滚轮/双指缩放(防手机误触过度缩放)
        "displayModeBar": True,      # 显示工具栏(需缩放时用按钮)
        "displaylogo": False,
        "responsive": True,          # 响应式宽度(手机自适应)
        "staticPlot": False,
    }


def mobile_notice_html() -> str:
    """手机端顶部提示条:仅≤768px显示,提示主要适配电脑端。桌面端不显示。"""
    return ('<div class="mobile-notice">💻 <strong>本系统主要适配电脑端</strong>'
            '·手机端图表已禁用缩放防误触,建议用电脑访问以获得最佳体验。</div>')


def heatmap_redblue_scale() -> list:
    """热力图专用:超平滑全色谱渐变(蓝→青→绿→黄→橙→红→粉),3000断点HSL插值。
    暗色模式:色相240→0(蓝→红→粉),饱和度0.85,明度0.25→0.75;
    亮色模式:色相240→0,饱和度0.90,明度0.75→0.40(深色高峰)。"""
    p = current_palette()
    N = 3000  # 超密断点,丝滑渐变
    scale = []
    for i in range(N + 1):
        t = i / N  # 0→1
        if p is LIGHT_PALETTE:
            hue = 240 * (1 - t)
            sat = 0.90
            light = 0.78 - 0.38 * t
        else:
            hue = 240 * (1 - t)
            sat = 0.85
            light = 0.22 + 0.52 * t
        scale.append([t, _hsl_to_rgb(hue, sat, light)])
    return scale



SEQ_BLUESCALE = [
    [0.0, DARK_PALETTE["surface"]],
    [0.2, "#104281"], [0.4, "#184f95"], [0.6, "#256abf"], [0.8, "#3987e5"], [1.0, "#6da7ec"],
]

# ===== 标记规范常量(dataviz marks-and-anatomy)=====
MARK_LINE_WIDTH = 2          # 线 2px
MARK_BAR_MAXWIDTH = 24       # 柱 ≤24px
MARK_MARKER_SIZE = 9         # marker ≥8px
MARK_RING_WIDTH = 2          # surface ring 2px
MARK_GAP = 2                 # 堆叠/相邻 mark 间 2px surface gap


def apply_theme(fig, height=400, show_legend=None):
    """统一注入当前主题(明/暗)。show_legend=None 时按 trace 数自动判定(≥2 显式,1 隐藏)。"""
    if show_legend is None:
        n_traces = len(getattr(fig, "data", []))
        show_legend = n_traces >= 2

    p = current_palette()
    fig.update_layout(
        paper_bgcolor=p["page_bg"],
        plot_bgcolor=p["surface"],
        font=dict(color=p["text_secondary"], family="system-ui, -apple-system, 'Segoe UI', sans-serif", size=13),
        height=height,
        margin=dict(l=8, r=16, t=16, b=8),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor=p["surface"],
            font_color=p["text_primary"],
            bordercolor=p["border"],
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color=p["text_secondary"], size=12),
            bgcolor="rgba(0,0,0,0)",
        ),
        showlegend=show_legend,
    )
    # 轴:弱化网格 + hairline
    fig.update_xaxes(
        gridcolor=p["gridline"], gridwidth=1, zeroline=False,
        linecolor=p["axis_line"], linewidth=1,
        tickfont=dict(color=p["text_muted"], size=11),
        title_font=dict(color=p["text_secondary"], size=12),
    )
    fig.update_yaxes(
        gridcolor=p["gridline"], gridwidth=1, zeroline=False,
        linecolor=p["axis_line"], linewidth=1,
        tickfont=dict(color=p["text_muted"], size=11),
        title_font=dict(color=p["text_secondary"], size=12),
    )
    return fig


# ===== 图表工厂 =====
def themed_line(x, y, name="", color=None, height=400, mode="lines"):
    """单/多序列折线。线 2px,marker≥8px 带 surface ring,端点直接标签由调用方加。"""
    fig = go.Figure()
    p = current_palette()
    c = color or p["cat_blue"]
    fig.add_trace(go.Scatter(
        x=x, y=y, name=name, mode=mode + "+markers" if "markers" not in mode else mode,
        line=dict(color=c, width=MARK_LINE_WIDTH, shape="spline", smoothing=0.3),
        marker=dict(size=MARK_MARKER_SIZE, color=c,
                    line=dict(color=p["surface"], width=MARK_RING_WIDTH)),
        hovertemplate="%{x}<br>%{y:,.0f}<extra>" + (name or "值") + "</extra>",
    ))
    return apply_theme(fig, height=height, show_legend=bool(name))


def themed_bar(x, y, name="", color=None, orientation="v", height=400,
               text=None, category_color_map=None):
    """柱/条形。柱≤24px,圆角端,直接标值(选择性,由 text 控制)。"""
    fig = go.Figure()
    p = current_palette()
    if category_color_map is not None:
        # 多序列按实体上色(颜色跟随实体)
        for xi, yi in zip(x, y):
            c = category_color_map.get(xi, p["cat_blue"])
            fig.add_trace(go.Bar(
                x=[xi], y=[yi], name=str(xi),
                orientation=("h" if orientation == "h" else "v"),
                marker_color=c,
                width=0.6,
                text=[f"{yi:,.0f}"], textposition="outside",
                textfont=dict(color=p["text_secondary"], size=12),
                hovertemplate=f"{xi}<br>%{{y:,.0f}}<extra></extra>",
            ))
    else:
        c = color or p["cat_blue"]
        if orientation == "h":
            fig.add_trace(go.Bar(
                y=list(x), x=list(y), name=name, orientation="h",
                marker_color=c, width=0.6,
                text=text or [f"{v:,.0f}" for v in y], textposition="outside",
                textfont=dict(color=p["text_secondary"], size=12),
                hovertemplate="%{y}<br>%{x:,.0f}<extra></extra>",
            ))
        else:
            fig.add_trace(go.Bar(
                x=list(x), y=list(y), name=name, orientation="v",
                marker_color=c, width=0.6,
                text=text or [f"{v:,.0f}" for v in y], textposition="outside",
                textfont=dict(color=PALETTE["text_secondary"], size=12),
                hovertemplate="%{x}<br>%{y:,.0f}<extra></extra>",
            ))
    # 限制柱宽
    fig.update_traces(marker_line_width=0)
    if orientation == "v":
        fig.update_layout(bargap=0.4)
    else:
        fig.update_layout(bargap=0.4)
    return apply_theme(fig, height=height, show_legend=category_color_map is not None)


def themed_heatmap(z, x, y, height=420):
    """热力图:红蓝渐变(蓝=低客流,红=高峰),冷暖对比直观。"""
    p = current_palette()
    fig = go.Figure(data=go.Heatmap(
        z=z, x=x, y=y,
        colorscale=heatmap_redblue_scale(),
        showscale=True,
        colorbar=dict(
            tickfont=dict(color=p["text_muted"], size=11),
            outlinecolor=p["border"], outlinewidth=1,
            len=0.85,
        ),
        hovertemplate="%{y} %{x}<br>客流: %{z:,.0f}<extra></extra>",
        xgap=2, ygap=2,  # 2px surface gap
    ))
    fig.update_layout(
        xaxis=dict(side="bottom", tickfont=dict(color=p["text_muted"], size=10)),
        yaxis=dict(tickfont=dict(color=p["text_muted"], size=10)),
    )
    return apply_theme(fig, height=height, show_legend=False)


def themed_scatter(x, y, color_by, df, hover_name=None, size=None, height=420,
                   color_map=None):
    """散点:marker≥8px + 2px surface ring,分类色固定映射。"""
    p = current_palette()
    fig = px.scatter(
        df, x=x, y=y, color=color_by, size=size, hover_name=hover_name,
        color_discrete_map=color_map, color_discrete_sequence=categorical_colors(),
    )
    fig.update_traces(
        marker=dict(size=MARK_MARKER_SIZE, opacity=0.85,
                    line=dict(color=p["surface"], width=MARK_RING_WIDTH)),
        selector=dict(mode="markers"),
    )
    return apply_theme(fig, height=height, show_legend=True)


def themed_polar(r_theta_list, height=420):
    """雷达图:list of (name, r_list_with_close, theta_list_with_close, color)。
    固定分类色 + 2px surface ring 分离重叠。"""
    p = current_palette()
    fig = go.Figure()
    for i, (name, r, theta, color) in enumerate(r_theta_list):
        fig.add_trace(go.Scatterpolar(
            r=r, theta=theta, name=name, fill="toself", opacity=0.55,
            line=dict(color=color, width=MARK_LINE_WIDTH),
        ))
    fig.update_layout(
        polar=dict(
            bgcolor=p["surface"],
            radialaxis=dict(gridcolor=p["gridline"], gridwidth=1,
                            tickfont=dict(color=p["text_muted"], size=10),
                            linecolor=p["axis_line"]),
            angularaxis=dict(gridcolor=p["gridline"], gridwidth=1,
                             tickfont=dict(color=p["text_muted"], size=10),
                             linecolor=p["axis_line"]),
        ),
    )
    return apply_theme(fig, height=height, show_legend=True)


# ===== 卡片 / KPI =====
def stat_card_html(label, value, delta=None, delta_good=True, accent=None, subtitle=None):
    """单个 stat tile:背景 surface、左侧 4px 强调色条、tabular-nums、delta 状态色。
    返回紧凑单行 HTML —— 避免 st.markdown(unsafe_allow_html) 把多块 HTML 误判为代码块。"""
    p = current_palette()
    accent = accent or p["cat_blue"]
    parts = [f'<div class="kpi-card" style="border-left:4px solid {accent}">',
             f'<div class="kpi-label">{label}</div>',
             f'<div class="kpi-value">{value}</div>']
    if delta is not None:
        dc = p["good"] if delta_good else p["critical"]
        parts.append(f'<div class="kpi-delta" style="color:{dc}">{delta}</div>')
    if subtitle is not None:
        parts.append(f'<div class="kpi-sub">{subtitle}</div>')
    parts.append("</div>")
    return "".join(parts)


def hero_figure_html(label, value, subtitle=None, accent=None):
    """Hero figure:单个主指标 ≥48px。紧凑单行 HTML。"""
    p = current_palette()
    accent = accent or p["cat_gold"]
    parts = [f'<div class="hero-card" style="border-left:4px solid {accent}">',
             f'<div class="hero-label">{label}</div>',
             f'<div class="hero-value">{value}</div>']
    if subtitle is not None:
        parts.append(f'<div class="hero-sub">{subtitle}</div>')
    parts.append("</div>")
    return "".join(parts)


def kpi_grid_html(cards_html, cols=4):
    """把多个 stat_card_html 排成网格。cards_html 可为单卡 HTML 字符串或字符串列表。
    列数用 class(kpi-grid-N),CSS 媒体查询在手机端覆盖为 1-2 列。"""
    if isinstance(cards_html, (list, tuple)):
        cards = "".join(cards_html)
    else:
        cards = cards_html
    return f'<div class="kpi-grid kpi-grid-{cols}">{cards}</div>'


# 全局 CSS(注入 main.py 一次,所有页面共享)
def build_global_css():
    """构建全局 CSS,使用当前主题 token(明/暗动态)。"""
    p = current_palette()
    return f"""
    <style>
        html, body, .stApp, [data-testid="stAppViewContainer"],
        [data-testid="stMain"], [data-testid="stSidebarUserContent"],
        .stAppViewMain, .block-container {{
            background-color: {p['page_bg']};
            color: {p['text_primary']};
            font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;
        }}
        /* 顶部 header 装饰条强制深色 */
        [data-testid="stHeader"], [data-testid="stHeaderContainer"],
        header[data-testid="stHeader"] {{
            background-color: {p['page_bg']} !important;
        }}
        [data-testid="stToolbar"] {{ background: transparent !important; }}
        /* 主内容区背景 */
        .stAppViewMain, section[data-testid="stMain"] {{
            background-color: {p['page_bg']};
        }}
        /* 侧边栏 */
        section[data-testid="stSidebar"], [data-testid="stSidebar"] {{
            background-color: {p['sidebar_bg']};
            border-right: 1px solid {p['border']};
        }}
        section[data-testid="stSidebar"] .stMarkdown, section[data-testid="stSidebar"] h1 {{
            color: {p['text_primary']};
        }}
        /* 标题 */
        h1, h2, h3, h4 {{
            color: {p['text_primary']} !important;
            font-weight: 600 !important;
        }}
        h1 {{ border-bottom: 1px solid {p['border']}; padding-bottom: 8px; }}
        /* 默认 metric 弱化(用自定义卡片替代) */
        .stMetric {{
            background-color: {p['surface']};
            border-radius: 10px;
            padding: 14px 16px;
            border: 1px solid {p['border']};
        }}
        /* 卡片网格 */
        .kpi-grid {{
            display: grid;
            gap: 12px;
            margin: 12px 0 20px 0;
        }}
        .kpi-grid-4 {{ grid-template-columns: repeat(4, 1fr); }}
        .kpi-grid-3 {{ grid-template-columns: repeat(3, 1fr); }}
        .kpi-grid-2 {{ grid-template-columns: repeat(2, 1fr); }}
        .kpi-card {{
            background-color: {p['surface']};
            border: 1px solid {p['border']};
            border-radius: 10px;
            padding: 14px 16px;
        }}
        .kpi-label {{ color: {p['text_secondary']}; font-size: 0.82rem; margin-bottom: 6px; }}
        .kpi-value {{
            color: {p['text_primary']}; font-size: 1.7rem; font-weight: 700;
            font-variant-numeric: tabular-nums; line-height: 1.1;
        }}
        .kpi-delta {{ font-size: 0.8rem; margin-top: 6px; font-variant-numeric: tabular-nums; }}
        .kpi-sub {{ color: {p['text_muted']}; font-size: 0.75rem; margin-top: 4px; }}
        /* Hero */
        .hero-card {{
            background: linear-gradient(135deg, {p['surface']}, {p['page_bg']});
            border: 1px solid {p['border']};
            border-radius: 12px;
            padding: 20px 24px;
            margin: 12px 0 20px 0;
        }}
        .hero-label {{ color: {p['text_secondary']}; font-size: 0.9rem; margin-bottom: 6px; }}
        .hero-value {{
            color: {p['text_primary']}; font-size: 2.6rem; font-weight: 800;
            font-variant-numeric: tabular-nums; line-height: 1.1;
        }}
        .hero-sub {{ color: {p['text_muted']}; font-size: 0.85rem; margin-top: 8px; }}
        /* 策略卡片 */
        .strategy-card {{
            background-color: {p['surface']};
            border: 1px solid {p['border']};
            border-radius: 10px;
            padding: 12px 16px;
            margin: 8px 0;
            display: flex;
            align-items: flex-start;
            gap: 12px;
        }}
        .strategy-bullet {{
            width: 8px; height: 8px; border-radius: 50%;
            margin-top: 7px; flex-shrink: 0;
        }}
        .strategy-text {{ color: {p['text_secondary']}; font-size: 0.95rem; line-height: 1.5; }}
        /* 数据表 */
        .stDataFrame {{ border: 1px solid {p['border']}; border-radius: 8px; overflow: hidden; }}
        /* 隐藏页脚 */
        footer {{ visibility: hidden; }}
        /* 信息框弱化 */
        .stAlert {{ border-radius: 8px; }}
        /* 分隔线 */
        hr {{
            border-color: {p['border']} !important;
            margin: 18px 0 !important;
        }}
        /* ===== 品牌头部 ===== */
        .brand-header {{
            display: flex; align-items: center; gap: 14px;
            padding: 4px 0 12px 0;
            border-bottom: 1px solid {p['border']};
            margin-bottom: 18px;
        }}
        .brand-logo {{
            width: 44px; height: 44px; border-radius: 10px;
            background: linear-gradient(135deg, {p['cat_gold']}, {p['cat_orange']});
            display: flex; align-items: center; justify-content: center;
            font-size: 1.4rem; font-weight: 800; color: #1a1a19;
            flex-shrink: 0;
        }}
        .brand-title {{ font-size: 1.15rem; font-weight: 700; color: {p['text_primary']}; line-height: 1.2; }}
        .brand-sub {{ font-size: 0.78rem; color: {p['text_muted']}; margin-top: 2px; }}
        /* ===== AI 洞察条(首页日报) ===== */
        .insight-row {{ display: flex; flex-direction: column; gap: 8px; margin: 12px 0; }}
        .insight-card {{
            background-color: {p['surface']};
            border: 1px solid {p['border']};
            border-left: 3px solid {p['cat_gold']};
            border-radius: 8px;
            padding: 10px 14px;
            display: flex; align-items: flex-start; gap: 10px;
        }}
        .insight-icon {{ flex-shrink: 0; font-size: 1rem; }}
        .insight-text {{ color: {p['text_secondary']}; font-size: 0.9rem; line-height: 1.5; }}
        /* ===== 营销方案分块卡片(Agent 输出) ===== */
        .plan-section {{ margin: 14px 0; }}
        .plan-section-title {{
            font-size: 0.82rem; color: {p['text_muted']};
            text-transform: uppercase; letter-spacing: 0.5px;
            margin-bottom: 8px; font-weight: 600;
        }}
        .strategy-list {{ display: flex; flex-direction: column; gap: 10px; }}
        .strategy-item {{
            background-color: {p['surface']};
            border: 1px solid {p['border']};
            border-radius: 10px; padding: 12px 16px;
        }}
        .strategy-item-title {{ font-size: 0.95rem; font-weight: 600; color: {p['text_primary']}; margin-bottom: 4px; }}
        .strategy-item-desc {{ font-size: 0.85rem; color: {p['text_secondary']}; line-height: 1.5; }}
        .strategy-chips {{ margin-top: 8px; display: flex; gap: 6px; flex-wrap: wrap; }}
        .chip {{
            font-size: 0.7rem; padding: 2px 8px; border-radius: 10px;
            background-color: rgba(57,135,229,0.15); color: {p['cat_blue']};
            border: 1px solid rgba(57,135,229,0.3);
        }}
        /* 投放话术卡(高亮) */
        .copy-card {{
            background: linear-gradient(135deg, rgba(201,133,0,0.12), {p['surface']});
            border: 1px solid rgba(201,133,0,0.35);
            border-radius: 10px; padding: 14px 18px; margin: 10px 0;
            font-size: 0.95rem; line-height: 1.6; color: {p['text_primary']};
        }}
        /* ROI 网格 */
        .roi-grid {{ display: grid; grid-template-columns: repeat(4,1fr); gap: 10px; margin: 10px 0; }}
        .roi-tile {{
            background-color: {p['surface']}; border: 1px solid {p['border']};
            border-radius: 8px; padding: 10px 12px; text-align: center;
        }}
        .roi-label {{ font-size: 0.72rem; color: {p['text_muted']}; margin-bottom: 4px; }}
        .roi-value {{ font-size: 1.15rem; font-weight: 700; color: {p['text_primary']}; font-variant-numeric: tabular-nums; }}
        .roi-value.good {{ color: {p['good']}; }}
        /* AI 标记(标识来源) */
        .ai-badge {{
            display: inline-block; font-size: 0.68rem; padding: 2px 8px;
            border-radius: 4px; background-color: rgba(144,133,233,0.18);
            color: {p['cat_violet']}; border: 1px solid rgba(144,133,233,0.35);
            margin-left: 8px; vertical-align: middle;
        }}
        .ai-badge.fallback {{ background-color: rgba(137,135,129,0.18); color: {p['text_muted']}; border-color: {p['border']}; }}
        /* 选品卡 */
        .product-item {{
            background-color: {p['surface']}; border: 1px solid {p['border']};
            border-radius: 8px; padding: 10px 14px; margin: 6px 0;
            display: flex; gap: 10px; align-items: flex-start;
        }}
        .product-shop {{ font-weight: 600; color: {p['cat_gold']}; flex-shrink: 0; min-width: 90px; }}
        .product-reason {{ font-size: 0.85rem; color: {p['text_secondary']}; line-height: 1.5; }}
        /* 楼层商铺标签云 */
        .shop-tags {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0 14px 0; }}
        .shop-tag {{
            font-size: 0.78rem; padding: 3px 10px; border-radius: 12px;
            background-color: {p['surface']}; color: {p['text_secondary']};
            border: 1px solid {p['border']};
        }}
        .shop-tag.anchor {{ border-color: {p['cat_gold']}; color: {p['cat_gold']}; }}

        /* ===== 移动端适配 ===== */
        /* viewport: 禁止双指缩放 + 双击缩放,防误触 */
        @-webkit-viewport {{ width: device-width; user-zoom: fixed; zoom: 1; }}
        @viewport {{ width: device-width; user-zoom: fixed; zoom: 1; }}

        /* 全局:禁用文本长按选择(防误触弹出菜单)+ 禁用双击缩放 + 禁双指 */
        body, .stApp {{
            -webkit-touch-callout: none !important;
            -webkit-user-select: none !important;
            user-select: none !important;
            -webkit-text-size-adjust: 100% !important;
            touch-action: pan-y !important;  /* 只允许纵向滚动,禁双指缩放/双击缩放 */
            overscroll-behavior: none !important;
        }}
        /* 输入框/文本区域恢复选择(否则没法编辑) */
        input, textarea, [contenteditable] {{
            -webkit-user-select: text !important;
            user-select: text !important;
        }}

        /* Plotly 图表:仅允许垂直滚动(pan-y),禁止双指缩放防误触 */
        .js-plotly-plot, .js-plotly-plot .plotly, .js-plotly-plot .plotly .svg-container,
        .js-plotly-plot .modebar {{
            touch-action: pan-y !important;
        }}
        /* 隐藏 Plotly 工具条(手机端点了容易误触缩放/下载) */
        .js-plotly-plot .modebar {{ display: none !important; }}
        .plotly-notifier {{ display: none !important; }}

        /* 按钮:增大点击热区,防误触 */
        .stButton > button, button[kind="primary"] {{
            min-height: 44px !important;
            touch-action: manipulation !important;
        }}

        /* 手机端顶部提示条(仅≤768px显示) */
        .mobile-notice {{
            display: none;
        }}
        @media (max-width: 768px) {{
            .mobile-notice {{
                display: block !important;
                background: {p['surface']};
                border: 1px solid {p['cat_gold']};
                border-left: 4px solid {p['cat_gold']};
                border-radius: 8px;
                padding: 10px 14px;
                margin: 8px 0 16px 0;
                font-size: 0.82rem;
                color: {p['text_secondary']};
                line-height: 1.5;
            }}
            .mobile-notice strong {{ color: {p['cat_gold']}; }}
        }}

        /* 手机端(≤768px):单列布局 + 放大可读性 */
        @media (max-width: 768px) {{
            .kpi-grid-4, .kpi-grid-3 {{ grid-template-columns: repeat(2, 1fr) !important; }}
            .kpi-grid-2 {{ grid-template-columns: repeat(2, 1fr) !important; }}
            .kpi-card {{ padding: 12px 14px; }}
            .kpi-value {{ font-size: 1.4rem; }}
            .kpi-label {{ font-size: 0.78rem; }}
            .hero-card {{ padding: 16px 18px; }}
            .hero-value {{ font-size: 2rem; }}
            .roi-grid {{ grid-template-columns: repeat(2, 1fr) !important; }}
            .strategy-item, .product-item, .insight-card, .copy-card {{ padding: 10px 12px; }}
            /* 主内容区减少边距,手机屏更宽 */
            .block-container {{ padding-top: 1rem !important; padding-bottom: 1rem !important; }}
            /* 楼层商铺标签云手机端更紧凑 */
            .shop-tag {{ font-size: 0.72rem; padding: 2px 8px; }}
        }}

        /* 小屏手机(≤480px):KPI 单列 */
        @media (max-width: 480px) {{
            .kpi-grid-4, .kpi-grid-3, .kpi-grid-2 {{ grid-template-columns: 1fr !important; }}
            .roi-grid {{ grid-template-columns: repeat(2, 1fr) !important; }}
        }}
    </style>
    """


# 向后兼容:模块级 GLOBAL_CSS(求值于暗色;运行时请用 build_global_css() 注入当前主题)
GLOBAL_CSS = build_global_css()

def inject_global_css():
    """在每个页面开头注入全局暗色主题 CSS(供子页面调用,确保多页面会话下样式一致)。

    同时注入移动端防误触/防缩放 JS(__noZoomBound 守卫,重复调用安全)。
    """
    import streamlit as st
    st.markdown(build_global_css(), unsafe_allow_html=True)
    st.markdown(_ANTI_ZOOM_JS, unsafe_allow_html=True)


# 移动端防误触JS:阻止双指缩放(gesturestart)+ 双击缩放 + 多指触摸
# iOS Safari 的 CSS user-zoom:fixed 不完全可靠,需 JS 兜底;__noZoomBound 守卫防重复绑定
_ANTI_ZOOM_JS = """
<script>
(function(){
  if (window.__noZoomBound) return; window.__noZoomBound = true;
  var LOCK = 'width=device-width, initial-scale=1, maximum-scale=1, minimum-scale=1, user-scalable=no, viewport-fit=cover';
  // 持续锁定 viewport meta(Streamlit/浏览器可能重置)
  function lockMeta(){
    var meta = document.querySelector('meta[name="viewport"]');
    if (meta && meta.getAttribute('content') !== LOCK) {
      meta.setAttribute('content', LOCK);
    }
  }
  lockMeta();
  // 监听 meta 变化,被改回立即再锁
  var mo = new MutationObserver(lockMeta);
  if (document.querySelector('meta[name="viewport"]')) {
    mo.observe(document.querySelector('meta[name="viewport"]'), {attributes:true, attributeFilter:['content']});
  }
  // DOM 加载后再次确保(覆盖 Streamlit 后注入的 meta)
  document.addEventListener('DOMContentLoaded', lockMeta);
  // 阻止双指缩放手势(iOS)
  ['gesturestart','gesturechange','gestureend'].forEach(function(ev){
    document.addEventListener(ev, function(e){ e.preventDefault(); }, {passive:false});
  });
  // 阻止双击缩放(350ms内二次touchend)
  var lastTouchEnd = 0;
  document.addEventListener('touchend', function(e){
    var now = Date.now();
    if (now - lastTouchEnd <= 350) { e.preventDefault(); }
    lastTouchEnd = now;
  }, {passive:false});
  // 阻止双指 touchmove(安卓绕过 gesture 事件)
  document.addEventListener('touchmove', function(e){
    if (e.touches && e.touches.length > 1) { e.preventDefault(); }
  }, {passive:false});
  // 阻止 wheel+ctrl 缩放(桌面/部分浏览器)
  document.addEventListener('wheel', function(e){
    if (e.ctrlKey) { e.preventDefault(); }
  }, {passive:false});
  // 阻止键盘缩放快捷键
  document.addEventListener('keydown', function(e){
    if ((e.ctrlKey||e.metaKey) && ['=','-','+','0'].indexOf(e.key)>=0) { e.preventDefault(); }
  }, {passive:false});
})();
</script>
"""


# ===== 品牌头部 =====
def brand_header_html(title: str, subtitle: str = "", logo_char: str = "万") -> str:
    """品牌头部:渐变 logo + 标题 + 副标题"""
    parts = [
        f'<div class="brand-header">',
        f'<div class="brand-logo">{logo_char}</div>',
        f'<div><div class="brand-title">{title}</div>',
    ]
    if subtitle:
        parts.append(f'<div class="brand-sub">{subtitle}</div>')
    parts.append('</div></div>')
    return "".join(parts)


def ai_badge_html(source: str) -> str:
    """AI 来源标记(llm:xxx→AI生成,fallback→规则兜底)"""
    is_llm = "llm" in source.lower()
    label = "AI 生成" if is_llm else "规则兜底"
    cls = "" if is_llm else " fallback"
    return f'<span class="ai-badge{cls}">{label}</span>'


# ===== AI 洞察条(首页日报) =====
def insights_html(insights: list, title: str = "AI 运营日报", source: str = "llm") -> str:
    """首页 AI 运营日报:多条洞察卡。source 透传 ai_badge_html 判定来源。"""
    if not insights:
        return ""
    items = []
    for i, txt in enumerate(insights):
        icon = ["💡", "📈", "🎯"][i % 3]
        items.append(f'<div class="insight-card"><div class="insight-icon">{icon}</div>'
                     f'<div class="insight-text">{txt}</div></div>')
    body = "".join(items)
    badge = ai_badge_html(source)
    return (f'<div class="plan-section">'
            f'<div class="plan-section-title">{title}{badge}</div>'
            f'<div class="insight-row">{body}</div></div>')


# ===== 营销方案渲染(Agent 输出) =====
def marketing_plan_html(plan: dict) -> str:
    """把 Agent 返回的结构化方案渲染为分块卡片"""
    parts = []

    # 目标
    obj = plan.get("objective", "")
    if obj:
        parts.append(f'<div class="plan-section"><div class="plan-section-title">营销目标</div>'
                     f'<div class="copy-card">{obj}</div></div>')

    # 策略
    strategies = plan.get("strategies", [])
    if strategies:
        items = []
        for s in strategies:
            ch = "".join(f'<span class="chip">{c}</span>' for c in s.get("channels", []))
            items.append(
                f'<div class="strategy-item">'
                f'<div class="strategy-item-title">{s.get("title","")}</div>'
                f'<div class="strategy-item-desc">{s.get("desc","")}</div>'
                f'<div class="strategy-chips">{ch}</div></div>'
            )
        parts.append(f'<div class="plan-section"><div class="plan-section-title">策略方案</div>'
                     f'<div class="strategy-list">{"".join(items)}</div></div>')

    # 选品
    products = plan.get("products", [])
    if products:
        items = []
        for p in products:
            items.append(
                f'<div class="product-item"><div class="product-shop">{p.get("shop","")}</div>'
                f'<div class="product-reason">{p.get("reason","")}</div></div>'
            )
        parts.append(f'<div class="plan-section"><div class="plan-section-title">联动商户推荐</div>'
                     f'{"".join(items)}</div>')

    # 投放话术
    copy = plan.get("copywriting", "")
    if copy:
        parts.append(f'<div class="plan-section"><div class="plan-section-title">投放话术</div>'
                     f'<div class="copy-card">{copy}</div></div>')

    # ROI
    roi = plan.get("roi", {})
    if roi:
        def _tile(label, val, cls=""):
            return (f'<div class="roi-tile"><div class="roi-label">{label}</div>'
                    f'<div class="roi-value{cls}">{val}</div></div>')
        ratio_cls = " good" if isinstance(roi.get("roi_ratio"), (int, float)) and roi["roi_ratio"] >= 3 else ""
        grid = (
            _tile("触达人数", f"{roi.get('target_count',0):,}")
            + _tile("转化率", f"{roi.get('conversion_rate',0)}%")
            + _tile("增量营收", f"¥{roi.get('est_revenue',0):,}")
            + _tile("ROI", f"{roi.get('roi_ratio',0)}x", ratio_cls)
        )
        parts.append(f'<div class="plan-section"><div class="plan-section-title">效果预估</div>'
                     f'<div class="roi-grid">{grid}</div></div>')

    # 合规
    comp = plan.get("compliance_note", "")
    if comp:
        parts.append(f'<div class="plan-section"><div class="plan-section-title">合规提示</div>'
                     f'<div class="insight-text">⚠️ {comp}</div></div>')

    # 来源标记
    src = plan.get("_source", "")
    if src:
        parts.append(f'<div style="text-align:right;margin-top:6px">{ai_badge_html(src)}</div>')

    return "".join(parts)


# ===== 商铺标签云(楼层页) =====
def shop_tags_html(shops: list, anchor_names: set = None) -> str:
    """商铺标签云:shops=[name,...],主力店高亮金色"""
    anchor_names = anchor_names or set()
    tags = []
    for name in shops:
        cls = " anchor" if name in anchor_names else ""
        tags.append(f'<span class="shop-tag{cls}">{name}</span>')
    return f'<div class="shop-tags">{"".join(tags)}</div>'
