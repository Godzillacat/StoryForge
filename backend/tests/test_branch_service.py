"""场景分支：开分支、保存、采纳、合并、丢弃，以及与锁定 / 段落锁的关系。"""

import pytest

from app.db.models import Chapter, Project, Scene, SceneRevision, Volume
from app.services import branch_service, text_service


def _seed(session, *, body: str | None = "主版正文。"):
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    volume = Volume(project_id=project.id, seq=0, name="第一卷")
    session.add(volume)
    session.commit()
    chapter = Chapter(volume_id=volume.id, seq=0, title="第一章")
    session.add(chapter)
    session.commit()
    scene = Scene(chapter_id=chapter.id, seq=0, goal="开场", body=body)
    session.add(scene)
    session.commit()
    return project, scene


def test_a_new_branch_starts_from_the_main_body(session):
    project, scene = _seed(session)

    row = branch_service.create_branch(session, scene.id, "A 案")

    assert row.content == "主版正文。"
    detail = branch_service.get_branch(session, row.id)
    assert detail["name"] == "A 案"
    assert detail["chars"] == len("主版正文。")


def test_a_branch_of_an_empty_scene_starts_empty(session):
    _project, scene = _seed(session, body=None)

    row = branch_service.create_branch(session, scene.id, "A 案")

    assert row.content == ""


def test_duplicate_and_empty_names_are_rejected(session):
    _project, scene = _seed(session)
    branch_service.create_branch(session, scene.id, "A 案")

    with pytest.raises(ValueError, match="已经有叫「A 案」的分支"):
        branch_service.create_branch(session, scene.id, "A 案")
    with pytest.raises(ValueError, match="分支名称不能为空"):
        branch_service.create_branch(session, scene.id, "   ")


def test_the_same_name_is_allowed_on_different_scenes(session):
    project, scene = _seed(session)
    other = Scene(chapter_id=scene.chapter_id, seq=1, goal="第二场")
    session.add(other)
    session.commit()

    branch_service.create_branch(session, scene.id, "A 案")
    second = branch_service.create_branch(session, other.id, "A 案")

    assert second.name == "A 案"


def test_listing_is_in_creation_order(session):
    _project, scene = _seed(session)
    branch_service.create_branch(session, scene.id, "A 案")
    branch_service.create_branch(session, scene.id, "B 案")

    assert [row["name"] for row in branch_service.list_branches(session, scene.id)] == [
        "A 案",
        "B 案",
    ]


def test_renaming_rejects_a_taken_name(session):
    _project, scene = _seed(session)
    branch_service.create_branch(session, scene.id, "A 案")
    second = branch_service.create_branch(session, scene.id, "B 案")

    with pytest.raises(ValueError, match="已经有叫「A 案」的分支"):
        branch_service.update_branch(session, second.id, name="A 案")


def test_saving_a_branch_body_is_not_blocked_by_a_lock(session):
    """锁只约束 AI —— 分支里的手工作业与主版一样不受限。"""
    _project, scene = _seed(session)
    scene.locked = True
    session.commit()
    row = branch_service.create_branch(session, scene.id, "A 案")

    result = branch_service.save_branch_body(session, row.id, "作者自己写的。")

    assert result["content"] == "作者自己写的。"


def test_adopting_a_branch_draft_is_blocked_when_the_scene_is_locked(session):
    _project, scene = _seed(session)
    row = branch_service.create_branch(session, scene.id, "A 案")
    branch_service.save_branch_draft(session, row.id, "分支草稿。")
    scene.locked = True
    session.commit()

    with pytest.raises(ValueError, match="已锁定"):
        branch_service.adopt_branch_draft(session, row.id)


def test_adopting_a_branch_draft_respects_paragraph_locks(session):
    _project, scene = _seed(session)
    row = branch_service.create_branch(session, scene.id, "A 案")
    branch_service.save_branch_draft(session, row.id, "完全不同的正文。")
    scene.locked_paragraphs_json = ["必须保留的一段。"]
    session.commit()

    with pytest.raises(ValueError, match="必须保留的一段"):
        branch_service.adopt_branch_draft(session, row.id)


