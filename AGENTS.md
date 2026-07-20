# AGENTS.md

面向 AI 编码代理的项目指南。动手改代码或跑命令之前先读完本文件。

## 项目概览

**王凡周报生成器**：面向供应链周报场景的本地单用户工具。读取每周销售明细 Excel，自动完成清洗、平台/week_id 派生、加权指标计算与多维度图表绘制，一键产出含原生图表的 Excel 报表和基于模板的 PPT 周报。配套 Web 界面支持上传、预览、AI 文案润色、采购与下周计划结构化、打包下载。数据存本地 SQLite（`data/wfreport.db`），产物写入 `output/<week_id>/`。

## 技术栈与架构

两个包，命令一律从**仓库根目录**执行：

- `backend/` — Python 3.12 + FastAPI，**环境由 uv 管理**（根目录 `pyproject.toml` 声明依赖 + `uv.lock` 锁定 + `.python-version` 钉 3.12，`uv sync` 一键建 `.venv`）。**导入根是仓库根目录**（不是 `backend/`），导入形式为 `from backend.core.metrics import ...`。根目录的空 `conftest.py` 负责把仓库根锚进 `sys.path`（`pyproject.toml` 只做 uv 依赖管理，不含 pytest 配置）。
- `frontend/` — Vue 3 + Vite + Plotly.js（`plotly.js-dist-min`）+ axios。所有 npm 命令需加 `--prefix frontend`。

运行时架构：

- 后端入口 `backend/app/main.py`（`uvicorn backend.app.main:app`），API 统一前缀 `/api`，路由在 `backend/app/api.py`。
- 开发模式：uvicorn 跑 :8000，vite dev server 跑 :5173（`vite.config.js` 配了 `/api` 代理；`frontend/src/api.js` 在 DEV 下直接请求 `http://localhost:8000`）。
- 生产模式：uvicorn 同一进程通过 `StaticFiles` 直接托管 `frontend/dist`（`main.py` 检测 dist 存在才挂载，否则 API-only）。
- 指标核心 `backend/core/metrics.py:compute_all` 返回 `MetricsBundle`（dataclass），其字段名是 charts/reports/api 三方的硬契约，不要随意改名。
- 应用状态 `_state` 在内存中（单用户工具的有意设计）；历史周数据以 `week_id` 为主键存 SQLite，同一周重复上传先删后插（覆盖）。
- 日志：`backend/core/logging_conf.py`，控制台 + 轮转文件 `logs/wfreport.log`（10 MB × 3）。

## 安装 / 运行 / 构建

```bash
# 安装（需要 uv；Python 3.12 由 uv 自动下载，无需系统预装）
uv sync                            # 按 uv.lock 建 .venv 并装依赖（含 dev 组的 pytest）
npm --prefix frontend install

# 一键开发环境（推荐）：起 :8000 + :5173，日志在 /tmp/wfreport-{backend,frontend}.log
bash run.sh                # 前台阻塞，Ctrl-C 停止
bash run.sh --detached     # 后台启动；配合 --logs / --stop
bash run.sh --check        # 环境自检（python/node/.env/依赖）
bash run.sh --install      # 只装依赖
bash run.sh --test [dir]   # 跑 pytest 子集（默认 tests/core）

# 手动起开发服务（两个终端）
uv run uvicorn backend.app.main:app --reload --port 8000
npm --prefix frontend run dev

# 前端构建
npm --prefix frontend run build
```

## 测试（重要：有坑）

