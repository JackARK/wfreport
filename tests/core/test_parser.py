import pandas as pd
from backend.core.parser import load_excel, derive_platform

def test_load_excel_derives_columns():
    df = load_excel("resource/本周.xlsx")
    assert "平台" in df.columns
    assert "week_id" in df.columns
    assert len(df) == 18837
    assert df["订单日期"].dtype.kind == "M"

def test_derive_platform_whitelist():
    assert derive_platform("淘宝天猫-猫人严选旗舰店") == "淘宝天猫"
    assert derive_platform("初医生旅行用品") == "其他"

def test_real_data_platforms():
    df = load_excel("resource/本周.xlsx")
    plats = set(df["平台"].unique())
    assert "淘宝天猫" in plats and "拼多多" in plats
    assert "其他" in plats  # 初医生旅行用品 等落入其他

def test_load_excel_without_new_product_column():
    """上周.xlsx 无「是否新品」列 — 加载后自动补「否」。"""
    df = load_excel("resource/上周.xlsx")
    assert "是否新品" in df.columns
    assert set(df["是否新品"].unique()) == {"否"}

def test_metrics_without_new_product_column():
    """无「是否新品」列的数据 compute_all 不崩，new_products 为空表。"""
    from backend.core.metrics import compute_all
    df = load_excel("resource/上周.xlsx")
    bundle = compute_all(df)
    assert len(bundle.new_products) == 0

def test_load_excel_alias_columns():
    """下周.xlsx 是聚合口径: 渠道→店铺、日期→订单日期、无订单号补合成值。"""
    df = load_excel("resource/下周.xlsx")
    assert "店铺" in df.columns and "订单日期" in df.columns
    assert "线上订单号" in df.columns
    assert df["线上订单号"].is_unique
    assert df["订单日期"].dtype.kind == "M"
    assert str(df["week_id"].iloc[0]) == "2026-W28"
