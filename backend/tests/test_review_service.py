"""待复核标记：幂等新增、列表、单条 / 批量清除、对象删除时清理。"""

import pytest

from app.db.models import Chapter, Project, ReviewMark, Scene, SettingEntry, Volume
from app.services import review_service, world_service


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
    scene = Scene(chapter_id=chapter.id, seq=0, goal="开场")
    session.add(scene)
    session.commit()
    entry = SettingEntry(project_id=project.id, type="character", name="沈砚")
    session.add(entry)
    session.commit()
    return project, volume, chapter, scene, entry


def test_add_marks_is_idempotent(session):
    project, _volume, _chapter, scene, _entry = _seed(session)

    first = review_service.add_marks(
        session,
        project.id,
        [{"target_type": "scene", "target_id": scene.id, "reason": "架构已改"}],
    )
    second = review_service.add_marks(
        session,
        project.id,
        [{"target_type": "scene", "target_id": scene.id, "reason": "又改了一次"}],
    )

    assert first == 1
    assert second == 0
    rows = review_service.list_marks(session, project.id)
    assert len(rows) == 1
    # 原因更新为最新一次的 —— 作者看到的是「为什么现在要复核」。
    assert rows[0]["reason"] == "又改了一次"


def test_marks_carry_a_label_and_a_path(session):
    project, volume, _chapter, scene, entry = _seed(session)
    review_service.add_marks(
        session,
        project.id,
        [
            {"target_type": "scene", "target_id": scene.id},
            {"target_type": "entry", "target_id": entry.id},
            {"target_type": "volume", "target_id": volume.id},
        ],
    )

    rows = {row["target_type"]: row for row in review_service.list_marks(session, project.id)}

    assert rows["scene"]["label"] == "第1卷 第1章 场景1"
    assert rows["scene"]["path"].endswith(f"scene={scene.id}")
    assert rows["entry"]["label"] == "沈砚"
    assert "/world" in rows["entry"]["path"]
    assert "第一卷" in rows["volume"]["label"]


def test_list_marks_is_empty_for_a_fresh_project(session):
    project, _volume, _chapter, _scene, _entry = _seed(session)

    assert review_service.list_marks(session, project.id) == []


def test_clear_mark_removes_one(session):
    project, _volume, _chapter, scene, entry = _seed(session)
    review_service.add_marks(
        session,
        project.id,
        [
            {"target_type": "scene", "target_id": scene.id},
            {"target_type": "entry", "target_id": entry.id},
        ],
    )
    marks = review_service.list_marks(session, project.id)
    target = next(row for row in marks if row["target_type"] == "scene")

    review_service.clear_mark(session, target["id"])

    remaining = review_service.list_marks(session, project.id)
    assert [row["target_type"] for row in remaining] == ["entry"]


def test_clear_marks_by_target_removes_several(session):
    project, _volume, _chapter, scene, entry = _seed(session)
    review_service.add_marks(
        session,
        project.id,
        [
            {"target_type": "scene", "target_id": scene.id},
            {"target_type": "entry", "target_id": entry.id},
        ],
    )

    removed = review_service.clear_marks(
        session,
        project.id,
        [
            {"target_type": "scene", "target_id": scene.id},
            {"target_type": "entry", "target_id": entry.id},
        ],
    )

    assert removed == 2
    assert review_service.list_marks(session, project.id) == []


def test_clear_marks_ignores_targets_that_were_not_marked(session):
    project, _volume, _chapter, scene, _entry = _seed(session)

    removed = review_service.clear_marks(
        session, project.id, [{"target_type": "scene", "target_id": scene.id}]
    )

    assert removed == 0


def test_clearing_a_missing_mark_is_reported(session):
    with pytest.raises(ValueError, match="待复核标记不存在"):
        review_service.clear_mark(session, "nope")


def test_an_unknown_target_type_is_rejected(session):
    project, _volume, _chapter, scene, _entry = _seed(session)

    with pytest.raises(ValueError, match="未知的锁定目标类型"):
        review_service.add_marks(
            session, project.id, [{"target_type": "chapterr", "target_id": scene.id}]
        )


def test_a_mark_needs_a_target(session):
    project, _volume, _chapter, _scene, _entry = _seed(session)

    with pytest.raises(ValueError, match="需要指定对象"):
        review_service.add_marks(
            session, project.id, [{"target_type": "scene", "target_id": "  "}]
        )


def test_deleting_an_entry_removes_its_mark(session):
    project, _volume, _chapter, _scene, entry = _seed(session)
    review_service.add_marks(
        session, project.id, [{"target_type": "entry", "target_id": entry.id}]
    )

    world_service.delete_entry(session, entry.id)

    assert session.query(ReviewMark).filter_by(target_id=entry.id).count() == 0


def test_a_mark_whose_target_vanished_shows_as_deleted(session):
    """标记不会因为目标消失而变成一条裸 ID —— 界面得能看出发生了什么。"""
    project, _volume, _chapter, scene, _entry = _seed(session)
    review_service.add_marks(
        session, project.id, [{"target_type": "scene", "target_id": scene.id}]
    )
    # 绕过服务层直接删，模拟「标记清理漏了」的历史数据。
    session.delete(session.get(Scene, scene.id))
    session.commit()

    rows = review_service.list_marks(session, project.id)

    assert rows[0]["label"] == "（对象已删除）"


def test_one_conflict_does_not_drop_the_other_marks_in_the_batch(session):
    """并发撞唯一约束时只回滚这一条 —— 整会话回滚会丢掉同批前面已插入的。"""
    project, _volume, _chapter, scene, entry = _seed(session)
    # 先标记一条，让同批里再出现它时走冲突分支。
    review_service.add_marks(
        session, project.id, [{"target_type": "scene", "target_id": scene.id}]
    )

    added = review_service.add_marks(
        session,
        project.id,
        [
            {"target_type": "entry", "target_id": entry.id, "reason": "条目"},
            {"target_type": "scene", "target_id": scene.id, "reason": "冲突的一条"},
        ],
    )

    assert added == 1
    rows = {row["target_type"]: row for row in review_service.list_marks(session, project.id)}
    assert rows["entry"]["reason"] == "条目"
    assert rows["scene"]["reason"] == "冲突的一条"


def test_a_batch_of_marks_that_is_all_new_keeps_every_row(session):
    project, volume, chapter, scene, entry = _seed(session)

    added = review_service.add_marks(
        session,
        project.id,
        [
            {"target_type": "volume", "target_id": volume.id},
            {"target_type": "chapter", "target_id": chapter.id},
            {"target_type": "scene", "target_id": scene.id},
            {"target_type": "entry", "target_id": entry.id},
        ],
    )

    assert added == 4
    assert len(review_service.list_marks(session, project.id)) == 4
