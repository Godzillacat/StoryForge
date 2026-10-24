"""因果链图的只读投影。

不新增数据、不替作者判断因果讲不讲得通：场景树来自
`chapter_service.build_tree`，「因果问题」只复述逻辑自检已经报过、
作者还没处理的那几条。图的职责是**指出结构上缺了哪一段**。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Agent, AuditIssue, GenerationRun, Project
from app.logic_types import LOGIC_LAYERS
from app.services import chapter_service

_CAUSALITY_LAYER = "causality"
_SEVERITY_ORDER = {"critical": 0, "major": 1, "minor": 2}


def _issue_title(issue: AuditIssue) -> str:
    """`audit_issue` 没有 title 列：解释就是问题本身，原文兜底。

    前端把它放进节点的悬停提示，所以宁可长一点，也不截断成看不懂的半句。
    两者都空时给一个中性词 —— 不编造问题标题。
    """
    return (
        (issue.explanation or "").strip()
        or (issue.quote or "").strip()
        or "逻辑问题"
    )


def _open_causality_issues(
    session: Session, project_id: str
) -> dict[str, list[AuditIssue]]:
    """**一次查询**取全项目未处理的因果问题并按场景分组。

    这是本投影唯一的按问题取的查询：场景再多也只有这一条 SQL，不做 N+1。
    只收 `open` —— 已处理的问题不算断点，也不进 `issues`。
    """
    rows = session.scalars(
        select(AuditIssue).where(
            AuditIssue.project_id == project_id,
            AuditIssue.check_type == "logic",
            AuditIssue.stage == "plan",
            AuditIssue.status == "open",
            AuditIssue.layer == _CAUSALITY_LAYER,
        )
    ).all()
    grouped: dict[str, list[AuditIssue]] = {}
    for row in rows:
        grouped.setdefault(row.scene_id, []).append(row)
    for issues in grouped.values():
        issues.sort(
            key=lambda issue: _SEVERITY_ORDER.get(
                issue.severity, len(_SEVERITY_ORDER)
            )
        )
    return grouped


def _logic_checked(session: Session, project_id: str) -> bool:
    """项目跑过场景卡阶段的逻辑自检没有。

    「跑过就是跑过」：包含作者已经处理掉的问题，也包含因果链之外层面的问题。
    一次成功的自检如果一条问题都没报，`audit_issue` 里什么也没有 —— 那时
    跑过的证据只剩 `generation_run`，所以还要按 agent 的任务类型认一次运行
    （任意状态：失败也是跑过）。为 false 时前端显示「未检查」，**不能**
    显示成通过。
    """
    issue_seen = session.scalars(
        select(AuditIssue.id)
        .where(
            AuditIssue.project_id == project_id,
            AuditIssue.check_type == "logic",
            AuditIssue.stage == "plan",
        )
        .limit(1)
    ).first()
    if issue_seen is not None:
        return True
    # 运行表里 agent_id 是普通字符串（没有外键），只能显式 join 取任务类型。
    run_seen = session.scalars(
        select(GenerationRun.id)
        .join(Agent, Agent.id == GenerationRun.agent_id)
        .where(
            GenerationRun.project_id == project_id,
            Agent.task_type == "logic_check",
        )
        .limit(1)
    ).first()
    return run_seen is not None


def _breaks(scene: dict, issues: list[AuditIssue]) -> list[str]:
    """结构断点：缺目标、缺转折各最多一条，因果问题最多一条。"""
    breaks: list[str] = []
    if not (scene.get("goal") or "").strip():
        breaks.append("missing_goal")
    if not (scene.get("turn") or "").strip():
        breaks.append("missing_turn")
    if issues:
        breaks.append("causality_issue")
    return breaks


def build_map(session: Session, project_id: str) -> dict:
    """把项目投影成「卷 → 章 → 场景」的因果链。项目不存在抛 ValueError。"""
    if session.get(Project, project_id) is None:
        raise ValueError(f"项目不存在：{project_id}")

    issues_by_scene = _open_causality_issues(session, project_id)
    tree = chapter_service.build_tree(session, project_id)

    chapters = []
    scene_total = 0
    break_total = 0
    for volume in tree:
        # 有效锁定向下继承。按章缓存一次判定：同一章下的场景不再重复算，
        # 也不需要顺着 scene → chapter → volume 逐场回库查（那是 N+1）。
        volume_locked = bool(volume.get("locked"))
        for chapter in volume["chapters"]:
            chapter_locked = volume_locked or bool(chapter.get("locked"))
            scenes = []
            for scene in chapter["scenes"]:
                issues = issues_by_scene.get(scene["id"], [])
                breaks = _breaks(scene, issues)
                scene_total += 1
                break_total += len(breaks)
                scenes.append(
                    {
                        "id": scene["id"],
                        "seq": scene["seq"],
                        "label": f"场景{scene['seq'] + 1}",
                        "goal": scene["goal"],
                        "turn": scene["turn"],
                        "status": scene["status"],
                        "locked": chapter_locked or bool(scene.get("locked")),
                        "breaks": breaks,
                        "issues": [
                            {
                                "id": issue.id,
                                "layer": issue.layer,
                                "layer_label": LOGIC_LAYERS.get(
                                    issue.layer, issue.layer
                                ),
                                "severity": issue.severity,
                                "title": _issue_title(issue),
                            }
                            for issue in issues
                        ],
                    }
                )
            chapters.append(
                {
                    "id": chapter["id"],
                    "label": f"第{chapter['seq'] + 1}章 {chapter['title']}",
                    "volume_label": volume["name"],
                    "scenes": scenes,
                }
            )

    return {
        "chapters": chapters,
        "totals": {
            "scenes": scene_total,
            "breaks": break_total,
            "chapters": len(chapters),
        },
        "logic_checked": _logic_checked(session, project_id),
    }
