# 王凡周报生成器

## 1. 项目简介

王凡周报生成器是一套面向供应链周报场景的本地工具：读取每周销售明细 Excel，自动完成清洗、派生、加权指标计算与多维度图表绘制，并一键产出包含原生图表的 Excel 报表与基于模板的 PPT 周报。配套 Web 界面支持上传、预览、AI 文案润色、采购与下周计划结构化，以及打包下载。所有数据与产物默认保存在本地（SQLite + `output/`），AI 调用在缺少 `MINIMAX_API_KEY` 时自动回退到占位文案，保证开箱可用。

## 2. 目录结构

```
wfreport/
├── backend/                      # Python 后端
│   ├── app/                      # FastAPI 入口与路由
│   │   ├── main.py               # app = FastAPI(...)
│   │   └── api.py                # 上传/预览/配置/AI/生成/下载
│   ├── core/                     # 业务核心
│   │   ├── parser.py             # Excel 读取 + 平台/week_id 派生
│   │   ├── metrics.py            # 加权指标计算（MetricsBundle）
│   │   ├── history.py            # SQLite 历史周数据
│   │   └── week.py               # ISO week_id
│   ├── charts/                   # 图表
│   │   ├── plotly_figures.py     # 11 张图（汇总/每日/品牌/平台/店铺/产品/新品/工厂…）
│   │   └── render_png.py         # 渲染为 PNG
│   ├── reports/                  # 报表生成
│   │   ├── excel_builder.py      # 原生图表 Excel
│   │   ├── ppt_builder.py        # 模板填充 + 自动分页 PPT
│   │   └── web_report.py         # 前端预览 JSON
│   ├── ai/                       # MiniMax 客户端 + prompt 模板
│   │   ├── client.py             # 无 key 自动 fallback
│   │   └── prompts.py            # 热加载 prompts.yaml
│   ├── config/                   # 配置（可编辑）
│   │   ├── settings.yaml         # 数据库/AI/模板路径
│   │   ├── platform_map.yaml     # 店铺前缀 → 平台
│   │   └── prompts.yaml          # 4 处 AI prompt（热加载）
│   └── requirements.txt
├── frontend/                     # Vue3 + Vite
│   ├── src/
│   │   ├── App.vue
│   │   ├── api.js
│   │   └── components/
│   │       ├── UploadPage.vue    # 上传本周 Excel
│   │       ├── PreviewPage.vue   # 图表/数据预览
│   │       ├── ConfigPage.vue    # prompt 编辑（热生效）
│   │       └── GeneratePage.vue  # 采购/下周计划/一键生成/下载
│   └── package.json
├── tests/                        # pytest 单元 + 集成测试
├── resource/                     # 样例输入与 PPT 模板
│   ├── 本周.xlsx
│   ├── 上周.xlsx
│   └── 2026年第二十七周周报-王凡.pptx
├── data/                         # SQLite（wfreport.db，自动创建）
├── output/                       # 产物根目录（<week_id>/xlsx+pptx+png）
├── .env.example
└── README.md
```

## 3. 环境与安装

- **Python**：3.12（推荐）
- **Node.js**：18+（用于前端构建）

```bash
# 后端依赖
pip install -r backend/requirements.txt

# 前端依赖
npm --prefix frontend install
```

> 图表渲染依赖 `kaleido`（已包含在 requirements.txt）。首次执行 PNG 渲染可能略慢，属正常现象。

## 4. 配置

### 4.1 环境变量

```bash
cp .env.example .env
```

编辑 `.env` 填入**至少一个** AI provider 的 key。默认 `MiniMax`，也可以使用 **DeepSeek** 或 **Kimi (Moonshot)**——三者的 API 均兼容 OpenAI `/chat/completions`，运行时可在前端下拉框切换。

```
MINIMAX_API_KEY=sk-xxxxxxxxxxxxxxxx
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
KIMI_API_KEY=sk-xxxxxxxxxxxxxxxx
```

