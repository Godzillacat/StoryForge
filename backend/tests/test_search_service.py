from sqlalchemy import text

from app.db.models import Chapter, Project, Scene, SearchIndexState, SettingEntry, Volume
from app.services import search_service


def _seed(session):
    project = Project(name="南滨")
    session.add(project)
    session.commit()

    place = SettingEntry(
        project_id=project.id,
        type="place",
        name="南滨旧城",
        aliases_json=["旧城"],
        tags_json=["据点"],
        summary="记忆清算网络的据点",
        description="湿带边缘的旧城区",
    )
    character = SettingEntry(
        project_id=project.id,
        type="character",
        name="沈砚",
        aliases_json=["阿砚"],
        desire="找回被抹去的记忆",
        current_state="被旧城通缉",
    )
    session.add_all([place, character])
    session.commit()

    volume = Volume(project_id=project.id, seq=0, name="第一卷")
    session.add(volume)
    session.commit()

    chapter = Chapter(
        volume_id=volume.id,
        seq=0,
        title="开端",
        summary="南滨旧城的雨夜",
        hook="旧城信标亮起",
        lines_json=["主线"],
        pov="沈砚",
    )
    session.add(chapter)
    session.commit()

    scene = Scene(
        chapter_id=chapter.id,
        seq=0,
        goal="找到旧城信标",
        conflict="记忆清算人追来",
        turn="信标是假的",
        characters_json=[character.id],
        location_id=place.id,
        story_time="第三夜",
        pov="沈砚",
    )
    session.add(scene)
    session.commit()

    return project, place, character, volume, chapter, scene


def _docs(session, project_id):
    rows = session.execute(
        text(
            "SELECT doc_id, entity_type, subtype, title, body "
            "FROM search_document WHERE project_id = :p"
        ),
        {"p": project_id},
    ).mappings().all()
    return [dict(row) for row in rows]


def test_rebuild_indexes_entries_chapters_and_scenes(session):
    project, place, character, _, chapter, _ = _seed(session)

    search_service.rebuild_project(session, project.id)
    docs = {doc["doc_id"]: doc for doc in _docs(session, project.id)}

    assert f"entry:{place.id}" in docs
    assert f"entry:{character.id}" in docs
    assert f"chapter:{chapter.id}" in docs
    assert any(key.startswith("scene:") for key in docs)

    place_doc = docs[f"entry:{place.id}"]
    assert place_doc["entity_type"] == "entry"
    assert place_doc["subtype"] == "place"
    assert place_doc["title"] == "南滨旧城"
    assert "记忆清算网络的据点" in place_doc["body"]

    character_doc = docs[f"entry:{character.id}"]
    assert "找回被抹去的记忆" in character_doc["body"]
    assert "别名：阿砚" in character_doc["body"]

    chapter_doc = docs[f"chapter:{chapter.id}"]
    assert chapter_doc["title"] == "第1卷 第1章 开端"
    assert "旧城信标亮起" in chapter_doc["body"]

    scene_doc = next(doc for doc in docs.values() if doc["entity_type"] == "scene")
    assert scene_doc["title"].startswith("第1卷 第1章 场景1 找到旧城信标")
    assert "沈砚" in scene_doc["body"]
    assert "南滨旧城" in scene_doc["body"]


def test_rebuild_replaces_old_documents(session):
    project, place, _, _, _, _ = _seed(session)
    search_service.rebuild_project(session, project.id)

    place.name = "新南滨"
    session.commit()
    search_service.rebuild_project(session, project.id)

    docs = _docs(session, project.id)
    titles = {doc["title"] for doc in docs}
    assert "新南滨" in titles
    assert "南滨旧城" not in titles


def test_rebuild_is_project_scoped(session):
    first, _, _, _, _, _ = _seed(session)
    second = Project(name="另一个项目")
    session.add(second)
    session.commit()
    session.add(SettingEntry(project_id=second.id, type="place", name="别处"))
    session.commit()

    search_service.rebuild_project(session, first.id)

    assert _docs(session, first.id)
    assert _docs(session, second.id) == []


def test_mark_dirty_creates_and_updates_state(session):
    project = Project(name="标记")
    session.add(project)
    session.commit()

    search_service.mark_dirty(session, project.id)
    session.commit()
    state = session.get(SearchIndexState, project.id)
    assert state is not None and state.dirty == 1

    state.dirty = 0
    session.commit()
    search_service.mark_dirty(session, project.id)
    session.commit()
    assert session.get(SearchIndexState, project.id).dirty == 1


