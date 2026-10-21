import pytest

from app.audit_types import (
    AUDIT_KINDS,
    AUDIT_SEVERITIES,
    AUDIT_SOURCES,
    normalize_kind,
    normalize_resolution,
    normalize_severity,
)


def test_word_tables_match_design():
    assert AUDIT_KINDS == {
        "repetition": "重复",
        "alias": "称呼",
        "setting": "设定",
        "character": "人物",
        "timeline": "时间线",
        "term": "术语",
        "other": "其他",
    }
    assert AUDIT_SEVERITIES == {
        "critical": "致命",
        "major": "严重",
        "minor": "提示",
    }
    assert AUDIT_SOURCES == {"rule": "规则", "llm": "LLM"}


def test_normalize_kind_accepts_english_keys_and_chinese_labels():
    for key, label in AUDIT_KINDS.items():
        assert normalize_kind(key) == key
        assert normalize_kind(label) == key


def test_normalize_kind_falls_back_to_other_without_raising():
    for value in ("nonsense", "", "  ", None, 123, "未知分类"):
        assert normalize_kind(value) == "other"


def test_normalize_severity_accepts_english_keys_and_chinese_labels():
    for key, label in AUDIT_SEVERITIES.items():
        assert normalize_severity(key) == key
        assert normalize_severity(label) == key


def test_normalize_severity_falls_back_to_minor_without_raising():
    for value in ("nonsense", "", "  ", None, 3, "致命偏重"):
        assert normalize_severity(value) == "minor"


def test_normalize_resolution_accepts_the_four_author_actions():
    for value in ("story", "setting", "character", "exception"):
        assert normalize_resolution(value) == value


def test_normalize_resolution_rejects_anything_else():
    # 作者显式动作不自作主张：未知值必须报错，不能静默归到某一档。
    for value in ("bogus", "", None, "改故事", "open"):
        with pytest.raises(ValueError):
            normalize_resolution(value)