- **不要在单次 pytest 调用里跑全量套件**——会挂起数分钟。原因是 `kaleido`（经 chromium 子进程导出 PNG）在同一进程内被跨文件调用多次时死锁。代码本身没问题。
- **本机跑 charts/reports/集成测试前必须备好 kaleido 的 Chrome 环境**（Docker 镜像已内置，本机需手动）：
  1. Chrome 依赖库：`libxkbcommon.so.0`、`libgbm.so.1`（本机已放在 `~/.local/chrome-libs/usr/lib/x86_64-linux-gnu`）。
  2. 环境变量：`BROWSER_PATH=<chrome 二进制路径>`（choreographer/kaleido 1.x 读这个变量；本机可用 puppeteer 缓存的 `~/.cache/puppeteer/chrome/*/chrome-linux64/chrome`）+ `LD_LIBRARY_PATH=~/.local/chrome-libs/usr/lib/x86_64-linux-gnu`。
  3. **CJK 字体**：系统需有任意中文字体，否则 PNG 里中文全是豆腐块。本机已装 `~/.local/share/fonts/NotoSansSC.otf`（jsdelivr 下载）+ `fc-cache`。
- **按目录/子集分开跑**，每个子集都能干净结束：

```bash
uv run pytest tests/core -v
uv run pytest tests/charts tests/reports -v
uv run pytest tests/app tests/ai -v
uv run pytest tests/test_integration.py -v   # 集成：load_excel→compute_all→render_all_pngs→build_excel→build_ppt
```

- 集成/charts 测试较慢（kaleido 首次导出约 10–20s，另有 18.8k 行数据插入）。
- 需要隔离数据库的测试用 `monkeypatch.setenv("WFREPORT_DB_PATH", <tmp>)`（`backend/app/api.py` 读取该环境变量），不会碰真实的 `data/wfreport.db`。

## Docker 部署

根目录 `Dockerfile`（两阶段）+ `docker-compose.yml`：

- 阶段 1 用 node:20 构建 `frontend/dist`；阶段 2 是 python:3.12-slim 运行时。
- 阶段 2 用 uv（`COPY --from=ghcr.io/astral-sh/uv`）按 `pyproject.toml` + `uv.lock` 执行 `uv sync --frozen --no-dev` 装依赖，`.venv/bin` 加入 `PATH`。
- 镜像内安装 **chromium + Noto CJK 中文字体**（kaleido 导出中文 PNG 必须），并用 `KALEIDO_CHROME_PATH=/usr/bin/chromium` 指向系统 chromium。
- compose 挂载 `./data`、`./output`、`./logs`（读写）和 `./.env`、`./resource`（只读），端口 8000，健康检查打 `/api/ai/providers`。

## 配置与密钥

- `.env`（已被 `.gitignore` 忽略）经 `python-dotenv` 在 `backend/app/main.py` 加载，模板见 `.env.example`。
- **三家 AI provider**：`MINIMAX_API_KEY` / `DEEPSEEK_API_KEY` / `KIMI_API_KEY`，至少填一个。三者均兼容 OpenAI `/chat/completions`，注册表在 `backend/config/settings.yaml` 的 `ai.providers` 下，运行时可在前端下拉框切换；DeepSeek/Kimi 支持 thinking 开关。**缺 key 不报错**——AI 调用自动回退占位文案（见 `backend/ai/client.py`）。
- `backend/config/` 三份 YAML 可手工编辑：
  - `settings.yaml`：`db_path` / `output_dir` / `template_path` / AI provider 配置。
  - `platform_map.yaml`：店铺前缀（按 `-` 切分第 0 段）→ 平台名；未命中归「其他」。
  - `prompts.yaml`：4 处 AI prompt（`week_compare`、`daily_summary`、`procurement`、`next_plan`），前端配置页可编辑保存，后端热加载，无需重启。
- CORS 为 `allow_origins=["*"]`——定位为内部单用户工具，不要据此暴露到公网。

## 业务口径（不能搞错的硬规则）

