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
            plan_text TEXT DEFAULT '',
            plan_items_json TEXT DEFAULT '[]',
            procurement_items_json TEXT DEFAULT '[]',
            narrative_overrides_json TEXT DEFAULT '{}',
            updated_at TEXT);
        """)
        # Idempotent migration: older DBs may pre-date plan_text. SQLite ALTER
        # TABLE fails silently if the column already exists (we catch the error).
        try:
            conn.execute("ALTER TABLE weekly_workspace ADD COLUMN plan_text TEXT DEFAULT ''")
            conn.commit()
        except Exception:
            pass
        conn.commit()
    finally:
        conn.close()

def save_week(week_id: str, df: pd.DataFrame, overview: dict, db_path: str):
    """Re-upload of an existing week_id wipes its user workspace too. Re-uploads
    are treated as 'different data' by default — preserving last week's plan /
    procurement / AI narratives against new figures would be misleading. Callers
    that want to preserve user input must skip this path (e.g. a future
    `patch_workspace` endpoint)."""
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        # Delete leaf -> parent. workspace has no FK so explicit delete required.
        cur.execute("DELETE FROM weekly_workspace WHERE week_id=?", (week_id,))
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


# ---- history listing & raw-order reload for state recovery ----

def list_weeks_with_files(db_path: str, output_root) -> list:
    """Every week_id in the DB + a snapshot of its workspace and output files.
    Used by the UI history page so users can re-open a previous week without
    re-uploading, and so 0-input re-renders can find the existing xlsx/pptx."""
    import json as _json
    conn = _connect(db_path)
    try:
        rows = conn.execute("""
            SELECT s.week_id, s.周起始日, s.周结束日,
                   s.销售额, s.销售毛利, s.销售毛利率, s.销售数量,
                   (SELECT COUNT(*) FROM weekly_orders o WHERE o.week_id = s.week_id) AS row_count,
                   w.content, w.content_md, w.plan_text,
                   w.plan_items_json, w.procurement_items_json,
                   w.narrative_overrides_json, w.updated_at
            FROM weekly_summary s
            LEFT JOIN weekly_workspace w ON w.week_id = s.week_id
            ORDER BY s.week_id DESC
        """).fetchall()
        out = []
        for r in rows:
            wid = r[0]
            try:
                plan_n = len(_json.loads(r[10] or "[]"))
                proc_n = len(_json.loads(r[11] or "[]"))
            except Exception:
                plan_n = proc_n = 0
            week_dir = output_root / wid
            out.append({
                "week_id": wid,
                "周起始日": r[1],
                "周结束日": r[2],
                "销售额": r[3],
                "销售毛利": r[4],
                "销售毛利率": r[5],
                "销售数量": r[6],
                "rows": r[7],
                "workspace_summary": {
                    "content_chars": len(r[8] or ""),
                    "plan_text_chars": len(r[10] or ""),
                    "plan_items_count": plan_n,
                    "procurement_items_count": proc_n,
                    "updated_at": r[14],
                },
                "files": {
                    "xlsx": (week_dir / f"{wid}.xlsx").is_file(),
                    "pptx": (week_dir / f"{wid}.pptx").is_file(),
                    "bundle": (week_dir / "png").is_dir() or (week_dir / f"{wid}.xlsx").is_file(),
                },
                "urls": {
                    "xlsx": f"/api/download/{wid}/{wid}.xlsx",
                    "pptx": f"/api/download/{wid}/{wid}.pptx",
                    "bundle": f"/api/bundle/{wid}.zip",
                    "workspace": f"/api/workspace/{wid}/export.json",
                },
            })
        return out
    finally:
        conn.close()


def load_orders_as_df(week_id: str, db_path: str):
    """Reconstruct the source DataFrame from weekly_orders so _state can be
    rebuilt without re-uploading the original xlsx."""
    import pandas as _pd
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT 线上订单号,品牌,店铺,平台,订单日期,商品名称,工厂,商品编码,"
            "成本价,总成本,销售数量,销售金额,销售毛利,销售毛利率,是否新品 "
            "FROM weekly_orders WHERE week_id=? ORDER BY id", (week_id,)
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        return None
    cols = ["线上订单号","品牌","店铺","平台","订单日期","商品名称","工厂","商品编码",
            "成本价","总成本","销售数量","销售金额","销售毛利","销售毛利率","是否新品"]
    df = _pd.DataFrame(rows, columns=cols)
    df["订单日期"] = _pd.to_datetime(df["订单日期"])
    # Re-derive 平台 from 店铺 prefix using the same logic as parser.load_excel.
    try:
        from backend.core.parser import derive_platform
        df["平台"] = df["店铺"].astype(str).map(derive_platform)
    except Exception:
        df["平台"] = "其他"
    df["week_id"] = week_id
    return df

# ---- workspace (user-entered content + plan + AI narrative overrides) ----

def _empty_workspace(week_id: str) -> dict:
    return {"week_id": week_id, "content": "", "content_md": "",
            "plan_text": "",
            "plan_items": [], "procurement_items": [],
            "narrative_overrides": {}, "updated_at": None}

def load_workspace(week_id: str, db_path: str) -> dict:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM weekly_workspace WHERE week_id=?", (week_id,)).fetchone()
        if not row:
            return _empty_workspace(week_id)
        # Old DBs may not have plan_text column -> default to ''
        try:
            plan_text = row[7] if len(row) > 7 else ""
        except Exception:
            plan_text = ""
        return {
            "week_id": row[0],
            "content": row[1] or "",
            "content_md": row[2] or "",
            "plan_text": plan_text or "",
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
            """INSERT INTO weekly_workspace(week_id, content, content_md, plan_text, plan_items_json,
               procurement_items_json, narrative_overrides_json, updated_at)
               VALUES(?,?,?,?,?,?,?,?)
               ON CONFLICT(week_id) DO UPDATE SET
                 content=excluded.content,
                 content_md=excluded.content_md,
                 plan_text=excluded.plan_text,
                 plan_items_json=excluded.plan_items_json,
                 procurement_items_json=excluded.procurement_items_json,
                 narrative_overrides_json=excluded.narrative_overrides_json,
                 updated_at=excluded.updated_at""",
            (week_id,
             ws.get("content", ""),
             ws.get("content_md", ""),
             ws.get("plan_text", ""),
             json.dumps(ws.get("plan_items", []), ensure_ascii=False),
             json.dumps(ws.get("procurement_items", []), ensure_ascii=False),
             json.dumps(ws.get("narrative_overrides", {}), ensure_ascii=False),
             datetime.utcnow().isoformat()))
        conn.commit()
        return load_workspace(week_id, db_path)
    finally:
        conn.close()
