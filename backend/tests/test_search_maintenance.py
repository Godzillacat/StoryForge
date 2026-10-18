import pytest
from sqlalchemy import text

from app.db.models import Project, SearchIndexState
from app.services import (
    chapter_plan_service,
    chapter_service,
    project_service,
    scene_service,
    search_service,
    world_service,
)


def _project(session):
    project = Project(name="旧城")
    session.add(project)
    session.commit()
    return project


def _hits(session, project_id, query):
    return search_service.search(session, project_id, query)


def _prewarm(session, project):
    """把索引置为干净：重建会创建状态行并写 dirty=0。

    这是「现有真实状态」：作者搜索过一次后，状态行就是干净的。创建类写入
    若只靠惰性重建（状态行不存在时才会触发），标脏缺失就看不出来。
    """
    search_service.rebuild_project(session, project.id)
    assert session.get(SearchIndexState, project.id).dirty == 0


def _assert_dirty(session, project):
    assert session.get(SearchIndexState, project.id).dirty == 1


def test_entry_writes_refresh_search(session):
    project = _project(session)
    entry = world_service.create_entry(
        session, project.id, type="place", name="旧城信标"
    )
    assert any(hit.entity_id == entry.id for hit in _hits(session, project.id, "旧城信标"))

    world_service.update_entry(session, entry.id, name="新信标")
    assert not any(hit.entity_id == entry.id for hit in _hits(session, project.id, "旧城信标"))
    assert any(hit.entity_id == entry.id for hit in _hits(session, project.id, "新信标"))

    world_service.delete_entry(session, entry.id)
    assert not any(hit.entity_id == entry.id for hit in _hits(session, project.id, "新信标"))


def test_volume_and_chapter_writes_refresh_search(session):
    project = _project(session)
    volume = chapter_service.create_volume(session, project.id, name="第一卷")
    chapter = chapter_service.create_chapter(session, volume.id, title="旧章")
    assert any("旧章" in hit.title for hit in _hits(session, project.id, "旧章"))

    chapter_service.update_chapter(session, chapter.id, title="新章")
    assert any("新章" in hit.title for hit in _hits(session, project.id, "新章"))
    assert not any("旧章" in hit.title for hit in _hits(session, project.id, "旧章"))

    chapter_service.move_chapter(session, chapter.id, "up")
    # 移动后仍可搜到；具体序号由重建后的标题体现
    assert any(hit.entity_type == "chapter" for hit in _hits(session, project.id, "新章"))

    chapter_service.delete_volume(session, volume.id)
    assert not any(hit.entity_type == "chapter" for hit in _hits(session, project.id, "新章"))


def test_scene_writes_refresh_search(session):
    project = _project(session)
    volume = chapter_service.create_volume(session, project.id, name="第一卷")
    chapter = chapter_service.create_chapter(session, volume.id, title="章")
    scene = scene_service.create_scene(session, chapter.id, goal="旧目标")
    assert any(hit.entity_id == scene.id for hit in _hits(session, project.id, "旧目标"))

    scene_service.update_scene(session, scene.id, goal="新目标")
    assert any(hit.entity_id == scene.id for hit in _hits(session, project.id, "新目标"))

    scene_service.delete_scene(session, scene.id)
    assert not any(hit.entity_id == scene.id for hit in _hits(session, project.id, "新目标"))


def test_write_scenes_replace_refreshes_search(session):
    project = _project(session)
    volume = chapter_service.create_volume(session, project.id, name="第一卷")
    chapter = chapter_service.create_chapter(session, volume.id, title="章")
    scene_service.write_scenes(
        session, chapter.id, [{"goal": "旧的批量目标"}], "replace"
    )
    assert any("旧的批量目标" in hit.title for hit in _hits(session, project.id, "旧的批量目标"))

    scene_service.write_scenes(
        session, chapter.id, [{"goal": "新的批量目标"}], "replace"
    )
    assert any("新的批量目标" in hit.title for hit in _hits(session, project.id, "新的批量目标"))
    assert not any("旧的批量目标" in hit.title for hit in _hits(session, project.id, "旧的批量目标"))


def test_write_chapter_plan_refreshes_search(session):
    project = _project(session)
    chapter_plan_service.write_chapter_plan(
        session,
        project.id,
        [
            {
                "name": "新卷",
                "chapters": [{"title": "策划出来的章"}],
            }
        ],
        "replace",
    )

    assert any("策划出来的章" in hit.title for hit in _hits(session, project.id, "策划出来的章"))


