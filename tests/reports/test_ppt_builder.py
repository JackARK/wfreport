# tests/reports/test_ppt_builder.py
import os, tempfile, base64
from pptx import Presentation
from backend.reports.ppt_builder import build_ppt

_VALID_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_A_TR = f"{{{_A}}}tr"
_A_TCPR = f"{{{_A}}}tcPr"
_A_RPR = f"{{{_A}}}rPr"
_A_ENDPARARPR = f"{{{_A}}}endParaRPr"
_FILL_LOCALS = {"solidFill", "gradFill", "blipFill", "pattFill", "grpFill"}


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


def _localname(el):
    tag = el.tag
    return tag.rpartition("}")[2] if isinstance(tag, str) and "}" in tag else (tag or "")


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

    # 验证采购表(页12)列对齐: col0=序号, col1=事项内容, col4=完成时间
    table = None
    for sh in prs.slides[12].shapes:
        if sh.has_table:
            table = sh.table
            break
    assert table is not None, "页12 未找到表格"
    assert table.cell(1, 0).text == "1", f"序号列错误: {table.cell(1, 0).text!r}"
    assert table.cell(1, 1).text == "测试采购", f"事项内容列错误: {table.cell(1, 1).text!r}"
    assert table.cell(1, 4).text == "7月9日", f"完成时间列错误: {table.cell(1, 4).text!r}"


def test_data_rows_do_not_inherit_header_styling():
    """Data rows must not carry the header's bold/background fill."""
    d = tempfile.mkdtemp()
    out = build_ppt(
        template_path="resource/2026年第二十七周周报-王凡.pptx",
        png_paths=_pngs(d),
        ai_texts={"week_compare": "", "daily_summary": ""},
        narratives={"brand": "", "brand_share": "", "product": "", "new": ""},
        procurement_items=[{"事项内容": "x", "进度及责任人": ["a"],
                            "状态": "s", "完成时间": "t"}] * 2,
        plan_items=[],
        week_meta={"week_id": "2026-W27", "周起始日": "2026-07-03", "周结束日": "2026-07-09"},
        out_path=os.path.join(d, "styling.pptx"),
    )
    prs = Presentation(out)
    table = None
    for sh in prs.slides[12].shapes:
        if sh.has_table:
            table = sh.table
            break
    assert table is not None
    trs = table._tbl.findall(_A_TR)
    assert len(trs) >= 3, f"expected header + 2 data rows, got {len(trs)}"
    # inspect every data row (skip header at index 0)
    for tr in trs[1:]:
        # 1) no background fill on any cell's tcPr
        for tcpr in tr.iter(_A_TCPR):
            for child in tcpr:
                assert _localname(child) not in _FILL_LOCALS, (
                    f"data row carries header cell fill: {_localname(child)}")
        # 2) no bold runs (neither b="1" attr nor <a:b/> child)
        for rpr in tr.iter(_A_RPR):
            assert rpr.get("b") not in ("1", "true"), "data-row run is bold (b attr)"
            assert len(rpr.findall(f"{{{_A}}}b")) == 0, "data-row run is bold (<a:b/>)"
        for epr in tr.iter(_A_ENDPARARPR):
            assert epr.get("b") not in ("1", "true"), "data-row endParaRPr is bold"


def test_data_row_styling_when_table_has_only_header():
    """Edge case: a table reduced to header-only still clones without header styling."""
    d = tempfile.mkdtemp()
    # next_plan table on slide 16 has 10 rows normally; fill with 1 item to
    # force the clone path. We assert the resulting data row has no grad fill.
    out = build_ppt(
        template_path="resource/2026年第二十七周周报-王凡.pptx",
        png_paths=_pngs(d),
        ai_texts={"week_compare": "", "daily_summary": ""},
        narratives={"brand": "", "brand_share": "", "product": "", "new": ""},
        procurement_items=[],
        plan_items=[{"事项内容": "y", "提出时间": "t", "次周预计完成节点名称": "n",
                     "涉及部门": "d"}],
        week_meta={"week_id": "2026-W27", "周起始日": "2026-07-03", "周结束日": "2026-07-09"},
        out_path=os.path.join(d, "header_only.pptx"),
    )
    prs = Presentation(out)
    table = None
    for sh in prs.slides[16].shapes:
        if sh.has_table:
            table = sh.table
            break
    assert table is not None
    trs = table._tbl.findall(_A_TR)
    assert len(trs) >= 2
    # the single data row (index 1) must not carry the header gradient fill
    for tcpr in trs[1].iter(_A_TCPR):
        for child in tcpr:
            assert _localname(child) not in _FILL_LOCALS, (
                f"data row carries header fill: {_localname(child)}")

