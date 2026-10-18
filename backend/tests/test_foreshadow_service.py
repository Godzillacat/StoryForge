import pytest

from app.db.models import Project
from app.services import chapter_service, foreshadow_service, scene_service


def _project(session):
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    return project


def _chapter(session, project):
    volume = chapter_service.create_volume(session, project.id, name="卷")
    return chapter_service.create_chapter(session, volume.id, title="章")


def test_create_list_update_delete(session):
    project = _project(session)
    created = foreshadow_service.create_foreshadow(
        session, project.id, name="失忆的录音带", note="主角的过去"
    )
    assert [row.id for row in foreshadow_service.list_foreshadows(session, project.id)] == [created.id]

    updated = foreshadow_service.update_foreshadow(
        session, created.id, name="录音带", status="confirmed"
    )
    assert updated.name == "录音带"
    assert updated.status == "confirmed"

    foreshadow_service.delete_foreshadow(session, created.id)
    assert foreshadow_service.list_foreshadows(session, project.id) == []


def test_duplicate_name_is_a_readable_error(session):
    project = _project(session)
    foreshadow_service.create_foreshadow(session, project.id, name="录音带")
    with pytest.raises(ValueError, match="已经"):
        foreshadow_service.create_foreshadow(session, project.id, name="录音带")


def test_plan_pay_scene_must_belong_to_the_project(session):
    project = _project(session)
    chapter = _chapter(session, project)
    scene = scene_service.create_scene(session, chapter.id, goal="收")
    foreshadow = foreshadow_service.create_foreshadow(session, project.id, name="录音带")

    updated = foreshadow_service.update_foreshadow(
        session, foreshadow.id, plan_pay_scene_id=scene.id
    )
    assert updated.plan_pay_scene_id == scene.id

    with pytest.raises(ValueError, match="场景不存在"):
        foreshadow_service.update_foreshadow(
            session, foreshadow.id, plan_pay_scene_id="nope"
        )
