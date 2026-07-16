import os
import zipfile
import io
from pathlib import Path

import yaml
from fastapi import APIRouter, UploadFile, File, HTTPException, Body
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


@router.get("/api/history/all")
def history_all():
    """Every persisted week_id with its workspace summary and output file status.
    Powers the frontend history page; lets the user re-open a previous week
    without re-uploading anything."""
    return {"weeks": history.list_weeks_with_files(_db(), OUT_ROOT)}


def _ensure_state(week_id: str):
    """Rebuild _state for week_id from SQLite if the in-memory copy was lost
    (e.g. backend restarted). Returns True on success."""
    if week_id in _state:
        return True
    df = history.load_orders_as_df(week_id, _db())
    if df is None or len(df) == 0:
        return False
    bundle = metrics.compute_all(df)
    _state[week_id] = (df, bundle)
    return True


@router.post("/api/workspace/{week_id}/reload")
def reload_state(week_id: str):
    """Reconstruct in-memory state from SQLite weekly_orders. Used after a
    backend restart (or when the user opens a historical week that hasn't
    been loaded this session)."""
    if not history.week_exists(week_id, _db()):
        raise HTTPException(404, "该周数据未持久化到 SQLite")
    if not _ensure_state(week_id):
        raise HTTPException(500, "重算 _state 失败")
    return {"ok": True, "week_id": week_id, "rows": int(len(_state[week_id][0]))}


@router.get("/api/workspace/{week_id}/export.json")
def export_workspace_json(week_id: str):
    """Download the saved workspace (content + plans + AI overrides) for a
    week so users can back up or share their notes outside the app."""
    ws = history.load_workspace(week_id, _db())
    from fastapi.responses import JSONResponse
    return JSONResponse(ws, headers={
        "Content-Disposition": f"attachment; filename={week_id}-workspace.json"
    })


@router.post("/api/ai/parse_workspace/{week_id}")
def parse_workspace(week_id: str, payload: dict = Body(default={})):
    """Read this-week's freeform text + next-week's freeform plan,
    call the AI twice (procurement parser + next_plan parser), persist the
    structured rows + the raw text, and return the full workspace.

    Step-2 just shows two textareas; users type whatever prose they want.
    One click here does the heavy lifting - everything downstream (step 3
    preview, step 4 build, the PPT/Excel) consumes the parsed rows.
    """
    if week_id not in _state:
        if history.week_exists(week_id, _db()):
            _ensure_state(week_id)
        else:
            raise HTTPException(404, "请先上传")

    content   = (payload.get("content")   or "").strip()
    plan_text = (payload.get("plan_text") or "").strip()
    provider  = (payload.get("provider") or "").strip() or None
    thinking  = (payload.get("thinking") or "").strip() or None

    # Call AI (with key-fallback to []/placeholder in client.generate_json).
    proc_items = ai_client.generate_json(
        "procurement", {"user_input": content},
        provider=provider, thinking=thinking,
    ) if content else []

    plan_items = ai_client.generate_json(
        "next_plan", {"user_input": plan_text},
        provider=provider, thinking=thinking,
    ) if plan_text else []

    # Persist the raw text + parsed rows in one shot.
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
    provider = (payload.get("provider") or "").strip() or None
    thinking = (payload.get("thinking") or "").strip() or None
    if section in ("procurement", "next_plan"):
        items = ai_client.generate_json(
            section, {"user_input": payload.get("input", "")},
            provider=provider, thinking=thinking,
        )
        return {"items": items}
    if section == "week_compare":
        return {"text": ai_client.generate_section("week_compare", _week_compare_vars(payload), provider=provider, thinking=thinking)}
    if section == "daily_summary":
        return {"text": ai_client.generate_section("daily_summary", _daily_summary_vars(payload), provider=provider, thinking=thinking)}
    text = ai_client.generate_section(section, payload.get("vars", {}), provider=provider, thinking=thinking)
    return {"text": text}


@router.get("/api/ai/providers")
def ai_providers():
    """List configured AI providers for the UI dropdown.
    Each entry exposes only safe metadata (no secrets); has_key tells the
    UI whether to mark the provider as available / warn the user.
    """
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
    build_excel(bundle, recent, ai_texts, procurement_items, plan_items, xlsx)
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


# ===== Workflow / Workspace endpoints =====

@router.get("/api/workspace/{week_id}")
def get_workspace(week_id: str):
    """Combined view for step 3 (preview): returns data + user-entered workspace."""
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
    """Save user-entered content + plan + AI narrative overrides."""
    if week_id not in _state and not history.week_exists(week_id, _db()):
        raise HTTPException(404, "请先上传")
    if not history.week_exists(week_id, _db()):
        # touch summary row so FK succeeds if raw state lost
        history.save_week(week_id, _state[week_id][0], _state[week_id][1].overview, _db())
    saved = history.save_workspace(week_id, ws, _db())
    return saved


@router.post("/api/workspace/{week_id}/build")
def build_full(week_id: str, payload: dict = Body(default={})):
    """Step 4 trigger: render PNGs, build xlsx, build pptx using current workspace state."""
    if week_id not in _state:
        if history.week_exists(week_id, _db()):
            _ensure_state(week_id)
        else:
            raise HTTPException(404, "请先上传")
    df, bundle = _state[week_id]
    ws = history.load_workspace(week_id, _db())

    recent = history.get_recent_weeks(3, _db())
    os.makedirs("output", exist_ok=True)
    week_dir = OUT_ROOT / week_id
    week_dir.mkdir(parents=True, exist_ok=True)
    png_dir = week_dir / "png"
    pngs = render_all_pngs(bundle, recent, str(png_dir))

    week_meta = {"week_id": week_id,
                 "周起始日": str(df["订单日期"].min().date()),
                 "周结束日": str(df["订单日期"].max().date())}
    built_narratives = narratives_mod.build_narratives(bundle, week_meta)
    overrides = ws.get("narrative_overrides") or {}
    narratives = {k: (overrides.get(k) or built_narratives.get(k, ""))
                  for k in ("brand", "brand_share", "product", "new")}

    # ai_texts come from payload (caller asks AI live from step 3) but fall back to persisted content
    ai_texts_in = payload.get("ai_texts", {}) or {}
    ai_texts = {
        "week_compare": ai_texts_in.get("week_compare") or ws.get("content_md", ""),
        "daily_summary": ai_texts_in.get("daily_summary") or "",
        "procurement": "",
        "next_plan": "",
    }

    # plans come from persisted workspace
    proc_items = payload.get("procurement_items") or ws.get("procurement_items") or []
    plan_items = payload.get("plan_items") or ws.get("plan_items") or []

    xlsx = str(week_dir / f"{week_id}.xlsx")
    pptx = str(week_dir / f"{week_id}.pptx")
    build_excel(bundle, recent, ai_texts, proc_items, plan_items, xlsx)
    pngs["factory"] = pngs.get("factory") or pngs["three_weeks"]
    build_ppt(payload.get("template_path", "resource/2026年第二十七周周报-王凡.pptx"),
              pngs, ai_texts, narratives, proc_items, plan_items, week_meta, pptx)

    return {"ok": True,
            "xlsx_url": f"/api/download/{week_id}/{week_id}.xlsx",
            "ppt_url": f"/api/download/{week_id}/{week_id}.pptx"}


@router.get("/api/bundle/{week_id}.zip")
def download_bundle(week_id: str):
    """Bundle all generated artifacts + raw xlsx copy into a single zip."""
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
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            arcname = f.name  # basename only (avoid zip-slip)
            zf.write(f, arcname)
    buf.seek(0)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": f"attachment; filename={week_id}-bundle.zip"})
