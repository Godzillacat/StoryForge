"""卷 / 章的业务：CRUD、顺序、树。场景与伏笔的树节点由本模块统一查询。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chapter_types import normalize_status
from app.db.models import Chapter, Foreshadow, Project, Scene, Volume
from app.services import review_service, search_service


def _ordered_volumes(session: Session, project_id: str) -> list[Volume]:
    return list(
        session.scalars(
            select(Volume)
            .where(Volume.project_id == project_id)
            .order_by(Volume.seq, Volume.created_at)
        )
    )


def _ordered_chapters(session: Session, volume_id: str) -> list[Chapter]:
    return list(
        session.scalars(
            select(Chapter)
            .where(Chapter.volume_id == volume_id)
            .order_by(Chapter.seq, Chapter.created_at)
        )
    )


def _ordered_scenes(session: Session, chapter_id: str) -> list[Scene]:
    return list(
        session.scalars(
            select(Scene)
            .where(Scene.chapter_id == chapter_id)
            .order_by(Scene.seq, Scene.created_at)
        )
    )


def _project(session: Session, project_id: str) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError(f"项目不存在：{project_id}")
    return project


def get_project_for_volume(session: Session, volume_id: str) -> Project:
    volume = session.get(Volume, volume_id)
    if volume is None:
        raise ValueError(f"卷不存在：{volume_id}")
    return _project(session, volume.project_id)


def get_project_for_chapter(session: Session, chapter_id: str) -> Project:
    chapter = session.get(Chapter, chapter_id)
    if chapter is None:
        raise ValueError(f"章不存在：{chapter_id}")
    return get_project_for_volume(session, chapter.volume_id)


def _clean_name(value: str | None, label: str) -> str:
    name = (value or "").strip()
    if not name:
        raise ValueError(f"{label}不能为空")
    return name


def _positive_int(value, label: str) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label}必须是正整数")
    return value


def _level(value, label: str, maximum: int) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ValueError(f"{label}必须是 1–{maximum} 的整数")
    return value


def _ratio(value) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ValueError("对话占比必须是 0–1 之间的数")
    return float(value)


def create_volume(session: Session, project_id: str, **fields) -> Volume:
    _project(session, project_id)
    # 标签用「卷名称」而非「卷名」：服务层契约要求错误信息含「名称」，
    # 接口层契约要求含「卷名」，前者是后者的子串。
    name = _clean_name(fields.get("name"), "卷名称")
    last = session.scalars(
        select(Volume)
        .where(Volume.project_id == project_id)
        .order_by(Volume.seq.desc())
    ).first()
    volume = Volume(
        project_id=project_id,
        seq=(last.seq + 1) if last else 0,
        name=name,
        purpose=fields.get("purpose") or "",
        summary=fields.get("summary") or "",
        act_seq=fields.get("act_seq"),
        target_words=_positive_int(fields.get("target_words"), "目标字数"),
        status=normalize_status(fields.get("status")),
        source_run_id=fields.get("source_run_id"),
    )
    session.add(volume)
    search_service.mark_dirty(session, project_id)
    session.commit()
    return volume


def update_volume(session: Session, volume_id: str, **fields) -> Volume:
    volume = session.get(Volume, volume_id)
    if volume is None:
        raise ValueError(f"卷不存在：{volume_id}")
    # 先验后改：后面的校验失败时不能留下半截改动。任一步抛错都回滚。
    try:
        if "name" in fields:
            volume.name = _clean_name(fields.get("name"), "卷名称")
        if "purpose" in fields:
            volume.purpose = fields.get("purpose") or ""
        if "summary" in fields:
            volume.summary = fields.get("summary") or ""
        if "act_seq" in fields:
            value = fields.get("act_seq")
            volume.act_seq = None if value in (None, "") else int(value)
        if "target_words" in fields:
            volume.target_words = _positive_int(fields.get("target_words"), "目标字数")
        if "status" in fields:
            volume.status = normalize_status(fields.get("status"))
        if "source_run_id" in fields:
            volume.source_run_id = fields.get("source_run_id")
        search_service.mark_dirty(session, volume.project_id)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return volume


def delete_volume(session: Session, volume_id: str) -> None:
    volume = session.get(Volume, volume_id)
    if volume is None:
        raise ValueError(f"卷不存在：{volume_id}")
    # 显式逐章删除，而不是只靠库级 ON DELETE CASCADE：级联删除发生在数据库
    # 里，已经加载进 session 的章对象不会被标成 deleted，调用方随后
    # `session.get(Chapter, ...)` 会拿到一个库中已不存在、却仍是旧值的对象。
    for chapter in _ordered_chapters(session, volume_id):
        # 章里的场景也要清标记；级联删除发生在库里，标记清理得自己走一遍。
        for scene in _ordered_scenes(session, chapter.id):
            review_service.clear_for_target(session, volume.project_id, "scene", scene.id)
        review_service.clear_for_target(session, volume.project_id, "chapter", chapter.id)
        session.delete(chapter)
    review_service.clear_for_target(session, volume.project_id, "volume", volume_id)
    session.delete(volume)
    search_service.mark_dirty(session, volume.project_id)
    session.commit()


def move_volume(session: Session, volume_id: str, direction: str) -> Volume:
    volume = session.get(Volume, volume_id)
    if volume is None:
        raise ValueError(f"卷不存在：{volume_id}")
    if direction not in ("up", "down"):
        raise ValueError("移动方向只能是 up 或 down")
    ordered = _ordered_volumes(session, volume.project_id)
    index = next(i for i, item in enumerate(ordered) if item.id == volume_id)
    target = index - 1 if direction == "up" else index + 1
    if target < 0 or target >= len(ordered):
        return volume
    ordered.insert(target, ordered.pop(index))
    for position, item in enumerate(ordered):
        item.seq = position
    search_service.mark_dirty(session, volume.project_id)
    session.commit()
    return volume


def create_chapter(session: Session, volume_id: str, **fields) -> Chapter:
    volume = session.get(Volume, volume_id)
    if volume is None:
        raise ValueError(f"卷不存在：{volume_id}")
    title = _clean_name(fields.get("title"), "章标题")
    last = session.scalars(
        select(Chapter)
        .where(Chapter.volume_id == volume_id)
        .order_by(Chapter.seq.desc())
    ).first()
    chapter = Chapter(
        volume_id=volume_id,
        seq=(last.seq + 1) if last else 0,
        title=title,
        pov=fields.get("pov") or "",
        target_words=_positive_int(fields.get("target_words"), "目标字数"),
        emotional_tone=fields.get("emotional_tone") or "",
        lines_json=[str(item) for item in (fields.get("lines") or []) if str(item).strip()],
        hook=fields.get("hook") or "",
        summary=fields.get("summary") or "",
        conflict_level=_level(fields.get("conflict_level"), "冲突强度", 5),
        dialogue_ratio=_ratio(fields.get("dialogue_ratio")),
        hook_strength=_level(fields.get("hook_strength"), "钩子强度", 5),
        status=normalize_status(fields.get("status")),
        source_run_id=fields.get("source_run_id"),
    )
    session.add(chapter)
    search_service.mark_dirty(session, volume.project_id)
    session.commit()
    return chapter


def update_chapter(session: Session, chapter_id: str, **fields) -> Chapter:
    chapter = session.get(Chapter, chapter_id)
    if chapter is None:
        raise ValueError(f"章不存在：{chapter_id}")
    project = get_project_for_chapter(session, chapter_id)
    try:
        if "title" in fields:
            chapter.title = _clean_name(fields.get("title"), "章标题")
        if "pov" in fields:
            chapter.pov = fields.get("pov") or ""
        if "target_words" in fields:
            chapter.target_words = _positive_int(fields.get("target_words"), "目标字数")
        if "emotional_tone" in fields:
            chapter.emotional_tone = fields.get("emotional_tone") or ""
        if "lines" in fields:
            chapter.lines_json = [
                str(item) for item in (fields.get("lines") or []) if str(item).strip()
            ]
        if "hook" in fields:
            chapter.hook = fields.get("hook") or ""
        if "summary" in fields:
            chapter.summary = fields.get("summary") or ""
        if "conflict_level" in fields:
            chapter.conflict_level = _level(fields.get("conflict_level"), "冲突强度", 5)
        if "dialogue_ratio" in fields:
            chapter.dialogue_ratio = _ratio(fields.get("dialogue_ratio"))
        if "hook_strength" in fields:
            chapter.hook_strength = _level(fields.get("hook_strength"), "钩子强度", 5)
        if "status" in fields:
            chapter.status = normalize_status(fields.get("status"))
        if "source_run_id" in fields:
            chapter.source_run_id = fields.get("source_run_id")
        search_service.mark_dirty(session, project.id)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return chapter


def delete_chapter(session: Session, chapter_id: str) -> None:
    chapter = session.get(Chapter, chapter_id)
    if chapter is None:
        raise ValueError(f"章不存在：{chapter_id}")
    project = get_project_for_chapter(session, chapter_id)
    for scene in _ordered_scenes(session, chapter_id):
        review_service.clear_for_target(session, project.id, "scene", scene.id)
    review_service.clear_for_target(session, project.id, "chapter", chapter_id)
    session.delete(chapter)
    search_service.mark_dirty(session, project.id)
    session.commit()


def move_chapter(session: Session, chapter_id: str, direction: str) -> Chapter:
    chapter = session.get(Chapter, chapter_id)
    if chapter is None:
        raise ValueError(f"章不存在：{chapter_id}")
    project = get_project_for_chapter(session, chapter_id)
    if direction not in ("up", "down"):
        raise ValueError("移动方向只能是 up 或 down")
    ordered = _ordered_chapters(session, chapter.volume_id)
    index = next(i for i, item in enumerate(ordered) if item.id == chapter_id)
    target = index - 1 if direction == "up" else index + 1
    if target < 0 or target >= len(ordered):
        return chapter
    ordered.insert(target, ordered.pop(index))
    for position, item in enumerate(ordered):
        item.seq = position
    search_service.mark_dirty(session, project.id)
    session.commit()
    return chapter


def _scene_foreshadows(
    foreshadows: list[Foreshadow], scene_id: str
) -> dict[str, list[dict]]:
    return {
        "plants": [
            {"id": item.id, "name": item.name}
            for item in foreshadows
            if item.plant_scene_id == scene_id
        ],
        "pays": [
            {"id": item.id, "name": item.name}
            for item in foreshadows
            if item.plan_pay_scene_id == scene_id
        ],
        "actual_pays": [
            {"id": item.id, "name": item.name}
            for item in foreshadows
            if item.actual_pay_scene_id == scene_id
        ],
    }


def build_tree(session: Session, project_id: str) -> list[dict]:
    """一次查询整棵树；场景内嵌伏笔的埋设/回收。"""
    foreshadows = list(
        session.scalars(select(Foreshadow).where(Foreshadow.project_id == project_id))
    )
    volumes = []
    for volume in _ordered_volumes(session, project_id):
        chapters = []
        for chapter in _ordered_chapters(session, volume.id):
            scenes = [
                {
                    "id": scene.id,
                    "chapter_id": scene.chapter_id,
                    "seq": scene.seq,
                    "goal": scene.goal,
                    "conflict": scene.conflict,
                    "turn": scene.turn,
                    "characters": scene.characters_json,
                    "location_id": scene.location_id,
                    "story_time": scene.story_time,
                    "pov": scene.pov,
                    "target_words_min": scene.target_words_min,
                    "target_words_max": scene.target_words_max,
                    "status": scene.status,
                    "source_run_id": scene.source_run_id,
                    "locked": scene.locked,
                    "has_body": bool((scene.body or "").strip()),
                    "foreshadows": _scene_foreshadows(foreshadows, scene.id),
                }
                for scene in _ordered_scenes(session, chapter.id)
            ]
            chapters.append(
                {
                    "id": chapter.id,
                    "volume_id": chapter.volume_id,
                    "seq": chapter.seq,
                    "title": chapter.title,
                    "pov": chapter.pov,
                    "target_words": chapter.target_words,
                    "emotional_tone": chapter.emotional_tone,
                    "lines": chapter.lines_json,
                    "hook": chapter.hook,
                    "summary": chapter.summary,
                    "conflict_level": chapter.conflict_level,
                    "dialogue_ratio": chapter.dialogue_ratio,
                    "hook_strength": chapter.hook_strength,
                    "status": chapter.status,
                    "source_run_id": chapter.source_run_id,
                    "locked": chapter.locked,
                    "scenes": scenes,
                }
            )
        volumes.append(
            {
                "id": volume.id,
                "project_id": volume.project_id,
                "seq": volume.seq,
                "name": volume.name,
                "purpose": volume.purpose,
                "summary": volume.summary,
                "act_seq": volume.act_seq,
                "target_words": volume.target_words,
                "status": volume.status,
                "source_run_id": volume.source_run_id,
                "locked": volume.locked,
                "chapters": chapters,
            }
        )
    return volumes
