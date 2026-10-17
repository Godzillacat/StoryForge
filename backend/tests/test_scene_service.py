import pytest

from app.db.models import Foreshadow, Project
from app.db.session import SessionLocal
from app.services import chapter_service, scene_service, world_service


def _project(session) -> Project:
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    return project


def _chapter(session, project):
    volume = chapter_service.create_volume(session, project.id, name="第一卷")
    return chapter_service.create_chapter(session, volume.id, title="第一章")


def _entries(session, project):
    chen = world_service.create_entry(
        session, project.id, type="character", name="陈默", aliases=["阿默"]
    )
    lin = world_service.create_entry(session, project.id, type="character", name="林晚")
    place = world_service.create_entry(session, project.id, type="place", name="南滨旧城")
    return chen, lin, place


def test_create_scene_resolves_names_and_links(session):
    project = _project(session)
    chapter = _chapter(session, project)
    chen, lin, place = _entries(session, project)

    scene = scene_service.create_scene(
        session,
        chapter.id,
        goal="找到录音带",
        conflict="档案室有人",
        turn="录音带里是自己的声音",
        characters=["陈默", "阿默"],
        location="南滨旧城",
        story_time="第三年·春",
        target_words_min=800,
        target_words_max=1500,
        foreshadow_plants=["失忆的录音带"],
    )

    assert scene.characters_json == [chen.id]
    assert scene.location_id == place.id
    with SessionLocal() as fresh:
        payload = scene_service.scene_payload(fresh, fresh.get(type(scene), scene.id))
        assert payload["foreshadows"]["plants"][0]["name"] == "失忆的录音带"


def test_alias_and_ambiguous_and_non_character(session):
    project = _project(session)
    chapter = _chapter(session, project)
    _entries(session, project)
    world_service.create_entry(
        session, project.id, type="faction", name="记忆交易局", aliases=["交易局"]
    )

    with pytest.raises(ValueError, match="不是人物"):
        scene_service.resolve_character_names(session, project.id, ["交易局"])

    with pytest.raises(ValueError, match="找不到"):
        scene_service.resolve_character_names(session, project.id, ["不存在"])


def test_ambiguous_alias_is_rejected(session):
    project = _project(session)
    _chapter(session, project)
    world_service.create_entry(
        session, project.id, type="character", name="甲", aliases=["阿明"]
    )
    world_service.create_entry(
        session, project.id, type="character", name="乙", aliases=["阿明"]
    )

    with pytest.raises(ValueError, match="同时匹配"):
        scene_service.resolve_character_names(session, project.id, ["阿明"])


def test_foreshadow_conflict_is_rejected_before_mutation(session):
    project = _project(session)
    chapter = _chapter(session, project)
    _entries(session, project)
    first = scene_service.create_scene(
        session, chapter.id, goal="埋", foreshadow_plants=["失忆的录音带"]
    )
    second = scene_service.create_scene(
        session, chapter.id, goal="收", foreshadow_pays=["失忆的录音带"]
    )
    assert second.id != first.id

    with pytest.raises(ValueError, match="已经"):
        scene_service.create_scene(
            session, chapter.id, goal="重复埋", foreshadow_plants=["失忆的录音带"]
        )


def test_update_scene_clears_removed_links(session):
    project = _project(session)
    chapter = _chapter(session, project)
    _entries(session, project)
    scene = scene_service.create_scene(
        session, chapter.id, goal="埋", foreshadow_plants=["失忆的录音带"]
    )

    scene_service.update_scene(session, scene.id, foreshadow_plants=[])

    with SessionLocal() as fresh:
        payload = scene_service.scene_payload(fresh, fresh.get(type(scene), scene.id))
        assert payload["foreshadows"]["plants"] == []


