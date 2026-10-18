from app.agents.roster import DEFAULT_ROSTER, TASK_TYPES
from app.runtime.context import SLOT_REGISTRY
from app.world_types import CHARACTER_FIELDS


def test_task_types_cover_documented_roster():
    for task in (
        "idea_parse",
        "architecture",
        "worldbuilding",
        "chapter_plan",
        "scene_plan",
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

_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# 提示词里正当出现的非字段英文词（故事圣经 v0 的版本号、正文格式名）
_ALLOWED_LATIN = {"v0", "Markdown"}


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
        if not entry["output_schema"]:
            continue
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
        if not entry["output_schema"]:
            continue
        walk(entry["output_schema"], entry["key"])


def test_preset_prompts_do_not_hand_list_field_keys():
    """提示词里不许再出现字段键 —— 那份清单已由契约说明块自动生成。

    不能只查 snake_case：schema 的键多为单字（genre/premise/reason/tool…），
    而「在 reason 里说明缺什么」这种漂移正是最可能的复发形态。
    """
    for entry in DEFAULT_ROSTER:
        allowed = set(entry["context_slots"]) | _ALLOWED_LATIN
        found = set(_WORD_RE.findall(entry["system_prompt"]))
        hand_listed = found - allowed
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


def test_worldbuilder_is_in_the_default_roster():
    entry = next(e for e in DEFAULT_ROSTER if e["key"] == "worldbuilder")
    assert entry["task_type"] == "worldbuilding"
    assert entry["trigger_mode"] == "assist"
    assert entry["context_slots"] == ["parsed_idea", "story_bible", "project_core"]


def test_worldbuilder_prompt_forbids_inventing_settings():
    entry = next(e for e in DEFAULT_ROSTER if e["key"] == "worldbuilder")
    prompt = entry["system_prompt"]
    assert "编造" in prompt or "不许编" in prompt


def test_worldbuilder_schema_has_entries_and_open_questions():
    entry = next(e for e in DEFAULT_ROSTER if e["key"] == "worldbuilder")
    props = entry["output_schema"]["properties"]
    assert set(props) == {"entries", "open_questions"}
    assert entry["output_schema"]["required"] == ["entries"]
    item = props["entries"]["items"]
    assert set(item["properties"]) == {
        "type",
        "name",
        "aliases",
        "summary",
        "description",
        "hardness",
    } | set(CHARACTER_FIELDS)
    assert item["required"] == ["type", "name", "summary"]


def test_worldbuilder_character_fields_are_optional_and_generated_from_the_vocabulary():
    """人物八项**从唯一真相生成**：键与中文标签都必须与 CHARACTER_FIELDS 一致。

    它们是可选的 —— 非人物候选不填；契约校验器放过的「可选字段为 null」
    正好兜住这类省略。
    """
    entry = next(e for e in DEFAULT_ROSTER if e["key"] == "worldbuilder")
    item = entry["output_schema"]["properties"]["entries"]["items"]

    for key, (label, _multiline) in CHARACTER_FIELDS.items():
        assert key not in item["required"]
        assert item["properties"][key]["title"] == f"{label}（只有人物才填）"
        assert item["properties"][key]["type"] == "string"


def test_chapter_planner_is_in_the_default_roster():
    entry = next(e for e in DEFAULT_ROSTER if e["key"] == "chapter_planner")
    assert entry["task_type"] == "chapter_plan"
    assert entry["context_slots"] == [
        "project_core",
        "story_bible",
        "architecture",
        "parsed_idea",
        "world_context",
        "tool_library",
    ]
    props = entry["output_schema"]["properties"]
    assert set(props) == {"volumes", "open_questions"}
    chapter = props["volumes"]["items"]["properties"]["chapters"]["items"]
    assert {"title", "pov", "target_words", "conflict_level", "dialogue_ratio", "hook_strength"} <= set(
        chapter["properties"]
    )
    assert "编造" in entry["system_prompt"]


def test_scene_planner_is_in_the_default_roster():
    entry = next(e for e in DEFAULT_ROSTER if e["key"] == "scene_planner")
    assert entry["task_type"] == "scene_plan"
    assert entry["context_slots"] == [
        "project_core",
        "story_bible",
        "architecture",
        "world_context",
        "timeline",
        "volume_outline",
        "chapter_outline",
        "tool_library",
    ]
    props = entry["output_schema"]["properties"]
    assert set(props) == {"scenes", "open_questions"}
    scene = props["scenes"]["items"]
    assert {"goal", "conflict", "turn", "characters", "location", "foreshadow_plants", "foreshadow_pays"} <= set(
        scene["properties"]
    )
    assert "编造" in entry["system_prompt"]


def test_writer_is_in_the_default_roster():
    entry = next(e for e in DEFAULT_ROSTER if e["key"] == "writer")
    assert entry["name"] == "执笔"
    assert entry["task_type"] == "write"
    assert entry["output_schema"] is None
    assert entry["param_profile"] == "balanced"
    assert entry["trigger_mode"] == "manual"
    assert entry["context_slots"] == [
        "project_core",
        "story_bible",
        "world_context",
        "volume_outline",
        "chapter_outline",
        "timeline",
        "scene_card",
        "scene_characters",
        "related_settings",
        "recent_text",
    ]


def test_writer_prompt_is_plain_prose_not_json():
    entry = next(e for e in DEFAULT_ROSTER if e["key"] == "writer")
    prompt = entry["system_prompt"]
    assert "场景卡" in prompt
    assert "目标、冲突、转折、视角、故事内时间与目标字数" in prompt
    assert "Markdown 正文" in prompt
    assert "不要用代码块" in prompt
    assert "JSON" not in prompt
    assert entry["output_schema"] is None


def test_worldbuilder_type_descriptions_match_the_vocabulary():
    """契约里的字段说明必须把类型词表里的每一类都讲到 —— 提示词里不许写
    英文键（护栏会拦），所以模型只可能从契约说明块里知道有哪些类型。"""
    from app.world_types import ENTRY_TYPES

    entry = next(e for e in DEFAULT_ROSTER if e["key"] == "worldbuilder")
    described = describe_contract(entry["output_schema"])

    for label in ENTRY_TYPES.values():
        assert label in described, f"契约说明块没有讲到类型「{label}」"


_SLOT_VARIABLE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def test_every_prompt_slot_variable_is_registered():
    """提示词里的每个 {{ 槽位 }} 都必须是 SLOT_REGISTRY 的键。

    纯文本预置（writer）走 `allow_missing=True`：槽位天然可能为空，渲染层
    因此把「变量没有对应内容」当成空串而不是错误。拼错的槽位会被静默渲染
    成空串 —— 作者得不到任何报错，只会在真实调用里发现上下文缺了一段。
    这条测试就是那道放宽的护栏。
    """
    for entry in DEFAULT_ROSTER:
        used = set(_SLOT_VARIABLE.findall(entry["system_prompt"]))
        unknown = used - set(SLOT_REGISTRY)
        assert not unknown, (
            f"{entry['key']} 的提示词引用了未注册的槽位：{sorted(unknown)}"
        )