def test_adopting_a_branch_draft_moves_it_into_the_branch_body(session):
    _project, scene = _seed(session)
    row = branch_service.create_branch(session, scene.id, "A 案")
    branch_service.save_branch_draft(session, row.id, "分支草稿。")

    result = branch_service.adopt_branch_draft(session, row.id)

    assert result["content"] == "分支草稿。"
    assert result["draft"] is None


def test_merging_replaces_the_main_body_and_keeps_a_branch_revision(session):
    _project, scene = _seed(session)
    row = branch_service.create_branch(session, scene.id, "A 案")
    branch_service.save_branch_body(session, row.id, "另一版正文。")

    result = branch_service.merge_branch(session, row.id)

    assert result["body"] == "另一版正文。"
    session.expire_all()
    assert session.get(Scene, scene.id).body == "另一版正文。"
    revision = session.query(SceneRevision).filter_by(scene_id=scene.id).first()
    assert revision.source == "branch"
    assert revision.content == "主版正文。"
    assert "A 案" in revision.note


def test_merging_keeps_the_branch_itself(session):
    """合并是「我选这条作主版」，不是「其余作废」。"""
    _project, scene = _seed(session)
    row = branch_service.create_branch(session, scene.id, "A 案")

    branch_service.merge_branch(session, row.id)

    session.expire_all()
    assert branch_service.get_branch(session, row.id)["name"] == "A 案"


def test_merging_an_empty_branch_is_rejected(session):
    _project, scene = _seed(session, body=None)
    row = branch_service.create_branch(session, scene.id, "A 案")

    with pytest.raises(ValueError, match="分支正文为空"):
        branch_service.merge_branch(session, row.id)


def test_merging_is_blocked_when_the_scene_is_locked(session):
    _project, scene = _seed(session)
    row = branch_service.create_branch(session, scene.id, "A 案")
    branch_service.save_branch_body(session, row.id, "另一版。")
    scene.locked = True
    session.commit()

    with pytest.raises(ValueError, match="已锁定"):
        branch_service.merge_branch(session, row.id)


def test_merging_respects_paragraph_locks(session):
    _project, scene = _seed(session)
    row = branch_service.create_branch(session, scene.id, "A 案")
    branch_service.save_branch_body(session, row.id, "没有那一段的正文。")
    scene.locked_paragraphs_json = ["必须保留的一段。"]
    session.commit()

    with pytest.raises(ValueError, match="必须保留的一段"):
        branch_service.merge_branch(session, row.id)


def test_merging_an_empty_main_body_creates_no_revision(session):
    _project, scene = _seed(session, body=None)
    row = branch_service.create_branch(session, scene.id, "A 案")
    branch_service.save_branch_body(session, row.id, "第一版。")

    branch_service.merge_branch(session, row.id)

    assert session.query(SceneRevision).filter_by(scene_id=scene.id).count() == 0


def test_discarding_a_branch_leaves_the_main_body_alone(session):
    _project, scene = _seed(session)
    row = branch_service.create_branch(session, scene.id, "A 案")
    branch_service.save_branch_body(session, row.id, "另一版。")

    branch_service.discard_branch(session, row.id)

    session.expire_all()
    assert session.get(Scene, scene.id).body == "主版正文。"
    assert branch_service.list_branches(session, scene.id) == []


def test_branch_writes_do_not_touch_the_main_draft(session):
    """分支草稿与主版草稿是两份东西 —— 混在一起会让「采纳」与「合并」打架。"""
    from app.db.models import SceneDraft

    _project, scene = _seed(session)
    session.add(SceneDraft(scene_id=scene.id, content="主版草稿"))
    session.commit()
    row = branch_service.create_branch(session, scene.id, "A 案")

    branch_service.save_branch_draft(session, row.id, "分支草稿")

    session.expire_all()
    assert session.query(SceneDraft).filter_by(scene_id=scene.id).first().content == "主版草稿"
    assert branch_service.get_branch(session, row.id)["draft"]["content"] == "分支草稿"