def test_rebuild_sets_clean_state(session):
    project, _, _, _, _, _ = _seed(session)

    search_service.rebuild_project(session, project.id)

    state = session.get(SearchIndexState, project.id)
    assert state is not None
    assert state.dirty == 0
    assert state.schema_version == 2
    assert state.rebuilt_at


def test_delete_project_removes_docs_and_state(session):
    project, _, _, _, _, _ = _seed(session)
    search_service.rebuild_project(session, project.id)
    assert _docs(session, project.id)

    search_service.delete_project(session, project.id)
    session.commit()

    assert _docs(session, project.id) == []
    assert session.get(SearchIndexState, project.id) is None


def test_long_chinese_query_returns_ranked_entry(session):
    project, place, _, _, _, _ = _seed(session)

    hits = search_service.search(session, project.id, "南滨旧城")

    assert any(hit.entity_type == "entry" and hit.entity_id == place.id for hit in hits)
    assert hits[0].title == "南滨旧城"
    assert "南滨旧城" in hits[0].snippet


def test_short_chinese_name_uses_like_fallback(session):
    project, _, character, _, _, _ = _seed(session)

    hits = search_service.search(session, project.id, "沈砚")

    assert any(hit.entity_type == "entry" and hit.entity_id == character.id for hit in hits)
    assert any(hit.entity_type == "scene" for hit in hits)


def test_entity_type_filter(session):
    project, place, _, _, _, _ = _seed(session)

    hits = search_service.search(session, project.id, "南滨旧城", entity_types=["entry"])

    assert hits
    assert {hit.entity_type for hit in hits} == {"entry"}


def test_search_is_project_scoped(session):
    first, place, _, _, _, _ = _seed(session)
    second = Project(name="另一个项目")
    session.add(second)
    session.commit()
    other = SettingEntry(project_id=second.id, type="place", name="南滨旧城")
    session.add(other)
    session.commit()

    hits = search_service.search(session, first.id, "南滨旧城")

    assert any(hit.entity_id == place.id for hit in hits)
    assert all(hit.entity_id != other.id for hit in hits)


def test_empty_query_returns_empty(session):
    project, _, _, _, _, _ = _seed(session)
    assert search_service.search(session, project.id, "   ") == []


def test_special_characters_do_not_crash(session):
    project, _, _, _, _, _ = _seed(session)
    for query in ('"旧城"', "%", "旧_城", '旧城 AND "信标'):
        search_service.search(session, project.id, query)


def test_limit_is_applied(session):
    project = Project(name="限额")
    session.add(project)
    session.commit()
    for index in range(5):
        session.add(
            SettingEntry(
                project_id=project.id,
                type="place",
                name=f"旧城{index}",
                summary="旧城",
            )
        )
    session.commit()

    hits = search_service.search(session, project.id, "旧城", limit=2)

    assert len(hits) == 2


def test_dirty_state_triggers_rebuild(session):
    project, place, _, _, _, _ = _seed(session)
    search_service.rebuild_project(session, project.id)

    place.name = "改名之后的旧城"
    session.commit()
    search_service.mark_dirty(session, project.id)
    session.commit()

    hits = search_service.search(session, project.id, "改名之后的旧城")
    assert any(hit.entity_id == place.id for hit in hits)


def test_schema_version_mismatch_triggers_rebuild(session):
    project, place, _, _, _, _ = _seed(session)
    search_service.rebuild_project(session, project.id)

    place.name = "版本之后的名字"
    session.commit()
    state = session.get(SearchIndexState, project.id)
    state.dirty = 0
    state.schema_version = 0
    session.commit()

    hits = search_service.search(session, project.id, "版本之后的名字")
    assert any(hit.entity_id == place.id for hit in hits)


def test_stale_document_is_skipped(session):
    project, place, _, _, _, _ = _seed(session)
    search_service.rebuild_project(session, project.id)
    state = session.get(SearchIndexState, project.id)
    state.dirty = 0
    session.commit()
    session.execute(
        text(
            "INSERT INTO search_document"
            "(doc_id, project_id, entity_type, subtype, title, body) "
            "VALUES ('entry:missing', :p, 'entry', 'place', '幽灵旧城', '幽灵旧城')"
        ),
        {"p": project.id},
    )
    session.commit()

    hits = search_service.search(session, project.id, "幽灵旧城")

    assert all(hit.entity_id != "missing" for hit in hits)
