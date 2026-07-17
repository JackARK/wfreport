import json
import os
import re
import time
from pathlib import Path
import yaml

from backend.ai.prompts import render
from backend.core.logging_conf import get_logger

logger = get_logger("ai")

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
    #    false matches inside ```json ... ```)
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


# ---- provider resolution ----

def _resolve_provider(name: str | None = None) -> dict:
    """Pick the active provider config. Precedence:
    1. Explicit `name` arg (e.g. "deepseek").
    2. settings.ai.provider (default in YAML).
    3. Legacy flat fields (base_url / model) so old test paths still work.
    Returns a dict with keys: name, base_url, model, api_key, api_key_env,
    supports_thinking, temperature, timeout_seconds, provider_id.
    """
    s = _settings().get("ai", {})
    providers = s.get("providers") or {}
    requested = name or s.get("provider") or "minimax"
    provider_id = requested if requested in providers else (s.get("provider") or "minimax")

    if provider_id in providers:
        p = dict(providers[provider_id])
        p["provider_id"] = provider_id
        # backfill temperature / timeout from flat fields when missing
        for k in ("temperature", "timeout_seconds"):
            if k not in p and k in s:
                p[k] = s[k]
        # resolve API key
        env_var = p.get("api_key_env")
        p["api_key"] = os.getenv(env_var) if env_var else None
        p.setdefault("supports_thinking", False)
        p.setdefault("thinking_disabled_body_patch", {})
        return p

    # Legacy path - no registry, use flat fields.
    return {
        "provider_id": provider_id,
        "name": provider_id,
        "base_url": s.get("base_url"),
        "model": s.get("model"),
        "api_key_env": "MINIMAX_API_KEY",
        "api_key": os.getenv("MINIMAX_API_KEY"),
        "supports_thinking": False,
        "thinking_disabled_body_patch": {},
        "temperature": s.get("temperature", 0.6),
        "timeout_seconds": s.get("timeout_seconds", 30),
    }


def list_providers() -> list[dict]:
    """Return public-facing list of providers for the UI dropdown.
    Each entry: {id, name, base_url, model, supports_thinking, has_key}.
    Secrets are never included - only a boolean has_key flag.
    """
    s = _settings().get("ai", {})
    providers = s.get("providers") or {}
    active = s.get("provider") or "minimax"
    out = []
    for pid, p in providers.items():
        env_var = p.get("api_key_env")
        out.append({
            "id": pid,
            "name": p.get("name", pid),
            "base_url": p.get("base_url"),
            "model": p.get("model"),
            "supports_thinking": bool(p.get("supports_thinking", False)),
            "has_key": bool(os.getenv(env_var)) if env_var else False,
            "api_key_env": env_var,
            "is_active": pid == active,
        })
    return out


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

def _build_body(provider: dict, messages: list, thinking: str | None) -> dict:
    """Build the OpenAI-style /chat/completions body for the chosen provider.
    `thinking`:
        None       - leave as-is (provider default).
        "disabled" - patch the body to disable thinking (provider-specific
                     via provider['thinking_disabled_body_patch']); drop
                     `temperature` because DeepSeek ignores it in thinking
                     mode anyway, and we want the disabled call to be
                     deterministic.
        "enabled"  - do not patch (provider default is enabled for DeepSeek).
    """
    body = {"model": provider["model"], "messages": messages}
    if thinking == "disabled" and provider.get("supports_thinking"):
        body.update(provider.get("thinking_disabled_body_patch") or {})
        # DeepSeek v4 docs: when thinking is on, temperature is ignored. When
        # we explicitly disable it, temperature *is* honoured, so it's safe
        # to send - and useful for deterministic JSON output.
        body["temperature"] = provider.get("temperature", 0.6)
    elif thinking == "enabled" or not provider.get("supports_thinking"):
        # Non-thinking provider OR explicitly enabling thinking: set
        # temperature only when thinking is *not* active (DeepSeek restriction).
        if provider.get("supports_thinking") and thinking == "enabled":
            pass  # temperature would be ignored anyway; omit it
        else:
            body["temperature"] = provider.get("temperature", 0.6)
    return body


def call_ai(messages: list, *, provider: str | None = None, thinking: str | None = None) -> str:
    """Call the active (or named) provider's /chat/completions endpoint."""
    p = _resolve_provider(provider)
    if not p.get("api_key"):
        raise RuntimeError(f"{p.get('api_key_env', 'API_KEY')} missing")
    body = _build_body(p, messages, thinking)
    logger.info("AI 请求 provider=%s model=%s thinking=%s msgs=%d",
                p.get("provider_id"), p.get("model"), thinking, len(messages))
    t0 = time.perf_counter()
    import httpx
    resp = httpx.post(
        f"{p['base_url']}/chat/completions",
        headers={"Authorization": f"Bearer {p['api_key']}", "Content-Type": "application/json"},
        json=body,
        timeout=p.get("timeout_seconds", 30),
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    logger.info("AI 响应 provider=%s 耗时=%.1fs len=%d",
                p.get("provider_id"), time.perf_counter() - t0, len(content))
    return content


def generate_section(section: str, vars: dict, *, provider: str | None = None, thinking: str | None = None) -> str:
    """Plain-text AI output (week_compare / daily_summary)."""
    try:
        return sanitize_text(call_ai(render(section, vars), provider=provider, thinking=thinking))
    except Exception as e:
        logger.warning("AI section=%s 失败 回退占位 err=%s", section, e)
        return _fallback(section, vars)


def generate_json(section: str, vars: dict, *, provider: str | None = None, thinking: str | None = None) -> list:
    """Structured AI output (procurement / next_plan).

    Returns a list of items, falling back to [] on any parse / network /
    auth error. Tolerates: think-tag blobs, ```json fences, prefix prose,
    trailing characters.
    """
    try:
        raw = call_ai(render(section, vars), provider=provider, thinking=thinking)
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