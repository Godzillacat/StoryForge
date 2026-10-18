from app.db.models import Project
from app.services import chapter_plan_service


def test_normalize_chapter_plan_clamps_and_warns():
    parsed = {
        "volumes": [
            {
                "name": "第一卷",
                "act_seq": 9,
                "target_words": -3,
                "chapters": [
                    {
                        "title": "第一章",
                        "conflict_level": 9,
                        "dialogue_ratio": 2,
                        "hook_strength": 4,
                        "lines": ["主线"],
                    }
                ],
            }
        ],
        "open_questions": ["第二卷要不要换视角？"],
    }

    volumes, warnings = chapter_plan_service.normalize_chapter_plan(parsed, {1, 2})

    assert volumes[0]["name"] == "第一卷"
    assert volumes[0]["act_seq"] is None
    assert volumes[0]["target_words"] is None
    chapter = volumes[0]["chapters"][0]
    assert chapter["conflict_level"] is None
    assert chapter["dialogue_ratio"] is None
    assert chapter["hook_strength"] == 4
    assert chapter["lines"] == ["主线"]
    assert len(warnings) >= 4


def test_normalize_scene_plan_warns_unknown_names(session):
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    from app.services import world_service

    world_service.create_entry(session, project.id, type="character", name="陈默")

    parsed = {
        "scenes": [
            {
                "goal": "找到录音带",
                "conflict": "档案室有人",
                "turn": "录音带里是自己的声音",
                "characters": ["陈默", "不存在"],
                "location": "不存在的地方",
                "target_words_min": 1500,
                "target_words_max": 800,
                "foreshadow_plants": ["失忆的录音带"],
            }
        ],
        "open_questions": [],
    }

    scenes, warnings = chapter_plan_service.normalize_scene_plan(parsed, session, project.id)

    assert scenes[0]["characters"] == ["陈默", "不存在"]
    assert scenes[0]["target_words_min"] == 800
    assert scenes[0]["target_words_max"] == 1500
    assert any("不存在" in warning for warning in warnings)
    assert any("交换" in warning for warning in warnings)
