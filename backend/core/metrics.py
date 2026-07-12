from dataclasses import dataclass
import pandas as pd

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

def aggregate(df: pd.DataFrame, by: list[str]) -> dict:
    """按 by 聚合(空列表=全表)。返回单组汇总 dict。"""
    g = df.groupby(by) if by else df
    销售金额 = g["销售金额"].sum()
    销售数量 = g["销售数量"].sum()
    销售毛利 = g["销售毛利"].sum()
    if by:
        return pd.DataFrame({
            "销售金额": 销售金额, "销售数量": 销售数量, "销售毛利": 销售毛利,
        }).reset_index()
    # 全表 -> 单值 dict
    sa, sq, sp = float(销售金额), int(销售数量), float(销售毛利)
    return {"销售金额": sa, "销售数量": sq, "销售毛利": sp, "销售毛利率": sp / sa}

def _agg_dim(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    g = df.groupby(by)
    out = g.agg(销售金额=("销售金额", "sum"), 销售数量=("销售数量", "sum"), 销售毛利=("销售毛利", "sum")).reset_index()
    out["销售毛利率"] = out["销售毛利"] / out["销售金额"]
    return out

def compute_all(df: pd.DataFrame) -> MetricsBundle:
    total_qty = df["销售数量"].sum()
    # overview
    ov = aggregate(df, [])
    overview = {"销售金额": ov["销售金额"], "销售毛利": ov["销售毛利"],
                "销售毛利率": ov["销售毛利率"], "销售数量": ov["销售数量"]}
    # daily
    daily = _agg_dim(df, ["订单日期"]).sort_values("订单日期")
    # brand
    brand = _agg_dim(df, ["品牌"])
    brand["数量占比"] = brand["销售数量"] / brand["销售数量"].sum()
    # platform
    platform = _agg_dim(df, ["平台"])
    platform["数量占比"] = platform["销售数量"] / platform["销售数量"].sum()
    # shop TOP15 (by qty)
    shop_qty = df.groupby("店铺")["销售数量"].sum().sort_values(ascending=False)
    top15_shops = shop_qty.head(15).index.tolist()
    shop_top15_daily = (df[df["店铺"].isin(top15_shops)]
                        .groupby(["店铺", "订单日期"])["销售数量"].sum().reset_index())
    # product TOP15 (by qty); 用 商品编码 聚合，附带 商品名称
    prod_agg = df.groupby(["商品编码", "商品名称"]).agg(
        销售数量=("销售数量", "sum"), 销售金额=("销售金额", "sum"),
        销售毛利=("销售毛利", "sum")).reset_index()
    prod_agg["销售毛利率"] = prod_agg["销售毛利"] / prod_agg["销售金额"]
    top15_codes = prod_agg.sort_values("销售数量", ascending=False).head(15)[["商品编码", "商品名称"]]
    product_top15 = prod_agg.merge(top15_codes, on=["商品编码", "商品名称"]).sort_values("销售数量", ascending=False)
    product_top15_daily = (df[df["商品编码"].isin(top15_codes["商品编码"])]
                           .groupby(["商品编码", "商品名称", "订单日期"])["销售数量"].sum().reset_index())
    # new products
    new = df[df["是否新品"] == "是"]
    if len(new) > 0:
        new_products = new.groupby(["商品编码", "商品名称"]).agg(
            销售数量=("销售数量", "sum"), 销售金额=("销售金额", "sum"),
            销售毛利=("销售毛利", "sum")).reset_index()
        new_products["销售毛利率"] = new_products["销售毛利"] / new_products["销售金额"]
    else:
        new_products = pd.DataFrame(columns=["商品编码", "商品名称", "销售数量", "销售金额", "销售毛利率"])
    # factory TOP5
    factory = df.groupby("工厂").agg(
        销售数量=("销售数量", "sum"), 销售金额=("销售金额", "sum"),
        销售毛利=("销售毛利", "sum")).reset_index()
    factory["销售毛利率"] = factory["销售毛利"] / factory["销售金额"]
    factory_top5 = factory.sort_values("销售数量", ascending=False).head(5)
    return MetricsBundle(overview, daily, brand, platform, shop_top15_daily,
                         product_top15, product_top15_daily, new_products, factory_top5)
