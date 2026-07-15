import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

_PALETTE = {"blue":"#3b82f6","green":"#10b981","orange":"#f59e0b","red":"#ef4444","purple":"#8b5cf6"}

def _pct(x): return f"{x*100:.2f}%"
def _wan(x): return f"{x/10000:.2f}万"

def fig_overview(b) -> go.Figure:
    ov = b.overview
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=["本周"], y=[ov["销售金额"]], name="销售额",
                         text=[_wan(ov["销售金额"])], textposition="outside",
                         marker_color=_PALETTE["blue"]), secondary_y=False)
    fig.add_trace(go.Bar(x=["本周"], y=[ov["销售毛利"]], name="销售毛利",
                         text=[_wan(ov["销售毛利"])], textposition="outside",
                         marker_color=_PALETTE["green"]), secondary_y=False)
    fig.add_trace(go.Scatter(x=["本周"], y=[ov["销售毛利率"]], name="销售毛利率",
                             text=[_pct(ov["销售毛利率"])], textposition="top center",
                             mode="lines+markers+text", line=dict(color=_PALETTE["red"], width=3)),
                  secondary_y=True)
    fig.update_layout(title="本周销售概况", barmode="group", bargap=0.4,
                      yaxis=dict(title="金额(元)", visible=False),
                      yaxis2=dict(title="毛利率", tickformat=".1%"))
    return fig

def fig_daily(b) -> go.Figure:
    d = b.daily
    xs = d["订单日期"].dt.strftime("%m-%d")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=xs, y=d["销售金额"], name="销售额",
                         text=[_wan(v) for v in d["销售金额"]], textposition="outside",
                         marker_color=_PALETTE["blue"]), secondary_y=False)
    fig.add_trace(go.Scatter(x=xs, y=d["销售毛利率"], name="毛利率",
                             text=[_pct(v) for v in d["销售毛利率"]], textposition="top center",
                             mode="lines+markers+text", line=dict(color=_PALETTE["red"], width=3)),
                  secondary_y=True)
    fig.update_layout(title="每日销售趋势", yaxis=dict(title="销售额(元)"),
                      yaxis2=dict(title="毛利率", tickformat=".1%"))
    return fig

def fig_brand_combo(b) -> go.Figure:
    d = b.brand
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=d["品牌"], y=d["销售金额"], name="销售额",
                         text=[_wan(v) for v in d["销售金额"]], textposition="outside",
                         marker_color=_PALETTE["blue"]), secondary_y=False)
    fig.add_trace(go.Bar(x=d["品牌"], y=d["销售数量"], name="销售数量",
                         text=d["销售数量"].tolist(), textposition="outside",
                         marker_color=_PALETTE["green"]), secondary_y=False)
    fig.add_trace(go.Scatter(x=d["品牌"], y=d["销售毛利率"], name="毛利率",
                             text=[_pct(v) for v in d["销售毛利率"]], textposition="top center",
                             mode="lines+markers+text", line=dict(color=_PALETTE["red"], width=3)),
                  secondary_y=True)
    fig.update_layout(title="品牌分析", barmode="group",
                      yaxis=dict(title="数量"), yaxis2=dict(title="毛利率", tickformat=".1%"))
    return fig

def fig_brand_pie(b) -> go.Figure:
    d = b.brand
    fig = go.Figure(go.Pie(labels=d["品牌"], values=d["销售数量"], textinfo="label+percent",
                           hole=0.4, marker=dict(colors=[_PALETTE["blue"], _PALETTE["green"]])))
    fig.update_layout(title="品牌销售数量占比")
    return fig

