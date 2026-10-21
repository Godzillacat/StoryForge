"""一致性审计的业务编排：规则层 + LLM 层 + 问题生命周期。

规则层永远先跑，LLM 失败只降级为警告 —— 没有模型也要让作者看到确定性
问题。问题只记录状态，不自动改稿（D-05）。
"""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit_rules import RuleIssue, run_rule_checks
from app.audit_types import (
    AUDIT_KINDS,
    AUDIT_SEVERITIES,
    AUDIT_SOURCES,
    normalize_kind,
    normalize_resolution,
    normalize_severity,
)
from app.db.models import AuditIssue, Scene, SettingEntry
from app.logic_types import LOGIC_LAYERS
from app.services import agent_service, text_service, world_service
from app.services.runtime_service import RuntimeService

_SEVERITY_ORDER = {"critical": 0, "major": 1, "minor": 2}
_MAX_LLM_ISSUES = 30


def _scene(session: Session, scene_id: str) -> Scene:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise ValueError(f"场景不存在：{scene_id}")
    return scene


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _label(mapping: dict[str, str], key: str) -> str:
    return mapping.get(key, key)


def serialize_issue(session: Session, issue: AuditIssue) -> dict:
    target = (
        session.get(SettingEntry, issue.target_entry_id)
        if issue.target_entry_id
        else None
    )
    return {
        "id": issue.id,
        "source": issue.source,
        "source_label": _label(AUDIT_SOURCES, issue.source),
        "check_type": issue.check_type,
        "kind": issue.kind,
        "kind_label": _label(AUDIT_KINDS, issue.kind),
        "layer": issue.layer,
        "layer_label": LOGIC_LAYERS.get(issue.layer, issue.layer) if issue.layer else None,
        "stage": issue.stage,
        "severity": issue.severity,
        "severity_label": _label(AUDIT_SEVERITIES, issue.severity),
        "quote": issue.quote,
        "rule_ref": issue.rule_ref,
        "explanation": issue.explanation,
        "reader_impact": issue.reader_impact,
        "options": list(issue.options_json or []),
        "target_entry_id": issue.target_entry_id,
        "target_entry_name": target.name if target else None,
        "status": issue.status,
        "resolution": issue.resolution,
        "created_at": issue.created_at.isoformat() if issue.created_at else "",
    }


def sort_issues(issues: list[AuditIssue]) -> list[AuditIssue]:
    # 只按严重度排；同一严重度保留插入顺序（SQLite 按 rowid 返回）。
    # 不拿 created_at 当次级键：内存对象是带时区的，回库读出来是 naïve 的，
    # 混在一起比较会直接抛 TypeError。
    return sorted(
        issues, key=lambda item: _SEVERITY_ORDER.get(item.severity, len(_SEVERITY_ORDER))
    )


def _open_issues(session: Session, scene_id: str) -> list[AuditIssue]:
    rows = session.scalars(
        select(AuditIssue).where(
            AuditIssue.scene_id == scene_id, AuditIssue.status == "open"
        )
    ).all()
    return sort_issues(list(rows))


def _exception_fingerprints(session: Session, scene_id: str) -> set[str]:
    return set(
        session.scalars(
            select(AuditIssue.fingerprint).where(
                AuditIssue.scene_id == scene_id, AuditIssue.status == "exception"
            )
        ).all()
    )


def _supersede_open(session: Session, scene_id: str) -> None:
    rows = session.scalars(
        select(AuditIssue).where(
            AuditIssue.scene_id == scene_id, AuditIssue.status == "open"
        )
    ).all()
    for row in rows:
        row.status = "superseded"


def supersede_scene_issues(session: Session, scene_id: str) -> None:
    """正文整份变化后调用：针对旧文本的问题标为 superseded。

    只处理 stage="text" 的问题（一致性审计与正文阶段的逻辑自检）；
    「场景卡」阶段的逻辑问题审的是场景结构，不受正文替换影响。
    不在这里提交 —— 调用方与自己的写入共用一次事务。
    """
    rows = session.scalars(
        select(AuditIssue).where(
            AuditIssue.scene_id == scene_id,
            AuditIssue.stage == "text",
            AuditIssue.status == "open",
        )
    ).all()
    for row in rows:
        row.status = "superseded"


def _insert_issues(
    session: Session,
    *,
    project_id: str,
    scene_id: str,
    issues: list[RuleIssue],
    source: str,
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
            source=source,
            kind=issue.kind,
            severity=issue.severity,
            quote=issue.quote,
            rule_ref=issue.rule_ref,
            explanation=issue.explanation,
            reader_impact=issue.reader_impact,
            options_json=list(issue.options),
            target_entry_id=issue.target_entry_id,
            fingerprint=fingerprint,
        )
        session.add(row)
        inserted.append(row)
    session.commit()
    return inserted, suppressed


def _match_target(rule_ref: str, entries: list[SettingEntry]) -> str | None:
    """按名字或别名精确匹配；多个命中不猜。"""
    hits = [
        entry
        for entry in entries
        if entry.name == rule_ref or rule_ref in (entry.aliases_json or [])
    ]
    return hits[0].id if len(hits) == 1 else None


