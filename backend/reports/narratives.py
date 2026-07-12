# backend/reports/narratives.py
"""Program-assembled narrative texts for the PPT (brand / brand-share / product / new).

Per spec §3.3 / §3.6 these are template-stitched (not AI-generated) so the PPT
ships with non-empty text boxes on slides 5/6/9/9'.
"""
from datetime import datetime


def _fmt_date_range(week_meta: dict) -> str:
    """Render 周起始日~周结束日 as e.g. '7.3-7.9' (matches template example)."""
    start = str(week_meta.get("周起始日", "")).split(" ")[0]
    end = str(week_meta.get("周结束日", "")).split(" ")[0]
    try:
        sd = datetime.fromisoformat(start)
        ed = datetime.fromisoformat(end)
        return f"{sd.month}.{sd.day}-{ed.month}.{ed.day}"
    except ValueError:
        return f"{start}-{end}"


def build_narratives(bundle, week_meta: dict) -> dict:
    rng = _fmt_date_range(week_meta)

    # brand: one line per brand + margin-comparison conclusion
    lines = []
    for _, r in bundle.brand.iterrows():
        lines.append(
            f"{r['品牌']}：{rng}销售额{r['销售金额'] / 10000:.2f}万元，"
            f"销售数量{int(r['销售数量'])}件，毛利率{r['销售毛利率'] * 100:.2f}%；"
        )
    if len(bundle.brand) >= 2:
        ranked = bundle.brand.sort_values("销售毛利率", ascending=False)
        hi = ranked.iloc[0]["品牌"]
        lo = ranked.iloc[-1]["品牌"]
        if hi != lo:
            lines.append(f"综合：{hi}毛利率高于{lo}。")
    brand = "\n".join(lines)

    # brand_share: by 销售金额 share (not qty share)
    total = float(bundle.brand["销售金额"].sum())
    segs = [f"本周销售总额{total / 10000:.2f}万元"]
    for _, r in bundle.brand.iterrows():
        share = (r["销售金额"] / total) if total else 0.0
        segs.append(f"{r['品牌']}{r['销售金额'] / 10000:.2f}万元占{share * 100:.0f}%")
    brand_share = "；".join(segs) + "。"

    # product: top1 of product_top15
    if len(bundle.product_top15) > 0:
        top = bundle.product_top15.iloc[0]
        product = (f"本周TOP产品：{top['商品名称']}销量{int(top['销售数量'])}件居首；"
                   f"毛利率{top['销售毛利率'] * 100:.2f}%。")
    else:
        product = "本周无TOP产品。"

    # new products
    if len(bundle.new_products) == 0:
        new = "本周无新品。"
    else:
        new_lines = []
        for _, r in bundle.new_products.iterrows():
            new_lines.append(
                f"新品{r['商品名称']}：销量{int(r['销售数量'])}件，"
                f"毛利率{r['销售毛利率'] * 100:.2f}%。"
            )
        new = "\n".join(new_lines)

    return {"brand": brand, "brand_share": brand_share, "product": product, "new": new}
