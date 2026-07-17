import os
import zipfile
import io
import time
from pathlib import Path

import yaml
from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from fastapi.responses import FileResponse

from backend.ai import client as ai_client, prompts as ai_prompts
from backend.charts.render_png import render_all_pngs
from backend.core import parser, history, metrics
from backend.core.logging_conf import get_logger
from backend.core.week import week_range
from backend.reports import web_report
from backend.reports import narratives as narratives_mod
from backend.reports.excel_builder import build_excel
from backend.reports.ppt_builder import build_ppt

logger = get_logger("api")

router = APIRouter()
_state = {}  # week_id -> (df, bundle)
_CFG = Path(__file__).resolve().parents[1] / "config" / "settings.yaml"
OUT_ROOT = Path("output").resolve()
DEFAULT_TEMPLATE = "resource/2026年第二十七周周报-王凡.pptx"


def _tpath(payload) -> str:
    return payload.get("template_path") or DEFAULT_TEMPLATE


def _db():
    env = os.getenv("WFREPORT_DB_PATH")
    if env:
        return env
    with open(_CFG, encoding="utf-8") as f:
        return yaml.safe_load(f)["db_path"]


# ===== Upload =====

@router.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    safe_name = os.path.basename(file.filename or "").replace("..", "").strip()
    if not safe_name:
        safe_name = "upload.xlsx"
    tmp = os.path.join("output", safe_name)
    os.makedirs("output", exist_ok=True)
    with open(tmp, "wb") as f:
        f.write(await file.read())
    logger.info("上传文件 %s (%.1f KB)", safe_name, os.path.getsize(tmp) / 1024)
    df = parser.load_excel(tmp)
    wid = df["week_id"].iloc[0]
    logger.info("解析完成 week_id=%s rows=%d cols=%d", wid, len(df), len(df.columns))
    bundle = metrics.compute_all(df)
    history.init_db(_db())
    history.save_week(wid, df, bundle.overview, _db())
    logger.info("写入 SQLite week_id=%s overview=%s", wid,
                {k: round(v, 2) if isinstance(v, float) else v for k, v in bundle.overview.items()})
    _state[wid] = (df, bundle)
    start, end = week_range(df)
    return {"week_id": wid, "rows": len(df),
            "周起始日": str(start.date()), "周结束日": str(end.date())}


# ===== Preview =====

@router.post("/api/preview/{week_id}")
def preview(week_id: str):
    if week_id not in _state:
        raise HTTPException(404, "请先上传")
    _, bundle = _state[week_id]
    recent = history.get_recent_weeks(3, _db())
    logger.info("预览构建 week_id=%s figures=%d", week_id, 12)
    return web_report.build_report_json(bundle, recent)


# ===== History =====

@router.get("/api/history")
def history_api():
    return {"recent": history.get_recent_weeks(3, _db())}


@router.get("/api/history/all")
def history_all():
    weeks = history.list_weeks_with_files(_db(), OUT_ROOT)
    logger.info("历史列表 weeks=%d", len(weeks))
    return {"weeks": weeks}


# ===== Workspace =====

def _ensure_state(week_id: str):
    if week_id in _state:
        return True
    logger.info("重建内存状态 week_id=%s (从 SQLite)", week_id)
    df = history.load_orders_as_df(week_id, _db())
    if df is None or len(df) == 0:
        logger.warning("重建失败 week_id=%s — SQLite 无数据", week_id)
        return False
    bundle = metrics.compute_all(df)
    _state[week_id] = (df, bundle)
    logger.info("重建成功 week_id=%s rows=%d", week_id, len(df))
    return True


@router.post("/api/workspace/{week_id}/reload")
def reload_state(week_id: str):
    if not history.week_exists(week_id, _db()):
        raise HTTPException(404, "该周数据未持久化到 SQLite")
    if not _ensure_state(week_id):
        raise HTTPException(500, "重算 _state 失败")
    return {"ok": True, "week_id": week_id, "rows": int(len(_state[week_id][0]))}


