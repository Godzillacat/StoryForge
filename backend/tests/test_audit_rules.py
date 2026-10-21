from types import SimpleNamespace

from app.audit_rules import run_rule_checks


def _entry(entry_id: str, name: str, aliases: list[str] | None = None):
    return SimpleNamespace(
        id=entry_id,
        name=name,
        aliases_json=aliases or [],
        type="character",
    )


def _term(entry_id: str, entry_name: str, form: str) -> dict:
    return {
        "entry_id": entry_id,
        "entry_name": entry_name,
        "type": "character",
        "form": form,
        "is_primary": form == entry_name,
    }


def _check(body: str, *, terms=None, scene_character_ids=None, entries=None):
    return run_rule_checks(
        body,
        terms or [],
        scene_character_ids or [],
        entries or {},
    )


def test_repeated_sentence_reports_once():
    body = "雨落在旧城的铁皮屋顶上，声音像有人在数硬币。雨落在旧城的铁皮屋顶上，声音像有人在数硬币。"
    issues = _check(body)

    assert len(issues) == 1
    issue = issues[0]
    assert issue.kind == "repetition"
    assert issue.quote == "雨落在旧城的铁皮屋顶上，声音像有人在数硬币"
    assert issue.fingerprint.startswith("rule:repetition:")


def test_short_repeated_sentence_is_ignored():
    assert _check("好。好。") == []


def test_repetition_splits_on_multiple_punctuation():
    sentence = "档案室的门在自己身后合上，走廊里只剩雨声"
    body = f"{sentence}！{sentence}？{sentence}"
    issues = _check(body)

    # 第 2、3 次各报一条，但指纹相同（服务层会按指纹去重）
    assert len(issues) == 2
    assert {issue.fingerprint for issue in issues} == {issues[0].fingerprint}


def test_repetition_severity_depends_on_length():
    short_sentence = "走廊里的灯一盏一盏暗下去"  # 12 字，minor
    long_sentence = "走廊里的灯一盏一盏暗下去，像有人在远处慢慢合上一本很厚的书"  # ≥20，major

    short_issues = _check(f"{short_sentence}。{short_sentence}。")
    long_issues = _check(f"{long_sentence}。{long_sentence}。")

    assert short_issues[0].severity == "minor"
    assert long_issues[0].severity == "major"


def test_repetition_fingerprint_is_stable_across_whitespace():
    first = _check("雨落在旧城的铁皮屋顶上，声音像有人在数硬币。雨落在旧城的铁皮屋顶上，声音像有人在数硬币。")
    second = _check("雨落在旧城的铁皮屋顶上，声音像 有人在数硬币。\n雨落在旧城的铁皮屋顶上，声音像 有人在数硬币。")

    assert first[0].fingerprint == second[0].fingerprint


def test_shared_alias_reports_when_it_appears():
    terms = [
        _term("c1", "陈默", "陈默"),
        _term("c1", "陈默", "老师"),
        _term("c2", "沈砚", "沈砚"),
        _term("c2", "沈砚", "老师"),
    ]
    entries = {"c1": _entry("c1", "陈默", ["老师"]), "c2": _entry("c2", "沈砚", ["老师"])}

    issues = _check(
        "老师把录音带推到桌子中央。",
        terms=terms,
        scene_character_ids=["c1", "c2"],
        entries=entries,
    )

    alias_issues = [issue for issue in issues if issue.kind == "alias" and issue.quote == "老师"]
    assert len(alias_issues) == 1
    issue = alias_issues[0]
    assert issue.target_entry_id is None
    assert "陈默" in issue.rule_ref and "沈砚" in issue.rule_ref
    assert issue.fingerprint == "rule:alias:老师"


def test_shared_alias_not_reported_when_form_absent():
    terms = [
        _term("c1", "陈默", "陈默"),
        _term("c1", "陈默", "老师"),
        _term("c2", "沈砚", "沈砚"),
        _term("c2", "沈砚", "老师"),
    ]
    entries = {"c1": _entry("c1", "陈默", ["老师"]), "c2": _entry("c2", "沈砚", ["老师"])}

    issues = _check(
        "陈默把录音带推到桌子中央。",
        terms=terms,
        scene_character_ids=["c1", "c2"],
        entries=entries,
    )

    assert [issue for issue in issues if issue.kind == "alias" and issue.quote == "老师"] == []


def test_character_mentioned_by_alias_is_not_flagged():
    entry = _entry("c1", "沈砚", ["阿砚"])
    terms = [_term("c1", "沈砚", "沈砚"), _term("c1", "沈砚", "阿砚")]

    issues = _check(
        "阿砚把录音带推到桌子中央。",
        terms=terms,
        scene_character_ids=["c1"],
        entries={"c1": entry},
    )

    assert [issue for issue in issues if issue.fingerprint == "rule:unmentioned:c1"] == []


def test_unmentioned_character_reports_with_target():
    entry = _entry("c1", "沈砚", ["阿砚"])

    issues = _check(
        "档案室的门在自己身后合上。",
        scene_character_ids=["c1"],
        entries={"c1": entry},
    )

    assert len(issues) == 1
    issue = issues[0]
    assert issue.kind == "alias"
    assert issue.target_entry_id == "c1"
    assert issue.fingerprint == "rule:unmentioned:c1"
    assert "代词" in issue.explanation
    assert issue.options


def test_clean_body_returns_no_issues():
    entry = _entry("c1", "沈砚", ["阿砚"])
    terms = [_term("c1", "沈砚", "沈砚"), _term("c1", "沈砚", "阿砚")]
    body = "阿砚把录音带推到桌子中央，窗外的雨一直没有停。"

    assert (
        _check(body, terms=terms, scene_character_ids=["c1"], entries={"c1": entry}) == []
    )


def test_empty_body_returns_no_issues():
    entry = _entry("c1", "沈砚")
    assert _check("   \n ", scene_character_ids=["c1"], entries={"c1": entry}) == []


def test_rule_issues_have_readable_text_and_options():
    body = "雨落在旧城的铁皮屋顶上，声音像有人在数硬币。雨落在旧城的铁皮屋顶上，声音像有人在数硬币。"
    issue = _check(body)[0]

    assert issue.quote
    assert issue.explanation
    assert issue.reader_impact
    assert 2 <= len(issue.options) <= 3
