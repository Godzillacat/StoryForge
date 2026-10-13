from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Idea


def list_ideas(session: Session, project_id: str) -> list[Idea]:
    return list(session.scalars(select(Idea).where(Idea.project_id == project_id).order_by(Idea.created_at)))


def create_idea(session: Session, project_id: str, raw_text: str, tags: list[str]) -> Idea:
    idea = Idea(project_id=project_id, raw_text=raw_text, tags_json=tags)
    session.add(idea)
    session.commit()
    return idea


def get_idea(session: Session, idea_id: str) -> Idea | None:
    return session.get(Idea, idea_id)


def write_parsed(session: Session, idea_id: str, parsed: dict | None) -> Idea:
    """把解析结果写进 parsed_json。raw_text 永不触碰（D-04）。"""
    idea = session.get(Idea, idea_id)
    if idea is None:
        raise ValueError(f"灵感条目不存在：{idea_id}")
    if parsed is not None:
        idea.parsed_json = parsed
        idea.status = "parsed"
    else:
        idea.status = "parse_failed"
    session.commit()
    return idea


def parsed_as_text(session: Session, idea_id: str) -> str | None:
    idea = session.get(Idea, idea_id)
    if idea is None or not idea.parsed_json:
        return None
    return json.dumps(idea.parsed_json, ensure_ascii=False, indent=2)