@router.get("/api/workspace/{week_id}/export.json")
def export_workspace_json(week_id: str):
    ws = history.load_workspace(week_id, _db())
    from fastapi.responses import JSONResponse
    return JSONResponse(ws, headers={
        "Content-Disposition": f"attachment; filename={week_id}-workspace.json"
    })


@router.post("/api/ai/parse_workspace/{week_id}")
def parse_workspace(week_id: str, payload: dict = Body(default={})):
    if week_id not in _state:
        if history.week_exists(week_id, _db()):
            _ensure_state(week_id)
        else:
            raise HTTPException(404, "请先上传")

    content   = (payload.get("content")   or "").strip()
    plan_text = (payload.get("plan_text") or "").strip()
    provider  = (payload.get("provider") or "").strip() or None
    thinking  = (payload.get("thinking") or "").strip() or None

    logger.info("AI 解析 week_id=%s provider=%s thinking=%s 内容长度=%d 计划长度=%d",
                week_id, provider, thinking, len(content), len(plan_text))

    proc_items = ai_client.generate_json(
        "procurement", {"user_input": content},
        provider=provider, thinking=thinking,
    ) if content else []

    plan_items = ai_client.generate_json(
        "next_plan", {"user_input": plan_text},
        provider=provider, thinking=thinking,
    ) if plan_text else []

    logger.info("AI 解析完成 week_id=%s 采购=%d条 下周计划=%d条",
                week_id, len(proc_items), len(plan_items))

    ws = history.load_workspace(week_id, _db())
    ws["content"]         = content
    ws["plan_text"]       = plan_text
    ws["procurement_items"] = proc_items
    ws["plan_items"]        = plan_items
    saved = history.save_workspace(week_id, ws, _db())

    return {
        "ok": True,
        "week_id": week_id,
        "procurement_items_count": len(proc_items),
        "plan_items_count":        len(plan_items),
        "workspace": saved,
    }


def _week_compare_vars(payload: dict) -> dict:
    week_id = payload.get("week_id")
    if week_id not in _state:
        raise HTTPException(404, "请先上传")
    _, bundle = _state[week_id]
    cur_amt = float(bundle.overview["销售金额"])
    cur_prof = float(bundle.overview["销售毛利"])
    cur_marg = float(bundle.overview["销售毛利率"]) * 100
    prev = history.get_previous_week(week_id, _db())
    if prev:
        prev_amt = float(prev["销售额"])
        prev_prof = float(prev["销售毛利"])
        prev_marg = float(prev["销售毛利率"]) * 100
    else:
        prev_amt = prev_prof = prev_marg = 0.0

    def _rate(cur, prev):
        return "0" if prev == 0 else f"{(cur - prev) / prev * 100:.2f}"

    return {
        "cur_amount": f"{cur_amt:.2f}",
        "cur_profit": f"{cur_prof:.2f}",
        "cur_margin": f"{cur_marg:.2f}",
        "prev_amount": f"{prev_amt:.2f}",
        "prev_profit": f"{prev_prof:.2f}",
        "prev_margin": f"{prev_marg:.2f}",
        "amount_delta": f"{cur_amt - prev_amt:.2f}",
        "amount_delta_rate": _rate(cur_amt, prev_amt),
        "profit_delta": f"{cur_prof - prev_prof:.2f}",
        "profit_delta_rate": _rate(cur_prof, prev_prof),
        "margin_delta_pct": f"{cur_marg - prev_marg:.2f}",
    }


def _daily_summary_vars(payload: dict) -> dict:
    week_id = payload.get("week_id")
    if week_id not in _state:
        raise HTTPException(404, "请先上传")
    _, bundle = _state[week_id]
    lines = []
    for _, r in bundle.daily.iterrows():
        d = r["订单日期"]
        mmdd = d.strftime("%m-%d") if hasattr(d, "strftime") else str(d)[:5]
        lines.append(f"{mmdd}: 销售额{r['销售金额']:.2f}元, 毛利率{r['销售毛利率'] * 100:.2f}%")
    return {"daily_series": "\n".join(lines)}


