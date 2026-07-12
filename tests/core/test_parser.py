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