def fig_platform(b) -> go.Figure:
    d = b.platform.sort_values("销售数量", ascending=False)
    fig = make_subplots(rows=1, cols=2, specs=[[{"type":"domain"}, {"secondary_y": True}]],
                        subplot_titles=("平台数量占比", "数量与毛利率"))
    fig.add_trace(go.Pie(labels=d["平台"], values=d["销售数量"], textinfo="label+percent"), row=1, col=1)
    fig.add_trace(go.Bar(x=d["平台"], y=d["销售数量"], name="数量",
                         text=d["销售数量"].tolist(), textposition="outside",
                         marker_color=_PALETTE["blue"]), row=1, col=2, secondary_y=False)
    fig.add_trace(go.Scatter(x=d["平台"], y=d["销售毛利率"], name="毛利率",
                             text=[_pct(v) for v in d["销售毛利率"]], textposition="top center",
                             mode="lines+markers+text", line=dict(color=_PALETTE["red"], width=3)),
                  row=1, col=2, secondary_y=True)
    fig.update_layout(title="平台分析")
    fig.update_yaxes(title_text="数量", row=1, col=2, secondary_y=False)
    fig.update_yaxes(title_text="毛利率", tickformat=".1%", row=1, col=2, secondary_y=True)
    return fig

def _heatmap(long_df, title, entity_col):
    pivot = long_df.pivot_table(index=entity_col, columns="订单日期", values="销售数量", aggfunc="sum").fillna(0)
    pivot = pivot.sort_values(by=pivot.columns[-1], ascending=False)
    cols = [c.strftime("%m-%d") if hasattr(c, "strftime") else str(c) for c in pivot.columns]
    fig = go.Figure(go.Heatmap(z=pivot.values, x=cols, y=pivot.index,
                               text=[[int(v) for v in row] for row in pivot.values],
                               texttemplate="%{text}", colorscale="Blues", colorbar=dict(title="数量")))
    fig.update_layout(title=title, xaxis_title="日期", yaxis_title="")
    fig.update_yaxes(autorange="reversed")
    return fig

def fig_shop_heatmap(b) -> go.Figure:
    return _heatmap(b.shop_top15_daily, "TOP15 店铺每日销售数量", "店铺")

def fig_product_heatmap(b) -> go.Figure:
    return _heatmap(b.product_top15_daily, "TOP15 产品每日销售数量", "商品名称")

def fig_product_combo(b) -> go.Figure:
    """Deprecated: kept as alias for fig_product_horizontal so old code paths
    don't break, but new callers should use fig_product_horizontal + the data
    table view in the UI. See fig_product_horizontal for the redesigned chart."""
    return fig_product_horizontal(b)


def fig_product_horizontal(b) -> go.Figure:
    """Horizontal bar chart of TOP products by qty. Margin is encoded as bar
    color (red < 45% < yellow < 55% < green) and printed next to each bar so
    no numeric labels collide with the X axis. Product names live on the Y
    axis - never truncated, never rotated."""
    d = b.product_top15.sort_values("销售数量", ascending=True)  # ascending so biggest sits on top
    n = len(d)
    title = f"TOP{n} 产品 销量与毛利率" if n > 0 else "无产品数据"

    # Margin → color. Diverging 3-color scale around 50%.
    margins = d["销售毛利率"].astype(float)
    bar_colors = []
    for m in margins:
        if m < 0.45:        bar_colors.append(_PALETTE["red"])
        elif m < 0.50:      bar_colors.append(_PALETTE["orange"])
        elif m < 0.55:      bar_colors.append("#84cc16")   # lime
        else:               bar_colors.append(_PALETTE["green"])

    # Combined label inside each bar: "qty件 · margin%" — single text per bar
    # so we don't fight two label positions for the same horizontal real estate.
    qty_text = [f"{int(v)}件 · {_pct(m)}" for v, m in zip(d["销售数量"], margins)]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=d["商品名称"],
        x=d["销售数量"],
        orientation="h",
        marker=dict(color=bar_colors, line=dict(color="rgba(0,0,0,.15)", width=0.5)),
        text=qty_text,
        textposition="inside",
        insidetextanchor="end",
        textfont=dict(color="white", size=11, family="Arial"),
        cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>销量: %{x}件<br>毛利率: %{customdata}<extra></extra>",
        customdata=[_pct(m) for m in margins],
        name="销量",
    ))
    fig.update_layout(
        title=title,
        xaxis=dict(title="销售数量(件)", rangemode="tozero"),
        yaxis=dict(title="", automargin=True),
        margin=dict(l=10, r=20, t=70, b=40),
        height=max(420, 38 * n + 130),
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
    )

    # Top-right legend explaining the color scale.
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.99, y=1.08, xanchor="right", yanchor="bottom",
        text="<span style='color:#ef4444'>●</span> &lt;45% &nbsp;&nbsp; "
             "<span style='color:#f59e0b'>●</span> 45–50% &nbsp;&nbsp; "
             "<span style='color:#84cc16'>●</span> 50–55% &nbsp;&nbsp; "
             "<span style='color:#10b981'>●</span> ≥55%",
        showarrow=False, font=dict(size=10), align="right",
    )
    return fig


