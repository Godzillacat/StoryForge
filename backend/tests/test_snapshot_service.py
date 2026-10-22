"""快照：序列化往返、回滚边界、可撤销、锁定保留。"""

import pytest

from app.db.models import (
    Act,
    Architecture,
    Chapter,
    EntryRelation,
    Foreshadow,
    Idea,
    Project,
    ProjectSnapshot,
    Scene,
    SceneDraft,
    SceneRevision,
    SettingEntry,
    TimelineEvent,
    Volume,
)
from app.services import snapshot_service


def _seed(session):
    project = Project(name="雾港")
    session.add(project)
    session.commit()

    arch = Architecture(project_id=project.id, logline="旧故事", locked=True)
    session.add(arch)
    session.commit()
    session.add(Act(architecture_id=arch.id, seq=1, name="建置", purpose="开场"))

    volume = Volume(project_id=project.id, seq=0, name="第一卷", locked=True)
    session.add(volume)
    session.commit()
    chapter = Chapter(volume_id=volume.id, seq=0, title="第一章", hook="钩子")
    session.add(chapter)
    session.commit()
    scene = Scene(
        chapter_id=chapter.id,
        seq=0,
        goal="开场",
        body="第一段。\n\n第二段。",
        locked=True,
        locked_paragraphs_json=["第二段。"],
    )
    session.add(scene)
    session.commit()

    shen = SettingEntry(
        project_id=project.id,
        type="character",
        name="沈砚",
        aliases_json=["阿砚"],
        desire="查清真相",
    )
    city = SettingEntry(project_id=project.id, type="place", name="南滨旧城")
    session.add_all([shen, city])
    session.commit()
    session.add(
        EntryRelation(project_id=project.id, from_id=shen.id, to_id=city.id, kind="居住于", strength=3)
    )
    session.add(
        TimelineEvent(project_id=project.id, title="雨夜", story_time="第三年", order_index=0)
    )
    session.add(
        Foreshadow(project_id=project.id, name="录音带", plant_scene_id=scene.id)
    )
    idea = Idea(project_id=project.id, raw_text="作者的原话，永远不动")
    idea.parsed_json = {"genre": "悬疑"}
    session.add(idea)
    session.commit()
    return project, volume, chapter, scene, shen


def test_a_snapshot_captures_the_structure(session):
    project, _volume, _chapter, _scene, _shen = _seed(session)

    row = snapshot_service.create_snapshot(session, project.id, "初稿")

    assert row.volumes == 1
    assert row.chapters == 1
    assert row.scenes == 1
    assert row.words > 0
    data = row.data_json
    assert data["architecture"]["logline"] == "旧故事"
    assert len(data["entries"]) == 2
    assert len(data["relations"]) == 1
    assert len(data["timeline"]) == 1
    assert len(data["foreshadows"]) == 1


def test_the_snapshot_never_contains_the_authors_raw_idea(session):
    """D-04：回滚绝不能删掉作者的原话，所以快照根本不存它。"""
    project, *_ = _seed(session)

    row = snapshot_service.create_snapshot(session, project.id, "初稿")

    assert "作者的原话，永远不动" not in str(row.data_json)
    assert row.data_json["parsed_idea"] == {"genre": "悬疑"}


def test_creating_a_snapshot_does_not_change_the_project(session):
    project, _volume, chapter, _scene, _shen = _seed(session)

    snapshot_service.create_snapshot(session, project.id, "初稿")

    session.expire_all()
    assert session.get(Chapter, chapter.id).title == "第一章"
    assert session.query(Volume).filter_by(project_id=project.id).count() == 1


def test_duplicate_and_empty_names_are_rejected(session):
    project, *_ = _seed(session)
    snapshot_service.create_snapshot(session, project.id, "初稿")

    with pytest.raises(ValueError, match="已经有叫「初稿」的快照"):
        snapshot_service.create_snapshot(session, project.id, "初稿")

    with pytest.raises(ValueError, match="快照名称不能为空"):
        snapshot_service.create_snapshot(session, project.id, "   ")


def test_listing_is_newest_first_and_marks_auto_backups(session):
    project, *_ = _seed(session)
    snapshot_service.create_snapshot(session, project.id, "旧的")
    snapshot_service.create_snapshot(
        session, project.id, f"{snapshot_service.AUTO_PREFIX}（旧的）"
    )

    rows = snapshot_service.list_snapshots(session, project.id)

    assert [row["name"] for row in rows][0].startswith(snapshot_service.AUTO_PREFIX)
    assert rows[0]["auto"] is True
    assert rows[1]["auto"] is False


