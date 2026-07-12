# tests/reports/test_ppt_builder.py
import os, tempfile, base64
from pptx import Presentation
from backend.reports.ppt_builder import build_ppt

_VALID_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _pngs(d):
    paths = {}
    for name in ["overview", "daily", "brand_combo", "brand_pie", "platform",
                 "shop_heatmap", "product_combo", "product_heatmap", "new_products",
                 "three_weeks", "factory"]:
        p = os.path.join(d, name + ".png")
        with open(p, "wb") as f:
            f.write(_VALID_PNG)
        paths[name] = p
    return paths


def test_build_ppt_smoke():
    d = tempfile.mkdtemp()
    out = build_ppt(
        template_path="resource/2026年第二十七周周报-王凡.pptx",
        png_paths=_pngs(d),
        ai_texts={"week_compare": "本周概况测试", "daily_summary": "每日测试"},
        narratives={"brand": "品牌叙述", "product": "产品叙述", "new": "新品叙述"},
        procurement_items=[{"事项内容": "测试采购", "进度及责任人": ["a", "b"],
                            "状态": "已完成", "完成时间": "7月9日"}] * 6,
        plan_items=[{"事项内容": "测试计划", "提出时间": "7月10日",
                     "次周预计完成节点名称": "节点", "涉及部门": "供应链"}] * 5,
        week_meta={"week_id": "2026-W27", "周起始日": "2026-07-03", "周结束日": "2026-07-09"},
        out_path=os.path.join(d, "r.pptx"),
    )
    assert os.path.exists(out)
    prs = Presentation(out)
    assert len(prs.slides) >= 19  # 原始18 + 复制页9'