def fig_product_table(b) -> go.Figure:
    """Plain plotly Table view of the TOP product list — works as a printable
    data view that pairs with fig_product_horizontal in the UI. Returns a
    styled table (sortable-looking headers + alternating row shading)."""
    d = b.product_top15.reset_index(drop=True)
    n = len(d)
    title = f"TOP{n} 产品明细" if n > 0 else "无产品数据"

    # alternating row colors
    row_colors = ["#f8fafc" if i % 2 == 0 else "#ffffff" for i in range(n)]

    fig = go.Figure(data=[go.Table(
        columnwidth=[56, 220, 110, 110, 110, 110],
        header=dict(
            values=["#", "商品名称", "销售数量", "销售额(元)", "销售毛利(元)", "销售毛利率"],
            fill_color="#1f2937",
            font=dict(color="white", size=12),
            align=["center", "left", "right", "right", "right", "right"],
            height=34,
        ),
        cells=dict(
            values=[
                list(range(1, n + 1)),
                d["商品名称"].tolist(),
                [f"{int(v):,}" for v in d["销售数量"]],
                [_wan(v) for v in d["销售金额"]],
                [_wan(v) for v in d["销售毛利"]],
                [_pct(v) for v in d["销售毛利率"]],
            ],
            fill_color=[row_colors] * 6,
            font=dict(size=11, color="#111827"),
            align=["center", "left", "right", "right", "right", "right"],
            height=26,
        ),
    )])
    fig.update_layout(
        title=title,
        margin=dict(l=10, r=10, t=50, b=10),
        height=max(360, 30 * n + 80),
    )
    return fig

def fig_new_products(b) -> go.Figure:
    d = b.new_products
    if d.empty:
        return go.Figure().update_layout(title="无新品")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=d["商品名称"], y=d["销售数量"], name="数量",
                         text=d["销售数量"].tolist(), textposition="outside",
                         marker_color=_PALETTE["purple"]), secondary_y=False)
    fig.add_trace(go.Scatter(x=d["商品名称"], y=d["销售毛利率"], name="毛利率",
                             text=[_pct(v) for v in d["销售毛利率"]], textposition="top center",
                             mode="lines+markers+text", line=dict(color=_PALETTE["red"], width=3)),
                  secondary_y=True)
    fig.update_layout(title="新品 销量与毛利率", yaxis=dict(title="数量"),
                      yaxis2=dict(title="毛利率", tickformat=".1%"))
    return fig

def fig_three_weeks_table(recent_weeks: list) -> go.Figure:
    headers = ["周标识", "销售额", "销售毛利", "销售毛利率"]
    cells = [[w["week_id"] for w in recent_weeks],
             [_wan(w["销售额"]) for w in recent_weeks],
             [_wan(w["销售毛利"]) for w in recent_weeks],
             [_pct(w["销售毛利率"]) for w in recent_weeks]]
    fig = go.Figure(go.Table(header=dict(values=headers), cells=dict(values=cells)))
    fig.update_layout(title="最近三周")
    return fig


def fig_factory_table(b) -> go.Figure:
    d = b.factory_top5
    headers = ["工厂", "销售数量", "销售额", "销售毛利率"]
    cells = [d["工厂"].tolist(), [int(x) for x in d["销售数量"]],
             [_wan(x) for x in d["销售金额"]], [_pct(x) for x in d["销售毛利率"]]]
    fig = go.Figure(go.Table(header=dict(values=headers), cells=dict(values=cells)))
    fig.update_layout(title="供应商(TOP5)")
    return fig
