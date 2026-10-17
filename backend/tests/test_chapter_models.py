import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    Chapter,
    Foreshadow,
    Project,
    Scene,
    SettingEntry,
    Volume,
)
from app.db.session import SessionLocal


def _project(session) -> Project:
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    return project


def _volume(session, project) -> Volume:
    volume = Volume(project_id=project.id, seq=0, name="第一卷")
    session.add(volume)
    session.commit()
    return volume


def _chapter(session, volume) -> Chapter:
    chapter = Chapter(volume_id=volume.id, seq=0, title="第一章")
    session.add(chapter)
    session.commit()
    return chapter


def test_volume_and_chapter_defaults(session):
    project = _project(session)
    volume = _volume(session, project)
    chapter = _chapter(session, volume)

    assert volume.purpose == ""
    assert volume.summary == ""
    assert volume.act_seq is None
    assert volume.target_words is None
    assert volume.status == "planned"
    assert volume.source_run_id is None

    assert chapter.pov == ""
    assert chapter.lines_json == []
    assert chapter.conflict_level is None
    assert chapter.dialogue_ratio is None
    assert chapter.hook_strength is None
    assert chapter.status == "planned"


def test_scene_roundtrip_and_defaults(session):
    project = _project(session)
    volume = _volume(session, project)
    chapter = _chapter(session, volume)
    character = SettingEntry(project_id=project.id, type="character", name="陈默")
    place = SettingEntry(project_id=project.id, type="place", name="南滨")
    session.add_all([character, place])
    session.commit()

    scene = Scene(
        chapter_id=chapter.id,
        seq=0,
        goal="找到录音带",
        conflict="档案室有人",
        turn="录音带里是自己的声音",
        characters_json=[character.id],
        location_id=place.id,
        story_time="第三年·春",
        pov="陈默",
        target_words_min=800,
        target_words_max=1500,
    )
    session.add(scene)
    session.commit()

    stored = session.get(Scene, scene.id)
    assert stored.goal == "找到录音带"
    assert stored.characters_json == [character.id]
    assert stored.location_id == place.id
    assert stored.target_words_min == 800
    assert stored.status == "planned"


def test_foreshadow_name_is_unique_within_a_project(session):
    a = _project(session)
    b = Project(name="另一本")
    session.add(b)
    session.commit()

    session.add(Foreshadow(project_id=a.id, name="失忆的录音带"))
    session.add(Foreshadow(project_id=b.id, name="失忆的录音带"))
    session.commit()  # 跨项目同名合法

    session.add(Foreshadow(project_id=a.id, name="失忆的录音带"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_deleting_a_volume_cascades_to_chapters_and_scenes(session):
    project = _project(session)
    volume = _volume(session, project)
    chapter = _chapter(session, volume)
    scene = Scene(chapter_id=chapter.id, seq=0, goal="目标")
    session.add(scene)
    session.commit()
    scene_id = scene.id

    session.delete(volume)
    session.commit()

    with SessionLocal() as fresh:
        assert fresh.get(Chapter, chapter.id) is None
        assert fresh.get(Scene, scene_id) is None


def test_deleting_a_scene_clears_foreshadow_links(session):
    project = _project(session)
    volume = _volume(session, project)
    chapter = _chapter(session, volume)
    plant = Scene(chapter_id=chapter.id, seq=0, goal="埋")
    pay = Scene(chapter_id=chapter.id, seq=1, goal="收")
    session.add_all([plant, pay])
    session.commit()
    foreshadow = Foreshadow(
        project_id=project.id,
        name="失忆的录音带",
        plant_scene_id=plant.id,
        plan_pay_scene_id=pay.id,
    )
    session.add(foreshadow)
    session.commit()

    session.delete(plant)
    session.commit()

    with SessionLocal() as fresh:
        stored = fresh.get(Foreshadow, foreshadow.id)
        assert stored.plant_scene_id is None
        assert stored.plan_pay_scene_id == pay.id


def test_deleting_an_entry_clears_scene_location(session):
    project = _project(session)
    volume = _volume(session, project)
    chapter = _chapter(session, volume)
    place = SettingEntry(project_id=project.id, type="place", name="南滨")
    session.add(place)
    session.commit()
    scene = Scene(chapter_id=chapter.id, seq=0, goal="目标", location_id=place.id)
    session.add(scene)
    session.commit()

    session.delete(place)
    session.commit()

    with SessionLocal() as fresh:
        assert fresh.get(Scene, scene.id).location_id is None
