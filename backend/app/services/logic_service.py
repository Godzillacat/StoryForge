"""逻辑自检：五层语义检查，复用审计问题的存储与处理生命周期。

只有 LLM 层，没有确定性规则：五层判断都需要语义理解。没有模型时明确
警告，不假装检查过。
"""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit_rules import RuleIssue
from app.audit_types import normalize_severity
from app.db.models import AuditIssue, Scene
from app.logic_types import normalize_layer, normalize_stage
from app.services import agent_service, text_service
from app.services.audit_service import serialize_issue, sort_issues
from app.services.runtime_service import RuntimeService

_SEVERITY_ORDER = {"critical": 0, "major": 1, "minor": 2}
_MAX_LOGIC_ISSUES = 30


def _scene(session: Session, scene_id: str) -> Scene:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise ValueError(f"场景不存在：{scene_id}")
    return scene


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _level(project) -> str:
    value = project.logic_check_level or "loose"
    return value if value in {"loose", "standard", "strict"} else "loose"


def _exception_fingerprints(session: Session, scene_id: str, stage: str) -> set[str]:
    return set(
        session.scalars(
            select(AuditIssue.fingerprint).where(
                AuditIssue.scene_id == scene_id,
                AuditIssue.check_type == "logic",
                AuditIssue.stage == stage,
                AuditIssue.status == "exception",
            )
        ).all()
    )


def _supersede_open(session: Session, scene_id: str, stage: str) -> None:
    rows = session.scalars(
        select(AuditIssue).where(
            AuditIssue.scene_id == scene_id,
            AuditIssue.check_type == "logic",
            AuditIssue.stage == stage,
            AuditIssue.status == "open",
        )
    ).all()
    for row in rows:
        row.status = "superseded"


def _open_issues(session: Session, scene_id: str, stage: str) -> list[AuditIssue]:
    rows = session.scalars(
        select(AuditIssue).where(
            AuditIssue.scene_id == scene_id,
            AuditIssue.check_type == "logic",
            AuditIssue.stage == stage,
            AuditIssue.status == "open",
        )
    ).all()
    return sort_issues(list(rows))


def _normalize_llm_issues(
    parsed: Any, level: str, stage: str
) -> list[RuleIssue] | None:
    """结构不对返回 None（视为未结构化）；缺 quote / 解释的问题丢弃。"""
    if not isinstance(parsed, dict):
        return None
    raw_issues = parsed.get("issues")
    if not isinstance(raw_issues, list):
        return None

    issues: list[RuleIssue] = []
    for item in raw_issues:
        if not isinstance(item, dict):
            continue
        quote = str(item.get("quote") or "").strip()
        explanation = str(item.get("explanation") or "").strip()
        if not quote or not explanation:
            continue
        layer = normalize_layer(item.get("layer"))
        severity = normalize_severity(item.get("severity"))
        if level == "loose" and severity == "minor":
            continue
        raw_options = item.get("options")
        options = (
            [
                str(option).strip()
                for option in raw_options
                if isinstance(option, str) and str(option).strip()
            ][:3]
            if isinstance(raw_options, list)
            else []
        )
        issues.append(
            RuleIssue(
                # 逻辑问题用 kind 携带层面，落库时转存到 layer 列。
                kind=layer,
                severity=severity,
                quote=quote,
                rule_ref=str(item.get("rule_ref") or "").strip(),
                explanation=explanation,
                reader_impact=str(item.get("reader_impact") or "").strip(),
                options=options,
                fingerprint=f"logic:{stage}:{layer}:{_sha1(f'{quote}|{explanation}')}",
            )
        )

    issues.sort(key=lambda issue: _SEVERITY_ORDER.get(issue.severity, len(_SEVERITY_ORDER)))
    return issues[:_MAX_LOGIC_ISSUES]


