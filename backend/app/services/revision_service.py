"""修订建议：生成（Task 2）与逐条应用（Task 3）。

链路固定：影响面 → 过滤未锁的场景/章 → 组两个临时槽位跑「修订建议师」
→ 归一模型给的对象名与字段 → 只留能落到真实对象上的建议。

**`suggest()` 不写业务表。** 建议只落在 `generation_run.parsed_json`，
等作者逐条勾选后由 `apply()` 写入，并在写入前再查一次锁定与现值。

两个必须记住的约束：
- 模型看到的对象名就是这里给它的候选标签，所以映射必须**精确到 id**；
  标签撞车时整条丢弃，绝不「第一个匹配就写」。
- `before` 一律由服务端现取；模型返回的 before 不认（它可能编，也可能
  拿的是候选摘要里被截断的样子）。
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Architecture,
    Chapter,
    GenerationRun,
    Scene,
    SettingEntry,
    Volume,
)
from app.services import agent_service, change_service, impact_service, lock_service
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

# 模型抄候选清单时常把行首编号一起带回来（`1. 第1卷…`）。剥掉再精确匹配。
_LINE_NUMBER = re.compile(r"^\s*\d+\.\s*")

# 「场景的目标」「的冲突」「字段摘要」这类写法的装饰前缀；剥掉之后必须精确命中。
_FIELD_PREFIXES = ("场景的", "章的", "的", "字段")

# 服务端解析后的建议写回运行记录时用的键。模型的原始输出原样保留，
# 应用时只认这份解析结果 —— 下标与生成时的 before 都钉在这里。
_RESOLVED_KEY = "resolved_suggestions"

# 已经应用过的建议下标。值比对在「建议值 == 现值」时分辨不出「第一次」与
# 「第二次」（写进去的还是同一个值），所以单独留一份服务端标记来保证幂等。
_APPLIED_KEY = "applied_indices"

# 逐条应用时跳过某条的原因。放在一处，界面与测试都对着同一份文案。
_SKIP_BAD_INDEX = "下标无效"
_SKIP_MISSING = "对象已删除"
_SKIP_FOREIGN = "对象不属于这个项目"
_SKIP_LOCKED = "已锁定"
_SKIP_APPLIED = "已应用"
_SKIP_STALE = "现值已变化"
_SKIP_FIELD = "字段不可修改"

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

    只做「剥已知前缀 + 精确匹配」：不再按结尾模糊匹配 ——「目标和冲突」
    不是任何一个字段，猜成冲突比丢弃更危险。
    """
    text = str(raw or "").strip()
    if not text:
        return None
    changed = True
    while changed:
        changed = False
        for prefix in _FIELD_PREFIXES:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                changed = True
                break
    return _FIELD_ALIASES.get(text) or _FIELD_ALIASES.get(text.lower())


def _normalize_label(raw: object) -> str:
    """把模型照抄的候选行还原成对象标签。

    候选清单每行是 `1. 第1卷 第1章 场景1｜目标：…`；模型经常整行抄回来，
    所以先剥行首编号、再取 `｜` 之前的部分。仍然只做精确匹配，不猜。
    """
    text = _LINE_NUMBER.sub("", str(raw or "").strip())
    return text.split("｜", 1)[0].strip()


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


def _pick_candidates(candidates: list[dict]) -> list[dict]:
    """场景与章交替取样，避免章多时把场景饿死。

    影响面里章整组排在场景前面，项目章数 ≥ 上限时按顺序截断会让 12 个候选
    全是章摘要，场景一条也进不了模型。这里先场景后章轮流取，直到上限 ——
    两类对象都进得了模型视野。场景先取是因为场景卡的可改字段更多、建议
    也更具体。
    """
    scenes = [c for c in candidates if c["target_type"] == "scene"]
    chapters = [c for c in candidates if c["target_type"] == "chapter"]
    picked: list[dict] = []
    while len(picked) < MAX_SUGGESTIONS and (scenes or chapters):
        if scenes:
            picked.append(scenes.pop(0))
        if len(picked) >= MAX_SUGGESTIONS:
            break
        if chapters:
            picked.append(chapters.pop(0))
    return picked


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
        if not isinstance(raw, dict):
            dropped += 1
            continue
        label = _normalize_label(raw.get("target_label"))
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
        if len(suggestions) >= MAX_SUGGESTIONS:
            # 超过上限的**有效**建议也计入 dropped：它们既没进 suggestions，
            # 也不该像没发生过一样消失。
            dropped += 1
            continue
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


