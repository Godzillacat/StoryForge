import pytest

from app.runtime.render import MissingVariableError, render


def test_render_substitutes_variable():
    assert render("解析卡：{{ parsed_idea }}", {"parsed_idea": "题材：悬疑"}) == "解析卡：题材：悬疑"


def test_render_leaves_unknown_braces_alone():
    assert render("字面量 {{ 未注册 }}", {}) == "字面量 {{ 未注册 }}"


def test_render_raises_on_missing_declared_variable():
    with pytest.raises(MissingVariableError) as exc:
        render("解析卡：{{ parsed_idea }}", {})
    assert "parsed_idea" in str(exc.value)


def test_render_with_no_variables_is_identity():
    assert render("你是长篇小说结构顾问。", {}) == "你是长篇小说结构顾问。"


def test_render_handles_multiple_variables():
    out = render("{{ a }} 和 {{ b }}", {"a": "甲", "b": "乙"})
    assert out == "甲 和 乙"
