"""锁定：有效锁定的解析、设置入口与段落锁。

锁**只约束 AI 写路径**。作者手工保存、编辑、删除永远可行 —— 产品原话是
「锁定的内容 AI 不得改动」，把手工作者也锁死会让作者为了改一个字先去解锁，
是拿控制力换摩擦。

有效锁定**向下继承**：卷被锁 → 其下所有章与场景都算锁定；章被锁 → 其下
所有场景都算锁定。作者想保护的是「这一卷别动了」，逐个场景去点不现实。
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.db.models import Architecture, Chapter, Scene, SettingEntry, Volume
from app.lock_types import normalize_target_type

_MODEL = {
    "architecture": Architecture,
    "entry": SettingEntry,
    "volume": Volume,
    "chapter": Chapter,
    "scene": Scene,
}

# 空行分段：一个或多个只含空白的行。Markdown 里段落之间按空行分隔。
_PARA_SPLIT = re.compile(r"\n\s*\n")


def paragraphs_of(text: str | None) -> list[str]:
    """按空行切段并 strip；空段丢弃。**不做任何其它归一化。**"""
    if not text:
        return []
    return [part.strip() for part in _PARA_SPLIT.split(text) if part.strip()]


def missing_locks(content: str | None, locks: list[str]) -> list[str]:
    """返回 `locks` 里在 `content` 中找不到的段落。

    逐字比对：段落锁的全部意义就是「一字不改」。多一段、少一段都不算缺失，
    只有锁住的那段文本本身不在正文里才算。
    """
    if not locks:
        return []
    present = set(paragraphs_of(content))
    return [text for text in locks if text not in present]


def _scene_chapter_volume(
    session: Session, scene: Scene
) -> tuple[Chapter | None, Volume | None]:
    chapter = session.get(Chapter, scene.chapter_id)
    volume = session.get(Volume, chapter.volume_id) if chapter is not None else None
    return chapter, volume


def effective_scene_lock(session: Session, scene: Scene) -> dict:
    """场景的有效锁定：自己 > 章 > 卷。返回锁定来源，供界面说明「为什么不能动」。"""
    if scene.locked:
        return {"locked": True, "source": "scene", "source_id": scene.id, "label": "这一场"}
    chapter, volume = _scene_chapter_volume(session, scene)
    if chapter is not None and chapter.locked:
        return {
            "locked": True,
            "source": "chapter",
            "source_id": chapter.id,
            "label": f"第{chapter.seq + 1}章（{chapter.title}）",
        }
    if volume is not None and volume.locked:
        return {
            "locked": True,
            "source": "volume",
            "source_id": volume.id,
            "label": f"第{volume.seq + 1}卷（{volume.name}）",
        }
    return {"locked": False, "source": None, "source_id": None, "label": ""}


def effective_chapter_lock(session: Session, chapter: Chapter) -> dict:
    if chapter.locked:
        return {"locked": True, "source": "chapter", "source_id": chapter.id, "label": "这一章"}
    volume = session.get(Volume, chapter.volume_id)
    if volume is not None and volume.locked:
        return {
            "locked": True,
            "source": "volume",
            "source_id": volume.id,
            "label": f"第{volume.seq + 1}卷（{volume.name}）",
        }
    return {"locked": False, "source": None, "source_id": None, "label": ""}


def effective_volume_lock(volume: Volume) -> dict:
    if volume.locked:
        return {"locked": True, "source": "volume", "source_id": volume.id, "label": "这一卷"}
    return {"locked": False, "source": None, "source_id": None, "label": ""}


def get_locked(session: Session, target_type: str, target_id: str) -> dict:
    """读单个目标的锁定状态；未锁也返回结构（界面不需要判空）。"""
    kind = normalize_target_type(target_type)
    row = session.get(_MODEL[kind], target_id)
    if row is None:
        raise ValueError(f"{_MISSING[kind]}：{target_id}")
    if kind == "scene":
        state = effective_scene_lock(session, row)
    elif kind == "chapter":
        state = effective_chapter_lock(session, row)
    elif kind == "volume":
        state = effective_volume_lock(row)
    else:
        state = {
            "locked": bool(row.locked),
            "source": "self" if row.locked else None,
            "source_id": row.id if row.locked else None,
            "label": "这一条" if row.locked else "",
        }
    return {
        "target_type": kind,
        "target_id": row.id,
        "own_locked": bool(row.locked),
        **state,
    }


_MISSING = {
    "architecture": "故事圣经不存在",
    "entry": "设定条目不存在",
    "volume": "卷不存在",
    "chapter": "章不存在",
    "scene": "场景不存在",
}


def set_locked(session: Session, target_type: str, target_id: str, locked: bool) -> dict:
    kind = normalize_target_type(target_type)
    row = session.get(_MODEL[kind], target_id)
    if row is None:
        raise ValueError(f"{_MISSING[kind]}：{target_id}")
    row.locked = bool(locked)
    session.commit()
    return get_locked(session, kind, target_id)


def locked_scene_ids(session: Session, scene_ids: list[str]) -> set[str]:
    """在一批场景里挑出**有效锁定**的那些。replace 写入与批量生成都用它。"""
    if not scene_ids:
        return set()
    scenes = session.query(Scene).filter(Scene.id.in_(scene_ids)).all()
    return {scene.id for scene in scenes if effective_scene_lock(session, scene)["locked"]}


def locked_chapter_ids(session: Session, chapter_ids: list[str]) -> set[str]:
    if not chapter_ids:
        return set()
    chapters = session.query(Chapter).filter(Chapter.id.in_(chapter_ids)).all()
    return {
        chapter.id
        for chapter in chapters
        if effective_chapter_lock(session, chapter)["locked"]
    }


def locked_volume_ids(session: Session, volume_ids: list[str]) -> set[str]:
    if not volume_ids:
        return set()
    volumes = session.query(Volume).filter(Volume.id.in_(volume_ids)).all()
    return {volume.id for volume in volumes if volume.locked}


# ---- 段落锁 ----

def paragraph_locks(session: Session, scene_id: str) -> list[str]:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise ValueError(f"场景不存在：{scene_id}")
    return list(scene.locked_paragraphs_json or [])


def set_paragraph_locks(session: Session, scene_id: str, paragraphs: list[str]) -> list[str]:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise ValueError(f"场景不存在：{scene_id}")
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in paragraphs or []:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    # JSON 列必须赋新列表再提交：原地 mutate 不会被 SQLAlchemy 跟踪。
    scene.locked_paragraphs_json = cleaned
    session.commit()
    return cleaned
