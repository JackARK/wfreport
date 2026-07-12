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
    df["订单日期"] = pd.to_datetime(df["订单日期"])
    pm = _load_platform_map(platform_map_path)
    df["平台"] = df["店铺"].map(lambda s: derive_platform(s, pm))
    df["week_id"] = week_id(df["订单日期"].min())
    return df
