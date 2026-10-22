"""改动历史：每个接入点各写一条，业务失败不留记录。"""

from app.db.models import Chapter, Project, Scene, SettingEntry, Volume
from app.services import (
    architecture_service,
    change_service,
    chapter_service,
    scene_service,
    text_service,
    world_service,
)


def _seed(session):
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    volume = Volume(project_id=project.id, seq=0, name="第一卷")
    session.add(volume)
    session.commit()
    chapter = Chapter(volume_id=volume.id, seq=0, title="第一章")
    session.add(chapter)
    session.commit()
    scene = Scene(chapter_id=chapter.id, seq=0, goal="开场", body="旧正文")
    session.add(scene)
    session.commit()
    return project, volume, chapter, scene


def _rows(session, project_id):
    return change_service.list_changes(session, project_id)["changes"]


def test_saving_the_body_records_an_author_change(session):
    project, _volume, _chapter, scene = _seed(session)

    text_service.save_body(session, scene.id, "新正文，写了两句。")

    rows = _rows(session, project.id)
    assert len(rows) == 1
    assert rows[0]["target_type"] == "scene"
    assert rows[0]["action"] == "update"
    assert rows[0]["source"] == "author"
    assert "正文" in rows[0]["summary"]
    assert rows[0]["target_label"] == "第1卷 第1章 场景1"


def test_saving_an_unchanged_body_records_nothing(session):
    project, _volume, _chapter, scene = _seed(session)

    text_service.save_body(session, scene.id, "旧正文")

    assert _rows(session, project.id) == []


def test_adopting_a_draft_records_an_ai_change(session):
    from app.db.models import SceneDraft

    project, _volume, _chapter, scene = _seed(session)
    session.add(SceneDraft(scene_id=scene.id, content="采纳的内容。"))
    session.commit()

    text_service.adopt_draft(session, scene.id)

    rows = _rows(session, project.id)
    assert rows[0]["action"] == "adopt"
    assert rows[0]["source"] == "ai"


def test_restoring_a_revision_records_a_restore(session):
    project, _volume, _chapter, scene = _seed(session)
    state = text_service.save_body(session, scene.id, "第一版。")
    old = state["revisions"][0]
    text_service.save_body(session, scene.id, "第二版。")

    text_service.restore_revision(session, scene.id, old["id"])

    rows = _rows(session, project.id)
    assert any(row["action"] == "restore" for row in rows)


def test_editing_a_chapter_and_a_volume_records_the_fields(session):
    project, volume, chapter, _scene = _seed(session)

    chapter_service.update_volume(session, volume.id, name="改名了")
    chapter_service.update_chapter(session, chapter.id, hook="新的钩子")

    rows = _rows(session, project.id)
    assert {row["target_type"] for row in rows} == {"volume", "chapter"}
    volume_row = next(row for row in rows if row["target_type"] == "volume")
    assert "卷名" in volume_row["summary"]
    assert "改名了" in volume_row["target_label"]


def test_editing_a_scene_card_records_a_change(session):
    project, _volume, _chapter, scene = _seed(session)

    scene_service.update_scene(session, scene.id, goal="换了个目标")

    rows = _rows(session, project.id)
    assert rows[0]["target_type"] == "scene"


def test_entry_create_update_delete_each_record(session):
    project, *_ = _seed(session)

    entry = world_service.create_entry(session, project.id, type="character", name="沈砚")
    world_service.update_entry(session, entry.id, desire="查清真相")
    world_service.delete_entry(session, entry.id)

    rows = _rows(session, project.id)
    assert [row["action"] for row in rows] == ["delete", "update", "create"]
    # 对象已删，历史里仍读得懂 —— 记的是当时的名称。
    assert rows[0]["target_label"] == "沈砚"


def test_architecture_adoption_is_recorded(session):
    project, *_ = _seed(session)

    architecture_service.adopt(
        session,
        project.id,
        {"logline": "一句话", "acts": [{"seq": 1, "name": "第一幕"}]},
    )

    rows = _rows(session, project.id)
    assert rows[0]["target_type"] == "architecture"
    assert rows[0]["action"] == "adopt"


def test_a_failed_write_leaves_no_history(session):
    """业务回滚时日志跟着回滚 —— 不记一笔没发生的事。"""
    project, *_ = _seed(session)
    world_service.create_entry(session, project.id, type="character", name="沈砚")

    try:
        world_service.create_entry(session, project.id, type="character", name="沈砚")
    except ValueError:
        pass

    rows = [row for row in _rows(session, project.id) if row["action"] == "create"]
    assert len(rows) == 1


def test_filtering_by_target_returns_only_that_object(session):
    project, _volume, chapter, scene = _seed(session)
    chapter_service.update_chapter(session, chapter.id, hook="钩子")
    text_service.save_body(session, scene.id, "新正文。")

    body = change_service.list_changes(
        session, project.id, target_type="scene", target_id=scene.id
    )

    assert len(body["changes"]) == 1
    assert body["changes"][0]["target_id"] == scene.id


def test_an_unknown_target_type_filter_is_rejected(session):
    import pytest

    project, *_ = _seed(session)

    with pytest.raises(ValueError, match="未知的历史目标类型"):
        change_service.list_changes(session, project.id, target_type="chapterr")


def test_history_is_newest_first(session):
    project, _volume, chapter, scene = _seed(session)
    chapter_service.update_chapter(session, chapter.id, hook="第一次")
    text_service.save_body(session, scene.id, "正文。")

    rows = _rows(session, project.id)

    assert rows[0]["target_type"] == "scene"
