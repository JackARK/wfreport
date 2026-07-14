# AGENTS.md

Compact guidance for OpenCode sessions working in this repo. Read this before running commands.

## Layout

Two packages, run from the **repo root** (`C:\Users\jack\Documents\codes\wfreport`):
- `backend/` — Python 3.12 + FastAPI. The import root is the repo root (not `backend/`), so imports look like `from backend.core.metrics import ...`. Empty root `conftest.py` anchors `sys.path` for tests.
- `frontend/` — Vue 3 + Vite + Plotly.js. All npm commands need `--prefix frontend`.

Entry points: backend app `backend/app/main.py` (`uvicorn backend.app.main:app`); metric core `backend/core/metrics.py:compute_all` returns a `MetricsBundle` whose field names are a hard contract used by charts/reports/api.

## Commands

```pwsh
# install
pip install -r backend/requirements.txt
npm --prefix frontend install

# dev servers (two terminals)
uvicorn backend.app.main:app --reload --port 8000   # API on :8000
npm --prefix frontend run dev                        # UI on :5173 (api.js hardcodes http://localhost:8000)

# build
npm --prefix frontend run build

# tests — see the test gotcha below before running pytest
python -m pytest tests/core tests/ai -v             # run a subset
python -m pytest tests/reports/test_ppt_builder.py::test_build_ppt_smoke -v   # single test
```

## Test gotcha (important)

Running the **whole** suite in one `pytest` invocation hangs (~minutes) because `kaleido` (PNG export via a chromium subprocess) deadlocks when invoked many times across files in one process. The code is fine — **run tests per directory/subset** (e.g. `tests/core`, `tests/charts`, `tests/reports`, `tests/app`, `tests/test_integration.py`). Each subset finishes cleanly.

Other test facts:
- Tests run from repo root; no `pyproject.toml`/`pytest.ini` — root `conftest.py` is what puts the repo root on `sys.path`.
- Integration/charts tests are slow (kaleido + 18.8k-row inserts). `kaleido`'s first export takes ~10–20s.
- Hermetic tests set `WFREPORT_DB_PATH=<tmp>` (monkeypatch) so they don't touch the real `data/wfreport.db`.

## Environment / secrets

- `.env` holds `MINIMAX_API_KEY`; loaded by `python-dotenv` (`load_dotenv()` in `backend/app/main.py`). Without the key the app still runs — AI calls fall back to placeholder text (never raise).
- **`需求描述.md` and `resource/` are untracked but NOT in `.gitignore`.** Never `git add -A` — `需求描述.md` contains a live API key. Stage files explicitly. Ideally rotate that key and remove it from the file.

## Hard-won business rules (don't get these wrong)

- **毛利率 (margin) is always weighted**: `Σ销售毛利 / Σ销售金额` per group. Never take the row-level `销售毛利率` mean (off by ~0.5pp). Overview is 50.1% on the sample week.
- **`week_id` is one value per upload** = ISO week of `df["订单日期"].min()` (start date). Do NOT compute it per-row — a week's data spans two ISO weeks but is one business week.
- **`平台`** = first segment of `店铺` split on `-`, mapped via `backend/config/platform_map.yaml`; unmapped → `其他`.
- **TOP rankings** (`店铺`/`产品` TOP15, `工厂` TOP5) are by `Σ销售数量` desc.
- Sample data: `resource/上周.xlsx` has **16 cols (no `是否新品`)**; `resource/本周.xlsx` has **17**. Metrics run only on freshly uploaded (current-week) files.

## Outputs / chart engines

- **Plotly** is the authoritative chart engine: figures render interactive on the web (`reports/web_report.py`) and export to PNG via `kaleido` for the PPT (`charts/render_png.py`). 11 figure keys including `factory`.
- **Excel** uses `xlsxwriter` **native charts** (editable objects, not images) — currently only the `汇总` combo chart (per-sheet charts are a known fast-follow).
- **PPT** (`reports/ppt_builder.py`) fills the template `resource/2026年第二十七周周报-王凡.pptx`: replaces PICTURE/TEXT/TABLE shapes by slide, duplicates slide 9 → 9' for new products, and auto-paginates procurement tables with continuous 序号. Shape names were verified against the real template — don't rename them without checking the file.

## Conventions

- Comments are not added to code unless requested.
- `CORS` is `allow_origins=["*"]` and `_state` is in-memory — intended for an internal single-user tool.
- Spec & plan live under `docs/superpowers/` (frozen after design); SDD scratch under `.superpowers/sdd/` (gitignored).