- **毛利率一律加权**：`Σ销售毛利 / Σ销售金额`（按分组聚合后一次计算）。绝不对行级 `销售毛利率` 取算术平均（会偏 ~0.5pp）。样例周全表毛利率 50.1%。
- **`week_id` 每次上传只有一个值** = `df["订单日期"].min()`（起始日期）所属 ISO 周，格式 `YYYY-Www`。不要逐行算——一周数据可能跨两个 ISO 周，但业务上是一周。
- **平台派生**：`店铺` 按 `-` 切分取第 0 段，查 `platform_map.yaml`，未命中 → 「其他」。
- **TOP 排名**：店铺 TOP15、产品 TOP15、工厂 TOP5 一律按 `Σ销售数量` 降序。
- 样例数据：`resource/上周.xlsx` 16 列（无 `是否新品`），`resource/本周.xlsx` 17 列，`resource/下周.xlsx` 15 列（聚合口径：`渠道`/`日期`、无 `线上订单号`/`是否新品`）。`parser.load_excel` 统一归一：`渠道→店铺`、`日期→订单日期`、缺 `线上订单号` 补 `SYN-<i>`、缺 `是否新品` 补「否」——下游（metrics/history）不需要再判空。指标只对新上传的当周文件计算。

## 输出物与图表引擎

- **Plotly 是唯一权威图表引擎**：Web 端交互渲染（`backend/reports/web_report.py`），PPT 用图经 `backend/charts/render_png.py` 由 kaleido 导出 PNG。图集合固定 **12 个 key**：`overview, daily, brand_combo, brand_pie, platform, shop_heatmap, product_horizontal, product_table, product_heatmap, new_products, three_weeks, factory`。
- **Excel**（`backend/reports/excel_builder.py`）用 **xlsxwriter 原生图表**（可编辑对象，不是图片）——目前只有「汇总」combo 图，分 sheet 图表是已知后续项。
- **PPT**（`backend/reports/ppt_builder.py`）填充模板 `resource/2026年第二十七周周报-王凡.pptx`：按 slide 替换 PICTURE/TEXT/TABLE 形状；**新品页按 `has_new_products` 条件生成**（调用方传 `len(bundle.new_products) > 0`）——有新品时复制第 9 页、改标题「销售表现-新品分析」并用 `move_slide` 插到「下周规划」分隔页之前，无新品时整页不生成；采购表自动分页且序号连续，增页插入采购区块内（不会跑到 THANKS 后），**0 条采购保底留 1 页空表**。注意：新增 slide 必须先于任何删除做（python-pptx 按 `len(slides)+1` 分配 partname，先删后加会撞名产生 duplicate zip 条目）。形状名已对真实模板核对过（有 `tests/reports/test_ppt_shape_names.py` 守护），改名字前先查模板文件。
- **产物/布局自检脚本** `scripts/gen_check.py`（非 pytest）：`uv run python scripts/gen_check.py` 用三周样例数据生成 PPT+PNG 到 `/tmp/wfcheck/`，检查 zip duplicate 条目与形状越界（分隔页背景图是满版出血设计，越界属正常）。

## 代码组织速查

- `backend/core/` — `parser.py`（Excel 读取 + 平台/week_id 派生）、`metrics.py`（MetricsBundle）、`history.py`（SQLite）、`week.py`、`logging_conf.py`
- `backend/charts/` — `plotly_figures.py`（12 张图）、`render_png.py`
- `backend/reports/` — `excel_builder.py`、`ppt_builder.py`、`web_report.py`（前端预览 JSON）、`narratives.py`
- `backend/ai/` — `client.py`（多 provider + fallback）、`prompts.py`（热加载 prompts.yaml）
- `backend/app/` — `main.py`（FastAPI 装配）、`api.py`（全部路由：上传/预览/workspace/AI/生成/下载/历史/日志导出）
- `frontend/src/components/` — UploadPage / PreviewPage / ConfigPage / GeneratePage / HistoryPage / SettingsPage 等

## 开发约定

- 除非被要求，**不给代码加注释**。
- 设计与计划文档在 `docs/superpowers/`（`specs/` 与 `plans/`，设计定稿后冻结）。
- `resource/`（样例 Excel + PPT 模板）已被 git 跟踪；`data/*.db`、`output/*`、`.env`、`frontend/dist/` 在 `.gitignore` 中。
- 前端无 lint/test 脚本，验证方式是 `npm --prefix frontend run build` 能过。
- 提交时显式 `git add` 具体文件，避免误带未跟踪的本地笔记/密钥文件。
