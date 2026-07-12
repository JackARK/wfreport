import json
import os
from pathlib import Path

import yaml

from backend.ai.prompts import render

_SETTINGS = Path(__file__).resolve().parents[1] / "config" / "settings.yaml"


def _settings():
    with open(_SETTINGS, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _fallback(section: str, vars: dict) -> str:
    if section == "week_compare":
        return (f"本周销售额{vars.get('cur_amount')}元，销售毛利{vars.get('cur_profit')}元，"
                f"销售毛利率{vars.get('cur_margin')}%；较上周销售额{vars.get('amount_delta')}元。")
    return "（AI 不可用，占位文本）"


def call_ai(messages: list) -> str:
    s = _settings()["ai"]
    key = os.getenv("MINIMAX_API_KEY")
    if not key:
        raise RuntimeError("MINIMAX_API_KEY missing")
    import httpx
    resp = httpx.post(
        f"{s['base_url']}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": s["model"], "temperature": s.get("temperature", 0.6), "messages": messages},
        timeout=s.get("timeout_seconds", 30),
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def generate_section(section: str, vars: dict) -> str:
    try:
        return call_ai(render(section, vars))
    except Exception:
        return _fallback(section, vars)


def generate_json(section: str, vars: dict) -> list:
    try:
        raw = call_ai(render(section, vars))
        return json.loads(raw)
    except Exception:
        return []