DeepSeek 的 `deepseek-v4-flash` / `v4-pro` 支持通过 `thinking.type=disabled` 关闭思考模式（前端开关控制，节省 token）；Kimi 同样支持思考模式控制。未填写时，AI 文案将自动回退到占位文本，不会阻塞流程。

### 4.2 YAML 配置（可选自定义）

`backend/config/` 下三份 YAML 均可在运行前手工编辑：

- `settings.yaml`：`db_path`、`output_dir`、`template_path`、AI `base_url/model/temperature/timeout_seconds`。
- `platform_map.yaml`：店铺前缀（按 `-` 切分第 0 段）→ 平台名映射；未命中归入「其他」。
- `prompts.yaml`：4 处 AI prompt 模板（`week_compare`、`daily_summary`、`procurement`、`next_plan`）。

**Prompt 热加载**：在前端「配置页」可直接编辑并保存 prompt，后端立即重载，无需重启服务。

## 5. 运行

### 后端（FastAPI + Uvicorn）

```bash
uvicorn backend.app.main:app --reload
```

默认地址 http://localhost:8000 ，API 前缀统一为 `/api`。

### 前端（Vite 开发服务器）

```bash
npm --prefix frontend run dev
```

默认地址 http://localhost:5173 ，开发模式已开启热更新。

## 6. 使用流程

1. **上传**：在「上传」页选择本周销售明细 Excel（如 `resource/本周.xlsx`），系统自动解析、派生平台与 `week_id`，并把当周写入 SQLite 历史。
2. **预览**：在「预览」页查看汇总、每日、品牌、平台、店铺热力、产品热力、新品、工厂等图表，以及最近三周对比表。
3. **配置 prompt**（可选）：在「配置」页调整 4 处 AI prompt 并保存，立即热生效。
4. **生成**：在「生成」页填写采购要点与下周计划（可用 AI 润色结构化为表格行），点击「一键生成」。
5. **下载**：生成完成后下载 Excel（含原生图表，多 sheet）与 PPT（基于模板、采购自动分页）到本地，文件位于 `output/<week_id>/`。

## 7. 计算口径说明

为保证不同维度下的口径一致、避免「行级毛利率再平均」的失真，所有汇总一律采用**加权法**：

| 指标 | 公式 |
|------|------|
| 毛利率（任意维度 D） | `Σ销售毛利 / Σ销售金额` |
| 销售额（D） | `Σ销售金额` |
| 销售数量（D） | `Σ销售数量` |
| 销售毛利（D） | `Σ销售毛利` |

> 不使用「逐行毛利率再算术平均」的口径。无论是全表、某品牌、某平台、某店铺、某产品、某工厂，均按上述加权法在聚合后一次计算。

其他派生规则：

- **平台派生**：店铺名称按 `-` 切分，取第 0 段作为前缀，在 `platform_map.yaml` 中查找；未命中白名单的归入「其他」。
- **week_id**：取上传数据中**起始订单日期**所属的 ISO 周，格式 `YYYY-Www`（例如 `2026-W27`）。
- **TOP 排名**：店铺 TOP15、产品 TOP15、工厂 TOP5 一律按 `Σ销售数量` 降序选取。
- **数量占比**：某品牌/平台 `销售数量 / 全表销售数量`。

## 8. 历史数据

- 存储后端：SQLite，默认路径 `data/wfreport.db`（首次运行自动创建）。
- 写入策略：以 `week_id` 为主键，**同一周再次上传会覆盖**（先删后插）。
- 支持查询：
  - **上周对比**：取小于当前 `week_id` 的最近一周，用于环比文案。
  - **近三周**：取最近 3 周（含本周）汇总，用于概览页与三周对比表。

## 测试

```bash
# 仅集成测试
python -m pytest tests/test_integration.py -v

# 全量测试
python -m pytest -v
```

集成测试会在 `tmp_path` 下完整跑通：`load_excel → compute_all → render_all_pngs → build_excel → build_ppt`，校验 PNG 键集合、Excel sheet 与原生图表、PPT 页数 ≥ 19。
