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
