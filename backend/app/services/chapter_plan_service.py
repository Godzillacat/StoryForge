"""策划结果归一化与章纲写入。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chapter_types import normalize_status
from app.db.models import Chapter, Project, Scene, Volume
from app.services import (
    chapter_service,
    lock_service,
    review_service,
    scene_service,
    search_service,
)


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _positive(value, warnings: list[str], label: str) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        warnings.append(f"{label}不是正整数，已清空")
        return None
    return value


def _level(value, warnings: list[str], label: str) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
        warnings.append(f"{label}不在 1–5，已清空")
        return None
    return value


def _ratio(value, warnings: list[str]) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        warnings.append("对话占比不在 0–1，已清空")
        return None
    return float(value)


def normalize_chapter_plan(
    parsed: dict | None, act_seqs: set[int]
) -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    if not isinstance(parsed, dict):
        return [], warnings
    raw_volumes = parsed.get("volumes")
    if not isinstance(raw_volumes, list):
        return [], warnings

    volumes: list[dict] = []
    for v_index, raw in enumerate(raw_volumes, start=1):
        if not isinstance(raw, dict):
            warnings.append(f"第{v_index}卷不是对象，已跳过")
            continue
        name = _text(raw.get("name"))
        if not name:
            warnings.append(f"第{v_index}卷缺少卷名")
        act_seq = raw.get("act_seq")
        if act_seq is not None and act_seq not in act_seqs:
            warnings.append(f"第{v_index}卷的幕序号 {act_seq} 不在当前幕骨架里，已清空")
            act_seq = None
        raw_chapters = raw.get("chapters")
        if not isinstance(raw_chapters, list):
            warnings.append(f"第{v_index}卷没有章列表")
            raw_chapters = []
        chapters: list[dict] = []
        for c_index, chapter in enumerate(raw_chapters, start=1):
            if not isinstance(chapter, dict):
                warnings.append(f"第{v_index}卷第{c_index}章不是对象，已跳过")
                continue
            title = _text(chapter.get("title"))
            if not title:
                warnings.append(f"第{v_index}卷第{c_index}章缺少标题")
            raw_lines = chapter.get("lines")
            lines = (
                [str(item).strip() for item in raw_lines if str(item).strip()]
                if isinstance(raw_lines, list)
                else []
            )
            chapters.append(
                {
                    "title": title,
                    "pov": _text(chapter.get("pov")),
                    "target_words": _positive(
                        chapter.get("target_words"),
                        warnings,
                        f"第{v_index}卷第{c_index}章目标字数",
                    ),
                    "emotional_tone": _text(chapter.get("emotional_tone")),
                    "lines": lines,
                    "hook": _text(chapter.get("hook")),
                    "summary": _text(chapter.get("summary")),
                    "conflict_level": _level(
                        chapter.get("conflict_level"),
                        warnings,
                        f"第{v_index}卷第{c_index}章冲突强度",
                    ),
                    "dialogue_ratio": _ratio(chapter.get("dialogue_ratio"), warnings),
                    "hook_strength": _level(
                        chapter.get("hook_strength"),
                        warnings,
                        f"第{v_index}卷第{c_index}章钩子强度",
                    ),
                    "status": "planned",
                }
            )
        volumes.append(
            {
                "name": name,
                "purpose": _text(raw.get("purpose")),
                "summary": _text(raw.get("summary")),
                "act_seq": act_seq,
                "target_words": _positive(
                    raw.get("target_words"), warnings, f"第{v_index}卷目标字数"
                ),
                "status": "planned",
                "chapters": chapters,
            }
        )
    return volumes, warnings


def _warn_name(
    session: Session, project_id: str, name: str, warnings: list[str], label: str, index: int
) -> None:
    try:
        entry = scene_service.resolve_entry_name(
            session, project_id, name, character_only=(label == "人物")
        )
    except ValueError as exc:
        warnings.append(f"第{index}个场景：{exc}")
        return
    if entry is None:
        warnings.append(f"第{index}个场景：{label}「{name}」在世界观里找不到")


def normalize_scene_plan(
    parsed: dict | None, session: Session, project_id: str
) -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    if not isinstance(parsed, dict):
        return [], warnings
    raw_scenes = parsed.get("scenes")
    if not isinstance(raw_scenes, list):
        return [], warnings

    scenes: list[dict] = []
    for index, raw in enumerate(raw_scenes, start=1):
        if not isinstance(raw, dict):
            warnings.append(f"第{index}个场景不是对象，已跳过")
            continue
        raw_characters = raw.get("characters")
        characters = (
            [str(item).strip() for item in raw_characters if str(item).strip()]
            if isinstance(raw_characters, list)
            else []
        )
        for name in characters:
            _warn_name(session, project_id, name, warnings, "人物", index)
        location = _text(raw.get("location"))
        if location:
            _warn_name(session, project_id, location, warnings, "地点", index)
        min_words = _positive(
            raw.get("target_words_min"), warnings, f"第{index}个场景字数下限"
        )
        max_words = _positive(
            raw.get("target_words_max"), warnings, f"第{index}个场景字数上限"
        )
        if min_words is not None and max_words is not None and min_words > max_words:
            min_words, max_words = max_words, min_words
            warnings.append(f"第{index}个场景的字数区间上下限颠倒，已交换")

        def names(key: str) -> list[str]:
            value = raw.get(key)
            return (
                [str(item).strip() for item in value if str(item).strip()]
                if isinstance(value, list)
                else []
            )

        scenes.append(
            {
                "goal": _text(raw.get("goal")),
                "conflict": _text(raw.get("conflict")),
                "turn": _text(raw.get("turn")),
                "characters": characters,
                "location": location,
                "story_time": _text(raw.get("story_time")),
                "pov": _text(raw.get("pov")),
                "target_words_min": min_words,
                "target_words_max": max_words,
                "foreshadow_plants": names("foreshadow_plants"),
                "foreshadow_pays": names("foreshadow_pays"),
            }
        )
    return scenes, warnings


def _strict_text(value, label: str) -> str:
    text = (value or "").strip() if isinstance(value, str) else ""
    if not text:
        raise ValueError(f"{label}不能为空")
    return text


def _strict_positive(value, label: str) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label}必须是正整数")
    return value


def _strict_level(value, label: str) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
        raise ValueError(f"{label}必须是 1–5 的整数")
    return value


def _strict_ratio(value) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ValueError("对话占比必须是 0–1 之间的数")
    return float(value)


def _clear_marks_for_volume(session: Session, project_id: str, volume) -> None:
    review_service.clear_for_target(session, project_id, "volume", volume.id)
    for chapter in session.scalars(
        select(Chapter).where(Chapter.volume_id == volume.id)
    ):
        review_service.clear_for_target(session, project_id, "chapter", chapter.id)
        for scene in session.scalars(
            select(Scene).where(Scene.chapter_id == chapter.id)
        ):
            review_service.clear_for_target(session, project_id, "scene", scene.id)


def _reject_locked_replace(session: Session, project_id: str) -> None:
    """替换章纲会删掉整个项目的卷章场景 —— 锁定的对象不能被这样抹掉。

    在删除之前整次拒绝。锁在卷 / 章 / 场景任一层级都算：卷锁住时它的章与
    场景一并受保护，而作者想保住的可能正是那个卷，所以要把最外层被锁的那个
    说出来，作者才知道该去解锁哪一处。
    """
    volumes = list(
        session.scalars(select(Volume).where(Volume.project_id == project_id))
    )
    locked_volumes = [v for v in volumes if v.locked]
    if locked_volumes:
        names = "、".join(f"第{v.seq + 1}卷（{v.name}）" for v in locked_volumes)
        raise ValueError(
            f"这些卷已锁定：{names}。替换写入会删掉它们，请先解锁，或改用「追加」。"
        )
    chapter_ids: list[str] = []
    for volume in volumes:
        chapter_ids.extend(
            session.scalars(select(Chapter.id).where(Chapter.volume_id == volume.id)).all()
        )
    locked_chapters = lock_service.locked_chapter_ids(session, chapter_ids)
    if locked_chapters:
        rows = session.query(Chapter).filter(Chapter.id.in_(locked_chapters)).all()
        names = "、".join(f"第{r.seq + 1}章（{r.title}）" for r in rows)
        raise ValueError(
            f"这些章已锁定：{names}。替换写入会删掉它们，请先解锁，或改用「追加」。"
        )
    scenes = (
        list(
            session.scalars(
                select(Scene).where(Scene.chapter_id.in_(chapter_ids))
            )
        )
        if chapter_ids
        else []
    )
    locked_scenes = lock_service.locked_scene_ids(session, [s.id for s in scenes])
    if locked_scenes:
        names = "、".join(
            f"场景{scene.seq + 1}" for scene in scenes if scene.id in locked_scenes
        )
        raise ValueError(
            f"这些场景已锁定：{names}。替换写入会删掉它们，请先解锁，或改用「追加」。"
        )


def write_chapter_plan(    session: Session,
    project_id: str,
    volumes: list[dict],
    mode: str,
    source_run_id: str | None = None,
) -> list[dict]:
    if mode not in ("replace", "append"):
        raise ValueError("写入模式只能是 replace 或 append")
    if not volumes:
        raise ValueError("章纲写入至少需要一卷")
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError(f"项目不存在：{project_id}")

    prepared: list[dict] = []
    for v_index, raw in enumerate(volumes, start=1):
        name = _strict_text(raw.get("name"), f"第{v_index}卷卷名")
        chapters: list[dict] = []
        for c_index, chapter in enumerate(raw.get("chapters") or [], start=1):
            title = _strict_text(chapter.get("title"), f"第{v_index}卷第{c_index}章标题")
            raw_lines = chapter.get("lines")
            lines = (
                [str(item).strip() for item in raw_lines if str(item).strip()]
                if isinstance(raw_lines, list)
                else []
            )
            chapters.append(
                {
                    "title": title,
                    "pov": chapter.get("pov") or "",
                    "target_words": _strict_positive(
                        chapter.get("target_words"),
                        f"第{v_index}卷第{c_index}章目标字数",
                    ),
                    "emotional_tone": chapter.get("emotional_tone") or "",
                    "lines": lines,
                    "hook": chapter.get("hook") or "",
                    "summary": chapter.get("summary") or "",
                    "conflict_level": _strict_level(
                        chapter.get("conflict_level"),
                        f"第{v_index}卷第{c_index}章冲突强度",
                    ),
                    "dialogue_ratio": _strict_ratio(chapter.get("dialogue_ratio")),
                    "hook_strength": _strict_level(
                        chapter.get("hook_strength"),
                        f"第{v_index}卷第{c_index}章钩子强度",
                    ),
                    "status": normalize_status(chapter.get("status")),
                }
            )
        prepared.append(
            {
                "name": name,
                "purpose": raw.get("purpose") or "",
                "summary": raw.get("summary") or "",
                "act_seq": raw.get("act_seq"),
                "target_words": _strict_positive(
                    raw.get("target_words"), f"第{v_index}卷目标字数"
                ),
                "status": normalize_status(raw.get("status")),
                "chapters": chapters,
            }
        )

    try:
        if mode == "replace":
            _reject_locked_replace(session, project_id)
            for volume in session.scalars(
                select(Volume).where(Volume.project_id == project_id)
            ):
                # 替换把整棵树删掉，标记会指向不存在的对象。这里逐层清 ——
                # 删除走的是直接 session.delete，绕过了 delete_* 里的清理。
                _clear_marks_for_volume(session, project_id, volume)
                session.delete(volume)
            session.flush()
            # FK 级联删场景、伏笔链接置空都发生在库里；过期掉 identity map。
            session.expire_all()
            start_seq = 0
        else:
            last = session.scalars(
                select(Volume)
                .where(Volume.project_id == project_id)
                .order_by(Volume.seq.desc())
            ).first()
            start_seq = (last.seq + 1) if last else 0

        for v_offset, volume_data in enumerate(prepared):
            volume = Volume(
                project_id=project_id,
                seq=start_seq + v_offset,
                name=volume_data["name"],
                purpose=volume_data["purpose"],
                summary=volume_data["summary"],
                act_seq=volume_data["act_seq"],
                target_words=volume_data["target_words"],
                status=volume_data["status"],
                source_run_id=source_run_id,
            )
            session.add(volume)
            session.flush()
            for c_offset, chapter_data in enumerate(volume_data["chapters"]):
                session.add(
                    Chapter(
                        volume_id=volume.id,
                        seq=c_offset,
                        title=chapter_data["title"],
                        pov=chapter_data["pov"],
                        target_words=chapter_data["target_words"],
                        emotional_tone=chapter_data["emotional_tone"],
                        lines_json=chapter_data["lines"],
                        hook=chapter_data["hook"],
                        summary=chapter_data["summary"],
                        conflict_level=chapter_data["conflict_level"],
                        dialogue_ratio=chapter_data["dialogue_ratio"],
                        hook_strength=chapter_data["hook_strength"],
                        status=chapter_data["status"],
                        source_run_id=source_run_id,
                    )
                )
        search_service.mark_dirty(session, project.id)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return chapter_service.build_tree(session, project_id)
