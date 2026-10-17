"""场景的 CRUD、名称解析、伏笔挂接与批量写入。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chapter_types import normalize_status
from app.db.models import Chapter, Foreshadow, Scene, SettingEntry
from app.services import chapter_service, foreshadow_service


def _chapter(session: Session, chapter_id: str) -> Chapter:
    chapter = session.get(Chapter, chapter_id)
    if chapter is None:
        raise ValueError(f"章不存在：{chapter_id}")
    return chapter


def _entries(session: Session, project_id: str) -> list[SettingEntry]:
    return list(
        session.scalars(select(SettingEntry).where(SettingEntry.project_id == project_id))
    )


def resolve_entry_name(
    session: Session,
    project_id: str,
    name: str,
    *,
    character_only: bool = False,
) -> SettingEntry | None:
    """精确名或别名匹配；找不到返回 None，歧义抛 ValueError。

    计划阶段用 None 收集 warning；写入阶段调用方把 None 变成 400。
    """
    clean = (name or "").strip()
    if not clean:
        return None
    entries = _entries(session, project_id)
    by_name = [entry for entry in entries if entry.name == clean]
    if by_name:
        matches = by_name
    else:
        matches = [entry for entry in entries if clean in (entry.aliases_json or [])]
    if not matches:
        return None
    if len(matches) > 1:
        labels = "、".join(entry.name for entry in matches)
        raise ValueError(f"名称「{clean}」同时匹配多个条目：{labels}")
    entry = matches[0]
    if character_only and entry.type != "character":
        raise ValueError(f"「{entry.name}」不是人物")
    return entry


def resolve_character_names(session: Session, project_id: str, names: list[str]) -> list[str]:
    out: list[str] = []
    for name in names or []:
        entry = resolve_entry_name(session, project_id, name, character_only=True)
        if entry is None:
            raise ValueError(f"人物「{name}」在世界观里找不到")
        if entry.id not in out:
            out.append(entry.id)
    return out


def resolve_location(session: Session, project_id: str, name: str | None) -> str | None:
    clean = (name or "").strip()
    if not clean:
        return None
    entry = resolve_entry_name(session, project_id, clean)
    if entry is None:
        raise ValueError(f"地点「{clean}」在世界观里找不到")
    return entry.id


def _foreshadow_conflicts(
    session: Session,
    project_id: str,
    desired: list[tuple[str, str]],
    scene_ids_to_replace: set[str],
) -> list[Foreshadow]:
    """校验并返回按名称需要的伏笔行（不存在的不在此处创建）。

    desired 是 (name, 'plant'|'pay') 列表；同一场景内重复先由调用方去重。
    同一名称不能出现在两个「埋设」或两个「计划回收」里。
    """
    seen_plant: dict[str, int] = {}
    seen_pay: dict[str, int] = {}
    for name, kind in desired:
        bucket = seen_plant if kind == "plant" else seen_pay
        bucket[name] = bucket.get(name, 0) + 1
    for name, count in seen_plant.items():
        if count > 1:
            raise ValueError(f"伏笔「{name}」在一次写入里被重复埋设")
    for name, count in seen_pay.items():
        if count > 1:
            raise ValueError(f"伏笔「{name}」在一次写入里被重复计划回收")

    rows: list[Foreshadow] = []
    for name, kind in desired:
        existing = foreshadow_service.find_by_name(session, project_id, name)
        if existing is None:
            continue
        linked = existing.plant_scene_id if kind == "plant" else existing.plan_pay_scene_id
        if linked is not None and linked not in scene_ids_to_replace:
            label = "埋设" if kind == "plant" else "计划回收"
            raise ValueError(f"伏笔「{name}」已经在另一个场景{label}")
        rows.append(existing)
    return rows


def _apply_scene_values(scene: Scene, fields: dict) -> None:
    if "goal" in fields:
        scene.goal = fields.get("goal") or ""
    if "conflict" in fields:
        scene.conflict = fields.get("conflict") or ""
    if "turn" in fields:
        scene.turn = fields.get("turn") or ""
    if "story_time" in fields:
        scene.story_time = fields.get("story_time") or ""
    if "pov" in fields:
        scene.pov = fields.get("pov") or ""
    if "target_words_min" in fields:
        scene.target_words_min = _positive_or_none(fields.get("target_words_min"), "字数下限")
    if "target_words_max" in fields:
        scene.target_words_max = _positive_or_none(fields.get("target_words_max"), "字数上限")
    if "status" in fields:
        scene.status = normalize_status(fields.get("status"))


def _positive_or_none(value, label: str) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label}必须是正整数")
    return value


def _validate_word_range(scene: Scene) -> None:
    if (
        scene.target_words_min is not None
        and scene.target_words_max is not None
        and scene.target_words_min > scene.target_words_max
    ):
        raise ValueError("目标字数下限不能大于上限")


def _apply_links(
    session: Session,
    project_id: str,
    scene: Scene,
    plant_names: list[str],
    pay_names: list[str],
    source_run_id: str | None,
    *,
    replaced_scene_ids: set[str] | None = None,
) -> None:
    """把本场景的埋设/回收名落到 foreshadow 表；先验后改。"""
    plant_names = [name.strip() for name in plant_names if name.strip()]
    pay_names = [name.strip() for name in pay_names if name.strip()]
    desired = [(name, "plant") for name in plant_names] + [
        (name, "pay") for name in pay_names
    ]
    _foreshadow_conflicts(
        session, project_id, desired, replaced_scene_ids or set()
    )

    # 先清掉本场景不再需要的旧链接（只清指向本场景的）
    existing = session.scalars(
        select(Foreshadow).where(Foreshadow.project_id == project_id)
    ).all()
    for row in existing:
        if row.plant_scene_id == scene.id and row.name not in plant_names:
            row.plant_scene_id = None
        if row.plan_pay_scene_id == scene.id and row.name not in pay_names:
            row.plan_pay_scene_id = None

    for name in plant_names:
        row = foreshadow_service.find_or_create(session, project_id, name, source_run_id)
        row.plant_scene_id = scene.id
    for name in pay_names:
        row = foreshadow_service.find_or_create(session, project_id, name, source_run_id)
        row.plan_pay_scene_id = scene.id


def create_scene(session: Session, chapter_id: str, **fields) -> Scene:
    _chapter(session, chapter_id)
    project = chapter_service.get_project_for_chapter(session, chapter_id)
    # 先把所有外部名称解析完，再改库 —— 失败不留半截。
    character_ids = resolve_character_names(
        session, project.id, fields.get("characters") or []
    )
    location_id = resolve_location(session, project.id, fields.get("location"))
    plant_names = [
        name.strip() for name in (fields.get("foreshadow_plants") or []) if name.strip()
    ]
    pay_names = [
        name.strip() for name in (fields.get("foreshadow_pays") or []) if name.strip()
    ]
    _foreshadow_conflicts(
        session,
        project.id,
        [(name, "plant") for name in plant_names]
        + [(name, "pay") for name in pay_names],
        set(),
    )

    try:
        last = session.scalars(
            select(Scene).where(Scene.chapter_id == chapter_id).order_by(Scene.seq.desc())
        ).first()
        scene = Scene(
            chapter_id=chapter_id,
            seq=(last.seq + 1) if last else 0,
            characters_json=character_ids,
            location_id=location_id,
            status=normalize_status(fields.get("status")),
            source_run_id=fields.get("source_run_id"),
        )
        _apply_scene_values(scene, fields)
        _validate_word_range(scene)
        session.add(scene)
        session.flush()
        _apply_links(
            session, project.id, scene, plant_names, pay_names, fields.get("source_run_id")
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return scene


def update_scene(session: Session, scene_id: str, **fields) -> Scene:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise ValueError(f"场景不存在：{scene_id}")
    project = chapter_service.get_project_for_chapter(session, scene.chapter_id)

    character_ids = None
    if "characters" in fields:
        character_ids = resolve_character_names(
            session, project.id, fields.get("characters") or []
        )
    location_id = None
    if "location" in fields:
        location_id = resolve_location(session, project.id, fields.get("location"))
    plant_names = fields.get("foreshadow_plants")
    pay_names = fields.get("foreshadow_pays")
    if plant_names is not None:
        plant_names = [name.strip() for name in plant_names if name.strip()]
    if pay_names is not None:
        pay_names = [name.strip() for name in pay_names if name.strip()]
    if plant_names is not None or pay_names is not None:
        _foreshadow_conflicts(
            session,
            project.id,
            [(name, "plant") for name in (plant_names or [])]
            + [(name, "pay") for name in (pay_names or [])],
            {scene.id},
        )

    try:
        # 全部校验通过后才动 ORM 对象
        _apply_scene_values(scene, fields)
        if character_ids is not None:
            scene.characters_json = character_ids
        if "location" in fields:
            scene.location_id = location_id
        _validate_word_range(scene)
        if plant_names is not None or pay_names is not None:
            current_plants = (
                [
                    row.name
                    for row in session.scalars(
                        select(Foreshadow).where(Foreshadow.plant_scene_id == scene.id)
                    )
                ]
                if plant_names is None
                else plant_names
            )
            current_pays = (
                [
                    row.name
                    for row in session.scalars(
                        select(Foreshadow).where(
                            Foreshadow.plan_pay_scene_id == scene.id
                        )
                    )
                ]
                if pay_names is None
                else pay_names
            )
            _apply_links(
                session,
                project.id,
                scene,
                current_plants,
                current_pays,
                fields.get("source_run_id"),
                replaced_scene_ids={scene.id},
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return scene


def delete_scene(session: Session, scene_id: str) -> None:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise ValueError(f"场景不存在：{scene_id}")
    session.delete(scene)
    session.commit()


def move_scene(session: Session, scene_id: str, direction: str) -> Scene:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise ValueError(f"场景不存在：{scene_id}")
    if direction not in ("up", "down"):
        raise ValueError("移动方向只能是 up 或 down")
    ordered = list(
        session.scalars(
            select(Scene)
            .where(Scene.chapter_id == scene.chapter_id)
            .order_by(Scene.seq, Scene.created_at)
        )
    )
    index = next(i for i, item in enumerate(ordered) if item.id == scene_id)
    target = index - 1 if direction == "up" else index + 1
    if target < 0 or target >= len(ordered):
        return scene
    ordered.insert(target, ordered.pop(index))
    for position, item in enumerate(ordered):
        item.seq = position
    session.commit()
    return scene


def write_scenes(
    session: Session,
    chapter_id: str,
    scenes: list[dict],
    mode: str,
    source_run_id: str | None = None,
) -> list[Scene]:
    """批量替换/追加场景；所有名称与伏笔冲突先验完，再改库。"""
    if mode not in ("replace", "append"):
        raise ValueError("写入模式只能是 replace 或 append")
    _chapter(session, chapter_id)
    project = chapter_service.get_project_for_chapter(session, chapter_id)
    existing = list(
        session.scalars(select(Scene).where(Scene.chapter_id == chapter_id))
    )
    replaced_ids = {scene.id for scene in existing} if mode == "replace" else set()

    prepared = []
    all_plant: list[str] = []
    all_pay: list[str] = []
    for item in scenes:
        character_ids = resolve_character_names(
            session, project.id, item.get("characters") or []
        )
        location_id = resolve_location(session, project.id, item.get("location"))
        plants = [
            name.strip() for name in (item.get("foreshadow_plants") or []) if name.strip()
        ]
        pays = [
            name.strip() for name in (item.get("foreshadow_pays") or []) if name.strip()
        ]
        all_plant.extend(plants)
        all_pay.extend(pays)
        prepared.append((item, character_ids, location_id, plants, pays))

    # 同一批里重复埋设/回收在 _apply_links 里会被发现；这里先整体查一次冲突。
    _foreshadow_conflicts(
        session,
        project.id,
        [(name, "plant") for name in all_plant] + [(name, "pay") for name in all_pay],
        replaced_ids,
    )

    created: list[Scene] = []
    try:
        if mode == "replace":
            for scene in existing:
                session.delete(scene)
            session.flush()
            # FK SET NULL 是在库里发生的；identity map 里的旧伏笔对象仍带着
            # 指向已删场景的 ID。强制过期，避免随后 build_tree 读到旧链接。
            session.expire_all()
            start = 0
        else:
            last = session.scalars(
                select(Scene)
                .where(Scene.chapter_id == chapter_id)
                .order_by(Scene.seq.desc())
            ).first()
            start = (last.seq + 1) if last else 0

        for offset, (item, character_ids, location_id, plants, pays) in enumerate(prepared):
            scene = Scene(
                chapter_id=chapter_id,
                seq=start + offset,
                characters_json=character_ids,
                location_id=location_id,
                status=normalize_status(item.get("status")),
                source_run_id=source_run_id,
            )
            _apply_scene_values(scene, item)
            _validate_word_range(scene)
            session.add(scene)
            session.flush()
            _apply_links(
                session,
                project.id,
                scene,
                plants,
                pays,
                source_run_id,
                replaced_scene_ids=replaced_ids,
            )
            created.append(scene)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return created


def scene_payload(session: Session, scene: Scene) -> dict:
    rows = session.scalars(
        select(Foreshadow).where(Foreshadow.project_id == _project_id(session, scene))
    ).all()
    return {
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
        "foreshadows": {
            "plants": [
                {"id": row.id, "name": row.name}
                for row in rows
                if row.plant_scene_id == scene.id
            ],
            "pays": [
                {"id": row.id, "name": row.name}
                for row in rows
                if row.plan_pay_scene_id == scene.id
            ],
        },
    }


def _project_id(session: Session, scene: Scene) -> str:
    return chapter_service.get_project_for_chapter(session, scene.chapter_id).id
