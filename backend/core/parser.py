from pathlib import Path
import pandas as pd
import yaml
from backend.core.week import week_id

_DEFAULT_PLATFORM_MAP = str(Path(__file__).resolve().parents[1] / "config" / "platform_map.yaml")

def _load_platform_map(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f).get("platforms", {})

def derive_platform(shop: str, platform_map: dict = None) -> str:
    if platform_map is None:
        platform_map = _load_platform_map(_DEFAULT_PLATFORM_MAP)
    prefix = str(shop).split("-", 1)[0]
    return platform_map.get(prefix, "其他")

def load_excel(path: str, platform_map_path: str = _DEFAULT_PLATFORM_MAP) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="Sheet1")
    # 列名别名归一：新版导出口径 渠道→店铺、日期→订单日期
    aliases = {"渠道": "店铺", "日期": "订单日期"}
    df = df.rename(columns={k: v for k, v in aliases.items()
                            if k in df.columns and v not in df.columns})
    if "线上订单号" not in df.columns:
        # 聚合口径文件无订单号 — 补合成值，保证下游入库列齐全
        df["线上订单号"] = [f"SYN-{i}" for i in range(len(df))]
    df["订单日期"] = pd.to_datetime(df["订单日期"])
    if "是否新品" not in df.columns:
        # 旧格式文件无此列 — 统一补「否」，下游 (metrics/history) 不用判空
        df["是否新品"] = "否"
    pm = _load_platform_map(platform_map_path)
    df["平台"] = df["店铺"].map(lambda s: derive_platform(s, pm))
    df["week_id"] = week_id(df["订单日期"].min())
    return df
