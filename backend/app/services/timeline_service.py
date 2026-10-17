"""故事内时间线：有序事件、参与者与地点。纯手工维护，不经过模型。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SettingEntry, TimelineEvent


def list_events(session: Session, project_id: str) -> list[TimelineEvent]:
    return list(
        session.scalars(
            select(TimelineEvent)
            .where(TimelineEvent.project_id == project_id)
            .order_by(TimelineEvent.order_index, TimelineEvent.created_at)
        )
    )


def get_event(session: Session, event_id: str) -> TimelineEvent | None:
    return session.get(TimelineEvent, event_id)


def _clean_title(value: str | None) -> str:
    title = (value or "").strip()
    if not title:
        raise ValueError("时间线事件必须有标题")
    return title


def _validated_participants(
    session: Session, project_id: str, values: list[str] | None
) -> list[str]:
    out: list[str] = []
    for entry_id in values or []:
        entry = session.get(SettingEntry, entry_id)
        if entry is None:
            raise ValueError(f"参与者条目不存在：{entry_id}")
        if entry.project_id != project_id:
            raise ValueError(f"参与者条目不属于这个项目：{entry_id}")
        if entry.type != "character":
            raise ValueError(f"「{entry.name}」不是人物，不能作为时间线事件的参与者")
        if entry_id not in out:
            out.append(entry_id)
    return out


def _validated_location(
    session: Session, project_id: str, value: str | None
) -> str | None:
    if not value:
        return None
    entry = session.get(SettingEntry, value)
    if entry is None:
        raise ValueError(f"地点条目不存在：{value}")
    if entry.project_id != project_id:
        raise ValueError(f"地点条目不属于这个项目：{value}")
    return value


def create_event(session: Session, project_id: str, **fields) -> TimelineEvent:
    title = _clean_title(fields.get("title"))
    participants = _validated_participants(session, project_id, fields.get("participants"))
    location_id = _validated_location(session, project_id, fields.get("location_id"))
    last = session.scalars(
        select(TimelineEvent)
        .where(TimelineEvent.project_id == project_id)
        .order_by(TimelineEvent.order_index.desc())
    ).first()
    event = TimelineEvent(
        project_id=project_id,
        title=title,
        story_time=(fields.get("story_time") or "").strip(),
        description=fields.get("description") or "",
        order_index=(last.order_index + 1) if last else 0,
        participants_json=participants,
        location_id=location_id,
    )
    session.add(event)
    session.commit()
    return event


def update_event(session: Session, event_id: str, **fields) -> TimelineEvent:
    event = session.get(TimelineEvent, event_id)
    if event is None:
        raise ValueError(f"时间线事件不存在：{event_id}")
    # 先把每个要给的值算完、验完，再落到对象上 —— 任何一项校验失败时，
    # 对象必须保持原样。边验边改的话，直接调用方捕获异常后若继续提交这个
    # session，会把「title 已改、参与者没改」的半截改动落库；HTTP 路径只是
    # 靠请求结束时 session.close() 的回滚才没暴露这个洞。
    if "title" in fields:
        title = _clean_title(fields.get("title"))
    if "story_time" in fields:
        story_time = (fields.get("story_time") or "").strip()
    if "description" in fields:
        description = fields.get("description") or ""
    if "participants" in fields:
        participants = _validated_participants(
            session, event.project_id, fields.get("participants")
        )
    if "location_id" in fields:
        location_id = _validated_location(
            session, event.project_id, fields.get("location_id")
        )
    # 全部校验通过后才动对象。
    if "title" in fields:
        event.title = title
    if "story_time" in fields:
        event.story_time = story_time
    if "description" in fields:
        event.description = description
    if "participants" in fields:
        event.participants_json = participants
    if "location_id" in fields:
        event.location_id = location_id
    session.commit()
    return event


def move_event(session: Session, event_id: str, direction: str) -> TimelineEvent:
    if direction not in ("up", "down"):
        raise ValueError("移动方向只能是 up 或 down")
    event = session.get(TimelineEvent, event_id)
    if event is None:
        raise ValueError(f"时间线事件不存在：{event_id}")
    ordered = list_events(session, event.project_id)
    index = next(i for i, item in enumerate(ordered) if item.id == event_id)
    target = index - 1 if direction == "up" else index + 1
    if target < 0 or target >= len(ordered):
        return event
    ordered.insert(target, ordered.pop(index))
    # 重排整条链，顺便把历史数据里可能的同序也归并成连续序号。
    for position, item in enumerate(ordered):
        item.order_index = position
    session.commit()
    return event


def delete_event(session: Session, event_id: str) -> None:
    event = session.get(TimelineEvent, event_id)
    if event is None:
        raise ValueError(f"时间线事件不存在：{event_id}")
    session.delete(event)
    session.commit()
