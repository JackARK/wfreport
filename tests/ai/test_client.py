import json
from unittest import mock

import pytest

from backend.ai import client
from backend.ai.client import (
    _build_body,
    _resolve_provider,
    call_ai,
    generate_json,
    generate_section,
    list_providers,
    _fallback,
)


# ---------- existing fallback / smoke tests (kept) ----------

def test_fallback_when_no_key(monkeypatch):
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    out = generate_section("week_compare", {"cur_amount": "1", "cur_profit": "1", "cur_margin": "1",
        "prev_amount": "1", "prev_profit": "1", "prev_margin": "1", "amount_delta": "0", "amount_delta_rate": "0",
        "profit_delta": "0", "profit_delta_rate": "0", "margin_delta_pct": "0"})
    assert isinstance(out, str) and len(out) > 0


def test_generate_json_returns_empty_list_when_no_key(monkeypatch):
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    out = generate_json("procurement", {"user_input": "测试"})
    assert out == []


def test_fallback_week_compare_contains_values():
    out = _fallback("week_compare", {"cur_amount": "200", "cur_profit": "50", "cur_margin": "25",
                                     "amount_delta": "+20"})
    assert "200" in out
    assert "50" in out


def test_fallback_generic_section():
    out = _fallback("unknown_section", {})
    assert isinstance(out, str) and len(out) > 0


def test_call_ai_raises_when_no_key(monkeypatch):
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        call_ai([{"role": "system", "content": "x"}, {"role": "user", "content": "y"}])


def test_generate_section_uses_ai_on_success(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "fake-key")
    with mock.patch("backend.ai.client.call_ai", return_value="AI生成文本") as m:
        out = generate_section("week_compare", {"cur_amount": "1", "cur_profit": "1", "cur_margin": "1",
            "prev_amount": "1", "prev_profit": "1", "prev_margin": "1", "amount_delta": "0",
            "amount_delta_rate": "0", "profit_delta": "0", "profit_delta_rate": "0", "margin_delta_pct": "0"})
    assert out == "AI生成文本"
    assert m.called


def test_generate_json_parses_on_success(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "fake-key")
    payload = [{"事项内容": "x"}]
    with mock.patch("backend.ai.client.call_ai", return_value=json.dumps(payload)):
        out = generate_json("procurement", {"user_input": "测试"})
    assert out == payload


# ---------- request-failure fallback (key present but call fails) ----------

_WC_VARS = {"cur_amount": "200", "cur_profit": "50", "cur_margin": "25",
            "prev_amount": "1", "prev_profit": "1", "prev_margin": "1",
            "amount_delta": "+20", "amount_delta_rate": "0",
            "profit_delta": "0", "profit_delta_rate": "0", "margin_delta_pct": "0"}


def test_generate_section_falls_back_on_network_error(monkeypatch):
    """有 key 但请求抛异常 (网络/超时) → 回退占位文案且含业务数值。"""
    monkeypatch.setenv("MINIMAX_API_KEY", "fake-key")
    with mock.patch("backend.ai.client.call_ai", side_effect=ConnectionError("boom")):
        out = generate_section("week_compare", _WC_VARS)
    assert "200" in out and "50" in out


def test_generate_section_falls_back_on_http_error(monkeypatch):
    """httpx 层 HTTP 状态错误 → 同样回退占位文案，不向上抛。"""
    import httpx
    monkeypatch.setenv("MINIMAX_API_KEY", "fake-key")

    def fake_post(url, headers=None, json=None, timeout=None):
        resp = mock.Mock()
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=mock.Mock(), response=mock.Mock())
        return resp

    monkeypatch.setattr("httpx.post", fake_post)
    out = generate_section("week_compare", _WC_VARS)
    assert "200" in out


def test_generate_json_returns_empty_on_network_error(monkeypatch):
    """结构化输出请求失败 → 空列表，主流程不中断。"""
    monkeypatch.setenv("MINIMAX_API_KEY", "fake-key")
    with mock.patch("backend.ai.client.call_ai", side_effect=TimeoutError("slow")):
        assert generate_json("procurement", {"user_input": "x"}) == []
        assert generate_json("next_plan", {"user_input": "x"}) == []


def test_generate_json_returns_empty_on_garbage_output(monkeypatch):
    """AI 返回非 JSON 垃圾 → 空列表而不是异常。"""
    monkeypatch.setenv("MINIMAX_API_KEY", "fake-key")
    with mock.patch("backend.ai.client.call_ai", return_value="这不是JSON<think>也没闭合"):
        assert generate_json("procurement", {"user_input": "x"}) == []


# ---------- multi-provider resolution ----------

def test_resolve_provider_default(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "abc")
    p = _resolve_provider()
    assert p["provider_id"] == "minimax"
    assert p["api_key"] == "abc"
    assert p["base_url"] == "https://api.minimaxi.com/v1"
    assert p["supports_thinking"] is False


