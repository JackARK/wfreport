from datetime import date
from backend.core.week import week_id, week_range
import pandas as pd

def test_week_id_iso():
    assert week_id(date(2026, 7, 8)) == "2026-W28"

def test_week_range_from_df():
    df = pd.DataFrame({"订单日期": pd.to_datetime(["2026-07-03", "2026-07-09"])})
    start, end = week_range(df)
    assert start == pd.Timestamp("2026-07-03")
    assert end == pd.Timestamp("2026-07-09")