def _normalize_llm_issues(
    parsed: Any, entries: list[SettingEntry]
) -> list[RuleIssue] | None:
    """把模型产出归一成问题对象；结构不对返回 None（视为未结构化）。

    空 quote / 空 explanation 的问题直接丢弃 —— 说不清是哪一句、为什么错的
    问题，交给作者只会增加噪声。
    """
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
        kind = normalize_kind(item.get("kind"))
        severity = normalize_severity(item.get("severity"))
        rule_ref = str(item.get("rule_ref") or "").strip()
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
        identity = _sha1(quote) if quote else _sha1(explanation)
        issues.append(
            RuleIssue(
                kind=kind,
                severity=severity,
                quote=quote,
                rule_ref=rule_ref,
                explanation=explanation,
                reader_impact=str(item.get("reader_impact") or "").strip(),
                options=options,
                fingerprint=f"llm:{kind}:{rule_ref}:{identity}",
                target_entry_id=_match_target(rule_ref, entries) if rule_ref else None,
            )
        )

    issues.sort(key=lambda issue: _SEVERITY_ORDER.get(issue.severity, len(_SEVERITY_ORDER)))
    return issues[:_MAX_LLM_ISSUES]


def _run_llm(
    session: Session,
    *,
    project_id: str,
    extra: dict,
    entries: list[SettingEntry],
) -> tuple[str | None, str, str, list[RuleIssue]]:
    """尝试 LLM 语义审计，返回 (run_id, llm_status, warning, 归一化后的问题)。"""
    agent = agent_service.find_by_task_type(session, "continuity")
    if agent is None:
        return None, "skipped", "找不到审校智能体，本次只跑了规则层检查。", []

    try:
        run, result = RuntimeService(session).execute(
            project_id, agent.id, extra, allow_missing=True
        )
    except ValueError as exc:
        return None, "skipped", f"语义审计已跳过：{exc}", []
    except Exception as exc:  # noqa: BLE001
        # 密钥解密失败、服务商返回结构异常等都不该把整次审校打成 500：
        # 规则层结果已经落库，作者至少应该拿到它们和一句可读原因。
        message = str(exc).strip() or exc.__class__.__name__
        return None, "error", f"语义审计失败：{message}", []

    if result.status != "ok":
        message = (result.error or {}).get("message") or "模型调用失败"
        return run.id, "error", f"语义审计失败：{message}", []

    issues = _normalize_llm_issues(result.parsed, entries)
    if issues is None:
        return run.id, "unstructured", "语义审计未返回结构化问题，本次只显示规则层结果。", []

    return run.id, "ok", "", issues


def run_audit(session: Session, scene_id: str) -> dict:
    scene = _scene(session, scene_id)
    body = (scene.body or "").strip()
    if not body:
        raise ValueError("还没有已采纳正文，无法审校")

    project, extra = text_service.scene_extra(session, scene)
    entries = world_service.list_entries(session, project.id)
    exceptions = _exception_fingerprints(session, scene.id)

    # 新一次审校取代旧的 open 问题：作者看到的是「这一次」的结果。
    _supersede_open(session, scene.id)
    session.commit()

    rule_issues = run_rule_checks(
        body,
        world_service.list_terms(session, project.id),
        list(scene.characters_json or []),
        {entry.id: entry for entry in entries},
    )
    _, suppressed = _insert_issues(
        session,
        project_id=project.id,
        scene_id=scene.id,
        issues=rule_issues,
        source="rule",
        run_id=None,
        exceptions=exceptions,
    )

    run_id, llm_status, warning, llm_issues = _run_llm(
        session, project_id=project.id, extra=extra, entries=entries
    )
    if llm_status == "ok":
        _, llm_suppressed = _insert_issues(
            session,
            project_id=project.id,
            scene_id=scene.id,
            issues=llm_issues,
            source="llm",
            run_id=run_id,
            exceptions=exceptions,
        )
        suppressed += llm_suppressed

    return {
        "run_id": run_id,
        "issues": [serialize_issue(session, row) for row in _open_issues(session, scene.id)],
        "suppressed": suppressed,
        "llm_status": llm_status,
        "warning": warning,
    }


def list_audit(session: Session, scene_id: str) -> dict:
    _scene(session, scene_id)
    latest = session.scalars(
        select(AuditIssue.created_at)
        .where(AuditIssue.scene_id == scene_id)
        .order_by(AuditIssue.created_at.desc())
    ).first()
    return {
        "issues": [serialize_issue(session, row) for row in _open_issues(session, scene_id)],
        "last_audited_at": latest.isoformat() if latest else None,
    }


def resolve_issue(session: Session, issue_id: str, resolution: str) -> dict:
    issue = session.get(AuditIssue, issue_id)
    if issue is None:
        raise ValueError("审计问题不存在")
    normalized = normalize_resolution(resolution)
    issue.resolution = normalized
    issue.status = "exception" if normalized == "exception" else "resolved"
    session.commit()
    return serialize_issue(session, issue)
