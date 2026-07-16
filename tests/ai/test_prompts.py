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


def test_procurement_prompt_constrains_completion_time_format():
    """The 完成时间 column ended up filled with narrative text in production
    ("上新已完成, 爬坡持续中") because the prompt didn't constrain the
    format. Pin the contract: the prompt must list the allowed shapes
    AND forbid the bad ones."""
    msgs = render("procurement", {"user_input": "工厂 B 欠料 已出货"})
    user_msg = msgs[1]["content"]
    # Allowed shapes:
    assert "YYYY-MM-DD" in user_msg
    assert "本周" in user_msg
    assert "待定" in user_msg
    # State enum:
    assert "进行中" in user_msg and "已完成" in user_msg
    # Forbidden shapes — the prompt must call these out so the model
    # doesn't fall back into writing prose:
    assert "叙述句" in user_msg or "叙述" in user_msg, \
        "procurement prompt must explicitly forbid narrative 完成时间"
    assert "持续观察" in user_msg or "持续推进" in user_msg, \
        "procurement prompt must show a concrete anti-example"


def test_next_plan_prompt_constrains_time_format():
    msgs = render("next_plan", {"user_input": "海马抱枕系列完成图文拍摄 周二前"})
    user_msg = msgs[1]["content"]
    assert "YYYY-MM-DD" in user_msg
    assert "周三前" in user_msg
    assert "叙述句" in user_msg or "叙述" in user_msg, \
        "next_plan prompt must forbid narrative time markers"