# ===== AI =====

@router.post("/api/ai/{section}")
def ai_section(section: str, payload: dict):
    provider = (payload.get("provider") or "").strip() or None
    thinking = (payload.get("thinking") or "").strip() or None
    logger.info("AI section=%s provider=%s thinking=%s", section, provider, thinking)
    if section in ("procurement", "next_plan"):
        items = ai_client.generate_json(
            section, {"user_input": payload.get("input", "")},
            provider=provider, thinking=thinking,
        )
        logger.info("AI section=%s 返回 items=%d", section, len(items))
        return {"items": items}
    if section == "week_compare":
        text = ai_client.generate_section("week_compare", _week_compare_vars(payload), provider=provider, thinking=thinking)
        logger.info("AI week_compare 返回 len=%d", len(text))
        return {"text": text}
    if section == "daily_summary":
        text = ai_client.generate_section("daily_summary", _daily_summary_vars(payload), provider=provider, thinking=thinking)
        logger.info("AI daily_summary 返回 len=%d", len(text))
        return {"text": text}
    text = ai_client.generate_section(section, payload.get("vars", {}), provider=provider, thinking=thinking)
    return {"text": text}


@router.get("/api/ai/providers")
def ai_providers():
    return {"providers": ai_client.list_providers()}


@router.get("/api/config/prompts")
def get_prompts():
    return ai_prompts.load()


@router.put("/api/config/prompts")
def put_prompts(body: dict):
    p = Path(__file__).resolve().parents[1] / "config" / "prompts.yaml"
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump(body, f, allow_unicode=True)
    ai_prompts.reload()
    logger.info("Prompts 已热加载")
    return ai_prompts.load()


# ===== Generate (legacy endpoint) =====

@router.post("/api/generate/{week_id}")
def generate(week_id: str, payload: dict):
    if week_id not in _state:
        raise HTTPException(404, "请先上传")
    df, bundle = _state[week_id]
    recent = history.get_recent_weeks(3, _db())
    os.makedirs("output", exist_ok=True)
    logger.info("Generate 开始 week_id=%s", week_id)
    t0 = time.perf_counter()
    pngs = render_all_pngs(bundle, recent, os.path.join("output", week_id, "png"),
                            template_path=_tpath(payload))
    logger.info("PNG 渲染完成 week_id=%s 耗时=%.1fs charts=%d",
                week_id, time.perf_counter() - t0, len(pngs))
    ai_texts = payload.get("ai_texts", {})
    procurement_items = payload.get("procurement_items", [])
    plan_items = payload.get("plan_items", [])
    week_meta = {"week_id": week_id,
                 "周起始日": str(df["订单日期"].min().date()),
                 "周结束日": str(df["订单日期"].max().date())}
    built_narratives = narratives_mod.build_narratives(bundle, week_meta)
    client_narratives = payload.get("narratives", {}) or {}
    narratives = {k: (client_narratives.get(k) or built_narratives.get(k, ""))
                  for k in ("brand", "brand_share", "product", "new")}
    xlsx = os.path.join("output", week_id, f"{week_id}.xlsx")
    build_excel(bundle, recent, ai_texts, procurement_items, plan_items, xlsx)
    logger.info("Excel 生成完成 week_id=%s path=%s", week_id, xlsx)
    pptx = os.path.join("output", week_id, f"{week_id}.pptx")
    pngs["factory"] = pngs.get("factory") or pngs["three_weeks"]
    build_ppt(_tpath(payload),
              pngs, ai_texts, narratives, procurement_items, plan_items, week_meta, pptx)
    logger.info("PPT 生成完成 week_id=%s path=%s", week_id, pptx)
    return {"excel": f"/api/download/{week_id}/{week_id}.xlsx",
            "ppt": f"/api/download/{week_id}/{week_id}.pptx"}


