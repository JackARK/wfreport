import sqlite3
import json
import pandas as pd
from datetime import datetime
from pathlib import Path

def _connect(db_path: str):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db(db_path: str):
    conn = _connect(db_path)
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS weekly_summary(
            week_id TEXT PRIMARY KEY, 周起始日 TEXT, 周结束日 TEXT,
            销售额 REAL, 销售毛利 REAL, 销售毛利率 REAL, 销售数量 INTEGER);
        CREATE TABLE IF NOT EXISTS weekly_orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT, week_id TEXT,
            线上订单号 TEXT, 品牌 TEXT, 店铺 TEXT, 平台 TEXT, 订单日期 TEXT,
            商品名称 TEXT, 工厂 TEXT, 商品编码 TEXT, 成本价 REAL, 总成本 REAL,
            销售数量 INTEGER, 销售金额 REAL, 销售毛利 REAL, 销售毛利率 REAL, 是否新品 TEXT,
            FOREIGN KEY(week_id) REFERENCES weekly_summary(week_id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS weekly_workspace(
            week_id TEXT PRIMARY KEY,
            content TEXT DEFAULT '',
            content_md TEXT DEFAULT '',
            plan_items_json TEXT DEFAULT '[]',
            procurement_items_json TEXT DEFAULT '[]',
            narrative_overrides_json TEXT DEFAULT '{}',
            updated_at TEXT);
        """)
        conn.commit()
    finally:
        conn.close()

def save_week(week_id: str, df: pd.DataFrame, overview: dict, db_path: str):
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        # Preserve any user-entered workspace across re-uploads of the same week.
        cur.execute("SELECT content, content_md, plan_items_json, procurement_items_json, narrative_overrides_json "
                    "FROM weekly_workspace WHERE week_id=?", (week_id,))
        ws_row = cur.fetchone()
        cur.execute("DELETE FROM weekly_orders WHERE week_id=?", (week_id,))
        cur.execute("DELETE FROM weekly_summary WHERE week_id=?", (week_id,))
        # re-add workspace row if it was preserved... actually CASCADE removed it; if user
        # already had content we wanted to keep, that's lost. Simpler: keep workspace by
        # saving it before delete and restoring after.
        # Below we always restore after insert (workspace table accepts absent row, FK satisfied).
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
        # restore workspace if it existed before (preserve user content across re-upload)
        if ws_row:
            cur.execute("""INSERT INTO weekly_workspace
               (week_id, content, content_md, plan_items_json, procurement_items_json,
                narrative_overrides_json, updated_at)
               VALUES(?,?,?,?,?,?,?)""",
               (week_id, ws_row[0], ws_row[1], ws_row[2], ws_row[3], ws_row[4],
                datetime.utcnow().isoformat()))
        conn.commit()
    finally:
        conn.close()

def week_exists(week_id: str, db_path: str) -> bool:
    conn = _connect(db_path)
    try:
        n = conn.execute("SELECT COUNT(*) FROM weekly_summary WHERE week_id=?", (week_id,)).fetchone()[0]
        return n > 0
    finally:
        conn.close()

def get_previous_week(week_id: str, db_path: str):
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM weekly_summary WHERE week_id<? ORDER BY week_id DESC LIMIT 1", (week_id,)).fetchone()
        return _row_to_summary(row) if row else None
    finally:
        conn.close()

def get_recent_weeks(n: int, db_path: str):
    conn = _connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM weekly_summary ORDER BY week_id DESC LIMIT ?", (n,)).fetchall()
        return [_row_to_summary(r) for r in rows][::-1]
    finally:
        conn.close()

def _row_to_summary(row):
    return {"week_id": row[0], "周起始日": row[1], "周结束日": row[2],
            "销售额": row[3], "销售毛利": row[4], "销售毛利率": row[5], "销售数量": row[6]}

# ---- workspace (user-entered content + plan + AI narrative overrides) ----

def _empty_workspace(week_id: str) -> dict:
    return {"week_id": week_id, "content": "", "content_md": "",
            "plan_items": [], "procurement_items": [],
            "narrative_overrides": {}, "updated_at": None}

def load_workspace(week_id: str, db_path: str) -> dict:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM weekly_workspace WHERE week_id=?", (week_id,)).fetchone()
        if not row:
            return _empty_workspace(week_id)
        return {
            "week_id": row[0],
            "content": row[1] or "",
            "content_md": row[2] or "",
            "plan_items": json.loads(row[3] or "[]"),
            "procurement_items": json.loads(row[4] or "[]"),
            "narrative_overrides": json.loads(row[5] or "{}"),
            "updated_at": row[6],
        }
    finally:
        conn.close()

def save_workspace(week_id: str, ws: dict, db_path: str) -> dict:
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO weekly_workspace(week_id, content, content_md, plan_items_json,
               procurement_items_json, narrative_overrides_json, updated_at)
               VALUES(?,?,?,?,?,?,?)
               ON CONFLICT(week_id) DO UPDATE SET
                 content=excluded.content,
                 content_md=excluded.content_md,
                 plan_items_json=excluded.plan_items_json,
                 procurement_items_json=excluded.procurement_items_json,
                 narrative_overrides_json=excluded.narrative_overrides_json,
                 updated_at=excluded.updated_at""",
            (week_id,
             ws.get("content", ""),
             ws.get("content_md", ""),
             json.dumps(ws.get("plan_items", []), ensure_ascii=False),
             json.dumps(ws.get("procurement_items", []), ensure_ascii=False),
             json.dumps(ws.get("narrative_overrides", {}), ensure_ascii=False),
             datetime.utcnow().isoformat()))
        conn.commit()
        return load_workspace(week_id, db_path)
    finally:
        conn.close()