def test_resolve_provider_named(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-key")
    p = _resolve_provider("deepseek")
    assert p["provider_id"] == "deepseek"
    assert p["api_key"] == "ds-key"
    assert p["base_url"] == "https://api.deepseek.com"
    assert p["supports_thinking"] is True
    assert p["thinking_disabled_body_patch"] == {"thinking": {"type": "disabled"}}


def test_resolve_provider_kimi(monkeypatch):
    monkeypatch.setenv("KIMI_API_KEY", "k-key")
    p = _resolve_provider("kimi")
    assert p["provider_id"] == "kimi"
    assert p["api_key"] == "k-key"
    assert p["base_url"] == "https://api.kimi.com/coding/v1"
    assert p["supports_thinking"] is True
    assert p["model"] == "k3"


def test_resolve_provider_glm(monkeypatch):
    monkeypatch.setenv("GLM_API_KEY", "g-key")
    p = _resolve_provider("glm")
    assert p["provider_id"] == "glm"
    assert p["api_key"] == "g-key"
    assert p["base_url"] == "https://open.bigmodel.cn/api/coding/paas/v4"
    assert p["model"] == "glm-5.2"


def test_resolve_provider_unknown_falls_back(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "abc")
    p = _resolve_provider("nope")
    # falls back to the YAML default (minimax)
    assert p["provider_id"] == "minimax"


def test_resolve_provider_no_key_returns_none(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    p = _resolve_provider("deepseek")
    assert p["api_key"] is None


def test_list_providers_marks_active_and_has_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds")
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    providers = list_providers()
    by_id = {p["id"]: p for p in providers}
    assert set(by_id.keys()) >= {"minimax", "deepseek", "kimi"}
    assert by_id["deepseek"]["has_key"] is True
    assert by_id["kimi"]["has_key"] is False
    assert by_id["minimax"]["has_key"] is False
    assert by_id["minimax"]["is_active"] is True
    assert by_id["deepseek"]["supports_thinking"] is True


# ---------- _build_body (thinking toggle) ----------

def _ds():
    return _resolve_provider("deepseek")


def test_build_body_no_thinking_when_provider_lacks_support():
    p = _resolve_provider("minimax")
    body = _build_body(p, [{"role": "user", "content": "x"}], thinking="disabled")
    assert "thinking" not in body
    assert body["temperature"] == 0.6


def test_build_body_disabled_patches_thinking_field():
    p = _ds()
    body = _build_body(p, [{"role": "user", "content": "x"}], thinking="disabled")
    assert body["thinking"] == {"type": "disabled"}
    # DeepSeek ignores temperature when thinking is on; we explicitly disable
    # it, so temperature is now meaningful - confirm it lands in the body.
    assert body["temperature"] == 0.6


def test_build_body_enabled_omits_temperature_for_deepseek():
    p = _ds()
    body = _build_body(p, [{"role": "user", "content": "x"}], thinking="enabled")
    assert "thinking" not in body  # DeepSeek default IS enabled; no patch needed
    assert "temperature" not in body  # ignored in thinking mode anyway


def test_build_body_none_is_noop():
    p = _ds()
    body = _build_body(p, [{"role": "user", "content": "x"}], thinking=None)
    assert "thinking" not in body
    assert "temperature" not in body


# ---------- call_ai end-to-end (httpx mocked) ----------

def test_call_ai_uses_named_provider_base_url_and_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-key")
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        m = mock.Mock()
        m.raise_for_status = lambda: None
        m.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        return m

    monkeypatch.setattr("httpx.post", fake_post)
    out = call_ai([{"role": "user", "content": "hi"}], provider="deepseek", thinking="disabled")
    assert out == "ok"
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer ds-key"
    assert captured["json"]["model"] == "deepseek-v4-flash"
    assert captured["json"]["thinking"] == {"type": "disabled"}


def test_generate_section_forwards_provider_and_thinking(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-key")
    with mock.patch("backend.ai.client.call_ai", return_value="x<think>hidden</think>\n**bold** text") as m:
        out = generate_section("week_compare", {"cur_amount": "1", "cur_profit": "1", "cur_margin": "1",
            "prev_amount": "1", "prev_profit": "1", "prev_margin": "1", "amount_delta": "0",
            "amount_delta_rate": "0", "profit_delta": "0", "profit_delta_rate": "0", "margin_delta_pct": "0"},
            provider="deepseek", thinking="disabled")
    assert "hidden" not in out
    assert "bold" in out
    assert m.call_args.kwargs["provider"] == "deepseek"
    assert m.call_args.kwargs["thinking"] == "disabled"


def test_generate_json_forwards_provider_and_thinking(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-key")
    with mock.patch("backend.ai.client.call_ai", return_value=json.dumps([{"事项内容": "ok"}])) as m:
        out = generate_json("procurement", {"user_input": "x"}, provider="deepseek", thinking="disabled")
    assert out == [{"事项内容": "ok"}]
    assert m.call_args.kwargs["provider"] == "deepseek"
    assert m.call_args.kwargs["thinking"] == "disabled"