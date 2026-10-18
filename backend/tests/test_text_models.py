import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import Chapter, Project, Scene, SceneDraft, SceneRevision, Volume
from app.db.session import SessionLocal
from app.text_stats import count_words


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


def test_count_words_counts_non_whitespace_characters():
    assert count_words(None) == 0
    assert count_words("") == 0
    assert count_words("  \n\t") == 0
    assert count_words("他 说：\n你好") == 5
    assert count_words("Hello, 世界") == 8


def test_scene_body_defaults_to_none(session):
    scene = _scene(session)
    assert scene.body is None
    scene.body = "正文第一段。"
    session.commit()
    assert session.get(Scene, scene.id).body == "正文第一段。"


def test_draft_is_unique_per_scene(session):
    scene = _scene(session)
    session.add(SceneDraft(scene_id=scene.id, content="第一版"))
    session.commit()
    session.add(SceneDraft(scene_id=scene.id, content="第二版"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_revision_roundtrip(session):
    scene = _scene(session)
    revision = SceneRevision(
        scene_id=scene.id, content="旧稿", source="author", note="第一次保存"
    )
    session.add(revision)
    session.commit()

    stored = session.get(SceneRevision, revision.id)
    assert stored.content == "旧稿"
    assert stored.source == "author"
    assert stored.note == "第一次保存"
    assert stored.created_at is not None


def test_deleting_scene_cascades_draft_and_revision(session):
    scene = _scene(session)
    session.add(SceneDraft(scene_id=scene.id, content="草稿"))
    session.add(SceneRevision(scene_id=scene.id, content="修订", source="ai"))
    session.commit()
    scene_id = scene.id

    session.delete(scene)
    session.commit()

    with SessionLocal() as fresh:
        assert fresh.query(SceneDraft).filter_by(scene_id=scene_id).count() == 0
        assert fresh.query(SceneRevision).filter_by(scene_id=scene_id).count() == 0
