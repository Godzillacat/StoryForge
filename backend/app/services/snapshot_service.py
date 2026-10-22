"""项目快照：序列化、创建、回滚（产品 §4.11）。

**快照覆盖结构与正文，不含灵感原话。** D-04 说作者原话永久保留 —— 回滚
把作者后来写下的原话删掉，是产品明令禁止的事。这条边界让回滚永远不会
伤到最不能丢的那份材料。

**也不含日志类与配置类数据**：运行记录、修订历史、审计问题、草稿、批量
任务、管线、待复核标记、智能体、服务商、单价。回滚作品不该回滚「AI 花过
多少钱」或「作者调过的提示词」。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    Act,
    Architecture,
    Chapter,
    EntryRelation,
    Foreshadow,
    Idea,
    Project,
    ProjectSnapshot,
    Scene,
    SceneDraft,
    SceneRevision,
    SettingEntry,
    TimelineEvent,
    Volume,
)
from app.services import change_service
from app.text_stats import count_words

# 自动备份的名字前缀：界面据此把它与作者手动建的区分开。
AUTO_PREFIX = "回滚前自动备份"


def _project(session: Session, project_id: str) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError(f"项目不存在：{project_id}")
    return project


# ---- 序列化 ----

def dump_project(session: Session, project_id: str) -> dict:
    """把作品结构序列化成一份自包含的 JSON。"""
    project = _project(session, project_id)

    architecture = session.scalars(
        select(Architecture).where(Architecture.project_id == project_id)
    ).first()
    acts = (
        list(
            session.scalars(
                select(Act)
                .where(Act.architecture_id == architecture.id)
                .order_by(Act.seq)
            )
        )
        if architecture is not None
        else []
    )

    entries = list(
        session.scalars(
            select(SettingEntry).where(SettingEntry.project_id == project_id)
        )
    )
    relations = list(
        session.scalars(
            select(EntryRelation).where(EntryRelation.project_id == project_id)
        )
    )
    events = list(
        session.scalars(
            select(TimelineEvent)
            .where(TimelineEvent.project_id == project_id)
            .order_by(TimelineEvent.order_index)
        )
    )
    foreshadows = list(
        session.scalars(select(Foreshadow).where(Foreshadow.project_id == project_id))
    )

    volumes_out: list[dict] = []
    for volume in session.scalars(
        select(Volume)
        .where(Volume.project_id == project_id)
        .order_by(Volume.seq, Volume.created_at)
    ):
        chapters_out: list[dict] = []
        for chapter in session.scalars(
            select(Chapter)
            .where(Chapter.volume_id == volume.id)
            .order_by(Chapter.seq, Chapter.created_at)
        ):
            scenes_out = [
                {
                    "id": scene.id,
                    "seq": scene.seq,
                    "goal": scene.goal,
                    "conflict": scene.conflict,
                    "turn": scene.turn,
                    "characters": list(scene.characters_json or []),
                    "location_id": scene.location_id,
                    "story_time": scene.story_time,
                    "pov": scene.pov,
                    "target_words_min": scene.target_words_min,
                    "target_words_max": scene.target_words_max,
                    "status": scene.status,
                    "source_run_id": scene.source_run_id,
                    "body": scene.body,
                    "locked": bool(scene.locked),
                    "locked_paragraphs": list(scene.locked_paragraphs_json or []),
                }
                for scene in session.scalars(
                    select(Scene)
                    .where(Scene.chapter_id == chapter.id)
                    .order_by(Scene.seq, Scene.created_at)
                )
            ]
            chapters_out.append(
                {
                    "id": chapter.id,
                    "seq": chapter.seq,
                    "title": chapter.title,
                    "pov": chapter.pov,
                    "target_words": chapter.target_words,
                    "emotional_tone": chapter.emotional_tone,
                    "lines": list(chapter.lines_json or []),
                    "hook": chapter.hook,
                    "summary": chapter.summary,
                    "conflict_level": chapter.conflict_level,
                    "dialogue_ratio": chapter.dialogue_ratio,
                    "hook_strength": chapter.hook_strength,
                    "status": chapter.status,
                    "source_run_id": chapter.source_run_id,
                    "locked": bool(chapter.locked),
                    "scenes": scenes_out,
                }
            )
        volumes_out.append(
            {
                "id": volume.id,
                "seq": volume.seq,
                "name": volume.name,
                "purpose": volume.purpose,
                "summary": volume.summary,
                "act_seq": volume.act_seq,
                "target_words": volume.target_words,
                "status": volume.status,
                "source_run_id": volume.source_run_id,
                "locked": bool(volume.locked),
                "chapters": chapters_out,
            }
        )

    # 灵感只存**派生卡**，不存 raw_text —— 见模块说明。
    idea = session.scalars(
        select(Idea).where(Idea.project_id == project_id).order_by(Idea.created_at)
    ).first()

    return {
        "architecture": None
        if architecture is None
        else {
            "id": architecture.id,
            "tool_ref": architecture.tool_ref,
            "logline": architecture.logline,
            "theme": architecture.theme,
            "premise": architecture.premise,
            "ending_direction": architecture.ending_direction,
            "locked": bool(architecture.locked),
            "acts": [
                {
                    "id": act.id,
                    "seq": act.seq,
                    "name": act.name,
                    "purpose": act.purpose,
                    "target_word_ratio": act.target_word_ratio,
                    "summary": act.summary,
                }
                for act in acts
            ],
        },
        "entries": [
            {
                "id": entry.id,
                "type": entry.type,
                "name": entry.name,
                "aliases": list(entry.aliases_json or []),
                "tags": list(entry.tags_json or []),
                "summary": entry.summary,
                "description": entry.description,
                "hardness": entry.hardness,
                "source_run_id": entry.source_run_id,
                "locked": bool(entry.locked),
                # 人物八项由 CHARACTER_FIELDS 派生，手抄会漏掉日后新增的项。
                **{key: getattr(entry, key) for key in _character_keys()},
            }
            for entry in entries
        ],
        "relations": [
            {
                "id": relation.id,
                "from_id": relation.from_id,
                "to_id": relation.to_id,
                "kind": relation.kind,
                "note": relation.note,
                "strength": relation.strength,
            }
            for relation in relations
        ],
        "timeline": [
            {
                "id": event.id,
                "title": event.title,
                "story_time": event.story_time,
                "description": event.description,
                "order_index": event.order_index,
                "participants": list(event.participants_json or []),
                "location_id": event.location_id,
            }
            for event in events
        ],
        "foreshadows": [
            {
                "id": row.id,
                "name": row.name,
                "note": row.note,
                "plant_scene_id": row.plant_scene_id,
                "plan_pay_scene_id": row.plan_pay_scene_id,
                "actual_pay_scene_id": row.actual_pay_scene_id,
                "status": row.status,
                "source_run_id": row.source_run_id,
            }
            for row in foreshadows
        ],
        "volumes": volumes_out,
        "parsed_idea": idea.parsed_json if idea is not None else None,
    }


def _character_keys() -> tuple[str, ...]:
    from app.world_types import CHARACTER_FIELDS

    return tuple(CHARACTER_FIELDS)


def _scale(data: dict) -> dict:
    volumes = data.get("volumes") or []
    chapters = sum(len(v.get("chapters") or []) for v in volumes)
    scenes = 0
    words = 0
    for volume in volumes:
        for chapter in volume.get("chapters") or []:
            for scene in chapter.get("scenes") or []:
                scenes += 1
                words += count_words(scene.get("body"))
    return {
        "volumes": len(volumes),
        "chapters": chapters,
        "scenes": scenes,
        "words": words,
    }


# ---- 创建与查询 ----

def _clean_name(value: str | None) -> str:
    name = (value or "").strip()
    if not name:
        raise ValueError("快照名称不能为空")
    return name


def _find_by_name(session: Session, project_id: str, name: str) -> ProjectSnapshot | None:
    return session.scalars(
        select(ProjectSnapshot).where(
            ProjectSnapshot.project_id == project_id, ProjectSnapshot.name == name
        )
    ).first()


def create_snapshot(
    session: Session, project_id: str, name: str, note: str = "", *, commit: bool = True
) -> ProjectSnapshot:
    project = _project(session, project_id)
    clean = _clean_name(name)
    if _find_by_name(session, project_id, clean) is not None:
        raise ValueError(f"这个项目里已经有叫「{clean}」的快照了")
    data = dump_project(session, project_id)
    scale = _scale(data)
    row = ProjectSnapshot(
        project_id=project_id,
        name=clean,
        note=(note or "").strip(),
        data_json=data,
        **scale,
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ValueError(f"这个项目里已经有叫「{clean}」的快照了") from exc
    if commit:
        # 回滚时新建的自动备份必须自己提交：随后那次回滚可能失败，
        # 而这份备份正是为失败准备的后路。
        change_service.record(
            session,
            project_id,
            target_type="snapshot",
            target_id=row.id,
            target_label=clean,
            action="create",
            source="author" if not clean.startswith(AUTO_PREFIX) else "snapshot",
            summary=f"{scale['volumes']} 卷 / {scale['chapters']} 章 / {scale['scenes']} 场 / {scale['words']} 字",
        )
        session.commit()
    return row


def serialize_snapshot(row: ProjectSnapshot) -> dict:
    return {
        "id": row.id,
        "project_id": row.project_id,
        "name": row.name,
        "note": row.note,
        "volumes": row.volumes,
        "chapters": row.chapters,
        "scenes": row.scenes,
        "words": row.words,
        "auto": row.name.startswith(AUTO_PREFIX),
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


def list_snapshots(session: Session, project_id: str) -> list[dict]:
    _project(session, project_id)
    rows = session.scalars(
        select(ProjectSnapshot)
        .where(ProjectSnapshot.project_id == project_id)
        .order_by(ProjectSnapshot.created_at.desc(), ProjectSnapshot.id.desc())
    ).all()
    return [serialize_snapshot(row) for row in rows]


def get_snapshot(session: Session, snapshot_id: str) -> dict:
    row = _snapshot(session, snapshot_id)
    data = row.data_json or {}
    return {
        **serialize_snapshot(row),
        "preview": {
            "entries": len(data.get("entries") or []),
            "relations": len(data.get("relations") or []),
            "timeline": len(data.get("timeline") or []),
            "foreshadows": len(data.get("foreshadows") or []),
            "has_architecture": data.get("architecture") is not None,
            "volume_names": [v.get("name", "") for v in (data.get("volumes") or [])],
        },
    }


def _snapshot(session: Session, snapshot_id: str) -> ProjectSnapshot:
    row = session.get(ProjectSnapshot, snapshot_id)
    if row is None:
        raise ValueError(f"快照不存在：{snapshot_id}")
    return row


def delete_snapshot(session: Session, snapshot_id: str) -> None:
    row = _snapshot(session, snapshot_id)
    session.delete(row)
    session.commit()


# ---- 回滚 ----

def restore_snapshot(session: Session, snapshot_id: str) -> dict:
    """把项目结构恢复到快照当时。回滚前先自动备份，所以回滚本身可撤销。"""
    row = _snapshot(session, snapshot_id)
    project_id = row.project_id
    data = row.data_json or {}

    # 1. 自动备份：独立提交，回滚失败时它仍然在。
    backup = create_snapshot(
        session,
        project_id,
        f"{AUTO_PREFIX}（{row.name}）",
        note=f"回滚到「{row.name}」之前的自动备份",
    )

    # 2. 修订与草稿挂在场景上、写了 ON DELETE CASCADE —— 删场景会把它们一起
    #    带走。而它们是**日志**，回滚作品不该回滚日志（§1.2）。先抄出来，
    #    重建场景之后再按原 id 插回去。
    preserved = _preserve_attachments(session, project_id)

    _clear_structure(session, project_id)
    session.expire_all()

    # 3. 按快照里的原 id 重建，让修订 / 审计 / 伏笔继续指得着同一个对象。
    _rebuild(session, project_id, data)
    session.flush()
    _restore_attachments(session, preserved)
    session.flush()

    idea = session.scalars(
        select(Idea).where(Idea.project_id == project_id).order_by(Idea.created_at)
    ).first()
    if idea is not None and data.get("parsed_idea") is not None:
        idea.parsed_json = data["parsed_idea"]

    change_service.record(
        session,
        project_id,
        target_type="snapshot",
        target_id=row.id,
        target_label=row.name,
        action="rollback",
        source="snapshot",
        summary=f"回滚到「{row.name}」；回滚前已自动备份为「{backup.name}」",
    )
    session.commit()

    from app.services import search_service

    search_service.mark_dirty(session, project_id)
    session.commit()

    return {
        "snapshot": serialize_snapshot(row),
        "backup": serialize_snapshot(backup),
        "scale": _scale(_current_dump(session, project_id)),
    }


def _current_dump(session: Session, project_id: str) -> dict:
    return dump_project(session, project_id)


def _preserve_attachments(session: Session, project_id: str) -> dict:
    """把修订、草稿与审计问题按平值抄出来，待结构重建后再插回。"""
    from app.db.models import AuditIssue

    scene_ids = [
        row
        for row in session.scalars(
            select(Scene.id)
            .join(Chapter, Scene.chapter_id == Chapter.id)
            .join(Volume, Chapter.volume_id == Volume.id)
            .where(Volume.project_id == project_id)
        ).all()
    ]
    if not scene_ids:
        return {"revisions": [], "drafts": [], "issues": []}
    revisions = [
        {
            "id": row.id,
            "scene_id": row.scene_id,
            "content": row.content,
            "source": row.source,
            "run_id": row.run_id,
            "note": row.note,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in session.scalars(
            select(SceneRevision).where(SceneRevision.scene_id.in_(scene_ids))
        ).all()
    ]
    drafts = [
        {
            "id": row.id,
            "scene_id": row.scene_id,
            "run_id": row.run_id,
            "content": row.content,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in session.scalars(
            select(SceneDraft).where(SceneDraft.scene_id.in_(scene_ids))
        ).all()
    ]
    issues = [
        {
            "id": row.id,
            "project_id": row.project_id,
            "check_type": row.check_type,
            "layer": row.layer,
            "stage": row.stage,
            "scene_id": row.scene_id,
            "run_id": row.run_id,
            "source": row.source,
            "kind": row.kind,
            "severity": row.severity,
            "quote": row.quote,
            "rule_ref": row.rule_ref,
            "explanation": row.explanation,
            "reader_impact": row.reader_impact,
            "options_json": list(row.options_json or []),
            "target_entry_id": row.target_entry_id,
            "fingerprint": row.fingerprint,
            "status": row.status,
            "resolution": row.resolution,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in session.scalars(
            select(AuditIssue).where(AuditIssue.scene_id.in_(scene_ids))
        ).all()
    ]
    # 先删掉，别让 FK 级联在结构重建时再把它们带走一次。
    for row in session.scalars(
        select(SceneRevision).where(SceneRevision.scene_id.in_(scene_ids))
    ).all():
        session.delete(row)
    for row in session.scalars(
        select(SceneDraft).where(SceneDraft.scene_id.in_(scene_ids))
    ).all():
        session.delete(row)
    for row in session.scalars(
        select(AuditIssue).where(AuditIssue.scene_id.in_(scene_ids))
    ).all():
        session.delete(row)
    session.flush()
    return {"revisions": revisions, "drafts": drafts, "issues": issues}


def _restore_attachments(session: Session, preserved: dict) -> None:
    from app.db.models import AuditIssue

    scene_ids = {row.id for row in session.query(Scene).all()}
    for row in preserved["revisions"]:
        if row["scene_id"] not in scene_ids:
            continue
        item = SceneRevision(
            id=row["id"],
            scene_id=row["scene_id"],
            content=row["content"],
            source=row["source"],
            run_id=row["run_id"],
            note=row["note"],
        )
        item.created_at = row["created_at"]
        item.updated_at = row["updated_at"]
        session.add(item)
    for row in preserved["drafts"]:
        if row["scene_id"] not in scene_ids:
            continue
        item = SceneDraft(
            id=row["id"],
            scene_id=row["scene_id"],
            run_id=row["run_id"],
            content=row["content"],
        )
        item.created_at = row["created_at"]
        item.updated_at = row["updated_at"]
        session.add(item)
    for row in preserved["issues"]:
        if row["scene_id"] not in scene_ids:
            continue
        item = AuditIssue(
            id=row["id"],
            project_id=row["project_id"],
            check_type=row["check_type"],
            layer=row["layer"],
            stage=row["stage"],
            scene_id=row["scene_id"],
            run_id=row["run_id"],
            source=row["source"],
            kind=row["kind"],
            severity=row["severity"],
            quote=row["quote"],
            rule_ref=row["rule_ref"],
            explanation=row["explanation"],
            reader_impact=row["reader_impact"],
            options_json=row["options_json"],
            target_entry_id=row["target_entry_id"],
            fingerprint=row["fingerprint"],
            status=row["status"],
            resolution=row["resolution"],
        )
        item.created_at = row["created_at"]
        item.updated_at = row["updated_at"]
        session.add(item)
    session.flush()


def _clear_structure(session: Session, project_id: str) -> None:
    for volume in session.scalars(
        select(Volume).where(Volume.project_id == project_id)
    ).all():
        for chapter in session.scalars(
            select(Chapter).where(Chapter.volume_id == volume.id)
        ).all():
            for scene in session.scalars(
                select(Scene).where(Scene.chapter_id == chapter.id)
            ).all():
                session.delete(scene)
            session.delete(chapter)
        session.delete(volume)
    for entry in session.scalars(
        select(SettingEntry).where(SettingEntry.project_id == project_id)
    ).all():
        session.delete(entry)
    for event in session.scalars(
        select(TimelineEvent).where(TimelineEvent.project_id == project_id)
    ).all():
        session.delete(event)
    for row in session.scalars(
        select(Foreshadow).where(Foreshadow.project_id == project_id)
    ).all():
        session.delete(row)
    for architecture in session.scalars(
        select(Architecture).where(Architecture.project_id == project_id)
    ).all():
        for act in session.scalars(
            select(Act).where(Act.architecture_id == architecture.id)
        ).all():
            session.delete(act)
        session.delete(architecture)
    session.flush()


def _rebuild(session: Session, project_id: str, data: dict) -> None:
    architecture = data.get("architecture")
    if architecture:
        session.add(
            Architecture(
                id=architecture["id"],
                project_id=project_id,
                tool_ref=architecture.get("tool_ref"),
                logline=architecture.get("logline"),
                theme=architecture.get("theme"),
                premise=architecture.get("premise"),
                ending_direction=architecture.get("ending_direction"),
                locked=bool(architecture.get("locked")),
            )
        )
        # SQLAlchemy 不保证同批 add 的插入顺序；幕引用架构、场景引用章，
        # 每一层都得先落库再加下一层。
        session.flush()
        for act in architecture.get("acts") or []:
            session.add(
                Act(
                    id=act["id"],
                    architecture_id=architecture["id"],
                    seq=act.get("seq", 0),
                    name=act.get("name", ""),
                    purpose=act.get("purpose"),
                    target_word_ratio=act.get("target_word_ratio"),
                    summary=act.get("summary"),
                )
            )
    session.flush()

    for entry in data.get("entries") or []:
        row = SettingEntry(id=entry["id"], project_id=project_id, type="concept", name="")
        row.type = entry.get("type") or "concept"
        row.name = entry.get("name") or ""
        row.aliases_json = list(entry.get("aliases") or [])
        row.tags_json = list(entry.get("tags") or [])
        row.summary = entry.get("summary") or ""
        row.description = entry.get("description") or ""
        row.hardness = entry.get("hardness")
        row.source_run_id = entry.get("source_run_id")
        row.locked = bool(entry.get("locked"))
        for key in _character_keys():
            setattr(row, key, entry.get(key))
        session.add(row)
    session.flush()

    for relation in data.get("relations") or []:
        session.add(
            EntryRelation(
                id=relation["id"],
                project_id=project_id,
                from_id=relation["from_id"],
                to_id=relation["to_id"],
                kind=relation.get("kind", ""),
                note=relation.get("note") or "",
                strength=relation.get("strength"),
            )
        )

    for event in data.get("timeline") or []:
        session.add(
            TimelineEvent(
                id=event["id"],
                project_id=project_id,
                title=event.get("title", ""),
                story_time=event.get("story_time") or "",
                description=event.get("description") or "",
                order_index=event.get("order_index", 0),
                participants_json=list(event.get("participants") or []),
                location_id=event.get("location_id"),
            )
        )

    for volume in data.get("volumes") or []:
        session.flush()
        session.add(
            Volume(
                id=volume["id"],
                project_id=project_id,
                seq=volume.get("seq", 0),
                name=volume.get("name", ""),
                purpose=volume.get("purpose") or "",
                summary=volume.get("summary") or "",
                act_seq=volume.get("act_seq"),
                target_words=volume.get("target_words"),
                status=volume.get("status", "planned"),
                source_run_id=volume.get("source_run_id"),
                locked=bool(volume.get("locked")),
            )
        )
        session.flush()
        for chapter in volume.get("chapters") or []:
            session.add(
                Chapter(
                    id=chapter["id"],
                    volume_id=volume["id"],
                    seq=chapter.get("seq", 0),
                    title=chapter.get("title", ""),
                    pov=chapter.get("pov") or "",
                    target_words=chapter.get("target_words"),
                    emotional_tone=chapter.get("emotional_tone") or "",
                    lines_json=list(chapter.get("lines") or []),
                    hook=chapter.get("hook") or "",
                    summary=chapter.get("summary") or "",
                    conflict_level=chapter.get("conflict_level"),
                    dialogue_ratio=chapter.get("dialogue_ratio"),
                    hook_strength=chapter.get("hook_strength"),
                    status=chapter.get("status", "planned"),
                    source_run_id=chapter.get("source_run_id"),
                    locked=bool(chapter.get("locked")),
                )
            )
            session.flush()
            for scene in chapter.get("scenes") or []:
                session.add(
                    Scene(
                        id=scene["id"],
                        chapter_id=chapter["id"],
                        seq=scene.get("seq", 0),
                        goal=scene.get("goal") or "",
                        conflict=scene.get("conflict") or "",
                        turn=scene.get("turn") or "",
                        characters_json=list(scene.get("characters") or []),
                        location_id=scene.get("location_id"),
                        story_time=scene.get("story_time") or "",
                        pov=scene.get("pov") or "",
                        target_words_min=scene.get("target_words_min"),
                        target_words_max=scene.get("target_words_max"),
                        status=scene.get("status", "planned"),
                        source_run_id=scene.get("source_run_id"),
                        body=scene.get("body"),
                        locked=bool(scene.get("locked")),
                        locked_paragraphs_json=list(scene.get("locked_paragraphs") or []),
                    )
                )
    session.flush()

    for row in data.get("foreshadows") or []:
        session.add(
            Foreshadow(
                id=row["id"],
                project_id=project_id,
                name=row.get("name", ""),
                note=row.get("note") or "",
                plant_scene_id=row.get("plant_scene_id"),
                plan_pay_scene_id=row.get("plan_pay_scene_id"),
                actual_pay_scene_id=row.get("actual_pay_scene_id"),
                status=row.get("status", "planned"),
                source_run_id=row.get("source_run_id"),
            )
        )
