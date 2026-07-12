import json
from unittest import mock

from backend.ai.client import generate_section, generate_json, _fallback, call_ai


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
    try:
        call_ai([{"role": "system", "content": "x"}, {"role": "user", "content": "y"}])
        assert False, "should have raised"
    except RuntimeError:
        pass


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
