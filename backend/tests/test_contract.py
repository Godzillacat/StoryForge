from app.runtime.contract import describe_contract

SIMPLE = {
    "type": "object",
    "required": ["genre", "open_questions"],
    "properties": {
        "genre": {"type": "string", "title": "题材"},
        "sub_genre": {"type": "string", "title": "子类型"},
        "open_questions": {"type": "array", "items": {"type": "string"}, "title": "它没把握的问题"},
    },
}

NESTED = {
    "type": "object",
    "required": ["options"],
    "properties": {
        "options": {
            "type": "array",
            "minItems": 2,
            "title": "候选方案",
            "items": {
                "type": "object",
                "required": ["tool", "fit_score"],
                "properties": {
                    "tool": {"type": "string", "title": "结构名"},
                    "fit_score": {"type": "number", "title": "适配度"},
                    "risks": {"type": "array", "items": {"type": "string"}, "title": "风险"},
                },
            },
        },
    },
}


def test_empty_schema_returns_empty_string():
    assert describe_contract(None) == ""
    assert describe_contract({}) == ""


def test_describes_top_level_keys_with_chinese_titles():
    block = describe_contract(SIMPLE)
    assert "- genre（题材）：字符串，必填" in block
    assert "- sub_genre（子类型）：字符串" in block
    assert "必填" not in block.split("- sub_genre（子类型）")[1].split("\n")[0]


def test_describes_array_element_type_and_min_items():
    block = describe_contract(SIMPLE)
    assert "- open_questions（它没把握的问题）：数组" in block
    assert "元素是字符串" in block


def test_describes_nested_object_fields():
    block = describe_contract(NESTED)
    assert "- options（候选方案）：数组" in block
    assert "至少 2 项" in block
    # 元素对象的字段要出现在 options 之后、且缩进更深
    assert "  - tool（结构名）：字符串，必填" in block
    assert "  - fit_score（适配度）：数字，必填" in block
    assert "  - risks（风险）：数组" in block


def test_key_without_title_has_no_parentheses():
    block = describe_contract(
        {"type": "object", "properties": {"bare_key": {"type": "string"}}}
    )
    assert "- bare_key：字符串" in block


def test_enum_values_are_listed():
    block = describe_contract(
        {
            "type": "object",
            "properties": {
                "level": {"type": "string", "enum": ["loose", "strict"], "title": "严格度"}
            },
        }
    )
    assert "取值：loose、strict" in block
