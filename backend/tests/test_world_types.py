import pytest

from app.world_types import (
    ENTRY_TYPES,
    HARDNESS_LEVELS,
    normalize_hardness,
    normalize_type,
)


def test_type_vocabulary_matches_the_spec():
    assert set(ENTRY_TYPES) == {
        "place",
        "faction",
        "organization",
        "rule",
        "event",
        "item",
        "concept",
        "term",
    }
    assert ENTRY_TYPES["rule"] == "规则体系"
    assert set(HARDNESS_LEVELS) == {"hard", "soft", "atmosphere"}


def test_normalize_type_accepts_both_the_key_and_the_chinese_label():
    assert normalize_type("faction") == "faction"
    assert normalize_type("势力") == "faction"
    assert normalize_type("  规则体系  ") == "rule"


def test_normalize_type_rejects_unknown_values_with_a_readable_reason():
    """报错而不是猜一个类型：猜错会把设定塞进错误的分类，作者可能很久之后才发现。"""
    with pytest.raises(ValueError) as excinfo:
        normalize_type("魔法体系")
    assert "魔法体系" in str(excinfo.value)
    assert "势力" in str(excinfo.value)  # 可读错误要列出可用值


def test_normalize_hardness_maps_labels_and_falls_back_to_none():
    assert normalize_hardness("hard") == "hard"
    assert normalize_hardness("硬规则") == "hard"
    assert normalize_hardness("氛围") == "atmosphere"
    assert normalize_hardness("") is None
    assert normalize_hardness(None) is None
    assert normalize_hardness("很硬") is None