def _run_llm(
    session: Session,
    *,
    project_id: str,
    extra: dict,
    level: str,
    stage: str,
) -> tuple[str | None, str, str, list[RuleIssue]]:
    agent = agent_service.find_by_task_type(session, "logic_check")
    if agent is None:
        return None, "skipped", "找不到逻辑审查官，请检查智能体工作室。", []

    try:
        run, result = RuntimeService(session).execute(
            project_id, agent.id, extra, allow_missing=True
        )
    except ValueError as exc:
        return None, "skipped", f"逻辑自检已跳过：{exc}", []
    except Exception as exc:  # noqa: BLE001
        message = str(exc).strip() or exc.__class__.__name__
        return None, "error", f"逻辑自检失败：{message}", []

    if result.status != "ok":
        message = (result.error or {}).get("message") or "模型调用失败"
        return run.id, "error", f"逻辑自检失败：{message}", []

    issues = _normalize_llm_issues(result.parsed, level, stage)
    if issues is None:
        return run.id, "unstructured", "逻辑自检未返回结构化问题，本次没有结果。", []

    return run.id, "ok", "", issues


def _insert_issues(
    session: Session,
    *,
    project_id: str,
    scene_id: str,
    stage: str,
    issues: list[RuleIssue],
    run_id: str | None,
    exceptions: set[str],
) -> tuple[list[AuditIssue], int]:
    inserted: list[AuditIssue] = []
    suppressed = 0
    seen: set[str] = set()
    for issue in issues:
        fingerprint = issue.fingerprint
        if not fingerprint or fingerprint in seen:
            continue
        seen.add(fingerprint)
        if fingerprint in exceptions:
            suppressed += 1
            continue
        row = AuditIssue(
            project_id=project_id,
            scene_id=scene_id,
            run_id=run_id,
            source="llm",
            check_type="logic",
            layer=issue.kind,
            stage=stage,
            kind="other",
            severity=issue.severity,
            quote=issue.quote,
            rule_ref=issue.rule_ref,
            explanation=issue.explanation,
            reader_impact=issue.reader_impact,
            options_json=list(issue.options),
            fingerprint=fingerprint,
        )
        session.add(row)
        inserted.append(row)
    session.commit()
    return inserted, suppressed


def run_logic_check(session: Session, scene_id: str, stage: str) -> dict:
    stage = normalize_stage(stage)
    scene = _scene(session, scene_id)
    body = (scene.body or "").strip()
    if stage == "text" and not body:
        raise ValueError("还没有已采纳正文，无法逻辑自检")

    project, extra = text_service.scene_extra(session, scene)
    extra = dict(extra)
    if stage == "plan":
        extra["skip_scene_text"] = True
    level = _level(project)
    exceptions = _exception_fingerprints(session, scene.id, stage)

    run_id, llm_status, warning, issues = _run_llm(
        session, project_id=project.id, extra=extra, level=level, stage=stage
    )
    suppressed = 0
    if llm_status == "ok":
        # 只有真正拿到新结果才取代旧问题：失败一次不能把作者还没处理的
        # 逻辑问题静默清掉（逻辑自检没有规则层兜底）。
        _supersede_open(session, scene.id, stage)
        session.commit()
        _, suppressed = _insert_issues(
            session,
            project_id=project.id,
            scene_id=scene.id,
            stage=stage,
            issues=issues,
            run_id=run_id,
            exceptions=exceptions,
        )

    return {
        "stage": stage,
        "run_id": run_id,
        "issues": [
            serialize_issue(session, row) for row in _open_issues(session, scene.id, stage)
        ],
        "suppressed": suppressed,
        "llm_status": llm_status,
        "warning": warning,
    }


def list_logic_check(session: Session, scene_id: str, stage: str) -> dict:
    stage = normalize_stage(stage)
    _scene(session, scene_id)
    latest = session.scalars(
        select(AuditIssue.created_at)
        .where(
            AuditIssue.scene_id == scene_id,
            AuditIssue.check_type == "logic",
            AuditIssue.stage == stage,
        )
        .order_by(AuditIssue.created_at.desc())
    ).first()
    return {
        "stage": stage,
        "issues": [
            serialize_issue(session, row) for row in _open_issues(session, scene_id, stage)
        ],
        "last_checked_at": latest.isoformat() if latest else None,
    }
