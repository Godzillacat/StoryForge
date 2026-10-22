from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Act, Architecture


def get_architecture(session: Session, project_id: str) -> tuple[Architecture | None, list[Act]]:
    arch = session.scalars(
        select(Architecture).where(Architecture.project_id == project_id).order_by(Architecture.created_at)
    ).first()
    if arch is None:
        return None, []
    acts = list(session.scalars(select(Act).where(Act.architecture_id == arch.id).order_by(Act.seq)))
    return arch, acts


def adopt(session: Session, project_id: str, payload: dict) -> tuple[Architecture, list[Act]]:
    """作者确认故事圣经后写入项目结构。重复采纳则原地更新。"""
    arch, existing_acts = get_architecture(session, project_id)
    if arch is not None and arch.locked:
        raise ValueError(
            "故事圣经已锁定，AI 不会改动它。要重新采纳请先在架构页解锁。"
        )
    if arch is None:
        arch = Architecture(project_id=project_id)
        session.add(arch)
        session.flush()
    for key in ("tool_ref", "logline", "theme", "premise", "ending_direction"):
        if payload.get(key) is not None:
            setattr(arch, key, payload[key])
    for act in existing_acts:
        session.delete(act)
    session.flush()

    acts: list[Act] = []
    for item in payload.get("acts", []):
        act = Act(
            architecture_id=arch.id,
            seq=item["seq"],
            name=item["name"],
            purpose=item.get("purpose"),
            target_word_ratio=item.get("target_word_ratio"),
            summary=item.get("summary"),
        )
        session.add(act)
        acts.append(act)
    session.commit()
    return arch, acts