def test_deleting_a_snapshot_leaves_the_project_alone(session):
    project, _volume, _chapter, scene, _shen = _seed(session)
    row = snapshot_service.create_snapshot(session, project.id, "初稿")

    snapshot_service.delete_snapshot(session, row.id)

    session.expire_all()
    assert session.get(Scene, scene.id).body is not None
    assert session.query(ProjectSnapshot).count() == 0


def test_restore_brings_the_structure_back(session):
    project, volume, chapter, scene, _shen = _seed(session)
    snapshot_service.create_snapshot(session, project.id, "初稿")

    # 改成另一副样子：删卷、改正文、加条目。
    session.delete(session.get(Volume, volume.id))
    session.commit()
    session.add(SettingEntry(project_id=project.id, type="faction", name="新势力"))
    session.commit()

    snapshot_service.restore_snapshot(session, _only_snapshot(session, "初稿").id)

    session.expire_all()
    assert session.get(Volume, volume.id) is not None
    assert session.get(Chapter, chapter.id).title == "第一章"
    assert session.get(Scene, scene.id).body == "第一段。\n\n第二段。"
    assert session.query(SettingEntry).filter_by(name="新势力").count() == 0


def test_restore_keeps_locks_and_paragraph_locks(session):
    project, _volume, _chapter, scene, shen = _seed(session)
    snapshot_service.create_snapshot(session, project.id, "初稿")

    session.delete(session.get(Scene, scene.id))
    session.commit()

    snapshot_service.restore_snapshot(session, _only_snapshot(session, "初稿").id)

    session.expire_all()
    restored = session.get(Scene, scene.id)
    assert restored.locked is True
    assert restored.locked_paragraphs_json == ["第二段。"]
    assert session.get(SettingEntry, shen.id).locked is False


def test_restore_does_not_touch_runs_revisions_audits_or_the_raw_idea(session):
    project, _volume, _chapter, scene, _shen = _seed(session)
    session.add(SceneRevision(scene_id=scene.id, content="旧版本", source="author"))
    session.add(SceneDraft(scene_id=scene.id, content="草稿"))
    session.commit()
    snapshot_service.create_snapshot(session, project.id, "初稿")

    session.query(SceneRevision).delete()
    session.commit()

    snapshot_service.restore_snapshot(session, _only_snapshot(session, "初稿").id)

    session.expire_all()
    # 修订历史是日志：回滚作品不回滚日志，被删的那条不会因为回滚而复活。
    assert session.query(SceneRevision).count() == 0
    assert session.query(SceneDraft).count() == 1
    assert session.scalars(
        session.query(Idea).filter_by(project_id=project.id).statement
    ).first().raw_text == "作者的原话，永远不动"


def test_restore_makes_an_automatic_backup_first(session):
    project, _volume, _chapter, scene, _shen = _seed(session)
    snapshot_service.create_snapshot(session, project.id, "初稿")
    session.get(Scene, scene.id).body = "改过的正文"
    session.commit()

    result = snapshot_service.restore_snapshot(
        session, _only_snapshot(session, "初稿").id
    )

    assert result["backup"]["auto"] is True
    assert "初稿" in result["backup"]["name"]


def test_the_automatic_backup_can_undo_the_restore(session):
    project, _volume, _chapter, scene, _shen = _seed(session)
    snapshot_service.create_snapshot(session, project.id, "初稿")
    session.get(Scene, scene.id).body = "改过的正文"
    session.commit()

    result = snapshot_service.restore_snapshot(
        session, _only_snapshot(session, "初稿").id
    )
    session.expire_all()
    assert session.get(Scene, scene.id).body == "第一段。\n\n第二段。"

    snapshot_service.restore_snapshot(session, result["backup"]["id"])

    session.expire_all()
    assert session.get(Scene, scene.id).body == "改过的正文"


def test_restoring_an_empty_snapshot_clears_the_structure(session):
    """回滚到一份「空项目」快照是合法的 —— 等于清空结构，但项目本身还在。"""
    project, volume, _chapter, scene, _shen = _seed(session)

    # 在同一个项目上先记一份空结构：手工建一份 data 为空的快照。
    empty = ProjectSnapshot(
        project_id=project.id,
        name="空的",
        data_json={"volumes": [], "entries": [], "relations": [], "timeline": [],
                   "foreshadows": [], "architecture": None, "parsed_idea": None},
    )
    session.add(empty)
    session.commit()

    snapshot_service.restore_snapshot(session, empty.id)

    session.expire_all()
    assert session.get(Project, project.id) is not None
    assert session.query(Volume).filter_by(project_id=project.id).count() == 0
    assert session.query(Scene).filter_by(id=scene.id).count() == 0


