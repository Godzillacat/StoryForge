"""修订建议：生成（Task 2）。

链路固定：影响面 → 过滤未锁的场景/章 → 组两个临时槽位跑「修订建议师」
→ 归一模型给的对象名与字段 → 只留能落到真实对象上的建议。

**本模块的 `suggest()` 不写库。** 建议只落在 `generation_run.parsed_json`，
等作者逐条勾选后由 `apply()`（Task 3）写入，并在写入前再查一次锁定与现值。

两个必须记住的约束：
- 模型看到的对象名就是这里给它的候选标签，所以映射必须**精确到 id**；
  标签撞车时整条丢弃，绝不「第一个匹配就写」。
- `before` 一律由服务端现取；模型返回的 before 不认（它可能编，也可能
  拿的是候选摘要里被截断的样子）。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Architecture, Chapter, Scene, SettingEntry, Volume
from app.services import agent_service, impact_service
from app.services.runtime_service import RuntimeService

# 单次最多 12 条建议；候选也按同一上限截断。
MAX_SUGGESTIONS = 12
# 候选清单里每个字段值的截断上限。候选最多 12 条，单条约 40 字量级，
# 所以 `impact_candidates` 槽位被注册成「永不裁剪」也放得进预算。
_CANDIDATE_VALUE_LIMIT = 60
_TARGET_VALUE_LIMIT = 200

_FIELD_LABELS = {
    "goal": "目标",
    "conflict": "冲突",
    "turn": "转折",
    "summary": "摘要",
}

# 提示词刻意不许出现英文键名（护栏会拦），所以模型返回的「改哪一项」
# 几乎总是中文标签；不先归一就过白名单，等于把整批建议都丢掉。
# 英文原值也接受，供作者自定义提示词时使用。
_FIELD_ALIASES = {
    "goal": "goal",
    "conflict": "conflict",
    "turn": "turn",
    "summary": "summary",
    "目标": "goal",
    "冲突": "conflict",
    "转折": "turn",
    "摘要": "summary",
}

# 每种对象能改的字段。章只改摘要，场景只改三项 —— 正文一律不碰。
_ALLOWED_FIELDS = {
    "scene": ("goal", "conflict", "turn"),
    "chapter": ("summary",),
}

# 描述「这次改了什么」时从目标对象上取哪些字段。
_TARGET_FIELDS = {
    "architecture": (
        ("logline", "logline"),
        ("theme", "主题句"),
        ("premise", "前提"),
        ("ending_direction", "结局方向"),
    ),
    "entry": (("name", "名称"), ("summary", "概述"), ("description", "说明")),
    "volume": (("name", "卷名"), ("summary", "纲要")),
    "chapter": (("title", "章标题"), ("summary", "摘要"), ("hook", "钩子")),
    "scene": (("goal", "目标"), ("conflict", "冲突"), ("turn", "转折")),
}


def _clip(text: str, limit: int) -> str:
    collapsed = " ".join(str(text or "").split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit] + "……"


def _normalize_field(raw: object) -> str | None:
    """把模型给的「改哪一项」归一成英文键；认不出就返回 None（该条丢弃）。

    除了中文标签与英文原值，也接受「场景的目标」「章的摘要」这类带前缀
    的写法 —— 只按结尾匹配，且必须只命中一个字段，否则算歧义。
    """
    text = str(raw or "").strip()
    if not text:
        return None
    direct = _FIELD_ALIASES.get(text) or _FIELD_ALIASES.get(text.lower())
    if direct is not None:
        return direct
    hits = {
        field
        for alias, field in _FIELD_ALIASES.items()
        if not alias.isascii() and text.endswith(alias)
    }
    if len(hits) == 1:
        return hits.pop()
    return None


def _build_candidates(session: Session, report: dict) -> list[dict]:
    """从影响面里取未锁的场景与章，连同它们的当前字段值。

    同一个对象可能出现在多个分组里（设定条目目标下「出场场景」与「正文提到
    的场景」会重叠），按 (类型, id) 去重，避免自己跟自己撞出歧义。
    """
    candidates: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for group in report.get("groups") or []:
        for item in group.get("items") or []:
            kind = item.get("type")
            allowed = _ALLOWED_FIELDS.get(kind)
            target_id = item.get("id")
            if allowed is None or not target_id or item.get("locked"):
                continue
            key = (kind, target_id)
            if key in seen:
                continue
            seen.add(key)
            values = _current_values(session, kind, target_id)
            if values is None:
                continue
            # 标签直接用影响面里的写法：模型照抄它，我们再用同一份映射回来。
            label = str(item.get("label") or "").strip()
            if not label:
                continue
            candidates.append(
                {
                    "target_type": kind,
                    "target_id": target_id,
                    "target_label": label,
                    "values": values,
                }
            )
    return candidates


def _current_values(session: Session, kind: str, target_id: str) -> dict[str, str] | None:
    if kind == "scene":
        scene = session.get(Scene, target_id)
        if scene is None:
            return None
        return {
            field: str(getattr(scene, field) or "") for field in _ALLOWED_FIELDS[kind]
        }
    chapter = session.get(Chapter, target_id)
    if chapter is None:
        return None
    return {"summary": str(chapter.summary or "")}


def _render_candidates(candidates: list[dict]) -> str:
    lines = []
    for index, candidate in enumerate(candidates, start=1):
        parts = [
            f"{_FIELD_LABELS[field]}：{_clip(value, _CANDIDATE_VALUE_LIMIT) or '（空）'}"
            for field, value in candidate["values"].items()
        ]
        lines.append(f"{index}. {candidate['target_label']}｜" + "；".join(parts))
    return "\n".join(lines)


def _describe_target(session: Session, report: dict) -> str:
    """把「这次改了什么」写成模型能读的一段。

    服务只能拿到改了哪个对象，拿不到作者改前改后的 diff —— 所以给的是
    该对象**现在的样子**，让建议与改动后的设定保持一致。
    """
    target = report["target"]
    kind = target["type"]
    label = target["label"]
    row = None
    if kind == "architecture":
        row = session.scalars(
            select(Architecture).where(
                Architecture.project_id == report["project_id"]
            )
        ).first()
    elif kind == "entry":
        row = session.get(SettingEntry, target["id"])
    elif kind == "volume":
        row = session.get(Volume, target["id"])
    elif kind == "chapter":
        row = session.get(Chapter, target["id"])
    else:
        row = session.get(Scene, target["id"])
        if row is not None:
            chapter = session.get(Chapter, row.chapter_id)
            volume = session.get(Volume, chapter.volume_id) if chapter else None
            if chapter is not None and volume is not None:
                label = impact_service.scene_label(volume, chapter, row.seq)

    lines = [f"本次改动发生在{target['type_label']}「{label}」，它现在的样子是："]
    if row is not None:
        for attr, attr_label in _TARGET_FIELDS[kind]:
            value = getattr(row, attr, None)
            if value:
                lines.append(f"{attr_label}：{_clip(value, _TARGET_VALUE_LIMIT)}")
    return "\n".join(lines)


def _parse_suggestions(
    parsed: dict, candidates: list[dict]
) -> tuple[list[dict], int]:
    """把模型建议映射到真实对象；返回 (建议清单, 丢弃条数)。"""
    by_label: dict[str, list[dict]] = {}
    for candidate in candidates:
        by_label.setdefault(candidate["target_label"], []).append(candidate)

    suggestions: list[dict] = []
    seen: set[tuple[str, str]] = set()
    dropped = 0
    raw_items = parsed.get("suggestions")
    if not isinstance(raw_items, list):
        return [], 0
    for raw in raw_items:
        if len(suggestions) >= MAX_SUGGESTIONS:
            break
        if not isinstance(raw, dict):
            dropped += 1
            continue
        label = str(raw.get("target_label") or "").strip()
        matched = by_label.get(label) or []
        # 对不上（模型编了对象名）或标签撞车（两个对象同名）：都丢弃，绝不猜。
        if len(matched) != 1:
            dropped += 1
            continue
        candidate = matched[0]
        field = _normalize_field(raw.get("field"))
        if field is None or field not in _ALLOWED_FIELDS[candidate["target_type"]]:
            dropped += 1
            continue
        after = str(raw.get("after") or "").strip()
        if not after:
            dropped += 1
            continue
        key = (candidate["target_id"], field)
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        suggestions.append(
            {
                "index": len(suggestions),
                "target_type": candidate["target_type"],
                "target_id": candidate["target_id"],
                "target_label": candidate["target_label"],
                "field": field,
                "field_label": _FIELD_LABELS[field],
                # before 只认服务端现取的值，模型给的 before 一律忽略。
                "before": candidate["values"][field],
                "after": after,
                "reason": str(raw.get("reason") or "").strip(),
            }
        )
    return suggestions, dropped


def _skipped(warning: str) -> dict:
    return {
        "run_id": None,
        "llm_status": "skipped",
        "suggestions": [],
        "dropped": 0,
        "warning": warning,
    }


def _failed(warning: str, run_id: str | None = None) -> dict:
    return {
        "run_id": run_id,
        "llm_status": "error",
        "suggestions": [],
        "dropped": 0,
        "warning": warning,
    }


def suggest(
    session: Session,
    project_id: str,
    target_type: str,
    target_id: str,
    client=None,
) -> dict:
    """为一次上游改动生成待勾选的修订建议。

    返回 `{run_id, llm_status, suggestions, dropped, warning}`；
    任何失败都折成 `llm_status="error"` + 中文原因，不把异常漏成 500。
    """
    try:
        return _suggest(session, project_id, target_type, target_id, client)
    except Exception as exc:  # noqa: BLE001 — 服务层负责把失败变成可读结果
        reason = str(exc).strip() or type(exc).__name__
        return _failed(f"无法生成修订建议：{reason}")


def _suggest(
    session: Session,
    project_id: str,
    target_type: str,
    target_id: str,
    client,
) -> dict:
    report = impact_service.analyze(session, project_id, target_type, target_id)
    candidates = _build_candidates(session, report)[:MAX_SUGGESTIONS]
    if not candidates:
        return _skipped("没有可建议的下游对象：受影响的场景与章都已锁定，或者还没有下游内容")

    agent = agent_service.find_by_task_type(session, "revision_suggest")
    if agent is None:
        return _skipped("还没有可用的「修订建议师」：请先在智能体工作室里启用这个预置")

    run, result = RuntimeService(session, client=client).execute(
        project_id,
        agent.id,
        {
            "impact_target": _describe_target(session, report),
            "impact_candidates": _render_candidates(candidates),
        },
        allow_missing=True,
    )

    if result.status != "ok":
        reason = str((result.error or {}).get("message") or "").strip() or "模型调用失败"
        return _failed(f"修订建议生成失败：{reason}", run_id=run.id)

    if not result.structured or not isinstance(run.parsed_json, dict):
        detail = result.parse_error or "模型没有按输出契约返回"
        return _failed(
            f"模型没有按输出契约返回，本轮没有可用的修订建议（{detail}）",
            run_id=run.id,
        )

    suggestions, dropped = _parse_suggestions(run.parsed_json, candidates)
    warning = (
        f"有 {dropped} 条建议没对上受影响对象或可改字段，已丢弃" if dropped else ""
    )
    return {
        "run_id": run.id,
        "llm_status": "ok",
        "suggestions": suggestions,
        "dropped": dropped,
        "warning": warning,
    }
