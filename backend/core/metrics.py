from dataclasses import dataclass
import time
import pandas as pd
from backend.core.logging_conf import get_logger

logger = get_logger("metrics")


@dataclass
class MetricsBundle:
    overview: dict
    daily: pd.DataFrame
    brand: pd.DataFrame
    platform: pd.DataFrame
    shop_top15_daily: pd.DataFrame
    product_top15: pd.DataFrame
    product_top15_daily: pd.DataFrame
    new_products: pd.DataFrame
    factory_top5: pd.DataFrame


def _fmt_summary(label: str, df: pd.DataFrame) -> str:
    """Compact one-line summary of an aggregate dataframe for logs."""
    parts = []
    for _, r in df.head(8).iterrows():
        name = str(r.iloc[0])
        qty = int(r.get("销售数量", 0) or 0)
        amt = float(r.get("销售金额", 0) or 0)
        mrg = float(r.get("销售毛利率", 0) or 0)
        parts.append(f"{name}={qty}件/{amt:.0f}元/{mrg*100:.1f}%")
    if len(df) > 8:
        parts.append(f"...(+{len(df)-8} more)")
    return "; ".join(parts)


def aggregate(df: pd.DataFrame) -> dict:
    """全表汇总。加权平均 Σ毛利/Σ金额。"""
    t0 = time.perf_counter()
    sa = float(df["销售金额"].sum())
    sq = int(df["销售数量"].sum())
    sp = float(df["销售毛利"].sum())
    margin = sp / sa
    logger.info(
        "aggregate(rows=%d) Σ销售金额=%.2f ÷ Σ销售数量=%d → 加权毛利率=%.4f%% (%.3fs)",
        len(df), sa, sq, margin * 100, time.perf_counter() - t0,
    )
    return {"销售金额": sa, "销售数量": sq, "销售毛利": sp, "销售毛利率": margin}


def _agg_dim(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    g = df.groupby(by)
    out = g.agg(销售金额=("销售金额", "sum"), 销售数量=("销售数量", "sum"), 销售毛利=("销售毛利", "sum")).reset_index()
    out["销售毛利率"] = out["销售毛利"] / out["销售金额"]
    return out


def compute_all(df: pd.DataFrame) -> MetricsBundle:
    t0 = time.perf_counter()
    rows_in = len(df)
    logger.info("compute_all START rows_in=%d cols=%s", rows_in, list(df.columns))

    # overview
    ov = aggregate(df)
    overview = {"销售金额": ov["销售金额"], "销售毛利": ov["销售毛利"],
                "销售毛利率": ov["销售毛利率"], "销售数量": ov["销售数量"]}
    logger.info("overview → %s", {k: (round(v, 4) if isinstance(v, float) else v)
                                    for k, v in overview.items()})

    # daily
    daily = _agg_dim(df, ["订单日期"]).sort_values("订单日期")
    logger.info("daily by 订单日期 rows=%d 覆盖 %s ~ %s",
                len(daily),
                daily["订单日期"].min() if len(daily) else "n/a",
                daily["订单日期"].max() if len(daily) else "n/a")

    # brand
    brand = _agg_dim(df, ["品牌"])
    brand["数量占比"] = brand["销售数量"] / brand["销售数量"].sum()
    logger.info("brand (%d): %s", len(brand), _fmt_summary("brand", brand))

    # platform
    platform = _agg_dim(df, ["平台"])
    platform["数量占比"] = platform["销售数量"] / platform["销售数量"].sum()
    logger.info("platform (%d): %s", len(platform), _fmt_summary("platform", platform))

    # shop TOP15 (by qty)
    shop_qty = df.groupby("店铺")["销售数量"].sum().sort_values(ascending=False)
    top15_shops = shop_qty.head(15).index.tolist()
    logger.info("shop TOP15(by 销售数量 desc) = %s",
                [(s, int(shop_qty[s])) for s in top15_shops[:5]] + (["...(top10 more)"] if len(top15_shops) > 5 else []))
    shop_top15_daily = (df[df["店铺"].isin(top15_shops)]
                        .groupby(["店铺", "订单日期"])["销售数量"].sum().reset_index())

    # product TOP15 (by qty); 按 商品名称 聚合 — 同一产品名下的多个 SKU
    # (颜色/尺码等不同商品编码) 合并为一个产品行,图表 / 周报才能呈现
    # 真正的「产品 TOP」,而不是同款不同色被切成几行后被 Plotly 当作
    # 同一根柱子(同名 collapse)导致 5+ 根柱子消失的问题.
    prod_agg = df.groupby("商品名称").agg(
        销售数量=("销售数量", "sum"), 销售金额=("销售金额", "sum"),
        销售毛利=("销售毛利", "sum")).reset_index()
    n_unique = prod_agg["商品名称"].nunique()
    n_total_rows = len(df)  # 用于推断 SKU 合并数
    prod_agg["销售毛利率"] = prod_agg["销售毛利"] / prod_agg["销售金额"]
    product_top15 = prod_agg.sort_values("销售数量", ascending=False).head(15).reset_index(drop=True)
    logger.info("product TOP15: 按 商品名称 聚合 unique=%d rows_in=%d, 取 top15 by 销售数量 → %s",
                n_unique, n_total_rows, _fmt_summary("product", product_top15))
    product_top15_daily = (df[df["商品名称"].isin(product_top15["商品名称"])]
                           .groupby(["商品名称", "订单日期"])["销售数量"].sum().reset_index())

    # new products
    new = df[df["是否新品"] == "是"]
    if len(new) > 0:
        new_products = new.groupby(["商品编码", "商品名称"]).agg(
            销售数量=("销售数量", "sum"), 销售金额=("销售金额", "sum"),
            销售毛利=("销售毛利", "sum")).reset_index()
        new_products["销售毛利率"] = new_products["销售毛利"] / new_products["销售金额"]
        logger.info("new_products: rows_in=%d 是新品 rows=%d → TOP %d",
                    n_total_rows, len(new), len(new_products))
    else:
        new_products = pd.DataFrame(columns=["商品编码", "商品名称", "销售数量", "销售金额", "销售毛利率"])
        logger.info("new_products: 数据中无新品 (是否新品!=是), 返回空表")

    # factory TOP5
    factory = df.groupby("工厂").agg(
        销售数量=("销售数量", "sum"), 销售金额=("销售金额", "sum"),
        销售毛利=("销售毛利", "sum")).reset_index()
    factory["销售毛利率"] = factory["销售毛利"] / factory["销售金额"]
    factory_top5 = factory.sort_values("销售数量", ascending=False).head(5)
    logger.info("factory TOP5 (by 销售数量): %s", _fmt_summary("factory", factory_top5))

    logger.info("compute_all DONE 总耗时=%.3fs", time.perf_counter() - t0)
    return MetricsBundle(overview, daily, brand, platform, shop_top15_daily,
                         product_top15, product_top15_daily, new_products, factory_top5)