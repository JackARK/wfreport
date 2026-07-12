import os
from pathlib import Path

import yaml
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

from backend.ai import client as ai_client, prompts as ai_prompts
from backend.charts.render_png import render_all_pngs
from backend.core import parser, history, metrics
from backend.core.week import week_range
from backend.reports import web_report
from backend.reports.excel_builder import build_excel
from backend.reports.ppt_builder import build_ppt

router = APIRouter()
_state = {}  # week_id -> (df, bundle)
_CFG = Path(__file__).resolve().parents[1] / "config" / "settings.yaml"
OUT_ROOT = Path("output").resolve()


def _db():
    env = os.getenv("WFREPORT_DB_PATH")
    if env:
        return env
    with open(_CFG, encoding="utf-8") as f:
        return yaml.safe_load(f)["db_path"]


@router.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    safe_name = os.path.basename(file.filename or "").replace("..", "").strip()
    if not safe_name:
        safe_name = "upload.xlsx"
    tmp = os.path.join("output", safe_name)
    os.makedirs("output", exist_ok=True)
    with open(tmp, "wb") as f:
        f.write(await file.read())
    df = parser.load_excel(tmp)
    wid = df["week_id"].iloc[0]
    bundle = metrics.compute_all(df)
    history.init_db(_db())
    history.save_week(wid, df, bundle.overview, _db())
    _state[wid] = (df, bundle)
    start, end = week_range(df)
    return {"week_id": wid, "rows": len(df),
            "周起始日": str(start.date()), "周结束日": str(end.date())}


@router.post("/api/preview/{week_id}")
def preview(week_id: str):
    if week_id not in _state:
        raise HTTPException(404, "请先上传")
    _, bundle = _state[week_id]
    recent = history.get_recent_weeks(3, _db())
    return web_report.build_report_json(bundle, recent)


@router.get("/api/history")
def history_api():
    return {"recent": history.get_recent_weeks(3, _db())}


@router.post("/api/ai/{section}")
def ai_section(section: str, payload: dict):
    if section in ("procurement", "next_plan"):
        items = ai_client.generate_json(section, {"user_input": payload.get("input", "")})
        return {"items": items}
    text = ai_client.generate_section(section, payload.get("vars", {}))
    return {"text": text}


@router.get("/api/config/prompts")
def get_prompts():
    return ai_prompts.load()


@router.put("/api/config/prompts")
def put_prompts(body: dict):
    p = Path(__file__).resolve().parents[1] / "config" / "prompts.yaml"
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump(body, f, allow_unicode=True)
    ai_prompts.reload()
    return ai_prompts.load()


@router.post("/api/generate/{week_id}")
def generate(week_id: str, payload: dict):
    if week_id not in _state:
        raise HTTPException(404, "请先上传")
    df, bundle = _state[week_id]
    recent = history.get_recent_weeks(3, _db())
    os.makedirs("output", exist_ok=True)
    pngs = render_all_pngs(bundle, recent, os.path.join("output", week_id, "png"))
    ai_texts = payload.get("ai_texts", {})
    procurement_items = payload.get("procurement_items", [])
    plan_items = payload.get("plan_items", [])
    narratives = payload.get("narratives", {})
    week_meta = {"week_id": week_id,
                 "周起始日": str(df["订单日期"].min().date()),
                 "周结束日": str(df["订单日期"].max().date())}
    xlsx = os.path.join("output", week_id, f"{week_id}.xlsx")
    build_excel(bundle, recent, ai_texts, xlsx)
    pptx = os.path.join("output", week_id, f"{week_id}.pptx")
    pngs["factory"] = pngs.get("factory") or pngs["three_weeks"]
    build_ppt(payload.get("template_path", "resource/2026年第二十七周周报-王凡.pptx"),
              pngs, ai_texts, narratives, procurement_items, plan_items, week_meta, pptx)
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
