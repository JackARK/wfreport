from datetime import date
import pandas as pd

def week_id(d) -> str:
    """返回 ISO 周标识 YYYY-Www。"""
    ts = pd.Timestamp(d)
    iso = ts.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"

def week_range(df: pd.DataFrame):
    """返回 df 中 订单日期 的 (min, max)。"""
    return df["订单日期"].min(), df["订单日期"].max()
