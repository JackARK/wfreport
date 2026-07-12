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


def build_excel(bundle, recent_weeks, ai_texts: dict, out_path: str) -> str:
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
    ch = wb.add_chart({"type": "column"})
    ch.add_series({"name": "销售额", "values": ["汇总", 0, 1, 0, 1]})
    ch.add_series({"name": "销售毛利", "values": ["汇总", 1, 1, 1, 1]})
    ch.set_title({"name": "本周销售概况"})
    ws.insert_chart("E1", ch)

    write_table(wb.add_worksheet("每日"), "每日销售", bundle.daily,
                numcols=["销售金额", "销售毛利"], pctcols=["销售毛利率"])
    write_table(wb.add_worksheet("品牌"), "品牌", bundle.brand,
                numcols=["销售金额", "销售数量", "销售毛利", "数量占比"],
                pctcols=["销售毛利率", "数量占比"])
    write_table(wb.add_worksheet("平台"), "平台", bundle.platform,
                numcols=["销售数量", "销售金额", "销售毛利", "数量占比"],
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
    wb.close()
    return out_path
