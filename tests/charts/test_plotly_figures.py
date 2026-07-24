from backend.core.parser import load_excel
from backend.core.metrics import compute_all
from backend.charts import plotly_figures as pf

def _bundle():
    return compute_all(load_excel("resource/本周.xlsx"))

def test_fig_overview_has_bars_and_line():
    fig = pf.fig_overview(_bundle())
    types = [t.type for t in fig.data]
    assert "bar" in types and "scatter" in types  # 柱+折线

def test_fig_brand_pie():
    fig = pf.fig_brand_pie(_bundle())
    assert fig.data[0].type == "pie"

def test_fig_shop_heatmap():
    fig = pf.fig_shop_heatmap(_bundle())
    assert fig.data[0].type == "heatmap"

def test_fig_platform_two_subplots():
    fig = pf.fig_platform(_bundle())
    assert len(fig.data) >= 2  # 饼+双轴

def test_fig_three_weeks_table():
    fig = pf.fig_three_weeks_table([{"week_id":"2026-W27","销售额":100,"销售毛利":50,"销售毛利率":0.5}])
    assert fig is not None

def test_fig_factory_table_uses_top15():
    b = _bundle()
    fig = pf.fig_factory_table(b)
    assert len(fig.data[0].cells.values[0]) == len(b.factory_top15)
