from app.agents.roster import DEFAULT_ROSTER
from app.runtime.schema import apply_contract, extract_json, validate_json

SCHEMA = {
    "type": "object",
    "required": ["genre", "open_questions"],
    "properties": {
        "genre": {"type": "string"},
        "open_questions": {"type": "array", "items": {"type": "string"}},
        "fit_score": {"type": "number"},
        "tone": {"type": "string", "enum": ["冷峻", "温暖"]},
    },
}


def test_extract_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_from_markdown_fence():
    text = '好的，这是结果：\n```json\n{"a": 1}\n```\n希望有用。'
    assert extract_json(text) == {"a": 1}


def test_extract_json_with_leading_prose_no_fence():
    assert extract_json('以下是解析卡：{"a": 1} 完毕') == {"a": 1}


def test_extract_returns_none_for_garbage():
    assert extract_json("完全不是 JSON") is None


def test_validate_accepts_conforming_object():
    ok, errors = validate_json(
        {"genre": "悬疑", "open_questions": ["主要对手是谁"], "fit_score": 0.8, "tone": "冷峻"},
        SCHEMA,
    )
    assert ok is True and errors == []


def test_validate_reports_missing_required():
    ok, errors = validate_json({"genre": "悬疑"}, SCHEMA)
    assert ok is False
    assert any("open_questions" in e for e in errors)


def test_validate_reports_wrong_type():
    ok, errors = validate_json({"genre": 3, "open_questions": []}, SCHEMA)
    assert ok is False
    assert any("genre" in e for e in errors)


def test_validate_reports_enum_violation():
    ok, errors = validate_json({"genre": "x", "open_questions": [], "tone": "阴沉"}, SCHEMA)
    assert ok is False
    assert any("tone" in e for e in errors)


def test_validate_ignores_unknown_properties():
    ok, _ = validate_json({"genre": "x", "open_questions": [], "extra": 1}, SCHEMA)
    assert ok is True


def test_validate_array_item_type():
    ok, errors = validate_json({"genre": "x", "open_questions": [1, 2]}, SCHEMA)
    assert ok is False
    assert any("open_questions" in e for e in errors)


def test_apply_contract_success_path():
    data, structured, err = apply_contract('```json\n{"genre": "悬疑", "open_questions": []}\n```', SCHEMA)
    assert data == {"genre": "悬疑", "open_questions": []}
    assert structured is True and err is None


def test_apply_contract_degrades_on_bad_json():
    data, structured, err = apply_contract("模型没按格式返回", SCHEMA)
    assert data is None and structured is False
    assert err is not None


def test_apply_contract_degrades_on_schema_violation():
    data, structured, err = apply_contract('{"genre": 5}', SCHEMA)
    assert data is None and structured is False
    assert "genre" in (err or "")


def test_apply_contract_without_schema_marks_unstructured():
    data, structured, err = apply_contract("自由文本", None)
    assert data is None and structured is False
    assert err == "该智能体未定义输出结构"


def test_extract_prefers_last_fence_over_leading_example():
    text = (
        '这是一个模板示例：\n'
        '```json\n'
        '{"genre": "题材", "open_questions": []}\n'
        '```\n'
        '以下是正式结果：\n'
        '```json\n'
        '{"genre": "悬疑", "open_questions": ["对手是谁"]}\n'
        '```\n'
    )
    assert extract_json(text) == {"genre": "悬疑", "open_questions": ["对手是谁"]}


def test_apply_contract_uses_last_fence():
    text = (
        '```json\n{"genre": "题材", "open_questions": []}\n```\n'
        '```json\n{"genre": "悬疑", "open_questions": []}\n```'
    )
    data, structured, err = apply_contract(text, SCHEMA)
    assert structured is True and err is None
    assert data["genre"] == "悬疑"


def test_optional_fields_may_be_null():
    """模型把可选字段写成 null 是「这项为空」的常见写法 —— 契约里没有
    nullable 的表达方式，不该让整份 payload 因此降级成纯文本。"""
    parser = next(e for e in DEFAULT_ROSTER if e["key"] == "idea_parser")
    payload = {
        "genre": "悬疑",
        "premise": "p",
        "protagonist_desire": "d",
        "conflict_source": "c",
        "open_questions": [],
        # 以下全是可选字段
        "sub_genre": None,
        "emotional_core": None,
        "tone": None,
        "length_expectation": None,
        "comparable_works": None,
    }

    ok, errors = validate_json(payload, parser["output_schema"])

    assert ok, errors


def test_required_fields_may_not_be_null():
    """必填字段的 null 是真空缺，不是省略 —— 仍要按类型报错。"""
    parser = next(e for e in DEFAULT_ROSTER if e["key"] == "idea_parser")
    payload = {
        "genre": None,  # 必填
        "premise": "p",
        "protagonist_desire": "d",
        "conflict_source": "c",
        "open_questions": [],
    }

    ok, errors = validate_json(payload, parser["output_schema"])

    assert not ok
    assert any("genre" in error for error in errors)


def test_the_worldbuilders_optional_hardness_may_be_null():
    """世界观构建师的非规则类候选会填一个空的硬度 —— 契约把它声明为 string，
    而模型写成 null 是同一件事的另一种写法。"""
    builder = next(e for e in DEFAULT_ROSTER if e["key"] == "worldbuilder")
    # 该契约的 entries 带 minItems=3，不足会因条数报错 —— 那条与「可选字段的
    # null」无关，故把候选凑满；后两条只留必填键，顺带盖住「可选字段缺键」。
    entry = {"type": "地理", "name": "南滨旧城", "summary": "小城"}
    payload = {
        "entries": [
            {**entry, "aliases": None, "description": None, "hardness": None},
            dict(entry, name="北岸码头"),
            dict(entry, name="西关水系"),
        ]
    }

    ok, errors = validate_json(payload, builder["output_schema"])

    assert ok, errors


def test_a_null_inside_an_array_item_is_still_checked():
    """放过的是「可选字段的 null」，不是「数组元素里的 null」—— 那里 null
    不是省略，是一个类型不对的元素。"""
    schema = {
        "type": "object",
        "required": ["items"],
        "properties": {"items": {"type": "array", "items": {"type": "string"}}},
    }

    ok, errors = validate_json({"items": ["甲", None]}, schema)

    assert not ok
    assert any("items[1]" in error for error in errors)
