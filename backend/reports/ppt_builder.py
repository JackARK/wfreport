import copy
from pptx import Presentation

_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_A_TR = f"{{{_A}}}tr"
_A_T = f"{{{_A}}}t"
_A_TCPR = f"{{{_A}}}tcPr"
_A_B = f"{{{_A}}}b"
_FILL_LOCALS = {"solidFill", "gradFill", "blipFill", "pattFill", "grpFill"}


def _localname(el) -> str:
    tag = el.tag
    return tag.rpartition("}")[2] if isinstance(tag, str) and "}" in tag else (tag or "")


def _strip_row_styling(tr):
    """Remove header-originated bold + cell background from a data <a:tr> clone.

    Strips: (a) any fill child of <a:tcPr> (solidFill/gradFill/...), and
    (b) bold on run props (<a:b/> child or b="1" attribute on rPr/endParaRPr).
    Cell count/structure is left intact.
    """
    for el in tr.iter():
        local = _localname(el)
        if local == "tcPr":
            for child in list(el):
                if _localname(child) in _FILL_LOCALS:
                    el.remove(child)
        elif local in ("rPr", "endParaRPr"):
            for b in el.findall(_A_B):
                el.remove(b)
            if el.get("b") in ("1", "true"):
                del el.attrib["b"]


def _picture_shapes(slide):
    return [s for s in slide.shapes if s.shape_type == 13]  # PICTURE


def replace_picture(slide, which: int, png_path: str):
    """Swap a picture in-place: capture its geometry, remove the old <p:pic>
    element from spTree, and insert the new picture at the same anchor.

    Also drops the old picture's <Relationship> from the slide's rels so
    the package doesn't carry an orphan reference (image file bloat —
    the embed still references the old PNG even though it's not rendered).
    PowerPoint silently keeps the embed if the rel survives; this is the
    P0-#4 cleanup.
    """
    pics = _picture_shapes(slide)
    if which >= len(pics):
        return
    old = pics[which]
    left, top, width, height = old.left, old.top, old.width, old.height

    # Capture the rId of the old picture's blip embed before we drop the
    # element so we can drop the corresponding relationship.
    blip_rId = None
    blip_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
    embed_attr = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
    blip = old._element.find(f".//{{{blip_ns}}}blip")
    if blip is not None:
        blip_rId = blip.get(embed_attr)

    sp = old._element
    sp.getparent().remove(sp)

    # Drop the now-unused relationship + image part from the package.
    if blip_rId:
        try:
            slide.part.drop_rel(blip_rId)
        except Exception:
            pass

    slide.shapes.add_picture(png_path, left, top, width=width, height=height)


def set_text(slide, name_part: str, text: str):
    for sh in slide.shapes:
        if sh.has_text_frame and name_part in sh.name:
            tf = sh.text_frame
            tf.clear()
            tf.text = str(text)


def duplicate_slide(prs, index: int):
    src = prs.slides[index]
    blank = prs.slide_layouts[6]
    new = prs.slides.add_slide(blank)
    for sh in src.shapes:
        el = sh._element
        new.shapes._spTree.insert_element_before(copy.deepcopy(el), "p:extLst")
    for rel in src.part.rels.values():
        if "image" in rel.reltype or "chart" in rel.reltype:
            new.part.rels.get_or_add(rel.reltype, rel._target)
    return new


def delete_slide(prs, slide_index: int):
    """Remove a slide from the presentation by index. python-pptx has no
    built-in API for this so we manipulate the sldIdLst XML directly.

    PowerPoint will renumber subsequent slides when reopening. Note that
    slide indices in the caller's list are NOT updated by this call —
    pass the absolute index before any other slides were added/deleted.
    """
    sldIdLst = prs.slides._sldIdLst
    sldId_elems = list(sldIdLst)
    if slide_index < 0 or slide_index >= len(sldId_elems):
        return False
    sldId = sldId_elems[slide_index]
    rId = sldId.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
    # Drop the relationship so the package doesn't carry an orphan
    # reference. Part drop_rel also marks the part for removal.
    try:
        prs.part.drop_rel(rId)
    except Exception:
        pass
    sldIdLst.remove(sldId)
    return True


def _add_row(table, template_tr):
    new_tr = copy.deepcopy(template_tr)
    for t in new_tr.iter(_A_T):
        t.text = ""
    _strip_row_styling(new_tr)
    # append after the current last row so order is preserved
    last_tr = table._tbl.findall(_A_TR)[-1]
    last_tr.addnext(new_tr)


