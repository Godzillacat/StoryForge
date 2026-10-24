"""性格漂移：人物在章上的手记状态（写入）与整本投影（只读）。

不调用模型、也不判断「这个变化合不合理」—— 那是逻辑自检的事。服务只负责两件：
把「某章、某人、当时的状态」按 `(chapter_id, entry_id)` 唯一地存好，以及按阅读
顺序投影成「每人一行、按章排列」的格子。

变化判定是纯比较：`changed` 与**该人物上一条记录**比（不是与上一章比），首条
恒 `false` —— 没有上一状态可对比。没记录的章不进 `cells`，前端按 `chapters`
对齐后留白；「没记录」与「没变化」是两件事，不能混成 0。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chapter, CharacterState, Project, SettingEntry, Volume
from app.services import chapter_service
from app.text_stats import count_words

NOTE_LIMIT = 500

_REASON_NO_CHARACTERS = "还没有人物"
_REASON_NO_STATES = "还没有状态记录"


def _chapter_project(session: Session, chapter_id: str) -> str | None:
    """章所属项目；章不存在（或卷已损坏）时返回 None，由调用方翻成 404。"""
    return session.scalars(
        select(Volume.project_id)
        .join(Chapter, Chapter.volume_id == Volume.id)
        .where(Chapter.id == chapter_id)
    ).first()


def _chapter_list(session: Session, project_id: str) -> list[dict]:
    """全项目章列表，按阅读顺序（卷序 → 章序）。

    `chapters` 与有没有记录无关：它的职责是给前端对齐列，缺格才留得出来。
    """
    tree = chapter_service.build_tree(session, project_id)
    return [
        {
            "id": chapter["id"],
            "label": f"第{chapter['seq'] + 1}章 {chapter['title']}".strip(),
        }
        for volume in tree
        for chapter in volume["chapters"]
    ]


def _character_entries(session: Session, project_id: str) -> list[SettingEntry]:
    """项目里的人物条目，按创建顺序 —— 人物行的顺序因此在两次读之间稳定。"""
    return list(
        session.scalars(
            select(SettingEntry)
            .where(
                SettingEntry.project_id == project_id,
                SettingEntry.type == "character",
            )
            .order_by(SettingEntry.created_at, SettingEntry.id)
        )
    )


def _project_states(session: Session, project_id: str) -> dict[str, list[CharacterState]]:
    """**一次查询**取全项目状态行并按人物分组。

    连卷过滤项目而不是只按 `entry_id`：作者库若被手工改过，也不会把别的项目的
    章状态混进来。场景 / 章再多也只有这一条 SQL，不做 N+1。
    """
    rows = session.scalars(
        select(CharacterState)
        .join(Chapter, Chapter.id == CharacterState.chapter_id)
        .join(Volume, Volume.id == Chapter.volume_id)
        .where(Volume.project_id == project_id)
    ).all()
    grouped: dict[str, list[CharacterState]] = {}
    for row in rows:
        grouped.setdefault(row.entry_id, []).append(row)
    return grouped


def get_drift(session: Session, project_id: str) -> dict:
    """项目 → 性格漂移的只读投影。项目不存在抛 ValueError（路由翻成 404）。"""
    if session.get(Project, project_id) is None:
        raise ValueError(f"项目不存在：{project_id}")

    characters = _character_entries(session, project_id)
    chapters = _chapter_list(session, project_id)
    order = {chapter["id"]: index for index, chapter in enumerate(chapters)}
    labels = {chapter["id"]: chapter["label"] for chapter in chapters}
    states_by_entry = _project_states(session, project_id)

    rows: list[dict] = []
    change_total = 0
    sparse = 0
    for entry in characters:
        states = [
            state
            for state in states_by_entry.get(entry.id, [])
            if state.chapter_id in order
        ]
        if not states:
            # 只列有记录的人物：没记过的人不该占一行空白。
            continue
        states.sort(key=lambda state: order[state.chapter_id])

        cells: list[dict] = []
        previous: str | None = None
        for state in states:
            changed = previous is not None and state.note != previous
            cells.append(
                {
                    "chapter_id": state.chapter_id,
                    "label": labels[state.chapter_id],
                    "note": state.note,
                    "changed": changed,
                }
            )
            previous = state.note

        changes = sum(1 for cell in cells if cell["changed"])
        change_total += changes
        if len(cells) == 1:
            # 只有一条记录的人物看不出漂移 —— 顶部汇总要能把它点出来。
            sparse += 1
        rows.append(
            {
                "entry_id": entry.id,
                "name": entry.name,
                "cells": cells,
                "changes": changes,
                "recorded": len(cells),
            }
        )

    if not characters:
        reason = _REASON_NO_CHARACTERS
    elif not rows:
        reason = _REASON_NO_STATES
    else:
        reason = ""

    return {
        "characters": rows,
        "chapters": chapters,
        "totals": {
            "characters": len(rows),
            "changes": change_total,
            "sparse": sparse,
        },
        "reason": reason,
    }


def _state_out(state: CharacterState) -> dict:
    return {
        "chapter_id": state.chapter_id,
        "entry_id": state.entry_id,
        "note": state.note,
        "created_at": state.created_at.isoformat(),
        "updated_at": state.updated_at.isoformat(),
    }


def put_state(session: Session, chapter_id: str, entry_id: str, note: str) -> dict:
    """写入一条手记状态；同章同人重复写是 upsert（更新 `updated_at`）。"""
    project_id = _chapter_project(session, chapter_id)
    if project_id is None:
        raise ValueError(f"章不存在：{chapter_id}")

    entry = session.get(SettingEntry, entry_id)
    # 跨项目的条目与不存在一样，都是 404：作者看到「人物不存在」即可，
    # 不必知道那个 id 在别的项目里真实存在。
    if entry is None or entry.project_id != project_id:
        raise ValueError(f"人物不存在：{entry_id}")
    if entry.type != "character":
        raise ValueError("只能记录人物的状态")

    cleaned = (note or "").strip()
    if not cleaned:
        raise ValueError("状态不能为空")
    if count_words(cleaned) > NOTE_LIMIT:
        raise ValueError(f"状态不能超过 {NOTE_LIMIT} 字")

    state = session.scalars(
        select(CharacterState).where(
            CharacterState.chapter_id == chapter_id,
            CharacterState.entry_id == entry_id,
        )
    ).first()
    if state is None:
        state = CharacterState(chapter_id=chapter_id, entry_id=entry_id, note=cleaned)
        session.add(state)
    else:
        state.note = cleaned
    session.commit()
    return _state_out(state)


def delete_state(session: Session, chapter_id: str, entry_id: str) -> None:
    """删除一条记录；没有就是 404（「没有这条记录」），不是静默成功。"""
    state = session.scalars(
        select(CharacterState).where(
            CharacterState.chapter_id == chapter_id,
            CharacterState.entry_id == entry_id,
        )
    ).first()
    if state is None:
        raise ValueError(f"没有这条记录：{chapter_id}/{entry_id}")
    session.delete(state)
    session.commit()
