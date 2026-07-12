import os, tempfile
from backend.core.parser import load_excel
from backend.core.metrics import compute_all
from backend.core.history import init_db, save_week, week_exists, get_previous_week, get_recent_weeks

def _tmp():
    d = tempfile.mkdtemp()
    return os.path.join(d, "t.db")

def test_save_and_exists():
    p = _tmp(); init_db(p)
    df = load_excel("resource/本周.xlsx")
    ov = compute_all(df).overview
    wid = df["week_id"].iloc[0]
    save_week(wid, df, ov, p)
    assert week_exists(wid, p)
    prev = get_previous_week(wid, p)
    assert prev is None  # 只有一周
    rec = get_recent_weeks(3, p)
    assert len(rec) == 1 and rec[0]["week_id"] == wid