def fill_table(table, items: list, col_keys: list, start_row: int = 1, start_no: int = 1):
    tbl = table._tbl
    trs = tbl.findall(_A_TR)
    # Prefer an existing data-row as the clone template so data rows don't
    # inherit header styling (bold / gradient fill). Fall back to the header
    # row; _strip_row_styling removes header bold/fill from each clone.
    template_tr = trs[start_row] if len(trs) > start_row else trs[0]
    while len(table.rows) > start_row:
        last = len(table.rows) - 1
        tr = table.rows[last]._tr
        tr.getparent().remove(tr)
    for i, item in enumerate(items):
        _add_row(table, template_tr)
        row_idx = len(table.rows) - 1
        table.cell(row_idx, 0).text = str(start_no + i)  # 序号, col 0, continuous
        for c, key in enumerate(col_keys):
            val = item.get(key, "")
            if isinstance(val, list):
                val = "\n".join(f"{j+1}、{x}" for j, x in enumerate(val))
            table.cell(row_idx, c + 1).text = str(val)   # col_keys -> cols 1..N


def build_ppt(template_path, png_paths, ai_texts, narratives, procurement_items,
              plan_items, week_meta, out_path) -> str:
    prs = Presentation(template_path)
    S = prs.slides
    # 页3 销售表现
    set_text(S[3], "文本框 5", ai_texts.get("week_compare", ""))
    replace_picture(S[3], 0, png_paths["overview"])
    replace_picture(S[3], 1, png_paths["three_weeks"])
    # 页4 每日
    replace_picture(S[4], 0, png_paths["daily"])
    # 页5 品牌
    set_text(S[5], "文本框 9", narratives.get("brand", ""))
    replace_picture(S[5], 0, png_paths["brand_combo"])
    # 页6 品牌饼
    set_text(S[6], "文本框 2", narratives.get("brand_share", ""))
    replace_picture(S[6], 0, png_paths["brand_pie"])
    # 页7 店铺热力图
    replace_picture(S[7], 0, png_paths["shop_heatmap"])
    # 页8 平台
    replace_picture(S[8], 0, png_paths["platform"])
    # 页9 产品
    set_text(S[9], "文本框 5", narratives.get("product", ""))
    replace_picture(S[9], 0, png_paths["product_horizontal"])
    # 复制页9 为 9' 放新品
    new9 = duplicate_slide(prs, 9)
    for sh in new9.shapes:
        if sh.has_text_frame and "文本框 5" in sh.name:
            sh.text_frame.text = narratives.get("new", "")
    # P0-#4: drop the inherited product chart's rel (and any other
    # picture rels the duplicate brought along) before adding the
    # new_products chart. Use replace_picture so the geometry + rel
    # cleanup logic is consistent with the main picture swap.
    if _picture_shapes(new9):
        replace_picture(new9, 0, png_paths["new_products"])
    # 页10 工厂 (供应商 TOP5)
    replace_picture(S[10], 0, png_paths["factory"])
    # 采购自动分页 (页13,14,15 in 1-indexed -> [12,13,14] 0-indexed)
    # - Add pages if items > 12
    # - DELETE unused template pages when items < 12, otherwise the leftover
    #   template content ("京东自营及猫超产品入库" etc.) ships in the PPT.
    max_per = 4
    chunks = [procurement_items[i:i + max_per] for i in range(0, len(procurement_items), max_per)]
    proc_pages = [12, 13, 14]
    while len(chunks) > len(proc_pages):
        dup = duplicate_slide(prs, proc_pages[-1])
        proc_pages.append(len(prs.slides) - 1)
    running_no = 1
    for pi, chunk in enumerate(chunks):
        slide = prs.slides[proc_pages[pi]]
        for sh in slide.shapes:
            if sh.has_table:
                fill_table(sh.table, chunk, ["事项内容", "进度及责任人", "状态", "完成时间"], start_no=running_no)
        running_no += len(chunk)
    # P0-#3: drop unused procurement slides. We must do this AFTER the
    # fill_table loop so all the slides we're keeping have their data in
    # place. Delete in DESCENDING index order so earlier deletions don't
    # shift the indexes of later ones.
    for unused_idx in sorted([proc_pages[i] for i in range(len(chunks), len(proc_pages))],
                             reverse=True):
        delete_slide(prs, unused_idx)

    # 下周计划 — locate the slide by content rather than by index. The
    # procurement-slide deletion above shifts indexes by -1, which used
    # to silently land us on the "THANKS" / 感谢观看 page when only
    # 1-2 procurement pages were filled.
    plan_keys = ["事项内容", "提出时间", "次周预计完成节点名称", "涉及部门"]
    for slide in prs.slides:
        for sh in slide.shapes:
            if not sh.has_table:
                continue
            t = sh.table
            # plan template table: header row has at least 4 cells whose
            # text matches the expected column labels
            if len(t.columns) < len(plan_keys):
                continue
            header = [c.text_frame.text.strip() for c in t.rows[0].cells]
            if all(any(k in h for h in header) for k in plan_keys):
                fill_table(t, plan_items, plan_keys, start_no=1)
                break
        else:
            continue
        break
    prs.save(out_path)
    return out_path
