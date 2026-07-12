import sqlite3
import pandas as pd
from pathlib import Path

def _connect(db_path: str):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db(db_path: str):
    conn = _connect(db_path)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS weekly_summary(
        week_id TEXT PRIMARY KEY, 周起始日 TEXT, 周结束日 TEXT,
        销售额 REAL, 销售毛利 REAL, 销售毛利率 REAL, 销售数量 INTEGER);
    CREATE TABLE IF NOT EXISTS weekly_orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT, week_id TEXT,
        线上订单号 TEXT, 品牌 TEXT, 店铺 TEXT, 平台 TEXT, 订单日期 TEXT,
        商品名称 TEXT, 工厂 TEXT, 商品编码 TEXT, 成本价 REAL, 总成本 REAL,
        销售数量 INTEGER, 销售金额 REAL, 销售毛利 REAL, 销售毛利率 REAL, 是否新品 TEXT,
        FOREIGN KEY(week_id) REFERENCES weekly_summary(week_id));
    """)
    conn.commit(); conn.close()

def save_week(week_id: str, df: pd.DataFrame, overview: dict, db_path: str):
    conn = _connect(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM weekly_orders WHERE week_id=?", (week_id,))
    cur.execute("DELETE FROM weekly_summary WHERE week_id=?", (week_id,))
    start, end = df["订单日期"].min(), df["订单日期"].max()
    cur.execute("INSERT INTO weekly_summary VALUES(?,?,?,?,?,?,?)", (
        week_id, str(start.date()), str(end.date()),
        overview["销售金额"], overview["销售毛利"], overview["销售毛利率"], overview["销售数量"]))
    cols = ["线上订单号","品牌","店铺","平台","订单日期","商品名称","工厂","商品编码",
            "成本价","总成本","销售数量","销售金额","销售毛利","销售毛利率","是否新品"]
    rows = df[cols].copy()
    rows["订单日期"] = rows["订单日期"].dt.strftime("%Y-%m-%d")
    for _, r in rows.iterrows():
        cur.execute("INSERT INTO weekly_orders(week_id," + ",".join(cols) + ") VALUES(?," + ",".join("?"*len(cols)) + ")",
                    (week_id, *r.tolist()))
    conn.commit(); conn.close()

def week_exists(week_id: str, db_path: str) -> bool:
    conn = _connect(db_path)
    n = conn.execute("SELECT COUNT(*) FROM weekly_summary WHERE week_id=?", (week_id,)).fetchone()[0]
    conn.close(); return n > 0

def get_previous_week(week_id: str, db_path: str):
    conn = _connect(db_path)
    row = conn.execute("SELECT * FROM weekly_summary WHERE week_id<? ORDER BY week_id DESC LIMIT 1", (week_id,)).fetchone()
    conn.close()
    return _row_to_summary(row) if row else None

def get_recent_weeks(n: int, db_path: str):
    conn = _connect(db_path)
    rows = conn.execute("SELECT * FROM weekly_summary ORDER BY week_id DESC LIMIT ?", (n,)).fetchall()
    conn.close()
    return [_row_to_summary(r) for r in rows][::-1]

def _row_to_summary(row):
    return {"week_id": row[0], "周起始日": row[1], "周结束日": row[2],
            "销售额": row[3], "销售毛利": row[4], "销售毛利率": row[5], "销售数量": row[6]}