def _persist_suggestions(
    session: Session, run: GenerationRun, suggestions: list[dict]
) -> None:
    """把服务端解析后的建议写回运行记录，供 `apply()` 按 run_id + 下标取用。

    模型的原始 `suggestions` 原样保留（调试台要看得见它到底返回了什么），
    解析结果另起一个键。不存这份结果的话，`apply()` 只能重新解析一遍，
    而候选会随下游内容变化、下标随之漂移 —— 作者勾的第 2 条可能写到别的
    对象上。`before` 也必须以生成时的值为准，事后重取的现值比不出「已变化」。
    """
    parsed = run.parsed_json if isinstance(run.parsed_json, dict) else {}
    run.parsed_json = {**parsed, _RESOLVED_KEY: suggestions}
    session.commit()


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
    all_candidates = _build_candidates(session, report)
    candidates = _pick_candidates(all_candidates)
    # 没进模型的不是「模型没建议」：数量要如实告诉作者，否则会被读成全覆盖。
    omitted = len(all_candidates) - len(candidates)
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

    # 契约正常时 `suggestions` 必是数组；自定义契约放行别的形状后，
    # 不能让「不是数组」静默变成「这次没有要改的地方」。
    if not isinstance(run.parsed_json.get("suggestions"), list):
        return _failed(
            "模型返回的「修订建议」不是数组，本轮没有可用的修订建议",
            run_id=run.id,
        )

    suggestions, dropped = _parse_suggestions(run.parsed_json, candidates)
    _persist_suggestions(session, run, suggestions)
    warnings: list[str] = []
    if omitted:
        warnings.append(f"另有 {omitted} 个对象未纳入本轮建议")
    if dropped:
        warnings.append(
            f"有 {dropped} 条建议没被采用（对不上对象、字段不可改，或超过 "
            f"{MAX_SUGGESTIONS} 条上限），已丢弃"
        )
    return {
        "run_id": run.id,
        "llm_status": "ok",
        "suggestions": suggestions,
        "dropped": dropped,
        "warning": "；".join(warnings),
    }


def _row_of(session: Session, target_type: str, target_id: str):
    """按建议里的对象类型取回当前行；类型不认识也当「对象已删除」。"""
    if target_type == "scene":
        return session.get(Scene, target_id)
    if target_type == "chapter":
        return session.get(Chapter, target_id)
    return None


def _locked(session: Session, target_type: str, row) -> bool:
    """锁定检查。场景看自己/章/卷三级继承，章看自己与所属卷。"""
    if target_type == "scene":
        return bool(lock_service.effective_scene_lock(session, row)["locked"])
    volume = session.get(Volume, row.volume_id)
    return bool(row.locked or (volume is not None and volume.locked))


def _ownership_issue(
    session: Session, target_type: str, row, project_id: str
) -> str | None:
    """对象归属检查：返回跳过原因，没问题返回 None。

    运行记录里的建议理论上都由本项目的服务端生成，但 `apply()` 只凭 run_id
    取对象；万一同一 id 落在别的项目名下（或被手改过运行记录），写入就会
    越项目。取不到祖先（章/卷已删）时报「对象已删除」，不能把「不存在」
    说成「不属于这个项目」。
    """
    if target_type == "scene":
        chapter = session.get(Chapter, row.chapter_id)
        if chapter is None:
            return _SKIP_MISSING
        volume = session.get(Volume, chapter.volume_id)
    else:
        volume = session.get(Volume, row.volume_id)
    if volume is None:
        return _SKIP_MISSING
    if volume.project_id != project_id:
        return _SKIP_FOREIGN
    return None