@router.get("/api/download/{week_id}/{name}")
def download(week_id: str, name: str):
    if (week_id in ("", ".", "..") or name in ("", ".", "..")
            or "/" in name or "\\" in name or "/" in week_id or "\\" in week_id):
        raise HTTPException(status_code=404)
    target = (OUT_ROOT / week_id / name).resolve()
    try:
        target.relative_to(OUT_ROOT)
    except ValueError:
        raise HTTPException(status_code=404)
    if not target.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(str(target))


# ===== Workflow / Workspace endpoints =====

@router.get("/api/workspace/{week_id}")
def get_workspace(week_id: str):
    if week_id not in _state:
        if not history.week_exists(week_id, _db()):
            raise HTTPException(404, "请先上传")
        _ensure_state(week_id)
    df, bundle = _state.get(week_id, (None, None))
    ws = history.load_workspace(week_id, _db())
    recent = history.get_recent_weeks(3, _db())
    return {
        "workspace": ws,
        "data": web_report.build_report_json(bundle, recent) if bundle else None,
        "generated": {
            "xlsx_exists": (OUT_ROOT / week_id / f"{week_id}.xlsx").is_file(),
            "ppt_exists": (OUT_ROOT / week_id / f"{week_id}.pptx").is_file(),
            "xlsx_url": f"/api/download/{week_id}/{week_id}.xlsx",
            "ppt_url": f"/api/download/{week_id}/{week_id}.pptx",
        },
    }


@router.put("/api/workspace/{week_id}")
def put_workspace(week_id: str, ws: dict = Body(...)):
    if week_id not in _state and not history.week_exists(week_id, _db()):
        raise HTTPException(404, "请先上传")
    if not history.week_exists(week_id, _db()):
        history.save_week(week_id, _state[week_id][0], _state[week_id][1].overview, _db())
    saved = history.save_workspace(week_id, ws, _db())
    logger.info("保存 workspace week_id=%s keys=%s", week_id, list(ws.keys()))
    return saved


@router.post("/api/workspace/{week_id}/build")
def build_full(week_id: str, payload: dict = Body(default={})):
    if week_id not in _state:
        if history.week_exists(week_id, _db()):
            _ensure_state(week_id)
        else:
            raise HTTPException(404, "请先上传")
    df, bundle = _state[week_id]
    ws = history.load_workspace(week_id, _db())

    logger.info("Build 开始 week_id=%s 采购=%d 计划=%d",
                week_id,
                len(payload.get("procurement_items") or ws.get("procurement_items") or []),
                len(payload.get("plan_items") or ws.get("plan_items") or []))

    recent = history.get_recent_weeks(3, _db())
    os.makedirs("output", exist_ok=True)
    week_dir = OUT_ROOT / week_id
    week_dir.mkdir(parents=True, exist_ok=True)
    png_dir = week_dir / "png"

    t0 = time.perf_counter()
    pngs = render_all_pngs(bundle, recent, str(png_dir),
                        template_path=_tpath(payload))
    logger.info("PNG 渲染完成 week_id=%s 耗时=%.1fs charts=%d",
                week_id, time.perf_counter() - t0, len(pngs))

    week_meta = {"week_id": week_id,
                 "周起始日": str(df["订单日期"].min().date()),
                 "周结束日": str(df["订单日期"].max().date())}
    built_narratives = narratives_mod.build_narratives(bundle, week_meta)
    overrides = ws.get("narrative_overrides") or {}
    narratives = {k: (overrides.get(k) or built_narratives.get(k, ""))
                  for k in ("brand", "brand_share", "product", "new")}

    ai_texts_in = payload.get("ai_texts", {}) or {}
    ai_texts = {
        "week_compare": ai_texts_in.get("week_compare") or ws.get("content_md", ""),
        "daily_summary": ai_texts_in.get("daily_summary") or "",
        "procurement": "",
        "next_plan": "",
    }

    proc_items = payload.get("procurement_items") or ws.get("procurement_items") or []
    plan_items = payload.get("plan_items") or ws.get("plan_items") or []

    xlsx = str(week_dir / f"{week_id}.xlsx")
    build_excel(bundle, recent, ai_texts, proc_items, plan_items, xlsx)
    logger.info("Excel 生成 week_id=%s size=%.0fKB", week_id, os.path.getsize(xlsx) / 1024)

    pptx = str(week_dir / f"{week_id}.pptx")
    pngs["factory"] = pngs.get("factory") or pngs["three_weeks"]
    build_ppt(_tpath(payload),
              pngs, ai_texts, narratives, proc_items, plan_items, week_meta, pptx)
    logger.info("PPT 生成 week_id=%s size=%.0fKB 总耗时=%.1fs",
                week_id, os.path.getsize(pptx) / 1024, time.perf_counter() - t0)

    return {"ok": True,
            "xlsx_url": f"/api/download/{week_id}/{week_id}.xlsx",
            "ppt_url": f"/api/download/{week_id}/{week_id}.pptx"}


