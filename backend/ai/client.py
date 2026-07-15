import json
import os
import re
from pathlib import Path
import yaml

from backend.ai.prompts import render

_SETTINGS = Path(__file__).resolve().parents[1] / "config" / "settings.yaml"


# ---- regex patterns ----
# Strip 思考/推理标签 (Anthropic-style + Qwen-style; tolerant to nested)
_THINK_RE       = re.compile(r'<\s*think\s*>.*?<\s*/\s*think\s*>', re.DOTALL | re.IGNORECASE)
_THINK_ORPHAN_RE = re.compile(r'<\s*think\s*>.*$', re.DOTALL | re.IGNORECASE)
# Strip markdown code fences ```json / ```text / ```
_FENCE_OPEN_RE  = re.compile(r'```[a-zA-Z0-9_+\-]*[ \t]*\n?', re.MULTILINE)
_FENCE_CLOSE_RE = re.compile(r'\n?```[ \t]*\n?', re.MULTILINE)
# Inline markdown formatting (kept text, dropped markers)
_BOLD_RE        = re.compile(r'\*\*([^*\n]+?)\*\*')
_ITAL_RE        = re.compile(r'(?<![*\w])\*([^*\n]+?)\*(?![*\w])')
_INLINE_CODE_RE = re.compile(r'`([^`\n]+)`')
_LINK_RE        = re.compile(r'\[([^\]]+)\]\(([^)\s]+)\)')
# Block-level markdown
_HEADING_RE     = re.compile(r'^#{1,6}[ \t]+', re.MULTILINE)
_LIST_RE        = re.compile(r'^([ \t]*)[-*+][ \t]+', re.MULTILINE)
_BLOCKQ_RE      = re.compile(r'^>[ \t]*', re.MULTILINE)
_HR_RE          = re.compile(r'^---+\s*$', re.MULTILINE)


def _settings():
    with open(_SETTINGS, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---- public API: pure-text and JSON helpers ----

def sanitize_text(raw: str) -> str:
    r"""Drop AI thinking tags + every common markdown marker, leaving plain text.
    Robust to orphaned/un-closed think blocks and trailing leading junk.
    """
    if not raw:
        return ""
    s = raw
    # 1. drop think-tag blocks (paired, then orphaned)
    s = _THINK_RE.sub('', s)
    s = _THINK_ORPHAN_RE.sub('', s)
    # 2. drop markdown code fences (must be done before link/bold to avoid
    #    false matches inside `\`\`\`json ... \`\`\``)
    s = _FENCE_OPEN_RE.sub('', s)
    s = _FENCE_CLOSE_RE.sub('', s)
    # 3. inline formatting
    s = _BOLD_RE.sub(r'\1', s)
    s = _ITAL_RE.sub(r'\1', s)
    s = _INLINE_CODE_RE.sub(r'\1', s)
    s = _LINK_RE.sub(r'\1', s)
    # 4. block-level
    s = _HEADING_RE.sub('', s)
    s = _LIST_RE.sub(r'\1', s)   # drop bullet char, keep indent
    s = _BLOCKQ_RE.sub('', s)
    s = _HR_RE.sub('', s)
    # 5. cleanup - collapse blank lines and trim leading blank lines (often
    #    introduced by stripping a wrapped think-tag); keep indentation.
    s = re.sub(r'\n{3,}', '\n\n', s)
    s = re.sub(r'^\n+', '', s)
    return s.rstrip()


def extract_json(raw: str):
    r"""Pull a JSON value (object or array) out of AI output. Tolerates
    fenced code blocks, prefix prose, trailing characters, and any
    leftover think tags. Returns None if nothing valid can be parsed."""
    s = sanitize_text(raw)
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        pass
    decoder = json.JSONDecoder()
    for opener in ('[', '{'):
        i = s.find(opener)
        if i < 0:
            continue
        try:
            obj, _ = decoder.raw_decode(s, i)
            return obj
        except Exception:
            continue
    return None


# ---- fallback placeholders ----

def _fallback(section: str, vars: dict) -> str:
    if section == "week_compare":
        return (f"本周销售额{vars.get('cur_amount')}元，销售毛利{vars.get('cur_profit')}元，"
                f"销售毛利率{vars.get('cur_margin')}%；较上周销售额{vars.get('amount_delta')}元。")
    if section == "daily_summary":
        series = vars.get("daily_series") or ""
        if series:
            return f"本周每日销售概况（AI 不可用，占位）：\n{series}"
        return "（AI 不可用，占位文本）"
    return "（AI 不可用，占位文本）"


# ---- main callers ----

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
    """Plain-text AI output (week_compare / daily_summary).
    Returns sanitized plain text - no think tags, no markdown, no code fences.
    """
    try:
        return sanitize_text(call_ai(render(section, vars)))
    except Exception:
        return _fallback(section, vars)


def generate_json(section: str, vars: dict) -> list:
    """Structured AI output (procurement / next_plan).
    Returns a list of items, falling back to [] on any parse / network / auth error.
    Tolerates: think-tag blobs, ```json fences, prefix prose, trailing characters.
    """
    try:
        raw = call_ai(render(section, vars))
        result = extract_json(raw)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            # some models wrap in {"items": [...]} - unwrap common shapes
            for key in ("items", "plan_items", "procurement_items", "next_plan", "data", "result"):
                v = result.get(key)
                if isinstance(v, list):
                    return v
            return []  # object without a list inside -> treat as empty
        return []
    except Exception:
        return []
