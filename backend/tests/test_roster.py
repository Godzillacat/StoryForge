from app.agents.roster import DEFAULT_ROSTER, TASK_TYPES


def test_task_types_cover_documented_roster():
    for task in (
        "idea_parse",
        "architecture",
        "worldbuilding",
        "chapter_plan",
        "write",
        "polish",
        "continuity",
        "logic_check",
        "reader",
        "assistant",
    ):
        assert task in TASK_TYPES


def test_roster_defines_the_two_p1a_agents():
    keys = {entry["key"] for entry in DEFAULT_ROSTER}
    assert {"idea_parser", "architect"} <= keys


def test_every_roster_entry_has_required_fields():
    for entry in DEFAULT_ROSTER:
        assert entry["key"] and entry["name"] and entry["task_type"]
        assert entry["system_prompt"].strip()
        assert isinstance(entry["context_slots"], list) and entry["context_slots"]
        assert entry["param_profile"] in {"strict", "balanced", "creative"}


def test_architect_prompt_forbids_deciding_for_the_author():
    architect = next(e for e in DEFAULT_ROSTER if e["key"] == "architect")
    prompt = architect["system_prompt"]
    assert "不替作者决定" in prompt or "只作建议" in prompt


def test_parser_prompt_requires_asking_instead_of_inventing():
    parser = next(e for e in DEFAULT_ROSTER if e["key"] == "idea_parser")
    assert "不许编" in parser["system_prompt"] or "编造" in parser["system_prompt"]


def test_parser_output_schema_lists_documented_fields():
    parser = next(e for e in DEFAULT_ROSTER if e["key"] == "idea_parser")
    props = parser["output_schema"]["properties"]
    for field in (
        "genre",
        "sub_genre",
        "premise",
        "protagonist_desire",
        "conflict_source",
        "emotional_core",
        "tone",
        "length_expectation",
        "comparable_works",
        "open_questions",
    ):
        assert field in props


def test_architect_output_schema_has_options_and_bible():
    architect = next(e for e in DEFAULT_ROSTER if e["key"] == "architect")
    props = architect["output_schema"]["properties"]
    assert "options" in props and "story_bible_v0" in props


import re

from app.runtime.contract import describe_contract

_KEY_IN_BLOCK = re.compile(r"^\s*- ([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)


def _property_keys(schema: dict) -> set[str]:
    """递归收集契约里出现过的全部字段键。"""
    keys: set[str] = set()
    for key, sub in (schema.get("properties") or {}).items():
        keys.add(key)
        if sub.get("type") == "object":
            keys |= _property_keys(sub)
        elif sub.get("type") == "array":
            item = sub.get("items") or {}
            if item.get("type") == "object":
                keys |= _property_keys(item)
    return keys


def test_contract_block_covers_every_field_of_every_preset_agent():
    """跨产物一致性：契约里的每个字段，说明块都必须讲到。

    这是本切片补的关键测试。旧测试把「提示词」与「契约」分开验，没有一条
    要求两者一致，于是键名不一致在真实模型下必败、却全程没被发现。
    """
    for entry in DEFAULT_ROSTER:
        schema = entry["output_schema"]
        described = set(_KEY_IN_BLOCK.findall(describe_contract(schema)))
        missing = _property_keys(schema) - described
        assert not missing, f"{entry['key']} 的契约说明块漏了字段：{sorted(missing)}"


def test_every_schema_property_carries_a_chinese_title():
    """字段清单只能有一份：中文名必须长在契约上，提示词不再手抄。"""
    def walk(node: dict, path: str) -> None:
        for key, sub in (node.get("properties") or {}).items():
            assert sub.get("title"), f"{path}.{key} 缺少中文 title"
            if sub.get("type") == "object":
                walk(sub, f"{path}.{key}")
            elif sub.get("type") == "array" and (sub.get("items") or {}).get("type") == "object":
                walk(sub["items"], f"{path}.{key}[]")

    for entry in DEFAULT_ROSTER:
        walk(entry["output_schema"], entry["key"])


def test_preset_prompts_do_not_hand_list_field_keys():
    """提示词里不许再出现字段键 —— 那份清单已经由契约说明块自动生成。"""
    for entry in DEFAULT_ROSTER:
        found = set(re.findall(r"\b[a-z]+(?:_[a-z]+)+\b", entry["system_prompt"]))
        hand_listed = found - set(entry["context_slots"])
        assert not hand_listed, f"{entry['key']} 的提示词手写了字段键：{sorted(hand_listed)}"


def test_adding_titles_does_not_change_validation():
    """title 是给渲染层读的，校验器不该受它影响 —— 加字段说明不该改动校验语义。"""
    from app.runtime.schema import apply_contract

    parser = next(e for e in DEFAULT_ROSTER if e["key"] == "idea_parser")
    valid = (
        '{"genre": "悬疑", "premise": "p", "protagonist_desire": "d",'
        ' "conflict_source": "c", "open_questions": []}'
    )
    parsed, ok, error = apply_contract(valid, parser["output_schema"])
    assert ok is True and error is None
    assert parsed["genre"] == "悬疑"

    _, ok_missing, error_missing = apply_contract('{"genre": "悬疑"}', parser["output_schema"])
    assert ok_missing is False
    assert "premise" in (error_missing or "")
