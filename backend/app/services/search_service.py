"""全文检索：文档构建、按项目重建、脏标记、删除清理与查询入口。

FTS5 表只由本模块写入；查询按脏标记与索引版本决定是否先重建。
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
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


@dataclass(frozen=True)
class SearchHit:
    entity_type: str
    entity_id: str
    subtype: str
    title: str
    snippet: str


_ALLOWED_TYPES = ("entry", "chapter", "scene")
_MODEL_BY_TYPE = {
    "entry": SettingEntry,
    "chapter": Chapter,
    "scene": Scene,
}


def search(
    session: Session,
    project_id: str,
    query: str,
    entity_types: list[str] | None = None,
    limit: int = 20,
) -> list[SearchHit]:
    normalized = " ".join((query or "").split())
    if not normalized:
        return []

    types = tuple(entity_types or _ALLOWED_TYPES)
    invalid = [item for item in types if item not in _ALLOWED_TYPES]
    if invalid:
        raise ValueError(f"未知的检索类型：{', '.join(invalid)}")
    limit = max(1, min(int(limit), 50))

    _ensure_fresh(session, project_id)

    terms = normalized.split()[:8]
    if all(len(term) >= 3 for term in terms):
        rows = _fts_rows(session, project_id, terms, types, limit)
    else:
        rows = _like_rows(session, project_id, terms, types, limit)

    hits: list[SearchHit] = []
    for row in rows:
        doc_id = str(row["doc_id"])
        if ":" not in doc_id:
            continue
        entity_type = row["entity_type"]
        entity_id = doc_id.split(":", 1)[1]
        if not _exists(session, entity_type, entity_id):
            continue
        hits.append(
            SearchHit(
                entity_type=entity_type,
                entity_id=entity_id,
                subtype=row["subtype"] or "",
                title=row["title"],
                # 命中词可能只出现在标题（如条目名），只取 body 会截不中。
                snippet=_snippet(f"{row['title']} {row['body']}", terms),
            )
        )
    return hits


def _ensure_fresh(session: Session, project_id: str) -> None:
    state = session.get(SearchIndexState, project_id)
    if (
        state is not None
        and state.dirty == 0
        and state.schema_version == SEARCH_INDEX_VERSION
    ):
        return
    rebuild_project(session, project_id)


def _fts_rows(session, project_id, terms, types, limit):
    match = " AND ".join(
        '"' + term.replace('"', '""') + '"' for term in terms
    )
    placeholders = ", ".join(f":t{index}" for index in range(len(types)))
    params = {
        "match": match,
        "pid": project_id,
        "limit": limit,
        **{f"t{index}": item for index, item in enumerate(types)},
    }
    sql = (
        "SELECT doc_id, entity_type, subtype, title, body "
        "FROM search_document "
        "WHERE search_document MATCH :match AND project_id = :pid "
        f"AND entity_type IN ({placeholders}) "
        "ORDER BY bm25(search_document) LIMIT :limit"
    )
    try:
        return list(session.execute(text(sql), params).mappings())
    except OperationalError:
        # 全是引号/特殊符号时 FTS 语法可能报错；回退 LIKE，不把 500 抛给作者。
        return _like_rows(session, project_id, terms, types, limit)


def _like_rows(session, project_id, terms, types, limit):
    conditions = []
    params = {"pid": project_id, "scan": limit * 3}
    for index, term in enumerate(terms):
        params[f"p{index}"] = f"%{_escape_like(term)}%"
        conditions.append(
            f"(title LIKE :p{index} ESCAPE '\\' OR body LIKE :p{index} ESCAPE '\\')"
        )
    placeholders = ", ".join(f":t{index}" for index in range(len(types)))
    params.update({f"t{index}": item for index, item in enumerate(types)})
    sql = (
        "SELECT doc_id, entity_type, subtype, title, body "
        "FROM search_document "
        f"WHERE project_id = :pid AND {' AND '.join(conditions)} "
        f"AND entity_type IN ({placeholders}) LIMIT :scan"
    )
    rows = list(session.execute(text(sql), params).mappings())
    rows.sort(key=lambda row: _like_rank(row, terms))
    return rows[:limit]


def _escape_like(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def _like_rank(row, terms) -> tuple[int, str, str]:
    title = str(row["title"]).casefold()
    body = str(row["body"]).casefold()
    best = 3
    for term in terms:
        needle = term.casefold()
        if title == needle:
            best = min(best, 0)
        elif needle in title:
            best = min(best, 1)
        elif needle in body:
            best = min(best, 2)
    return (best, str(row["entity_type"]), str(row["title"]))


def _snippet(body: str, terms: list[str], width: int = 30) -> str:
    flat = " ".join((body or "").split())
    folded = flat.casefold()
    for term in terms:
        needle = term.casefold()
        index = folded.find(needle)
        if index >= 0:
            start = max(0, index - width)
            end = min(len(flat), index + len(term) + width)
            prefix = "…" if start > 0 else ""
            suffix = "…" if end < len(flat) else ""
            return prefix + flat[start:end] + suffix
    return flat[:80] + ("…" if len(flat) > 80 else "")


def _exists(session: Session, entity_type: str, entity_id: str) -> bool:
    model = _MODEL_BY_TYPE.get(entity_type)
    return model is not None and session.get(model, entity_id) is not None