@router.get("/api/bundle/{week_id}.zip")
def download_bundle(week_id: str):
    if (week_id in ("", ".", "..") or "/" in week_id or "\\" in week_id):
        raise HTTPException(404)
    week_dir = (OUT_ROOT / week_id).resolve()
    try:
        week_dir.relative_to(OUT_ROOT)
    except ValueError:
        raise HTTPException(404)
    if not week_dir.is_dir():
        raise HTTPException(404)

    files = []
    for sub in week_dir.rglob("*"):
        if sub.is_file():
            files.append(sub)
    if not files:
        raise HTTPException(404, "本周尚未生成任何产物")
    logger.info("打包下载 week_id=%s files=%d", week_id, len(files))

    # Snapshot current wfreport.log + rotated backups into
    # logs/exports/YYYY_MM_DD_HH_MM_SS.log so the user gets a copy of
    # the log alongside the bundle. Done before zip so any further log
    # writes happen to the new rotated file.
    from datetime import datetime
    from backend.core.logging_conf import get_logger
    export_logger = get_logger("api.export")
    export_dir = Path("logs/exports")
    export_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    log_snapshot = export_dir / f"{ts}.log"
    log_files = []
    main_log = Path("logs/wfreport.log")
    if main_log.exists():
        log_files.append(main_log)
    # Rotated backups: wfreport.log.1, wfreport.log.2, wfreport.log.3
    for i in range(1, 4):
        rotated = Path(f"logs/wfreport.log.{i}")
        if rotated.exists():
            log_files.append(rotated)
    if log_files:
        try:
            with open(log_snapshot, "wb") as out:
                for lf in sorted(log_files):
                    out.write(b"\n===== " + str(lf).encode() + b" =====\n")
                    out.write(lf.read_bytes())
            logger.info("日志快照已导出 %s (%d 字节, %d 个源文件)",
                        log_snapshot, log_snapshot.stat().st_size, len(log_files))
            export_logger.info("log_export_ok path=%s bytes=%d sources=%d",
                               str(log_snapshot), log_snapshot.stat().st_size, len(log_files))
            files.append(log_snapshot)
        except OSError as e:
            logger.warning("日志快照导出失败 %s: %s", log_snapshot, e)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            arcname = f.name
            zf.write(f, arcname)
    buf.seek(0)
    from fastapi.responses import StreamingResponse
    logger.info("打包下载 DONE week_id=%s total_files=%d", week_id, len(files))
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": f"attachment; filename={week_id}-bundle.zip"})


# ===== Log export =====

@router.get("/api/logs/export")
def export_log_snapshot():
    """Manual snapshot of the current log file (for ops debugging
    without triggering a full build). File: logs/exports/<timestamp>.log"""
    from datetime import datetime
    export_dir = Path("logs/exports")
    export_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    out = export_dir / f"{ts}.log"
    main_log = Path("logs/wfreport.log")
    if not main_log.exists():
        raise HTTPException(404, "日志文件不存在")
    out.write_bytes(b"===== " + str(main_log).encode() + b" =====\n"
                     + main_log.read_bytes())
    logger.info("手动日志快照已导出 %s (%d 字节)", out, out.stat().st_size)
    from fastapi.responses import FileResponse
    return FileResponse(str(out),
                        headers={"Content-Disposition": f"attachment; filename={ts}.log"})
