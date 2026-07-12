import sqlite3
from backend.core.parser import load_excel
from backend.core.metrics import compute_all, aggregate
from backend.core.history import init_db, save_week, week_exists, get_previous_week, get_recent_weeks

def _db(tmp_path):
    return str(tmp_path / "t.db")

def _count(db_path, table, week_id=None):
    conn = sqlite3.connect(db_path)
    try:
        if week_id is None:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE week_id=?", (week_id,)).fetchone()[0]
    finally:
        conn.close()

def test_save_and_exists(tmp_path):
    p = _db(tmp_path); init_db(p)
    df = load_excel("resource/本周.xlsx")
    ov = compute_all(df).overview
    wid = df["week_id"].iloc[0]
    save_week(wid, df, ov, p)
    assert week_exists(wid, p)
    prev = get_previous_week(wid, p)
    assert prev is None  # 只有一周
    rec = get_recent_weeks(3, p)
    assert len(rec) == 1 and rec[0]["week_id"] == wid

def test_save_week_idempotent(tmp_path):
    p = _db(tmp_path); init_db(p)
    df = load_excel("resource/本周.xlsx")
    ov = compute_all(df).overview
    wid = "2026-W27"
    save_week(wid, df, ov, p)
    summary_n = _count(p, "weekly_summary")
    orders_n = _count(p, "weekly_orders", wid)
    assert summary_n == 1
    assert orders_n == len(df)
    save_week(wid, df, ov, p)
    assert _count(p, "weekly_summary") == summary_n
    assert _count(p, "weekly_orders", wid) == orders_n

def test_multi_week_ordering(tmp_path):
    p = _db(tmp_path); init_db(p)
    df_prev = load_excel("resource/上周.xlsx")
    df_prev["是否新品"] = "否"
    df_curr = load_excel("resource/本周.xlsx")
    save_week("2026-W26", df_prev, aggregate(df_prev), p)
    save_week("2026-W27", df_curr, aggregate(df_curr), p)
    prev = get_previous_week("2026-W27", p)
    assert prev is not None
    assert prev["week_id"] == "2026-W26"
    rec = get_recent_weeks(3, p)
    assert [w["week_id"] for w in rec] == ["2026-W26", "2026-W27"]
    assert len(rec) == 2