def test_project_delete_cleans_search(session):
    project = _project(session)
    world_service.create_entry(session, project.id, type="place", name="要删的旧城")
    assert _hits(session, project.id, "要删的旧城")

    project_service.delete_project(session, project.id)

    count = session.execute(
        text("SELECT COUNT(*) FROM search_document WHERE project_id = :p"),
        {"p": project.id},
    ).scalar()
    assert count == 0


def test_moves_and_deletes_mark_dirty(session):
    project = _project(session)
    first_volume = chapter_service.create_volume(session, project.id, name="甲")
    second_volume = chapter_service.create_volume(session, project.id, name="乙")
    first_chapter = chapter_service.create_chapter(session, first_volume.id, title="一")
    second_chapter = chapter_service.create_chapter(session, first_volume.id, title="二")
    scene_service.create_scene(session, first_chapter.id, goal="目标一")
    second_scene = scene_service.create_scene(session, first_chapter.id, goal="目标二")

    def reset():
        state = session.get(SearchIndexState, project.id)
        state.dirty = 0
        session.commit()

    assert session.get(SearchIndexState, project.id).dirty == 1
    reset()
    chapter_service.move_chapter(session, second_chapter.id, "up")
    assert session.get(SearchIndexState, project.id).dirty == 1

    reset()
    scene_service.move_scene(session, second_scene.id, "up")
    assert session.get(SearchIndexState, project.id).dirty == 1

    reset()
    chapter_service.move_volume(session, second_volume.id, "up")
    assert session.get(SearchIndexState, project.id).dirty == 1

    reset()
    chapter_service.update_volume(session, first_volume.id, name="丙")
    assert session.get(SearchIndexState, project.id).dirty == 1

    reset()
    chapter_service.delete_chapter(session, first_chapter.id)
    assert session.get(SearchIndexState, project.id).dirty == 1


def test_create_paths_mark_dirty(session):
    """创建类写入必须标脏。

    检索与删除路径都会被惰性重建 / `_exists` 过滤掩盖：状态行不存在时
    `_ensure_fresh` 会重建，删除后残留的文档会被 `_exists` 静默丢掉。
    先预热到干净，才能看出「这次写入到底有没有标脏」。
    """
    project = _project(session)

    _prewarm(session, project)
    world_service.create_entry(session, project.id, type="place", name="信标")
    _assert_dirty(session, project)

    _prewarm(session, project)
    volume = chapter_service.create_volume(session, project.id, name="第一卷")
    _assert_dirty(session, project)

    _prewarm(session, project)
    chapter = chapter_service.create_chapter(session, volume.id, title="章")
    _assert_dirty(session, project)

    _prewarm(session, project)
    scene_service.create_scene(session, chapter.id, goal="目标")
    _assert_dirty(session, project)

    _prewarm(session, project)
    chapter_plan_service.write_chapter_plan(
        session,
        project.id,
        [{"name": "新卷", "chapters": [{"title": "策划章"}]}],
        "replace",
    )
    _assert_dirty(session, project)


def test_delete_paths_mark_dirty(session):
    """删除类写入必须标脏 —— 残留文档在 `_exists` 过滤下不会报错。"""
    project = _project(session)
    entry = world_service.create_entry(session, project.id, type="place", name="要删")
    volume = chapter_service.create_volume(session, project.id, name="卷")
    chapter = chapter_service.create_chapter(session, volume.id, title="章")
    scene = scene_service.create_scene(session, chapter.id, goal="目标")

    _prewarm(session, project)
    world_service.delete_entry(session, entry.id)
    _assert_dirty(session, project)

    _prewarm(session, project)
    scene_service.delete_scene(session, scene.id)
    _assert_dirty(session, project)

    _prewarm(session, project)
    chapter_service.delete_volume(session, volume.id)
    _assert_dirty(session, project)


def test_failed_write_rolls_back_dirty_mark(session):
    """标脏与写入同一事务：写入失败时脏标记必须一起回滚。"""
    project = _project(session)
    world_service.create_entry(session, project.id, type="place", name="重名")
    _prewarm(session, project)

    with pytest.raises(ValueError):
        world_service.create_entry(session, project.id, type="place", name="重名")

    assert session.get(SearchIndexState, project.id).dirty == 0
