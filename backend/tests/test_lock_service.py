"""锁定的解析与设置：有效锁定、继承、段落锁与缺失比对。"""

import pytest

from app.db.models import Chapter, Project, Scene, SettingEntry, Volume
from app.lock_types import normalize_target_type
from app.services import lock_service


def _tree(session):
    project = Project(name="锁定项目")
    session.add(project)
    session.commit()
    volume = Volume(project_id=project.id, seq=0, name="第一卷")
    session.add(volume)
    session.commit()
    chapter = Chapter(volume_id=volume.id, seq=0, title="第一章")
    session.add(chapter)
    session.commit()
    scene = Scene(chapter_id=chapter.id, seq=0, goal="第一场")
    session.add(scene)
    session.commit()
    return project, volume, chapter, scene


def test_an_unlocked_scene_is_not_locked(session):
    _project, _volume, _chapter, scene = _tree(session)

    state = lock_service.effective_scene_lock(session, scene)

    assert state["locked"] is False
    assert state["source"] is None


def test_a_locked_chapter_locks_its_scenes(session):
    _project, _volume, chapter, scene = _tree(session)
    chapter.locked = True
    session.commit()

    state = lock_service.effective_scene_lock(session, scene)

    assert state["locked"] is True
    assert state["source"] == "chapter"
    assert state["source_id"] == chapter.id
    assert "第一章" in state["label"]


def test_a_locked_volume_locks_chapters_and_scenes(session):
    _project, volume, chapter, scene = _tree(session)
    volume.locked = True
    session.commit()

    assert lock_service.effective_scene_lock(session, scene)["source"] == "volume"
    assert lock_service.effective_chapter_lock(session, chapter)["source"] == "volume"


def test_the_scene_own_lock_wins_over_its_ancestors(session):
    _project, volume, _chapter, scene = _tree(session)
    volume.locked = True
    scene.locked = True
    session.commit()

    state = lock_service.effective_scene_lock(session, scene)

    assert state["source"] == "scene"


def test_set_locked_round_trips_for_every_target_type(session):
    project, volume, chapter, scene = _tree(session)
    entry = SettingEntry(project_id=project.id, type="character", name="沈砚")
    session.add(entry)
    session.commit()

    for kind, target_id in (
        ("entry", entry.id),
        ("volume", volume.id),
        ("chapter", chapter.id),
        ("scene", scene.id),
    ):
        result = lock_service.set_locked(session, kind, target_id, True)
        assert result["own_locked"] is True
        assert result["locked"] is True

        result = lock_service.set_locked(session, kind, target_id, False)
        assert result["own_locked"] is False


def test_unknown_target_type_is_rejected():
    with pytest.raises(ValueError, match="未知的锁定目标类型"):
        normalize_target_type("chapterr")


def test_missing_target_is_reported(session):
    with pytest.raises(ValueError, match="场景不存在"):
        lock_service.set_locked(session, "scene", "nope", True)


def test_missing_locks_is_exact_text_matching():
    body = "第一段。\n\n第二段。\n\n第三段。"
    assert lock_service.missing_locks(body, ["第二段。"]) == []
    assert lock_service.missing_locks(body, []) == []


def test_missing_locks_reports_the_text_that_is_gone():
    body = "第一段。\n\n第二段。\n\n第三段。"
    assert lock_service.missing_locks(body, ["第四段。"]) == ["第四段。"]


def test_missing_locks_is_not_fooled_by_a_one_character_edit():
    body = "第一段。\n\n第二段改了一个字。\n\n第三段。"
    assert lock_service.missing_locks(body, ["第二段。"]) == ["第二段。"]


def test_missing_locks_survives_reordering():
    body = "第三段。\n\n第一段。"
    assert lock_service.missing_locks(body, ["第一段。", "第三段。"]) == []


def test_paragraphs_of_ignores_blank_paragraphs():
    assert lock_service.paragraphs_of("一。\n\n\n\n二。\n\n   \n\n三。") == ["一。", "二。", "三。"]
    assert lock_service.paragraphs_of(None) == []


def test_set_paragraph_locks_trims_and_dedupes(session):
    _project, _volume, _chapter, scene = _tree(session)

    rows = lock_service.set_paragraph_locks(
        session, scene.id, ["  第一段。  ", "第一段。", "", "第二段。"]
    )

    assert rows == ["第一段。", "第二段。"]
    session.expire_all()
    assert lock_service.paragraph_locks(session, scene.id) == ["第一段。", "第二段。"]


def test_locked_scene_ids_includes_inherited_locks(session):
    _project, _volume, chapter, scene = _tree(session)
    other = Scene(chapter_id=chapter.id, seq=1, goal="第二场")
    session.add(other)
    session.commit()
    chapter.locked = True
    session.commit()

    assert lock_service.locked_scene_ids(session, [scene.id, other.id]) == {
        scene.id,
        other.id,
    }


def test_locked_scene_ids_is_empty_for_unknown_ids(session):
    assert lock_service.locked_scene_ids(session, ["nope"]) == set()
    assert lock_service.locked_scene_ids(session, []) == set()
