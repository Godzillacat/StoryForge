import pytest

from app.db.models import (
    Chapter,
    GenerationRun,
    Project,
    Scene,
    SceneDraft,
    SceneRevision,
    Volume,
)
from app.services import text_service


def _scene(session) -> Scene:
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    volume = Volume(project_id=project.id, seq=0, name="第一卷")
    session.add(volume)
    session.commit()
    chapter = Chapter(volume_id=volume.id, seq=0, title="第一章")
    session.add(chapter)
    session.commit()
    scene = Scene(chapter_id=chapter.id, seq=0, goal="找到录音带")
    session.add(scene)
    session.commit()
    return scene


def test_get_text_starts_empty(session):
    scene = _scene(session)
    state = text_service.get_text(session, scene.id)
    assert state["body"] is None
    assert state["has_body"] is False
    assert state["word_count"] == 0
    assert state["draft"] is None
    assert state["revisions"] == []


def test_save_body_creates_one_author_revision_only_when_changed(session):
    scene = _scene(session)
    first = text_service.save_body(session, scene.id, "第一段。")
    assert first["body"] == "第一段。"
    assert first["has_body"] is True
    assert first["word_count"] == 4
    assert len(first["revisions"]) == 1
    assert first["revisions"][0]["source"] == "author"

    second = text_service.save_body(session, scene.id, "第一段。")
    assert len(second["revisions"]) == 1

    third = text_service.save_body(session, scene.id, "第二段。")
    assert len(third["revisions"]) == 2
    assert third["body"] == "第二段。"


def test_draft_edit_and_discard(session):
    scene = _scene(session)
    session.add(SceneDraft(scene_id=scene.id, content="草稿"))
    session.commit()

    saved = text_service.save_draft(session, scene.id, "改过的草稿")
    assert saved["content"] == "改过的草稿"

    text_service.discard_draft(session, scene.id)
    assert text_service.get_text(session, scene.id)["draft"] is None


def test_save_draft_without_draft_is_an_error(session):
    scene = _scene(session)
    with pytest.raises(ValueError, match="草稿已被替换或删除"):
        text_service.save_draft(session, scene.id, "x")


def test_adopt_requires_a_non_empty_draft(session):
    scene = _scene(session)
    with pytest.raises(ValueError, match="当前没有可采纳的草稿"):
        text_service.adopt_draft(session, scene.id)

    session.add(SceneDraft(scene_id=scene.id, content="   "))
    session.commit()
    with pytest.raises(ValueError, match="草稿为空"):
        text_service.adopt_draft(session, scene.id)


def test_adopt_writes_body_and_ai_revision_and_deletes_draft(session):
    scene = _scene(session)
    run = GenerationRun(project_id=None, status="ok")
    session.add(run)
    session.commit()
    session.add(SceneDraft(scene_id=scene.id, content="采纳的正文。", run_id=run.id))
    session.commit()

    state = text_service.adopt_draft(session, scene.id)

    assert state["body"] == "采纳的正文。"
    assert state["draft"] is None
    assert state["revisions"][0]["source"] == "ai"
    assert state["revisions"][0]["run_id"] == run.id


def test_restore_creates_a_restore_revision(session):
    scene = _scene(session)
    text_service.save_body(session, scene.id, "旧版正文。")
    old = text_service.get_text(session, scene.id)["revisions"][0]

    text_service.save_body(session, scene.id, "新版正文。")
    state = text_service.restore_revision(session, scene.id, old["id"])

    assert state["body"] == "旧版正文。"
    sources = [row["source"] for row in state["revisions"]]
    assert sources[0] == "restore"
    assert "恢复自修订" in state["revisions"][0]["note"]


def test_revisions_are_scoped_to_the_scene(session):
    scene = _scene(session)
    other = Scene(chapter_id=scene.chapter_id, seq=1, goal="另一场")
    session.add(other)
    session.commit()
    text_service.save_body(session, other.id, "别的正文。")
    revision = text_service.get_text(session, other.id)["revisions"][0]

    with pytest.raises(ValueError, match="修订不存在"):
        text_service.get_revision(session, scene.id, revision["id"])


# ---- 锁定对 AI 写路径的强制（P4a）----

def test_adopt_is_rejected_when_the_scene_is_locked(session):
    scene = _scene(session)
    session.add(SceneDraft(scene_id=scene.id, content="草稿正文。"))
    scene.locked = True
    session.commit()

    with pytest.raises(ValueError, match="已锁定"):
        text_service.adopt_draft(session, scene.id)

    session.expire_all()
    assert session.get(Scene, scene.id).body is None


def test_adopt_is_rejected_when_the_chapter_is_locked(session):
    scene = _scene(session)
    session.add(SceneDraft(scene_id=scene.id, content="草稿正文。"))
    chapter = session.get(Chapter, scene.chapter_id)
    chapter.locked = True
    session.commit()

    with pytest.raises(ValueError, match="已锁定"):
        text_service.adopt_draft(session, scene.id)


def test_adopt_still_works_when_nothing_is_locked(session):
    scene = _scene(session)
    session.add(SceneDraft(scene_id=scene.id, content="草稿正文。"))
    session.commit()

    assert text_service.adopt_draft(session, scene.id)["body"] == "草稿正文。"


def test_adopt_rejects_a_draft_that_drops_a_locked_paragraph(session):
    scene = _scene(session)
    scene.locked_paragraphs_json = ["必须保留的一段。"]
    session.add(SceneDraft(scene_id=scene.id, content="完全不同的正文。"))
    session.commit()

    with pytest.raises(ValueError, match="必须保留的一段"):
        text_service.adopt_draft(session, scene.id)


def test_adopt_accepts_a_draft_that_keeps_the_locked_paragraph(session):
    scene = _scene(session)
    scene.locked_paragraphs_json = ["必须保留的一段。"]
    session.add(
        SceneDraft(scene_id=scene.id, content="新的开头。\n\n必须保留的一段。\n\n新的结尾。")
    )
    session.commit()

    body = text_service.adopt_draft(session, scene.id)["body"]
    assert "必须保留的一段。" in body


def test_save_body_is_never_blocked_by_a_lock(session):
    """锁只约束 AI。作者手工保存永远可行 —— 这是产品立场，不是遗漏。"""
    scene = _scene(session)
    scene.locked = True
    session.commit()

    assert text_service.save_body(session, scene.id, "作者自己写的。")["body"] == "作者自己写的。"


def test_prepare_generation_is_rejected_before_any_run_record(session):
    scene = _scene(session)
    scene.locked = True
    session.commit()

    with pytest.raises(ValueError, match="已锁定"):
        text_service.prepare_generation(session, scene.id)

    assert session.query(GenerationRun).count() == 0
