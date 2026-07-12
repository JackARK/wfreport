from backend.ai.prompts import load, reload, render


def test_render_substitutes_vars():
    msgs = render("week_compare", {"cur_amount": "100", "cur_profit": "50", "cur_margin": "50",
                                   "prev_amount": "80", "prev_profit": "40", "prev_margin": "50",
                                   "amount_delta": "20", "amount_delta_rate": "25",
                                   "profit_delta": "10", "profit_delta_rate": "25", "margin_delta_pct": "0"})
    assert msgs[0]["role"] == "system"
    assert "100" in msgs[1]["content"] and "{{cur_amount}}" not in msgs[1]["content"]


def test_load_returns_dict_with_sections():
    data = load()
    assert isinstance(data, dict)
    assert "week_compare" in data
    assert "daily_summary" in data
    assert "procurement" in data
    assert "next_plan" in data


def test_render_system_message_present():
    msgs = render("week_compare", {"cur_amount": "1", "cur_profit": "1", "cur_margin": "1",
                                   "prev_amount": "1", "prev_profit": "1", "prev_margin": "1",
                                   "amount_delta": "0", "amount_delta_rate": "0",
                                   "profit_delta": "0", "profit_delta_rate": "0", "margin_delta_pct": "0"})
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert "{{" not in msgs[0]["content"]
    assert "{{" not in msgs[1]["content"]


def test_load_is_cached():
    a = load()
    b = load()
    assert a is b


def test_reload_refreshes():
    a = load()
    b = reload()
    assert a == b


def test_chinese_preserved():
    msgs = render("daily_summary", {"daily_series": "周一: 100"})
    assert "供应链周报" in msgs[0]["content"]
