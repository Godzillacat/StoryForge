from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api._serializers import _run_out
from app.api.schemas import EntryCreate, EntryUpdate, RelationCreate
from app.db.session import get_session
from app.services import agent_service, world_service
from app.services.runtime_service import RuntimeService
from app.world_types import (
    CHARACTER_FIELDS,
    ENTRY_TYPES,
    HARDNESS_LEVELS,
    normalize_hardness,
    normalize_type,
)

router = APIRouter(prefix="/api", tags=["world"])


@router.get("/entry-types")
def list_entry_types() -> dict:
    """类型清单的唯一真相在 app/world_types.py，这里只做投影 ——
    前端不必再硬编一份，否则又会出现两份清单互相不一致的老问题。"""
    return {
        "types": [{"key": k, "label": v} for k, v in ENTRY_TYPES.items()],
        "hardness": [{"key": k, "label": v} for k, v in HARDNESS_LEVELS.items()],
        "character_fields": [
            {"key": key, "label": label, "multiline": multiline}
            for key, (label, multiline) in CHARACTER_FIELDS.items()
        ],
    }


def _normalized_candidates(entries: list) -> list[dict]:
    """把候选里的类型与硬度归一到英文键再交给前端。

    模型看到的是契约块里的**中文值**（那是唯一能合法写进契约的东西），
    所以它返回的是「规则体系」而不是 rule。落库时服务层会归一化，但界面
    拿标签去匹配英文键的下拉会落空：类型显示成第一个选项，规则类的硬度
    控件也不出现。在边界上归一一次，前端就不必再抄一遍映射 —— 而且这里
    的映射是纯逻辑，能被 pytest 覆盖。
    """
    out: list[dict] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        normalized = dict(item)
        try:
            normalized["type"] = normalize_type(str(item.get("type", "")))
        except ValueError:
            # 归一不了就原样留着：作者在表单里看得见、改得掉，采纳时才报
            # 可读错误 —— 不因为一条怪类型让整批候选拿不到。
            pass
        normalized["hardness"] = normalize_hardness(item.get("hardness"))
        out.append(normalized)
    return out


def _reason(result) -> str | None:
    """未结构化时给作者一句**能照做**的话。

    契约失败有现成原因，直接用。但另外两种失败只有运行记录里的技术错误：
    - `template` 是上游还没做（提示词要的槽位取不到值），作者该去补前置；
    - 其余（网络、超时、鉴权）是调用本身出了问题。
    两者都不该被界面显示成「模型没按契约返回」—— 那可能是句假话，
    而且作者照它排查会找到错的方向。
    """
    if result.structured:
        return None
    if result.parse_error:
        return result.parse_error
    error = result.error or {}
    if error.get("kind") == "template":
        # 把运行时给出的缺失变量名附上：template 失败不只发生在「上游没做」，
        # 也发生在作者自己在工作室把提示词改坏时 —— 那种情况下上面这句指引是错的，
        # 而变量名能让作者分辨自己是哪一种。
        return (
            "这个智能体要吃灵感解析卡与故事圣经：先去「灵感与解析」跑一次解析，"
            "再到「架构推荐」采纳一套结构，然后回来生成设定。"
            f"（运行记录里说缺的是：{error.get('message') or '未知变量'}）"
        )
    return error.get("message") or "这次运行没有得到可用的返回"


@router.post("/projects/{project_id}/entries/suggest")
def suggest_entries(project_id: str, session: Session = Depends(get_session)) -> dict:
    """跑一次世界观构建师，返回候选供作者逐条审。

    候选只落在运行记录里，不写 setting_entry —— 只有作者采纳才写（D-04）。
    """
    builder = agent_service.find_by_task_type(session, "worldbuilding")
    if builder is None:
        raise HTTPException(status_code=500, detail="找不到世界观构建师，请重新预置阵容")

    service = RuntimeService(session)
    try:
        run, result = service.execute(project_id, builder.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    parsed = result.parsed or {}
    return {
        "run": _run_out(run),
        "entries": _normalized_candidates(parsed.get("entries", [])) if result.structured else [],
        # `.get(key, [])` 的默认值只在**缺键**时生效；模型把可选的 open_questions
        # 写成显式 null 会原样返回 None，前端读 .length 会抛错。故在边界再兜一次。
        "open_questions": (parsed.get("open_questions") or []) if result.structured else [],
        "structured": result.structured,
        "parse_error": _reason(result),
        "raw_text": result.raw_output,
    }


def _entry_out(entry) -> dict:
    return {
        "id": entry.id,
        "project_id": entry.project_id,
        "type": entry.type,
        "name": entry.name,
        "aliases": entry.aliases_json,
        "tags": entry.tags_json,
        "summary": entry.summary,
        "description": entry.description,
        "hardness": entry.hardness,
        "source_run_id": entry.source_run_id,
        "appearance": entry.appearance,
        "personality": entry.personality,
        "desire": entry.desire,
        "fear": entry.fear,
        "arc_type": entry.arc_type,
        "abilities": entry.abilities,
        "speech_style": entry.speech_style,
        "current_state": entry.current_state,
        "created_at": entry.created_at.isoformat(),
    }


def _entry_fields(payload: EntryCreate | EntryUpdate) -> dict:
    """只做「未传的字段别覆盖」这一件事；领域名到列名的映射在服务层内部。"""
    return payload.model_dump(exclude_unset=True)


@router.get("/projects/{project_id}/entries")
def list_entries(
    project_id: str,
    type: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[dict]:
    try:
        entries = world_service.list_entries(session, project_id, type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [_entry_out(e) for e in entries]


@router.post("/projects/{project_id}/entries", status_code=201)
def create_entry(
    project_id: str, payload: EntryCreate, session: Session = Depends(get_session)
) -> dict:
    try:
        entry = world_service.create_entry(session, project_id, **_entry_fields(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _entry_out(entry)


@router.patch("/entries/{entry_id}")
def update_entry(
    entry_id: str, payload: EntryUpdate, session: Session = Depends(get_session)
) -> dict:
    try:
        entry = world_service.update_entry(session, entry_id, **_entry_fields(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _entry_out(entry)


@router.delete("/entries/{entry_id}", status_code=204)
def delete_entry(entry_id: str, session: Session = Depends(get_session)) -> None:
    try:
        world_service.delete_entry(session, entry_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _relation_out(relation) -> dict:
    return {
        "id": relation.id,
        "project_id": relation.project_id,
        "from_id": relation.from_id,
        "to_id": relation.to_id,
        "kind": relation.kind,
        "note": relation.note,
    }


@router.get("/projects/{project_id}/relations")
def list_relations(project_id: str, session: Session = Depends(get_session)) -> list[dict]:
    return [_relation_out(r) for r in world_service.list_relations(session, project_id)]


@router.post("/projects/{project_id}/relations", status_code=201)
def create_relation(
    project_id: str, payload: RelationCreate, session: Session = Depends(get_session)
) -> dict:
    try:
        relation = world_service.create_relation(session, project_id, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _relation_out(relation)


@router.delete("/relations/{relation_id}", status_code=204)
def delete_relation(relation_id: str, session: Session = Depends(get_session)) -> None:
    try:
        world_service.delete_relation(session, relation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/projects/{project_id}/terms")
def list_terms(project_id: str, session: Session = Depends(get_session)) -> list[dict]:
    return world_service.list_terms(session, project_id)
