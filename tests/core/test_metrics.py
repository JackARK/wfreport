import pandas as pd
from backend.core.parser import load_excel
from backend.core.metrics import compute_all, aggregate

def test_aggregate_weighted_margin():
    df = load_excel("resource/本周.xlsx")
    agg = aggregate(df, [])  # 全表
    assert round(agg["销售毛利率"], 3) == 0.501  # 加权 50.1%

def test_compute_all_shapes():
    df = load_excel("resource/本周.xlsx")
    b = compute_all(df)
    assert round(b.overview["销售毛利率"], 3) == 0.501
    assert b.overview["销售金额"] == df["销售金额"].sum()
    assert len(b.daily) == 7
    assert set(b.brand["品牌"]) == {"猫人", "初医生"}
    assert len(b.product_top15) == 15
    assert len(b.factory_top5) == 5
    assert len(b.new_products["商品编码"].unique()) == 1  # 仅1个新品
    # 数量占比和约等于1
    assert abs(b.brand["数量占比"].sum() - 1.0) < 1e-6
