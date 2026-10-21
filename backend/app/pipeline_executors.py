"""管线节点的执行器。

每个执行器两件事：**能不能跑**（check）与**跑一次**（run）。

`run` 一律走 `RuntimeService.execute`，所以模型分路、参数档、费用记账、
`usage_source` 全部自动生效。执行器**只返回摘要与去向**，不写项目结构 ——
唯一例外是灵感解析写回 `idea.parsed_json`，那是派生卡，与单点按钮行为一致，
作者原话一字不动（D-04）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Agent,
    Chapter,
    Idea,
    PipelineRunNode,
    Project,
    SettingEntry,
    Volume,
)
from app.services import agent_service, architecture_service, chapter_plan_service, idea_service
from app.services.runtime_service import RuntimeService


@dataclass(frozen=True)
class NodeOutcome:
    generation_run_id: str | None = None
    summary: dict[str, Any] = field(default_factory=dict)
    message: str = ""


@dataclass(frozen=True)
class Executor:
    label: str
    # 返回阻塞原因（含「去哪补」）；None 表示可以跑
    check: Callable[[Session, Project, PipelineRunNode], str | None]
    run: Callable[[Session, Project, PipelineRunNode], NodeOutcome]


def _resolve_agent(session: Session, node: PipelineRunNode, task_type: str):
    """节点绑定的智能体优先；否则按任务类型取第一个启用的。

    绑定到一个已被停用的智能体时仍然用它 —— 作者明确指定过，停用是暂时
    不想让它出现在默认选择里，不是「不许跑」。
    """
    if node.agent_id:
        agent = session.get(Agent, node.agent_id)
        if agent is not None:
            return agent
    return agent_service.find_by_task_type(session, task_type)


def _no_agent(task_type: str) -> str:
    from app.agents.roster import task_type_label

    return f"找不到「{task_type_label(task_type)}」智能体，请到「智能体工作室」启用一个"


def _execute(
    session: Session,
    project_id: str,
    agent,
    extra: dict | None = None,
    *,
    allow_missing: bool | None = None,
):
    """跑一次模型，并把「渲染失败」当成失败抛出去。

    结构化预置在缺上下文槽位时不会发起调用，`result.status` 仍是 `error`、
    `rendered_prompt` 为空。若执行器照常返回摘要，管线会显示「完成」而实际
    什么都没生成 —— 比直接失败更糟。
    """
    run, result = RuntimeService(session).execute(
        project_id, agent.id, extra, allow_missing=allow_missing
    )
    if result.status == "error":
        message = (result.error or {}).get("message") or "模型调用失败"
        raise ValueError(message)
    return run, result


# ---- 灵感解析 ----

def _check_idea_parse(session, project, node) -> str | None:
    idea = session.scalars(
        select(Idea).where(Idea.project_id == project.id).order_by(Idea.created_at)
    ).first()
    if idea is None:
        return "项目里还没有灵感条目，请先到「灵感与解析」录一段原话"
    return None


def _run_idea_parse(session, project, node) -> NodeOutcome:
    idea = session.scalars(
        select(Idea).where(Idea.project_id == project.id).order_by(Idea.created_at)
    ).first()
    agent = _resolve_agent(session, node, "idea_parse")
    if agent is None:
        raise ValueError(_no_agent("idea_parse"))

    run, result = _execute(session, project.id, agent, {"raw_idea_id": idea.id})
    # 与单点「解析」按钮同一行为：派生卡写回，原话不动。
    idea_service.write_parsed(session, idea.id, result.parsed if result.structured else None)
    parsed = result.parsed or {}
    return NodeOutcome(
        generation_run_id=run.id,
        summary={
            "idea_id": idea.id,
            "structured": result.structured,
            "fields": len([k for k, v in parsed.items() if v and k != "open_questions"]),
            "open_questions": len(parsed.get("open_questions") or []),
            "review_path": "/idea",
        },
    )


# ---- 架构推荐 ----

def _check_architecture(session, project, node) -> str | None:
    parsed = session.scalars(
        select(Idea).where(Idea.project_id == project.id, Idea.parsed_json.is_not(None))
    ).first()
    if parsed is None:
        return "还没有解析过的灵感，请先让「灵感解析」跑一次并在「灵感与解析」确认"
    return None


def _run_architecture(session, project, node) -> NodeOutcome:
    agent = _resolve_agent(session, node, "architecture")
    if agent is None:
        raise ValueError(_no_agent("architecture"))

    run, result = _execute(session, project.id, agent)
    parsed = result.parsed or {}
    bible = parsed.get("story_bible_v0") or {}
    return NodeOutcome(
        generation_run_id=run.id,
        summary={
            "structured": result.structured,
            "options": len(parsed.get("options") or []),
            "has_story_bible": bool(bible),
            # 不写 architecture 表：作者要去「架构推荐」页拍板（D-03）
            "review_path": "/architecture",
        },
    )


# ---- 世界观补全 ----

def _check_worldbuilding(session, project, node) -> str | None:
    arch, _acts = architecture_service.get_architecture(session, project.id)
    if arch is None or not arch.logline:
        return "还没有采纳的故事圣经，请先到「架构推荐」拍板一套方案"
    # 世界观构建师要读解析卡。只查故事圣经不够：作者可能手写了故事圣经
    # 却没跑过灵感解析，那样模型会缺槽位、渲染直接失败。
    parsed = session.scalars(
        select(Idea).where(Idea.project_id == project.id, Idea.parsed_json.is_not(None))
    ).first()
    if parsed is None:
        return "还没有解析过的灵感，请先让「灵感解析」跑一次"
    return None


def _run_worldbuilding(session, project, node) -> NodeOutcome:
    agent = _resolve_agent(session, node, "worldbuilding")
    if agent is None:
        raise ValueError(_no_agent("worldbuilding"))

    run, result = _execute(session, project.id, agent)
    parsed = result.parsed or {}
    entries = parsed.get("entries") or []
    return NodeOutcome(
        generation_run_id=run.id,
        summary={
            "structured": result.structured,
            "candidates": len(entries),
            "open_questions": len(parsed.get("open_questions") or []),
            "review_path": "/world",
        },
    )


# ---- 章纲策划 ----

def _check_chapter_plan(session, project, node) -> str | None:
    _arch, acts = architecture_service.get_architecture(session, project.id)
    if not acts:
        return "还没有幕骨架，请先到「架构推荐」采纳一套方案（幕骨架随故事圣经一起写入）"
    # 章纲策划的预置要读 world_context；设定条目一条都没有时渲染会直接失败。
    # 默认管线把「世界观补全」排在它前面，但那个节点只出候选 —— 作者没去
    # 世界观页采纳，这里就会缺上下文。
    if not session.scalars(
        select(SettingEntry).where(SettingEntry.project_id == project.id)
    ).first():
        return "世界观里还没有任何设定条目，请先跑「世界观补全」并到「世界观」页采纳几条"
    return None


def _acts(session, project_id) -> set[int]:
    _arch, acts = architecture_service.get_architecture(session, project_id)
    return {act.seq for act in acts}


def _run_chapter_plan(session, project, node) -> NodeOutcome:
    agent = _resolve_agent(session, node, "chapter_plan")
    if agent is None:
        raise ValueError(_no_agent("chapter_plan"))

    run, result = _execute(session, project.id, agent)
    volumes, warnings = chapter_plan_service.normalize_chapter_plan(
        result.parsed, _acts(session, project.id)
    )
    return NodeOutcome(
        generation_run_id=run.id,
        summary={
            "structured": result.structured,
            "volumes": len(volumes),
            "chapters": sum(len(v.get("chapters") or []) for v in volumes),
            "warnings": len(warnings),
            "review_path": "/chapters",
        },
    )


# ---- 场景卡 ----

def _first_chapter(session, project_id) -> Chapter | None:
    volume = session.scalars(
        select(Volume).where(Volume.project_id == project_id).order_by(Volume.seq)
    ).first()
    if volume is None:
        return None
    return session.scalars(
        select(Chapter).where(Chapter.volume_id == volume.id).order_by(Chapter.seq)
    ).first()


def _check_scene_plan(session, project, node) -> str | None:
    if _first_chapter(session, project.id) is None:
        return "还没有任何章，请先到「章节设计」排卷章（或用章纲策划）"
    return None


def _run_scene_plan(session, project, node) -> NodeOutcome:
    chapter = _first_chapter(session, project.id)
    agent = _resolve_agent(session, node, "scene_plan")
    if agent is None:
        raise ValueError(_no_agent("scene_plan"))

    # timeline 在空项目里天然为空，而场景策划是结构化预置、默认严格。
    # 与审校同一处理：只给这条路径显式放开，其它预置仍严格报缺变量。
    run, result = _execute(
        session,
        project.id,
        agent,
        {"chapter_id": chapter.id, "volume_id": chapter.volume_id},
        allow_missing=True,
    )
    scenes, warnings = chapter_plan_service.normalize_scene_plan(
        result.parsed, session, project.id
    )
    return NodeOutcome(
        generation_run_id=run.id,
        summary={
            "structured": result.structured,
            "chapter_id": chapter.id,
            "scenes": len(scenes),
            "warnings": len(warnings),
            "review_path": "/chapters",
        },
    )


EXECUTORS: dict[str, Executor] = {
    "idea_parse": Executor("灵感解析", _check_idea_parse, _run_idea_parse),
    "architecture": Executor("架构推荐", _check_architecture, _run_architecture),
    "worldbuilding": Executor("世界观补全", _check_worldbuilding, _run_worldbuilding),
    "chapter_plan": Executor("章纲策划", _check_chapter_plan, _run_chapter_plan),
    "scene_plan": Executor("场景卡", _check_scene_plan, _run_scene_plan),
}


def get_executor(task_type: str) -> Executor | None:
    return EXECUTORS.get(task_type)


def available_node_types() -> list[dict]:
    """可加进管线的节点类型。前端据此渲染「追加节点」的下拉 ——
    不让界面再抄一份任务类型清单。"""
    from app.agents.roster import task_type_label

    return [
        {"task_type": key, "label": task_type_label(key)}
        for key in EXECUTORS
    ]
