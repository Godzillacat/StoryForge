"""全文检索：文档构建、按项目重建、脏标记与删除清理。

FTS5 表只由本模块写入；查询入口在 Task 3 追加。
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.chapter_types import STATUS_LABELS
from app.db.models import (
    Chapter,
    Scene,
    SearchIndexState,
    SettingEntry,
    Volume,
)
from app.db.search import SEARCH_INDEX_VERSION
from app.world_types import CHARACTER_FIELDS, ENTRY_TYPES, HARDNESS_LEVELS


def mark_dirty(session: Session, project_id: str) -> None:
    """在写入事务内标记该项目需要重建；由调用方提交/回滚。"""
    state = session.get(SearchIndexState, project_id)
    if state is None:
        session.add(
            SearchIndexState(
                project_id=project_id,
                dirty=1,
                schema_version=0,
                rebuilt_at=None,
            )
        )
    else:
        state.dirty = 1


def delete_project(session: Session, project_id: str) -> None:
    """删除项目的检索文档与状态；由调用方提交。"""
    session.execute(
        text("DELETE FROM search_document WHERE project_id = :pid"),
        {"pid": project_id},
    )
    state = session.get(SearchIndexState, project_id)
    if state is not None:
        session.delete(state)


def rebuild_project(session: Session, project_id: str) -> None:
    """按基表重建一个项目的全部文档，并把状态置为干净。"""
    try:
        _replace_docs(session, project_id)
        state = session.get(SearchIndexState, project_id)
        if state is None:
            state = SearchIndexState(project_id=project_id)
            session.add(state)
        state.dirty = 0
        state.schema_version = SEARCH_INDEX_VERSION
        state.rebuilt_at = dt.datetime.now(dt.timezone.utc).isoformat()
        session.commit()
    except Exception:
        session.rollback()
        raise


def _replace_docs(session: Session, project_id: str) -> None:
    session.execute(
        text("DELETE FROM search_document WHERE project_id = :pid"),
        {"pid": project_id},
    )
    docs = list(_build_docs(session, project_id))
    if docs:
        session.execute(
            text(
                "INSERT INTO search_document"
                "(doc_id, project_id, entity_type, subtype, title, body) "
                "VALUES (:doc_id, :project_id, :entity_type, :subtype, :title, :body)"
            ),
            docs,
        )


def _build_docs(session: Session, project_id: str):
    entries = list(
        session.scalars(
            select(SettingEntry).where(SettingEntry.project_id == project_id)
        )
    )
    volumes = {
        volume.id: volume
        for volume in session.scalars(
            select(Volume).where(Volume.project_id == project_id)
        )
    }
    chapters = list(
        session.scalars(
            select(Chapter)
            .join(Volume, Chapter.volume_id == Volume.id)
            .where(Volume.project_id == project_id)
        )
    )
    chapter_by_id = {chapter.id: chapter for chapter in chapters}
    scenes = list(
        session.scalars(
            select(Scene)
            .join(Chapter, Scene.chapter_id == Chapter.id)
            .join(Volume, Chapter.volume_id == Volume.id)
            .where(Volume.project_id == project_id)
        )
    )
    entry_names = {entry.id: entry.name for entry in entries}

    for entry in entries:
        yield _entry_doc(entry)
    for chapter in chapters:
        yield _chapter_doc(volumes[chapter.volume_id], chapter)
    for scene in scenes:
        chapter = chapter_by_id[scene.chapter_id]
        yield _scene_doc(volumes[chapter.volume_id], chapter, scene, entry_names)


def _entry_doc(entry: SettingEntry) -> dict:
    parts = [f"类型：{ENTRY_TYPES.get(entry.type, entry.type)}"]
    if entry.aliases_json:
        parts.append("别名：" + "、".join(str(item) for item in entry.aliases_json))
    if entry.tags_json:
        parts.append("标签：" + "、".join(str(item) for item in entry.tags_json))
    if entry.summary:
        parts.append("摘要：" + entry.summary)
    if entry.description:
        parts.append("描述：" + entry.description)
    if entry.hardness:
        parts.append("硬度：" + HARDNESS_LEVELS.get(entry.hardness, entry.hardness))
    for key, (label, _multiline) in CHARACTER_FIELDS.items():
        value = getattr(entry, key, None)
        if value:
            parts.append(f"{label}：" + str(value))
    return {
        "doc_id": f"entry:{entry.id}",
        "project_id": entry.project_id,
        "entity_type": "entry",
        "subtype": entry.type,
        "title": entry.name,
        "body": " ".join(parts),
    }


def _chapter_doc(volume: Volume, chapter: Chapter) -> dict:
    parts: list[str] = []
    if chapter.pov:
        parts.append("视角：" + chapter.pov)
    if chapter.target_words:
        parts.append(f"目标字数：{chapter.target_words}")
    if chapter.emotional_tone:
        parts.append("情绪基调：" + chapter.emotional_tone)
    if chapter.lines_json:
        parts.append("推进的线：" + "、".join(str(item) for item in chapter.lines_json))
    if chapter.hook:
        parts.append("钩子：" + chapter.hook)
    if chapter.summary:
        parts.append("摘要：" + chapter.summary)
    if chapter.status:
        parts.append("状态：" + STATUS_LABELS.get(chapter.status, chapter.status))
    return {
        "doc_id": f"chapter:{chapter.id}",
        "project_id": volume.project_id,
        "entity_type": "chapter",
        "subtype": "",
        "title": f"第{volume.seq + 1}卷 第{chapter.seq + 1}章 {chapter.title}",
        "body": " ".join(parts),
    }


def _scene_doc(
    volume: Volume,
    chapter: Chapter,
    scene: Scene,
    entry_names: dict[str, str],
) -> dict:
    parts = ["目标：" + (scene.goal or "（未写目标）")]
    if scene.conflict:
        parts.append("冲突：" + scene.conflict)
    if scene.turn:
        parts.append("转折：" + scene.turn)
    people = [
        entry_names[item]
        for item in (scene.characters_json or [])
        if item in entry_names
    ]
    if people:
        parts.append("出场人物：" + "、".join(people))
    location = entry_names.get(scene.location_id) if scene.location_id else None
    if location:
        parts.append("地点：" + location)
    if scene.story_time:
        parts.append("时间：" + scene.story_time)
    if scene.pov:
        parts.append("视角：" + scene.pov)
    if scene.target_words_min is not None or scene.target_words_max is not None:
        parts.append(
            f"字数区间：{scene.target_words_min or '?'}–{scene.target_words_max or '?'}"
        )
    if scene.status:
        parts.append("状态：" + STATUS_LABELS.get(scene.status, scene.status))
    return {
        "doc_id": f"scene:{scene.id}",
        "project_id": volume.project_id,
        "entity_type": "scene",
        "subtype": "",
        "title": (
            f"第{volume.seq + 1}卷 第{chapter.seq + 1}章 场景{scene.seq + 1} "
            f"{scene.goal or '（未写目标）'}"
        ),
        "body": " ".join(parts),
    }