def test_write_scenes_replace_and_append_are_atomic(session):
    project = _project(session)
    chapter = _chapter(session, project)
    chen, _lin, place = _entries(session, project)

    first = scene_service.write_scenes(
        session,
        chapter.id,
        [
            {"goal": "开场", "characters": ["陈默"], "location": "南滨旧城"},
            {"goal": "转折", "characters": ["陈默"]},
        ],
        "replace",
    )
    assert [s.goal for s in first] == ["开场", "转折"]

    second = scene_service.write_scenes(
        session, chapter.id, [{"goal": "追加"}], "append"
    )
    assert second[-1].seq == 2

    with pytest.raises(ValueError, match="找不到"):
        scene_service.write_scenes(
            session,
            chapter.id,
            [{"goal": "坏", "characters": ["不存在"]}],
            "replace",
        )
    with SessionLocal() as fresh:
        goals = [
            s.goal
            for s in fresh.query(type(first[0]))
            .filter_by(chapter_id=chapter.id)
            .order_by("seq")
        ]
        assert goals == ["开场", "转折", "追加"]


def test_replace_relinks_foreshadow_and_clears_the_old_scene_link(session):
    project = _project(session)
    chapter = _chapter(session, project)
    first = scene_service.write_scenes(
        session,
        chapter.id,
        [{"goal": "旧埋", "foreshadow_plants": ["失忆的录音带"]}],
        "replace",
    )
    second = scene_service.write_scenes(
        session,
        chapter.id,
        [{"goal": "新埋", "foreshadow_plants": ["失忆的录音带"]}],
        "replace",
    )

    with SessionLocal() as fresh:
        row = fresh.query(Foreshadow).filter_by(project_id=project.id).one()
        assert row.plant_scene_id == second[0].id
        assert row.plant_scene_id != first[0].id
        payload = scene_service.scene_payload(fresh, fresh.get(type(second[0]), second[0].id))
        assert [item["name"] for item in payload["foreshadows"]["plants"]] == ["失忆的录音带"]


def test_replace_without_mention_clears_foreshadow_link(session):
    project = _project(session)
    chapter = _chapter(session, project)
    scene_service.write_scenes(
        session,
        chapter.id,
        [{"goal": "旧埋", "foreshadow_plants": ["失忆的录音带"]}],
        "replace",
    )
    scene_service.write_scenes(session, chapter.id, [{"goal": "新场景"}], "replace")

    with SessionLocal() as fresh:
        row = fresh.query(Foreshadow).filter_by(project_id=project.id).one()
        assert row.plant_scene_id is None


def test_delete_character_clears_it_from_scene_characters(session):
    """JSON 列没有外键：删人物必须显式把它从场景的出场人物里剔除。

    否则场景里会留下一个永远解析不到名称的 ID：编辑器显示「（已删除）」，
    每次保存都会把无效名称发给后端并得到 400。
    """
    project = _project(session)
    chapter = _chapter(session, project)
    chen, lin, _place = _entries(session, project)
    only_chen = scene_service.create_scene(
        session, chapter.id, goal="独场", characters=["陈默"]
    )
    both = scene_service.create_scene(
        session, chapter.id, goal="同场", characters=["陈默", "林晚"]
    )

    world_service.delete_entry(session, chen.id)

    with SessionLocal() as fresh:
        row = fresh.get(type(only_chen), only_chen.id)
        assert row is not None
        assert row.characters_json == []
        other = fresh.get(type(both), both.id)
        assert other is not None
        assert other.characters_json == [lin.id]


def test_move_scene_and_delete(session):
    project = _project(session)
    chapter = _chapter(session, project)
    a = scene_service.create_scene(session, chapter.id, goal="一")
    b = scene_service.create_scene(session, chapter.id, goal="二")

    scene_service.move_scene(session, b.id, "up")
    with SessionLocal() as fresh:
        rows = list(fresh.query(type(a)).filter_by(chapter_id=chapter.id).order_by("seq"))
        assert [row.goal for row in rows] == ["二", "一"]

    scene_service.delete_scene(session, a.id)
    with SessionLocal() as fresh:
        assert fresh.get(type(a), a.id) is None
