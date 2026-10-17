import pytest

from app.db.models import Project
from app.services import chapter_service


def _project(session) -> Project:
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    return project


def test_create_volume_appends_and_tree_orders(session):
    project = _project(session)
    first = chapter_service.create_volume(session, project.id, name="第一卷")
    second = chapter_service.create_volume(session, project.id, name="第二卷")

    assert (first.seq, second.seq) == (0, 1)
    tree = chapter_service.build_tree(session, project.id)
    assert [v["name"] for v in tree] == ["第一卷", "第二卷"]


def test_create_chapter_appends_and_tree_nests(session):
    project = _project(session)
    volume = chapter_service.create_volume(session, project.id, name="第一卷")
    first = chapter_service.create_chapter(session, volume.id, title="第一章")
    second = chapter_service.create_chapter(session, volume.id, title="第二章")

    assert (first.seq, second.seq) == (0, 1)
    tree = chapter_service.build_tree(session, project.id)
    assert [c["title"] for c in tree[0]["chapters"]] == ["第一章", "第二章"]


def test_move_volume_and_chapter(session):
    project = _project(session)
    a = chapter_service.create_volume(session, project.id, name="甲")
    b = chapter_service.create_volume(session, project.id, name="乙")
    chapter_service.move_volume(session, b.id, "up")
    assert [v["name"] for v in chapter_service.build_tree(session, project.id)] == ["乙", "甲"]

    c1 = chapter_service.create_chapter(session, a.id, title="一")
    c2 = chapter_service.create_chapter(session, a.id, title="二")
    chapter_service.move_chapter(session, c2.id, "up")
    tree = chapter_service.build_tree(session, project.id)
    volume_a = next(v for v in tree if v["id"] == a.id)
    assert [c["title"] for c in volume_a["chapters"]] == ["二", "一"]


def test_move_at_boundary_is_a_no_op(session):
    project = _project(session)
    volume = chapter_service.create_volume(session, project.id, name="唯一")
    chapter_service.move_volume(session, volume.id, "up")
    assert [v["name"] for v in chapter_service.build_tree(session, project.id)] == ["唯一"]


def test_update_and_delete_volume_cascade(session):
    project = _project(session)
    volume = chapter_service.create_volume(session, project.id, name="旧名")
    chapter = chapter_service.create_chapter(session, volume.id, title="章")
    updated = chapter_service.update_volume(
        session, volume.id, name="新名", purpose="本卷目标", act_seq=1, target_words=30000
    )
    assert updated.name == "新名"
    assert updated.act_seq == 1

    chapter_service.delete_volume(session, volume.id)
    assert chapter_service.build_tree(session, project.id) == []
    assert session.get(type(chapter), chapter.id) is None


def test_validation_rejects_empty_name_and_bad_status(session):
    project = _project(session)
    with pytest.raises(ValueError, match="名称"):
        chapter_service.create_volume(session, project.id, name="   ")
    with pytest.raises(ValueError, match="状态"):
        chapter_service.create_volume(
            session, project.id, name="卷", status="unknown"
        )


def test_validation_rejects_bad_rhythm_ranges(session):
    project = _project(session)
    volume = chapter_service.create_volume(session, project.id, name="卷")
    with pytest.raises(ValueError):
        chapter_service.create_chapter(
            session, volume.id, title="章", conflict_level=6
        )
    with pytest.raises(ValueError):
        chapter_service.create_chapter(
            session, volume.id, title="章", dialogue_ratio=1.5
        )


def test_tree_includes_empty_scene_and_foreshadow_slots(session):
    project = _project(session)
    volume = chapter_service.create_volume(session, project.id, name="卷")
    chapter_service.create_chapter(session, volume.id, title="章")

    tree = chapter_service.build_tree(session, project.id)

    assert tree[0]["chapters"][0]["scenes"] == []
