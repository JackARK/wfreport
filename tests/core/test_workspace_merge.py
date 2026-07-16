from backend.core import history


def _fresh_db(tmp_path):
    db = str(tmp_path / "ws.db")
    history.init_db(db)
    return db


def test_save_workspace_full_round_trip(tmp_path):
    db = _fresh_db(tmp_path)
    history.save_workspace("2026-W27", {
        "content": "本周内容",
        "plan_text": "下周计划",
        "plan_items": [{"事项内容": "x"}],
        "procurement_items": [{"事项内容": "y"}],
        "narrative_overrides": {"week_compare": "AI 写的"},
    }, db)
    ws = history.load_workspace("2026-W27", db)
    assert ws["content"] == "本周内容"
    assert ws["plan_text"] == "下周计划"
    assert len(ws["plan_items"]) == 1
    assert len(ws["procurement_items"]) == 1
    assert ws["narrative_overrides"]["week_compare"] == "AI 写的"


def test_save_workspace_partial_update_preserves_other_fields(tmp_path):
    """P0-#1 regression: a PUT that only carries narrative_overrides must
    NOT wipe content / plan_items / procurement_items / plan_text."""
    db = _fresh_db(tmp_path)
    history.save_workspace("2026-W27", {
        "content": "本周内容",
        "plan_text": "下周计划",
        "plan_items": [{"事项内容": "p1"}],
        "procurement_items": [{"事项内容": "q1"}],
        "narrative_overrides": {"week_compare": "v1"},
    }, db)

    # Now simulate StepPreview saving ONLY narrative_overrides.
    history.save_workspace("2026-W27", {
        "narrative_overrides": {"week_compare": "v2"},
    }, db)

    ws = history.load_workspace("2026-W27", db)
    assert ws["content"] == "本周内容", "content must survive partial update"
    assert ws["plan_text"] == "下周计划"
    assert len(ws["plan_items"]) == 1, "plan_items must survive"
    assert ws["plan_items"][0]["事项内容"] == "p1"
    assert len(ws["procurement_items"]) == 1, "procurement_items must survive"
    assert ws["procurement_items"][0]["事项内容"] == "q1"
    assert ws["narrative_overrides"]["week_compare"] == "v2"


def test_save_workspace_explicit_empty_clears_field(tmp_path):
    """If a caller sends {"content": ""} explicitly, content IS cleared.
    Distinguishing 'absent' from 'present with empty' is the contract."""
    db = _fresh_db(tmp_path)
    history.save_workspace("2026-W27", {
        "content": "本周内容",
        "plan_text": "下周计划",
    }, db)
    history.save_workspace("2026-W27", {"content": ""}, db)
    ws = history.load_workspace("2026-W27", db)
    assert ws["content"] == ""
    # plan_text was absent in the second call → preserved
    assert ws["plan_text"] == "下周计划"


def test_save_workspace_can_replace_plan_items_independently(tmp_path):
    """StepFill's autosave (sends content + plan_text + plan_items +
    procurement_items, no narrative_overrides) must NOT clobber the
    AI narratives the user already edited on step 3."""
    db = _fresh_db(tmp_path)
    # Step 3 first: user edited narrative
    history.save_workspace("2026-W27", {
        "narrative_overrides": {"brand": "user-edited 品牌文案"},
    }, db)
    # Then step 2 fires an autosave (no narrative_overrides key)
    history.save_workspace("2026-W27", {
        "content": "本周新内容",
        "plan_items": [{"事项内容": "新"}],
    }, db)
    ws = history.load_workspace("2026-W27", db)
    assert ws["content"] == "本周新内容"
    assert ws["plan_items"][0]["事项内容"] == "新"
    assert ws["narrative_overrides"]["brand"] == "user-edited 品牌文案"


def test_save_workspace_first_call_creates_row(tmp_path):
    """Save on a non-existent week should not blow up — every field falls
    back to defaults from the empty existing dict."""
    db = _fresh_db(tmp_path)
    history.save_workspace("2026-W99", {"content": "first"}, db)
    ws = history.load_workspace("2026-W99", db)
    assert ws["content"] == "first"
    assert ws["plan_items"] == []
    assert ws["procurement_items"] == []