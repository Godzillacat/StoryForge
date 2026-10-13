import json
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent / "app" / "tools_lib"

# 上位文档 §4.3 的完整清单
EXPECTED_KEYS = {
    "three_act", "four_act", "five_act", "hero_journey", "save_the_cat",
    "seven_point", "qi_cheng_zhuan_he", "jo_ha_kyu", "fichtean_curve",
    "golden_three_chapters", "volume_climax_layout", "hook_density", "chapter_payoff_beats",
    "character_arc", "want_vs_need", "trauma_backstory", "antagonist_mirror", "relationship_map",
    "tension_curve", "scene_sequel", "chapter_end_hooks",
    "theme_sentence", "motif", "symbol", "recurring_imagery",
}

VALID_CATEGORIES = {"通用结构", "长篇连载结构", "人物", "节奏", "主题"}


def _load_all():
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(TOOLS_DIR.glob("*.json"))]


def test_every_documented_tool_exists():
    assert {t["key"] for t in _load_all()} == EXPECTED_KEYS


def test_every_tool_has_required_fields():
    for tool in _load_all():
        assert tool["key"] and tool["name"] and tool["category"]
        assert tool["description"].strip()
        assert tool["category"] in VALID_CATEGORIES
        assert isinstance(tool["definition"], dict) and tool["definition"]
        assert isinstance(tool["checklist"], list) and tool["checklist"]


def test_every_tool_defines_slots():
    for tool in _load_all():
        slots = tool["definition"].get("slots")
        assert isinstance(slots, list) and slots, f"{tool['key']} 缺少 slots"
        for slot in slots:
            assert slot.get("key") and slot.get("label")


def test_all_categories_are_represented():
    assert {t["category"] for t in _load_all()} == VALID_CATEGORIES


def test_keys_are_unique():
    keys = [t["key"] for t in _load_all()]
    assert len(keys) == len(set(keys))
