"""场景正文分支：同一场戏的多种写法并行推进。

**只分支正文。** 场景卡（目标 / 冲突 / 转折 / 人物 / 地点）是共享的 ——
A、B 两案写的是同一场戏的不同写法，不是两场不同的戏。

锁定与段落锁的语义与主版**完全相同**：分支里的 AI 也是 AI。作者手工
保存一律不受限。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import BranchRevision, Scene, SceneBranch, SceneDraft, SceneRevision
from app.services import change_service, search_service
from app.text_stats import count_words


def _scene(session: Session, scene_id: str) -> Scene:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise ValueError(f"场景不存在：{scene_id}")
    return scene


def _branch(session: Session, branch_id: str) -> SceneBranch:
    row = session.get(SceneBranch, branch_id)
    if row is None:
        raise ValueError(f"分支不存在：{branch_id}")
    return row


def _clean_name(value: str | None) -> str:
    name = (value or "").strip()
    if not name:
        raise ValueError("分支名称不能为空")
    return name


def _find_by_name(session: Session, scene_id: str, name: str) -> SceneBranch | None:
    return session.scalars(
        select(SceneBranch).where(
            SceneBranch.scene_id == scene_id, SceneBranch.name == name
        )
    ).first()


def _label(session: Session, scene: Scene) -> str:
    """与写作台一致的场景标签。延迟导入避免与 text_service 的循环。"""
    from app.services.text_service import _scene_label

    return _scene_label(session, scene)


def create_branch(
    session: Session, scene_id: str, name: str, note: str = ""
) -> SceneBranch:
    scene = _scene(session, scene_id)
    clean = _clean_name(name)
    if _find_by_name(session, scene_id, clean) is not None:
        raise ValueError(f"这个场景里已经有叫「{clean}」的分支了")
    row = SceneBranch(
        scene_id=scene_id,
        name=clean,
        # 从主版正文起步：作者的典型路径是「主版写得差不多了，想试另一版」。
        content=scene.body or "",
        note=(note or "").strip(),
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ValueError(f"这个场景里已经有叫「{clean}」的分支了") from exc
    change_service.record(
        session,
        _project_id(session, scene),
        target_type="scene",
        target_id=scene_id,
        target_label=_label(session, scene),
        action="create",
        source="author",
        summary=f"开分支「{clean}」",
    )
    session.commit()
    return row


def _project_id(session: Session, scene: Scene) -> str:
    from app.services.chapter_service import get_project_for_chapter

    return get_project_for_chapter(session, scene.chapter_id).id


def serialize_branch(row: SceneBranch) -> dict:
    return {
        "id": row.id,
        "scene_id": row.scene_id,
        "name": row.name,
        "note": row.note,
        "chars": count_words(row.content),
        "has_draft": bool((row.draft_content or "").strip()),
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
    }


def serialize_branch_detail(row: SceneBranch) -> dict:
    return {
        **serialize_branch(row),
        "content": row.content,
        "draft": (
            {"content": row.draft_content, "run_id": row.draft_run_id}
            if (row.draft_content or "").strip()
            else None
        ),
    }


def list_branches(session: Session, scene_id: str) -> list[dict]:
    _scene(session, scene_id)
    rows = session.scalars(
        select(SceneBranch)
        .where(SceneBranch.scene_id == scene_id)
        .order_by(SceneBranch.created_at, SceneBranch.id)
    ).all()
    return [serialize_branch(row) for row in rows]


def get_branch(session: Session, branch_id: str) -> dict:
    return serialize_branch_detail(_branch(session, branch_id))


def update_branch(
    session: Session, branch_id: str, *, name: str | None = None, note: str | None = None
) -> dict:
    row = _branch(session, branch_id)
    try:
        if name is not None:
            clean = _clean_name(name)
            other = _find_by_name(session, row.scene_id, clean)
            if other is not None and other.id != row.id:
                raise ValueError(f"这个场景里已经有叫「{clean}」的分支了")
            row.name = clean
        if note is not None:
            row.note = note.strip()
        session.commit()
    except Exception:
        session.rollback()
        raise
    return serialize_branch_detail(row)


def save_branch_body(session: Session, branch_id: str, content: str) -> dict:
    """作者手工保存：**不受锁限制** —— 锁只约束 AI。"""
    row = _branch(session, branch_id)
    new_content = content or ""
    if (row.content or "") != new_content:
        _add_revision(session, row, new_content, "author")
        row.content = new_content
        session.commit()
    return serialize_branch_detail(row)


def _add_revision(
    session: Session, row: SceneBranch, content: str, source: str
) -> BranchRevision:
    revision = BranchRevision(
        branch_id=row.id, content=content or "", source=source
    )
    session.add(revision)
    return revision


def list_branch_revisions(session: Session, branch_id: str) -> list[dict]:
    row = _branch(session, branch_id)
    rows = session.scalars(
        select(BranchRevision)
        .where(BranchRevision.branch_id == row.id)
        .order_by(BranchRevision.created_at.desc(), BranchRevision.id.desc())
    ).all()
    return [
        {
            "id": item.id,
            "source": item.source,
            "note": item.note,
            "chars": count_words(item.content),
            "created_at": item.created_at.isoformat() if item.created_at else "",
            "preview": (
                item.content
                if len(item.content) <= 80
                else item.content[:80] + "…"
            ),
        }
        for item in rows
    ]


def save_branch_draft(session: Session, branch_id: str, content: str) -> dict:
    row = _branch(session, branch_id)
    row.draft_content = content or ""
    session.commit()
    return serialize_branch_detail(row)


def _reject_if_locked(session: Session, scene: Scene) -> None:
    """分支里的 AI 也是 AI：与主版走同一条判定。"""
    from app.services.text_service import _reject_locked

    _reject_locked(session, scene)


def _reject_missing_paragraphs(scene: Scene, content: str) -> None:
    from app.services.text_service import _reject_missing_paragraphs as check

    check(scene, content)


def adopt_branch_draft(session: Session, branch_id: str) -> dict:
    row = _branch(session, branch_id)
    scene = _scene(session, row.scene_id)
    _reject_if_locked(session, scene)
    content = row.draft_content or ""
    if not content.strip():
        raise ValueError("分支没有可采纳的草稿")
    _reject_missing_paragraphs(scene, content)
    if (row.content or "") != content:
        _add_revision(session, row, content, "ai")
    row.content = content
    row.draft_content = ""
    row.draft_run_id = None
    session.commit()
    return serialize_branch_detail(row)


def merge_branch(session: Session, branch_id: str) -> dict:
    """把分支正文合入主版。**分支保留** —— 合并是选它作主版，不是作废其余。"""
    row = _branch(session, branch_id)
    scene = _scene(session, row.scene_id)
    _reject_if_locked(session, scene)
    content = row.content or ""
    if not content.strip():
        raise ValueError("分支正文为空，不能合入主版")
    _reject_missing_paragraphs(scene, content)

    from app.services.text_service import _supersede_audit

    project_id = _project_id(session, scene)
    old = scene.body or ""
    if old.strip():
        session.add(
            SceneRevision(
                scene_id=scene.id,
                content=old,
                source="branch",
                note=f"合并分支「{row.name}」前的主版",
            )
        )
    scene.body = content
    # 主版正文刚被整份替换，旧草稿是「针对旧正文生成、还没采纳」的材料。
    # 留着它，作者下次点「采纳为正文」就会把刚合入的正文顶掉 —— 那不是
    # 他此刻的意图。合并本身就意味着「这一版我定了」。
    stale = session.scalars(
        select(SceneDraft).where(SceneDraft.scene_id == scene.id)
    ).first()
    if stale is not None:
        session.delete(stale)
    search_service.mark_dirty(session, project_id)
    _supersede_audit(session, scene.id)
    change_service.record(
        session,
        project_id,
        target_type="scene",
        target_id=scene.id,
        target_label=_label(session, scene),
        action="adopt",
        source="author",
        summary=f"合并分支「{row.name}」（{count_words(content)} 字）",
    )
    session.commit()
    return {
        "branch": serialize_branch_detail(row),
        "scene_id": scene.id,
        "body": scene.body,
        "chars": count_words(scene.body),
    }


def discard_branch(session: Session, branch_id: str) -> None:
    row = _branch(session, branch_id)
    scene = _scene(session, row.scene_id)
    project_id = _project_id(session, scene)
    name = row.name
    session.delete(row)
    change_service.record(
        session,
        project_id,
        target_type="scene",
        target_id=scene.id,
        target_label=_label(session, scene),
        action="delete",
        source="author",
        summary=f"丢弃分支「{name}」",
    )
    session.commit()
