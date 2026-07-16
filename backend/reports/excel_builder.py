import xlsxwriter


def _fmt(wb):
    return {
        "money": "#,##0.00",
        "pct": "0.00%",
        "header": wb.add_format({
            "bold": True,
            "bg_color": "#3b82f6",
            "font_color": "#FFFFFF",
            "border": 1,
        }),
    }


def _shop_pivot(bundle):
    pivot = (bundle.shop_top15_daily
             .pivot_table(index="店铺", columns="订单日期",
                          values="销售数量", aggfunc="sum")
             .fillna(0))
    pivot.columns = [c.strftime("%m-%d") if hasattr(c, "strftime") else str(c)
                     for c in pivot.columns]
    return pivot.reset_index()


def build_excel(bundle, recent_weeks, ai_texts: dict, procurement_items: list,
                plan_items: list, out_path: str) -> str:
    wb = xlsxwriter.Workbook(out_path)
    f = _fmt(wb)
    money = wb.add_format({"num_format": f["money"]})
    pct = wb.add_format({"num_format": f["pct"]})

    def write_table(ws, title, df, numcols=None, pctcols=None):
        ws.merge_range(0, 0, 0, max(1, len(df.columns) - 1), title, f["header"])
        for c, col in enumerate(df.columns):
            ws.write(1, c, col, f["header"])
        for r, row in enumerate(df.itertuples(index=False), start=2):
            for c, val in enumerate(row):
                fmt = None
                if numcols and df.columns[c] in numcols:
                    fmt = money
                if pctcols and df.columns[c] in pctcols:
                    fmt = pct
                ws.write(r, c, val, fmt)

    # 汇总
    ws = wb.add_worksheet("汇总")
    ws.write(0, 0, "本周销售额")
    ws.write(0, 1, bundle.overview["销售金额"], money)
    ws.write(1, 0, "销售毛利")
    ws.write(1, 1, bundle.overview["销售毛利"], money)
    ws.write(2, 0, "销售毛利率")
    ws.write(2, 1, bundle.overview["销售毛利率"], pct)
    ws.write(3, 0, "销售数量")
    ws.write(3, 1, bundle.overview["销售数量"])
    if recent_weeks:
        ws.write(5, 0, "最近三周", f["header"])
        ws.write_row(6, 0, ["周标识", "销售额", "销售毛利", "销售毛利率"], f["header"])
        for i, w in enumerate(recent_weeks, start=7):
            ws.write(i, 0, w["week_id"])
            ws.write(i, 1, w["销售额"], money)
            ws.write(i, 2, w["销售毛利"], money)
            ws.write(i, 3, w["销售毛利率"], pct)
    src_row = 20
    src_col = 9
    ws.write(src_row, src_col, "本周")
    ws.write(src_row + 1, src_col, "销售金额")
    ws.write(src_row + 1, src_col + 1, bundle.overview["销售金额"], money)
    ws.write(src_row + 2, src_col, "销售毛利")
    ws.write(src_row + 2, src_col + 1, bundle.overview["销售毛利"], money)
    ws.write(src_row + 3, src_col, "销售毛利率")
    ws.write(src_row + 3, src_col + 1, bundle.overview["销售毛利率"], pct)

    col_chart = wb.add_chart({"type": "column"})
    col_chart.add_series({
        "name": "销售金额",
        "categories": ["汇总", src_row, src_col, src_row, src_col],
        "values": ["汇总", src_row + 1, src_col + 1, src_row + 1, src_col + 1],
    })
    col_chart.add_series({
        "name": "销售毛利",
        "categories": ["汇总", src_row, src_col, src_row, src_col],
        "values": ["汇总", src_row + 2, src_col + 1, src_row + 2, src_col + 1],
    })
    line_chart = wb.add_chart({"type": "line"})
    line_chart.add_series({
        "name": "销售毛利率",
        "categories": ["汇总", src_row, src_col, src_row, src_col],
        "values": ["汇总", src_row + 3, src_col + 1, src_row + 3, src_col + 1],
        "y2_axis": True,
    })
    col_chart.set_title({"name": "本周销售概况"})
    col_chart.set_y_axis({"name": "金额"})
    col_chart.set_y2_axis({"num_format": "0.00%"})
    col_chart.combine(line_chart)
    ws.insert_chart("E1", col_chart)

    write_table(wb.add_worksheet("每日"), "每日销售", bundle.daily,
                numcols=["销售金额", "销售毛利"], pctcols=["销售毛利率"])
    write_table(wb.add_worksheet("品牌"), "品牌", bundle.brand,
                numcols=["销售金额", "销售数量", "销售毛利"],
                pctcols=["销售毛利率", "数量占比"])
    write_table(wb.add_worksheet("平台"), "平台", bundle.platform,
                numcols=["销售数量", "销售金额", "销售毛利"],
                pctcols=["销售毛利率", "数量占比"])
    # 店铺：TOP15 店铺 × 日期 透视表（数据 only，无原生图表）
    write_table(wb.add_worksheet("店铺"), "TOP15店铺每日销售数量",
                _shop_pivot(bundle))
    write_table(wb.add_worksheet("产品"), "TOP15产品", bundle.product_top15,
                numcols=["销售数量", "销售金额", "销售毛利"],
                pctcols=["销售毛利率"])
    write_table(wb.add_worksheet("工厂"), "TOP5工厂", bundle.factory_top5,
                numcols=["销售数量", "销售金额", "销售毛利"],
                pctcols=["销售毛利率"])

    wai = wb.add_worksheet("AI文案")
    for i, (k, v) in enumerate(ai_texts.items()):
        wai.write(i, 0, k, f["header"])
        wai.write(i, 1, v)

    # P1-#12: also persist the AI-parsed procurement + plan rows so the
    # reader can audit what fed into the report. Each row gets its own
    # sub-table starting after the AI text block.
    def _ai_rows(items, cols):
        out = []
        for r in (items or []):
            row = []
            for c in cols:
                v = r.get(c, "")
                if isinstance(v, list):
                    v = " / ".join(str(x) for x in v)
                row.append(str(v) if v is not None else "")
            out.append(row)
        return out

    def _write_subtable(start_row, title, cols, rows):
        if not rows:
            return start_row
        wai.merge_range(start_row, 0, start_row, len(cols) - 1, title, f["header"])
        start_row += 1
        for c, col in enumerate(cols):
            wai.write(start_row, c, col, f["header"])
        start_row += 1
        for r in rows:
            for c, val in enumerate(r):
                wai.write(start_row, c, val)
            start_row += 1
        return start_row + 1   # blank spacer row

    cursor = len(ai_texts) + 2
    cursor = _write_subtable(
        cursor, "采购跟进 (AI 解析)",
        ["事项内容", "进度及责任人", "状态", "完成时间"],
        _ai_rows(procurement_items, ["事项内容", "进度及责任人", "状态", "完成时间"]),
    )
    cursor = _write_subtable(
        cursor, "下周计划 (AI 解析)",
        ["事项内容", "提出时间", "次周预计完成节点名称", "涉及部门"],
        _ai_rows(plan_items, ["事项内容", "提出时间", "次周预计完成节点名称", "涉及部门"]),
    )

    wb.close()
    return out_path
