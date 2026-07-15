import pandas as pd
from backend.core.parser import load_excel
from backend.core.metrics import compute_all, aggregate

def test_aggregate_weighted_margin():
    df = load_excel("resource/本周.xlsx")
    agg = aggregate(df)  # 全表
    assert round(agg["销售毛利率"], 3) == 0.501  # 加权 50.1%

def test_compute_all_shapes():
    df = load_excel("resource/本周.xlsx")
    b = compute_all(df)
    assert round(b.overview["销售毛利率"], 3) == 0.501
    assert b.overview["销售金额"] == df["销售金额"].sum()
    assert len(b.daily) == 7
    assert set(b.brand["品牌"]) == {"猫人", "初医生"}
    # product_top15 is now aggregated by 商品名称, so each row is a unique
    # product (not a SKU) — fixes the "TOP15 title but only 9 bars" bug
    # where Plotly was collapsing same-name SKUs into one bar.
    assert len(b.product_top15) == b.product_top15["商品名称"].nunique()
    assert b.product_top15["商品名称"].is_unique
    assert len(b.product_top15) <= 15
    assert len(b.factory_top5) == 5
    assert len(b.new_products["商品编码"].unique()) == 1  # 仅1个新品
    # 数量占比和约等于1
    assert abs(b.brand["数量占比"].sum() - 1.0) < 1e-6
    # 维度毛利率为加权(毛利和/金额和)，非行均值
    brand0 = b.brand.iloc[0]
    expected = brand0["销售毛利"] / brand0["销售金额"]
    assert abs(brand0["销售毛利率"] - expected) < 1e-9


def test_product_top15_margin_is_weighted_not_row_mean():
    """Per-product margin must be Σ毛利 / Σ金额 (weighted), not the mean
    of row-level margins. Without this, the TOP products view gives the
    reader a misleading picture (e.g. 41% reported when the true weighted
    margin is 39%)."""
    df = load_excel("resource/本周.xlsx")
    b = compute_all(df)
    for _, row in b.product_top15.iterrows():
        name = row["商品名称"]
        sub = df[df["商品名称"] == name]
        expected_margin = sub["销售毛利"].sum() / sub["销售金额"].sum()
        assert abs(row["销售毛利率"] - expected_margin) < 1e-9, (
            f"{name}: stored {row['销售毛利率']:.4f} but weighted says "
            f"{expected_margin:.4f} - row-mean aggregation would diverge here"
        )