def apply(session: Session, project_id: str, run_id: str, accepted: list[int]) -> dict:
    """把作者勾选的建议逐条写进库，并各记一条改动历史。

    只认运行记录里服务端在生成时存下的那份建议：请求只带下标，`after` 与
    `before` 都从库里读回 —— 前端无法决定写入什么内容，也无法把下标指到
    另一条上去。每条落库前再查一次「对象还在、没被锁、现值仍等于 before」，
    任一不成立就跳过并给出原因；能写的与历史记录在同一事务里提交。

    Raises:
        ValueError: 运行记录不存在 / 不属于这个项目 / 不是一次可应用的运行。
    """
    run = session.get(GenerationRun, run_id)
    if run is None:
        raise ValueError(f"运行记录不存在：{run_id}")
    if run.project_id != project_id:
        raise ValueError(f"运行记录不存在于这个项目：{run_id}")

    parsed = run.parsed_json if isinstance(run.parsed_json, dict) else None
    if parsed is None or "suggestions" not in parsed:
        raise ValueError(f"这次运行没有可应用的修订建议：{run_id}")
    suggestions = parsed.get(_RESOLVED_KEY)
    if not isinstance(suggestions, list):
        # 解析结果由服务端写回；缺失说明这条运行不是本链路产出的（或来自旧版本），
        # 重新解析会让下标漂移，所以宁可让作者重新生成一次。
        raise ValueError("这次运行的建议缺少服务端解析结果，请重新生成修订建议")

    applied: list[dict] = []
    skipped: list[dict] = []
    seen: set[int] = set()
    # 已经应用过的下标存在运行记录里：建议值与现值相同（`after == before`）时
    # 值比对分不出第一次与第二次，只能靠这份标记保证幂等。
    applied_indices: set[int] = set()
    for stored in parsed.get(_APPLIED_KEY) or []:
        try:
            applied_indices.add(int(stored))
        except (TypeError, ValueError):
            continue
    for raw_index in accepted or []:
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            skipped.append({"index": raw_index, "reason": _SKIP_BAD_INDEX})
            continue
        # 同一批里重复勾同一个下标（列表传重了）：只算一次，不算错误。
        if index in seen:
            continue
        seen.add(index)
        if index < 0 or index >= len(suggestions):
            skipped.append({"index": index, "reason": _SKIP_BAD_INDEX})
            continue

        item = suggestions[index] if isinstance(suggestions[index], dict) else None
        if item is None:
            skipped.append({"index": index, "reason": _SKIP_BAD_INDEX})
            continue

        # 这一条已经应用过（哪怕对象后来被锁/被删/被改）：先报「已应用」。
        if index in applied_indices:
            skipped.append({"index": index, "reason": _SKIP_APPLIED})
            continue

        target_type = str(item.get("target_type") or "")
        target_id = str(item.get("target_id") or "")
        field = str(item.get("field") or "")
        field_label = str(
            item.get("field_label") or _FIELD_LABELS.get(field) or field
        )
        target_label = str(item.get("target_label") or "")
        before = str(item.get("before") or "")
        after = str(item.get("after") or "")

        # 白名单兜底：运行记录里混进别的字段（被改过、或来自更早的版本）也不写。
        if field not in _ALLOWED_FIELDS.get(target_type, ()):
            skipped.append({"index": index, "reason": _SKIP_FIELD})
            continue

        row = _row_of(session, target_type, target_id)
        if row is None:
            skipped.append({"index": index, "reason": _SKIP_MISSING})
            continue
        issue = _ownership_issue(session, target_type, row, project_id)
        if issue is not None:
            skipped.append({"index": index, "reason": issue})
            continue
        if _locked(session, target_type, row):
            skipped.append({"index": index, "reason": _SKIP_LOCKED})
            continue

        current = str(getattr(row, field, "") or "")
        if current != before:
            # 没有应用标记（旧运行记录）时，值等于建议值也判为「已应用」。
            # 与「作者手改过」区分开 —— 两者都写不得，但作者在意的不是一回事。
            reason = _SKIP_APPLIED if current == after else _SKIP_STALE
            skipped.append({"index": index, "reason": reason})
            continue

        setattr(row, field, after)
        change_service.record(
            session,
            project_id,
            target_type=target_type,
            target_id=target_id,
            target_label=target_label,
            action="update",
            source="ai",
            summary=f"修订建议 · {field_label}",
        )
        applied_indices.add(index)
        applied.append(
            {
                "index": index,
                "target_label": target_label,
                "field": field,
                "field_label": field_label,
            }
        )

    if applied:
        # 与写入同事务提交：失败时标记跟着回滚，不会出现「标记说应用过、库里没有」。
        run.parsed_json = {**parsed, _APPLIED_KEY: sorted(applied_indices)}
    session.commit()
    return {"applied": applied, "skipped": skipped}
