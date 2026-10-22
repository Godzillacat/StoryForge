"""影响面分析：改上游之前，先算出下游会被牵动哪里。

**只读。** 调用这里不改变任何数据 —— 副作用发生在作者点「标为待复核」时。
§3.3 的「交给作者定夺」要求先看到代价再决定，先斩后奏没有意义。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Act,
    Architecture,
    AuditIssue,
    Chapter,
    EntryRelation,
    Foreshadow,
    Project,
    Scene,
    SceneDraft,
    SceneRevision,
    SettingEntry,
    TimelineEvent,
    Volume,
)
from app.lock_types import LOCK_TARGETS, normalize_target_type
from app.services import lock_service


def scene_label(volume: Volume, chapter: Chapter, seq: int) -> str:
    return f"第{volume.seq + 1}卷 第{chapter.seq + 1}章 场景{seq + 1}"


def _walk(session: Session, project_id: str):
    """遍历整个项目，钉住每个场景的标签与它的卷章祖先。

    影响面的每个分组都要「场景在哪」与「锁定来源是谁」，一次遍历比每类
    目标各查一遍省事，也让标签格式只有一份。
    """
    volumes = list(
        session.scalars(
            select(Volume)
            .where(Volume.project_id == project_id)
            .order_by(Volume.seq, Volume.created_at)
        )
    )
    for volume in volumes:
        chapters = list(
            session.scalars(
                select(Chapter)
                .where(Chapter.volume_id == volume.id)
                .order_by(Chapter.seq, Chapter.created_at)
            )
        )
        for chapter in chapters:
            yield volume, chapter, list(
                session.scalars(
                    select(Scene)
                    .where(Scene.chapter_id == chapter.id)
                    .order_by(Scene.seq, Scene.created_at)
                )
            )


def _scene_item(session: Session, volume, chapter, scene) -> dict:
    state = lock_service.effective_scene_lock(session, scene)
    return {
        "type": "scene",
        "id": scene.id,
        "label": scene_label(volume, chapter, scene.seq),
        "detail": scene.goal,
        "locked": state["locked"],
        "locked_by": state["label"] if state["locked"] else "",
        "path": f"/chapters?project={volume.project_id}&scene={scene.id}",
    }


def _group(key: str, label: str, items: list[dict], note: str = "") -> dict:
    return {
        "key": key,
        "label": label,
        "total": len(items),
        "locked": sum(1 for item in items if item.get("locked")),
        "items": items,
        "note": note,
    }


def _open_issues(session: Session, scene_ids: list[str]) -> list[AuditIssue]:
    if not scene_ids:
        return []
    return list(
        session.scalars(
            select(AuditIssue).where(
                AuditIssue.scene_id.in_(scene_ids), AuditIssue.status == "open"
            )
        )
    )


def _foreshadows(session: Session, project_id: str) -> list[Foreshadow]:
    return list(
        session.scalars(select(Foreshadow).where(Foreshadow.project_id == project_id))
    )


# ---- 五种目标 ----

def _architecture_path(session: Session, project_id: str) -> dict:
    arch = session.scalars(
        select(Architecture).where(Architecture.project_id == project_id)
    ).first()
    if arch is None:
        raise ValueError("这个项目还没有故事圣经，无法分析影响面")
    acts = list(
        session.scalars(select(Act).where(Act.architecture_id == arch.id).order_by(Act.seq))
    )
    act_seqs = {act.seq for act in acts}

    volumes: list[dict] = []
    chapters: list[dict] = []
    scenes: list[dict] = []
    orphan_volumes: list[dict] = []
    for volume, chapter, scene_rows in _walk(session, project_id):
        if volume.act_seq is not None and volume.act_seq not in act_seqs:
            orphan_volumes.append(
                {
                    "type": "volume",
                    "id": volume.id,
                    "label": f"第{volume.seq + 1}卷（{volume.name}）",
                    "detail": "幕序号不在当前骨架里",
                    "locked": volume.locked,
                    "path": f"/chapters?project={project_id}&volume={volume.id}",
                }
            )
            continue
        volumes.append(
            {
                "type": "volume",
                "id": volume.id,
                "label": f"第{volume.seq + 1}卷（{volume.name}）",
                "detail": f"幕序号 {volume.act_seq}" if volume.act_seq else "",
                "locked": volume.locked,
                "path": f"/chapters?project={project_id}&volume={volume.id}",
            }
        )
        chapters.append(
            {
                "type": "chapter",
                "id": chapter.id,
                "label": f"第{volume.seq + 1}卷 第{chapter.seq + 1}章（{chapter.title}）",
                "detail": chapter.hook,
                "locked": chapter.locked or volume.locked,
                "path": f"/chapters?project={project_id}&chapter={chapter.id}",
            }
        )
        for scene in scene_rows:
            scenes.append(_scene_item(session, volume, chapter, scene))

    foreshadows = [
        row
        for row in _foreshadows(session, project_id)
        if row.actual_pay_scene_id is None and (row.plant_scene_id or row.plan_pay_scene_id)
    ]
    unrecovered = [
        {
            "type": "foreshadow",
            "id": row.id,
            "label": row.name,
            "detail": "未回收",
            "locked": False,
            "path": "/chapters?tab=foreshadows",
        }
        for row in foreshadows
    ]

    return {
        "groups": [
            _group(
                "acts",
                "幕骨架",
                [
                    {
                        "type": "act",
                        "id": act.id,
                        "label": f"第{act.seq}幕（{act.name}）",
                        "detail": act.purpose or "",
                        "locked": False,
                        "path": "/architecture",
                    }
                    for act in acts
                ],
            ),
            _group("volumes", "受影响的卷", volumes),
            _group("chapters", "受影响的章", chapters),
            _group("scenes", "受影响的场景", scenes),
            _group("unrecovered_foreshadows", "未回收伏笔", unrecovered),
            _group(
                "orphan_volumes",
                "幕序号已失效的卷",
                orphan_volumes,
                "这些卷指向的幕在当前骨架里不存在，改架构时最需要重看。",
            ),
        ]
    }


def _entry_path(session: Session, project_id: str, entry_id: str) -> dict:
    entry = session.get(SettingEntry, entry_id)
    if entry is None or entry.project_id != project_id:
        raise ValueError(f"设定条目不存在：{entry_id}")

    scenes: list[dict] = []
    for volume, chapter, scene_rows in _walk(session, project_id):
        for scene in scene_rows:
            hit = (
                entry.type == "character" and entry.id in (scene.characters_json or [])
            ) or scene.location_id == entry.id
            if hit:
                scenes.append(_scene_item(session, volume, chapter, scene))

    relations = list(
        session.scalars(
            select(EntryRelation).where(
                EntryRelation.project_id == project_id,
                (EntryRelation.from_id == entry.id) | (EntryRelation.to_id == entry.id),
            )
        )
    )
    related = []
    for relation in relations:
        other_id = relation.to_id if relation.from_id == entry.id else relation.from_id
        other = session.get(SettingEntry, other_id)
        if other is None:
            continue
        related.append(
            {
                "type": "relation",
                "id": relation.id,
                "label": f"{entry.name} —{relation.kind}→ {other.name}"
                if relation.from_id == entry.id
                else f"{other.name} —{relation.kind}→ {entry.name}",
                "detail": relation.note or "",
                "locked": other.locked,
                "path": f"/world?project={project_id}&entry={other.id}",
            }
        )

    events = [
        event
        for event in session.scalars(
            select(TimelineEvent).where(TimelineEvent.project_id == project_id)
        )
        if entry.id in (event.participants_json or []) or event.location_id == entry.id
    ]
    timeline = [
        {
            "type": "timeline_event",
            "id": event.id,
            "label": event.title,
            "detail": event.story_time or "",
            "locked": False,
            "path": f"/timeline?project={project_id}&event={event.id}",
        }
        for event in events
    ]

    # 「正文里提到它」走全文检索：索引是惰性的，刚写的内容可能还没进去。
    from app.services import search_service

    mentions: list[dict] = []
    seen: set[str] = set()
    for query in [entry.name, *(entry.aliases_json or [])]:
        text = (query or "").strip()
        if not text:
            continue
        for hit in search_service.search(session, project_id, text, ["scene"]):
            if hit.entity_id in seen:
                continue
            seen.add(hit.entity_id)
            scene = session.get(Scene, hit.entity_id)
            if scene is None:
                continue
            chapter = session.get(Chapter, scene.chapter_id)
            volume = session.get(Volume, chapter.volume_id) if chapter else None
            if chapter is None or volume is None:
                continue
            mentions.append(_scene_item(session, volume, chapter, scene))

    issue_scene_ids = [item["id"] for item in scenes]
    issues = _open_issues(session, issue_scene_ids)
    issue_rows = [
        {
            "type": "audit_issue",
            "id": issue.id,
            "label": issue.kind,
            "detail": issue.explanation,
            "locked": False,
            "path": f"/write?scene={issue.scene_id}",
        }
        for issue in issues
    ]

    return {
        "groups": [
            _group("scenes", "出场 / 使用它的场景", scenes),
            _group("mentions", "正文提到它的场景", mentions, "按全文检索，可能有延迟。"),
            _group("relations", "相关关系", related),
            _group("timeline", "时间线事件", timeline),
            _group("issues", "未处理的问题", issue_rows),
        ]
    }


def _volume_path(session: Session, project_id: str, volume_id: str) -> dict:
    volume = session.get(Volume, volume_id)
    if volume is None or volume.project_id != project_id:
        raise ValueError(f"卷不存在：{volume_id}")
    chapters: list[dict] = []
    scenes: list[dict] = []
    scene_ids: list[str] = []
    for row_volume, chapter, scene_rows in _walk(session, project_id):
        if row_volume.id != volume_id:
            continue
        chapters.append(
            {
                "type": "chapter",
                "id": chapter.id,
                "label": f"第{chapter.seq + 1}章（{chapter.title}）",
                "detail": chapter.hook,
                "locked": chapter.locked or row_volume.locked,
                "path": f"/chapters?project={project_id}&chapter={chapter.id}",
            }
        )
        for scene in scene_rows:
            scenes.append(_scene_item(session, row_volume, chapter, scene))
            scene_ids.append(scene.id)

    foreshadows = [
        row
        for row in _foreshadows(session, project_id)
        if row.actual_pay_scene_id is None
        and (row.plant_scene_id in scene_ids or row.plan_pay_scene_id in scene_ids)
    ]
    issues = _open_issues(session, scene_ids)
    return {
        "groups": [
            _group("chapters", "卷内的章", chapters),
            _group("scenes", "卷内的场景", scenes),
            _group(
                "foreshadows",
                "卷内未回收的伏笔",
                [
                    {
                        "type": "foreshadow",
                        "id": row.id,
                        "label": row.name,
                        "detail": "未回收",
                        "locked": False,
                        "path": "/chapters?tab=foreshadows",
                    }
                    for row in foreshadows
                ],
            ),
            _group(
                "issues",
                "未处理的问题",
                [
                    {
                        "type": "audit_issue",
                        "id": issue.id,
                        "label": issue.kind,
                        "detail": issue.explanation,
                        "locked": False,
                        "path": f"/write?scene={issue.scene_id}",
                    }
                    for issue in issues
                ],
            ),
        ]
    }


def _chapter_path(session: Session, project_id: str, chapter_id: str) -> dict:
    chapter = session.get(Chapter, chapter_id)
    if chapter is None:
        raise ValueError(f"章不存在：{chapter_id}")
    volume = session.get(Volume, chapter.volume_id)
    if volume is None or volume.project_id != project_id:
        raise ValueError(f"章不属于这个项目：{chapter_id}")
    scene_rows = list(
        session.scalars(select(Scene).where(Scene.chapter_id == chapter_id).order_by(Scene.seq))
    )
    scenes = [_scene_item(session, volume, chapter, scene) for scene in scene_rows]
    scene_ids = [scene.id for scene in scene_rows]

    foreshadows = [
        row
        for row in _foreshadows(session, project_id)
        if row.actual_pay_scene_id is None
        and (row.plant_scene_id in scene_ids or row.plan_pay_scene_id in scene_ids)
    ]
    issues = _open_issues(session, scene_ids)
    return {
        "groups": [
            _group("scenes", "章内的场景", scenes),
            _group(
                "foreshadows",
                "章内未回收的伏笔",
                [
                    {
                        "type": "foreshadow",
                        "id": row.id,
                        "label": row.name,
                        "detail": "未回收",
                        "locked": False,
                        "path": "/chapters?tab=foreshadows",
                    }
                    for row in foreshadows
                ],
            ),
            _group(
                "issues",
                "未处理的问题",
                [
                    {
                        "type": "audit_issue",
                        "id": issue.id,
                        "label": issue.kind,
                        "detail": issue.explanation,
                        "locked": False,
                        "path": f"/write?scene={issue.scene_id}",
                    }
                    for issue in issues
                ],
            ),
        ]
    }


def _scene_path(session: Session, project_id: str, scene_id: str) -> dict:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise ValueError(f"场景不存在：{scene_id}")
    chapter = session.get(Chapter, scene.chapter_id)
    volume = session.get(Volume, chapter.volume_id) if chapter else None
    if chapter is None or volume is None or volume.project_id != project_id:
        raise ValueError(f"场景不属于这个项目：{scene_id}")

    foreshadows = [
        row
        for row in _foreshadows(session, project_id)
        if row.plant_scene_id == scene_id
        or row.plan_pay_scene_id == scene_id
        or row.actual_pay_scene_id == scene_id
    ]
    issues = _open_issues(session, [scene_id])
    drafts = list(
        session.scalars(select(SceneDraft).where(SceneDraft.scene_id == scene_id))
    )
    revisions = list(
        session.scalars(select(SceneRevision).where(SceneRevision.scene_id == scene_id))
    )
    state = lock_service.effective_scene_lock(session, scene)
    return {
        "groups": [
            _group(
                "foreshadows",
                "这一场涉及的伏笔",
                [
                    {
                        "type": "foreshadow",
                        "id": row.id,
                        "label": row.name,
                        "detail": "已回收"
                        if row.actual_pay_scene_id
                        else ("计划回收" if row.plan_pay_scene_id == scene_id else "埋设"),
                        "locked": False,
                        "path": "/chapters?tab=foreshadows",
                    }
                    for row in foreshadows
                ],
            ),
            _group(
                "issues",
                "未处理的问题",
                [
                    {
                        "type": "audit_issue",
                        "id": issue.id,
                        "label": issue.kind,
                        "detail": issue.explanation,
                        "locked": False,
                        "path": f"/write?scene={scene_id}",
                    }
                    for issue in issues
                ],
            ),
            _group(
                "drafts",
                "草稿与修订",
                [
                    *[
                        {
                            "type": "draft",
                            "id": draft.id,
                            "label": "AI 草稿",
                            "detail": f"{len(draft.content or '')} 字",
                            # 草稿与修订本身不是可锁对象；不填 locked，
                            # 免得 totals.locked 里混进无法「标为待复核」的项。
                            "locked": False,
                            "path": f"/write?scene={scene_id}",
                        }
                        for draft in drafts
                    ],
                    *[
                        {
                            "type": "revision",
                            "id": revision.id,
                            "label": {
                                "ai": "采纳快照",
                                "author": "作者保存",
                                "restore": "恢复快照",
                            }.get(revision.source, revision.source),
                            "detail": f"{len(revision.content or '')} 字",
                            "locked": False,
                            "path": f"/write?scene={scene_id}",
                        }
                        for revision in revisions
                    ],
                ],
            ),
        ]
    }


def analyze(
    session: Session, project_id: str, target_type: str, target_id: str
) -> dict:
    kind = normalize_target_type(target_type)
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError(f"项目不存在：{project_id}")

    if kind == "architecture":
        arch = session.scalars(
            select(Architecture).where(Architecture.project_id == project_id)
        ).first()
        if arch is None:
            raise ValueError("这个项目还没有故事圣经，无法分析影响面")
        target_label = "故事圣经"
        own_locked = arch.locked
        body = _architecture_path(session, project_id)
    elif kind == "entry":
        entry = session.get(SettingEntry, target_id)
        if entry is None or entry.project_id != project_id:
            raise ValueError(f"设定条目不存在：{target_id}")
        target_label = entry.name
        own_locked = entry.locked
        body = _entry_path(session, project_id, target_id)
    elif kind == "volume":
        volume = session.get(Volume, target_id)
        if volume is None or volume.project_id != project_id:
            raise ValueError(f"卷不存在：{target_id}")
        target_label = f"第{volume.seq + 1}卷（{volume.name}）"
        own_locked = volume.locked
        body = _volume_path(session, project_id, target_id)
    elif kind == "chapter":
        chapter = session.get(Chapter, target_id)
        if chapter is None:
            raise ValueError(f"章不存在：{target_id}")
        volume = session.get(Volume, chapter.volume_id)
        if volume is None or volume.project_id != project_id:
            raise ValueError(f"章不属于这个项目：{target_id}")
        target_label = f"第{chapter.seq + 1}章（{chapter.title}）"
        own_locked = chapter.locked or volume.locked
        body = _chapter_path(session, project_id, target_id)
    else:
        scene = session.get(Scene, target_id)
        if scene is None:
            raise ValueError(f"场景不存在：{target_id}")
        state = lock_service.effective_scene_lock(session, scene)
        target_label = "这一场"
        own_locked = state["locked"]
        body = _scene_path(session, project_id, target_id)

    groups = body["groups"]
    return {
        "project_id": project.id,
        "target": {
            "type": kind,
            "type_label": LOCK_TARGETS[kind],
            "id": target_id,
            "label": target_label,
            "locked": own_locked,
        },
        "groups": groups,
        "totals": {
            "all": sum(group["total"] for group in groups),
            "locked": sum(group["locked"] for group in groups),
        },
    }