def test_branch_bodies_stay_out_of_the_search_index(session):
    """分支是未定稿的旁路，进索引会污染主版的检索命中。"""
    from app.services import search_service

    project, scene = _seed(session)
    row = branch_service.create_branch(session, scene.id, "A 案")
    branch_service.save_branch_body(session, row.id, "只在分支里出现的独特措辞。")

    hits = search_service.search(session, project.id, "只在分支里出现的独特措辞")

    assert hits == []


def test_missing_scene_and_branch_are_reported(session):
    with pytest.raises(ValueError, match="场景不存在"):
        branch_service.create_branch(session, "nope", "A 案")
    with pytest.raises(ValueError, match="分支不存在"):
        branch_service.get_branch(session, "nope")


def test_saving_a_branch_body_records_a_revision(session):
    _project, scene = _seed(session)
    row = branch_service.create_branch(session, scene.id, "A 案")

    branch_service.save_branch_body(session, row.id, "第二版。")

    rows = branch_service.list_branch_revisions(session, row.id)
    assert [item["source"] for item in rows] == ["author"]
    assert rows[0]["chars"] == len("第二版。")


def test_saving_an_unchanged_branch_body_records_nothing(session):
    _project, scene = _seed(session)
    row = branch_service.create_branch(session, scene.id, "A 案")

    branch_service.save_branch_body(session, row.id, row.content)

    assert branch_service.list_branch_revisions(session, row.id) == []


def test_adopting_a_branch_draft_records_an_ai_revision(session):
    _project, scene = _seed(session)
    row = branch_service.create_branch(session, scene.id, "A 案")
    branch_service.save_branch_draft(session, row.id, "AI 写的。")

    branch_service.adopt_branch_draft(session, row.id)

    rows = branch_service.list_branch_revisions(session, row.id)
    assert [item["source"] for item in rows] == ["ai"]


def test_branch_revisions_are_separate_from_scene_revisions(session):
    _project, scene = _seed(session)
    row = branch_service.create_branch(session, scene.id, "A 案")
    branch_service.save_branch_body(session, row.id, "分支的改动。")

    assert session.query(SceneRevision).filter_by(scene_id=scene.id).count() == 0
    assert len(branch_service.list_branch_revisions(session, row.id)) == 1


def test_merging_clears_the_stale_main_draft(session):
    """合并后主版正文变了，旧草稿是针对旧正文的 —— 留着会被误采纳。"""
    from app.db.models import SceneDraft

    _project, scene = _seed(session)
    session.add(SceneDraft(scene_id=scene.id, content="主版旧草稿"))
    session.commit()
    row = branch_service.create_branch(session, scene.id, "A 案")
    branch_service.save_branch_body(session, row.id, "合入的正文。")

    branch_service.merge_branch(session, row.id)

    session.expire_all()
    assert session.query(SceneDraft).filter_by(scene_id=scene.id).count() == 0


def test_rolling_back_a_snapshot_keeps_the_branches(session):
    """分支不进快照，但也不该被回滚删掉 —— 它是实验材料，不是快照的一部分。"""
    from app.services import snapshot_service

    project, scene = _seed(session)
    row = branch_service.create_branch(session, scene.id, "A 案")
    branch_service.save_branch_body(session, row.id, "实验正文。")
    snap = snapshot_service.create_snapshot(session, project.id, "初稿")

    snapshot_service.restore_snapshot(session, snap.id)

    session.expire_all()
    kept = branch_service.get_branch(session, row.id)
    assert kept["name"] == "A 案"
    assert kept["content"] == "实验正文。"
