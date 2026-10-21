import pytest

from app.logic_types import (
    LOGIC_LAYERS,
    LOGIC_STAGES,
    normalize_layer,
    normalize_stage,
)


def test_logic_layers_match_the_product_five_layers():
    assert LOGIC_LAYERS == {
        "world_rule": "世界规则",
        "causality": "因果链",
        "motivation": "动机与性格",
        "information": "信息流",
        "setting_load": "设定载荷",
        "other": "其他",
    }
    assert LOGIC_STAGES == {"plan": "场景卡", "text": "正文"}


def test_normalize_layer_accepts_keys_and_labels():
    assert normalize_layer("causality") == "causality"
    assert normalize_layer("因果链") == "causality"
    assert normalize_layer(" 世界规则 ") == "world_rule"


def test_normalize_layer_falls_back_to_other():
    assert normalize_layer("不存在的层") == "other"
    assert normalize_layer(None) == "other"
    assert normalize_layer(123) == "other"


def test_normalize_stage_accepts_both_stages():
    assert normalize_stage("plan") == "plan"
    assert normalize_stage("text") == "text"
    assert normalize_stage(" plan ") == "plan"


def test_normalize_stage_rejects_unknown_values():
    for value in ("", "draft", None, 1):
        with pytest.raises(ValueError, match="未知的逻辑自检时机"):
            normalize_stage(value)
