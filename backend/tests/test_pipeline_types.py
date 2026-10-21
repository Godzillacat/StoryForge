from app.agents.roster import TASK_TYPES
from app.pipeline_types import (
    DEFAULT_PIPELINE,
    NODE_STATUSES,
    PIPELINE_POLICIES,
    RUN_STATUSES,
    default_nodes,
    normalize_policy,
)


def test_default_pipeline_order():
    assert [node["task_type"] for node in DEFAULT_PIPELINE] == [
        "idea_parse",
        "architecture",
        "worldbuilding",
        "chapter_plan",
        "scene_plan",
    ]


def test_only_architecture_and_chapter_plan_are_checkpoints():
    checkpoints = [n["task_type"] for n in DEFAULT_PIPELINE if n["checkpoint"]]
    assert checkpoints == ["architecture", "chapter_plan"]


def test_default_task_types_are_registered():
    for node in DEFAULT_PIPELINE:
        assert node["task_type"] in TASK_TYPES


def test_normalize_policy_accepts_known_values():
    for value in PIPELINE_POLICIES:
        assert normalize_policy(value) == value


def test_normalize_policy_falls_back():
    assert normalize_policy("wild") == "key_only"
    assert normalize_policy(None) == "key_only"


def test_default_nodes_returns_a_fresh_list():
    first = default_nodes()
    first[0]["name"] = "改过了"
    first.append({"task_type": "extra"})

    second = default_nodes()
    assert second[0]["name"] == "灵感解析"
    assert len(second) == len(DEFAULT_PIPELINE)


def test_status_vocabularies_are_complete():
    assert "awaiting" in RUN_STATUSES
    assert "blocked" in NODE_STATUSES
    assert "skipped" in NODE_STATUSES