def test_restore_re_points_foreshadows_to_the_restored_scenes(session):
    project, _volume, _chapter, scene, _shen = _seed(session)
    snapshot_service.create_snapshot(session, project.id, "初稿")

    session.delete(session.get(Scene, scene.id))
    session.commit()

    snapshot_service.restore_snapshot(session, _only_snapshot(session, "初稿").id)

    session.expire_all()
    row = session.query(Foreshadow).filter_by(name="录音带").first()
    assert row.plant_scene_id == scene.id


def test_restore_writes_a_rollback_entry_into_the_history(session):
    project, *_ = _seed(session)
    snapshot_service.create_snapshot(session, project.id, "初稿")

    snapshot_service.restore_snapshot(session, _only_snapshot(session, "初稿").id)

    from app.services import change_service

    rows = change_service.list_changes(session, project.id)["changes"]
    assert any(row["action"] == "rollback" for row in rows)


def _only_snapshot(session, name: str) -> ProjectSnapshot:
    return session.query(ProjectSnapshot).filter_by(name=name).first()


def _only_snapshot_for(session, project_id: str, name: str) -> ProjectSnapshot:
    return (
        session.query(ProjectSnapshot)
        .filter_by(project_id=project_id, name=name)
        .first()
    )


def test_restoring_an_automatic_backup_does_not_make_another_backup(session):
    """回滚一份自动备份时不再备份 —— 否则名字会层层嵌套。"""
    project, _volume, _chapter, scene, _shen = _seed(session)
    snapshot_service.create_snapshot(session, project.id, "初稿")
    session.get(Scene, scene.id).body = "改过的正文"
    session.commit()

    first = snapshot_service.restore_snapshot(
        session, _only_snapshot(session, "初稿").id
    )
    second = snapshot_service.restore_snapshot(session, first["backup"]["id"])

    assert second["backup"] is None
    nested = [
        row
        for row in snapshot_service.list_snapshots(session, project.id)
        if row["name"].count(snapshot_service.AUTO_PREFIX) > 1
    ]
    assert nested == []


def test_restore_survives_an_issue_pointing_at_a_dropped_entry(session):
    """审校问题可能指向快照之后新建的条目 —— 回滚把它删了，问题不能因此卡住回滚。"""
    from app.db.models import AuditIssue

    project, _volume, _chapter, scene, _shen = _seed(session)
    snapshot_service.create_snapshot(session, project.id, "初稿")
    extra = SettingEntry(project_id=project.id, type="faction", name="新势力")
    session.add(extra)
    session.commit()
    session.add(
        AuditIssue(
            project_id=project.id,
            scene_id=scene.id,
            source="llm",
            kind="setting",
            severity="major",
            fingerprint="fp-1",
            target_entry_id=extra.id,
        )
    )
    session.commit()

    snapshot_service.restore_snapshot(session, _only_snapshot(session, "初稿").id)

    session.expire_all()
    issue = session.query(AuditIssue).filter_by(fingerprint="fp-1").first()
    assert issue is not None
    assert issue.target_entry_id is None  # 条目没了，引用按 FK 语义置空


def test_the_same_snapshot_can_be_restored_twice(session):
    """回滚过的快照还要能再回滚一次 —— 自动备份不能撞名。"""
    project, _volume, _chapter, scene, _shen = _seed(session)
    snapshot = snapshot_service.create_snapshot(session, project.id, "初稿")

    first = snapshot_service.restore_snapshot(session, snapshot.id)
    session.get(Scene, scene.id).body = "又改了"
    session.commit()
    second = snapshot_service.restore_snapshot(session, snapshot.id)

    assert first["backup"]["name"] != second["backup"]["name"]
    session.expire_all()
    assert session.get(Scene, scene.id).body == "第一段。\n\n第二段。"


def test_restore_does_not_silently_unlock_newer_locks(session):
    """快照之后才加的锁，回滚不该把它解掉 —— 解锁是静默的，作者不会发现。"""
    project, _volume, _chapter, scene, _shen = _seed(session)
    scene.locked = False
    session.commit()
    snapshot_service.create_snapshot(session, project.id, "初稿")
    scene.locked = True
    scene.locked_paragraphs_json = ["第一段。"]
    session.commit()

    snapshot_service.restore_snapshot(session, _only_snapshot(session, "初稿").id)

    session.expire_all()
    restored = session.get(Scene, scene.id)
    assert restored.locked is True
    assert "第一段。" in restored.locked_paragraphs_json
