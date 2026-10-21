"""状态与伏笔回写：从已采纳正文提取建议，作者确认后才落库。

建议不落库、不自动应用；apply 只改作者勾选的三类目标（章节摘要、
人物当前状态、伏笔实际回收）。名称匹配一律精确，匹配不到只给警告。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Chapter, Foreshadow, Scene, SettingEntry
from app.services import agent_service, foreshadow_service, text_service, world_service
from app.services.runtime_service import RuntimeService


def _scene(session: Session, scene_id: str) -> Scene:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise ValueError(f"场景不存在：{scene_id}")
    return scene


def _character_index(entries: list[SettingEntry]) -> dict[str, list[SettingEntry]]:
    index: dict[str, list[SettingEntry]] = {}
    for entry in entries:
        forms = [entry.name] + [alias.strip() for alias in (entry.aliases_json or []) if alias.strip()]
        for form in forms:
            index.setdefault(form, []).append(entry)
    return index


def _resolve_characters(
    entries: list[SettingEntry], updates: Any, warnings: list[str]
) -> list[dict]:
    if not isinstance(updates, list):
        return []
    index = _character_index(entries)
    result: list[dict] = []
    seen: set[str] = set()
    for item in updates:
        if not isinstance(item, dict):
            continue
        name = str(item.get("character") or "").strip()
        state = str(item.get("current_state") or "").strip()
        if not name or not state:
            continue
        matches = index.get(name, [])
        if len(matches) != 1:
            warnings.append(
                "人物名称匹配失败或存在歧义："
                f"「{name}」，未写入建议。"
            )
            continue
        entry = matches[0]
        if entry.id in seen:
            continue
        seen.add(entry.id)
        result.append(
            {
                "entry_id": entry.id,
                "name": entry.name,
                "current_state": state,
                "evidence": str(item.get("evidence") or "").strip(),
            }
        )
    return result


def _resolve_foreshadows(
    session: Session, project_id: str, pays: Any, warnings: list[str]
) -> list[dict]:
    if not isinstance(pays, list):
        return []
    result: list[dict] = []
    seen: set[str] = set()
    for item in pays:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        row = foreshadow_service.find_by_name(session, project_id, name)
        if row is None:
            warnings.append(f"伏笔名称匹配失败：「{name}」，未写入建议。")
            continue
        if row.id in seen:
            continue
        seen.add(row.id)
        result.append(
            {
                "foreshadow_id": row.id,
                "name": row.name,
                "evidence": str(item.get("evidence") or "").strip(),
            }
        )
    return result


def _normalize(parsed: Any, entries: list[SettingEntry], session: Session, project_id: str):
    if not isinstance(parsed, dict):
        return None
    warnings: list[str] = []
    summary = str(parsed.get("chapter_summary") or "").strip()
    characters = _resolve_characters(entries, parsed.get("character_updates"), warnings)
    foreshadows = _resolve_foreshadows(
        session, project_id, parsed.get("foreshadow_pays"), warnings
    )
    raw_questions = parsed.get("open_questions")
    questions = (
        [
            str(question).strip()
            for question in raw_questions
            if isinstance(question, str) and str(question).strip()
        ]
        if isinstance(raw_questions, list)
        else []
    )
    return {
        "chapter_summary": summary,
        "character_updates": characters,
        "foreshadow_pays": foreshadows,
        "open_questions": questions,
        "warnings": warnings,
    }


def suggest(session: Session, scene_id: str) -> dict:
    scene = _scene(session, scene_id)
    if not (scene.body or "").strip():
        raise ValueError("还没有已采纳正文，无法生成回写建议")
    project, extra = text_service.scene_extra(session, scene)
    entries = world_service.list_entries(session, project.id, type="character")

    agent = agent_service.find_by_task_type(session, "writeback")
    if agent is None:
        return {
            "run_id": None,
            "llm_status": "skipped",
            "warning": "找不到回写助手，请检查智能体工作室。",
            "chapter_summary": "",
            "character_updates": [],
            "foreshadow_pays": [],
            "open_questions": [],
            "warnings": [],
        }

    try:
        run, result = RuntimeService(session).execute(
            project.id, agent.id, extra, allow_missing=True
        )
    except ValueError as exc:
        return {
            "run_id": None,
            "llm_status": "skipped",
            "warning": f"回写建议已跳过：{exc}",
            "chapter_summary": "",
            "character_updates": [],
            "foreshadow_pays": [],
            "open_questions": [],
            "warnings": [],
        }
    except Exception as exc:  # noqa: BLE001
        message = str(exc).strip() or exc.__class__.__name__
        return {
            "run_id": None,
            "llm_status": "error",
            "warning": f"回写建议失败：{message}",
            "chapter_summary": "",
            "character_updates": [],
            "foreshadow_pays": [],
            "open_questions": [],
            "warnings": [],
        }

    if result.status != "ok":
        message = (result.error or {}).get("message") or "模型调用失败"
        return {
            "run_id": run.id,
            "llm_status": "error",
            "warning": f"回写建议失败：{message}",
            "chapter_summary": "",
            "character_updates": [],
            "foreshadow_pays": [],
            "open_questions": [],
            "warnings": [],
        }

    normalized = _normalize(result.parsed, entries, session, project.id)
    if normalized is None:
        return {
            "run_id": run.id,
            "llm_status": "unstructured",
            "warning": "回写建议未返回结构化结果，本次没有可用建议。",
            "chapter_summary": "",
            "character_updates": [],
            "foreshadow_pays": [],
            "open_questions": [],
            "warnings": [],
        }

    return {"run_id": run.id, "llm_status": "ok", "warning": "", **normalized}


def apply(session: Session, scene_id: str, payload: dict) -> dict:
    scene = _scene(session, scene_id)
    project, _extra = text_service.scene_extra(session, scene)
    chapter = session.get(Chapter, scene.chapter_id)
    if chapter is None:
        raise ValueError("场景的章节结构已损坏")

    summary = payload.get("chapter_summary")
    if summary is not None:
        chapter.summary = str(summary).strip()

    applied_characters: list[dict] = []
    for update in payload.get("character_updates") or []:
        entry_id = str(update.get("entry_id") or "").strip()
        state = str(update.get("current_state") or "").strip()
        if not entry_id or not state:
            raise ValueError("人物状态更新缺少条目或状态")
        entry = session.get(SettingEntry, entry_id)
        if entry is None:
            raise ValueError(f"人物不存在：{entry_id}")
        if entry.project_id != project.id:
            raise ValueError(f"人物不属于这个项目：{entry_id}")
        if entry.type != "character":
            raise ValueError(f"不是人物条目：{entry_id}")
        entry.current_state = state
        applied_characters.append({"entry_id": entry.id, "name": entry.name, "current_state": state})

    applied_foreshadows: list[dict] = []
    for item in payload.get("foreshadow_pays") or []:
        foreshadow_id = str(item.get("foreshadow_id") or "").strip()
        if not foreshadow_id:
            continue
        row = session.get(Foreshadow, foreshadow_id)
        if row is None:
            raise ValueError(f"伏笔不存在：{foreshadow_id}")
        if row.project_id != project.id:
            raise ValueError(f"伏笔不属于这个项目：{foreshadow_id}")
        row.actual_pay_scene_id = scene.id
        applied_foreshadows.append(
            {"foreshadow_id": row.id, "name": row.name, "actual_pay_scene_id": scene.id}
        )

    session.commit()
    return {
        "chapter_summary": chapter.summary,
        "character_updates": applied_characters,
        "foreshadow_pays": applied_foreshadows,
    }
