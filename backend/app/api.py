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
from backend.reports import narratives as narratives_mod
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


def _week_compare_vars(payload: dict) -> dict:
    week_id = payload.get("week_id")
    if week_id not in _state:
        raise HTTPException(404, "请先上传")
    _, bundle = _state[week_id]
    cur_amt = float(bundle.overview["销售金额"])
    cur_prof = float(bundle.overview["销售毛利"])
    cur_marg = float(bundle.overview["销售毛利率"]) * 100  # percent
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


@router.post("/api/ai/{section}")
def ai_section(section: str, payload: dict):
    if section in ("procurement", "next_plan"):
        items = ai_client.generate_json(section, {"user_input": payload.get("input", "")})
        return {"items": items}
    if section == "week_compare":
        return {"text": ai_client.generate_section("week_compare", _week_compare_vars(payload))}
    if section == "daily_summary":
        return {"text": ai_client.generate_section("daily_summary", _daily_summary_vars(payload))}
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
    week_meta = {"week_id": week_id,
                 "周起始日": str(df["订单日期"].min().date()),
                 "周结束日": str(df["订单日期"].max().date())}
    # Narratives: stitch server-side from the bundle; client values win only if non-empty.
    built_narratives = narratives_mod.build_narratives(bundle, week_meta)
    client_narratives = payload.get("narratives", {}) or {}
    narratives = {k: (client_narratives.get(k) or built_narratives.get(k, ""))
                  for k in ("brand", "brand_share", "product", "new")}
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
