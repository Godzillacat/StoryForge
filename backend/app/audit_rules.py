"""一致性审计的规则层（上位文档 §4.7）。

纯函数、不碰数据库、不碰 HTTP：输入正文与项目态投影，输出问题清单。
规则层永远可离线运行 —— 没有模型也能告诉作者确定性的写错。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

# 切句符：中文句末标点、英文句末标点、省略号与换行。
_SENTENCE_SPLIT = re.compile(r"[。！？!?…\n]+")
# 太短的句子重复出现更像有意叠用（「是。」「好。」），不值得报。
_MIN_REPEAT_LENGTH = 12
_MAJOR_REPEAT_LENGTH = 20


@dataclass(frozen=True)
class RuleIssue:
    kind: str
    severity: str
    quote: str
    rule_ref: str
    explanation: str
    reader_impact: str
    options: list[str] = field(default_factory=list)
    fingerprint: str = ""
    target_entry_id: str | None = None


def _normalize_sentence(sentence: str) -> str:
    return "".join(sentence.split())


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _sentences(body: str) -> list[tuple[str, str]]:
    """返回 (原句, 规范化句) 列表；空句丢弃。"""
    result: list[tuple[str, str]] = []
    for raw in _SENTENCE_SPLIT.split(body or ""):
        quote = raw.strip()
        normalized = _normalize_sentence(quote)
        if normalized:
            result.append((quote, normalized))
    return result


def _repeat_issues(body: str) -> list[RuleIssue]:
    seen: dict[str, int] = {}
    issues: list[RuleIssue] = []
    for quote, normalized in _sentences(body):
        if len(normalized) < _MIN_REPEAT_LENGTH:
            continue
        count = seen.get(normalized, 0) + 1
        seen[normalized] = count
        if count < 2:
            continue
        issues.append(
            RuleIssue(
                kind="repetition",
                severity="major" if len(normalized) >= _MAJOR_REPEAT_LENGTH else "minor",
                quote=quote,
                rule_ref="重复句",
                explanation="同一句在正文中重复出现，读者可能觉得是在复读或凑字。",
                reader_impact="读者会注意到重复，阅读节奏被打断。",
                options=["删掉重复的一句", "改写其中一句", "确认是有意复沓，接受为特例"],
                fingerprint=f"rule:repetition:{_sha1(normalized)}",
            )
        )
    return issues


def _character_forms(terms: list[dict]) -> dict[str, list[dict]]:
    """form -> 使用它的术语行（只留人物）。"""
    forms: dict[str, list[dict]] = {}
    for term in terms:
        if term.get("type") != "character":
            continue
        form = str(term.get("form") or "").strip()
        if not form:
            continue
        forms.setdefault(form, []).append(term)
    return forms


def _alias_issues(body: str, terms: list[dict]) -> list[RuleIssue]:
    issues: list[RuleIssue] = []
    for form, rows in sorted(_character_forms(terms).items()):
        entry_ids = {row["entry_id"] for row in rows}
        if len(entry_ids) <= 1 or form not in body:
            continue
        names = "、".join(dict.fromkeys(row["entry_name"] for row in rows))
        issues.append(
            RuleIssue(
                kind="alias",
                severity="minor",
                quote=form,
                rule_ref=f"「{form}」同时用于：{names}",
                explanation="正文出现这个称呼，但世界观里有多个角色共享它，读者可能分不清指谁。",
                reader_impact="读者需要回头猜测当前说的是哪个人物。",
                options=["换用专属称呼", "改用本名", "确认上下文清楚，接受为特例"],
                fingerprint=f"rule:alias:{form}",
            )
        )
    return issues


def _unmentioned_issues(
    body: str,
    scene_character_ids: list[str],
    entries: dict[str, Any],
) -> list[RuleIssue]:
    issues: list[RuleIssue] = []
    for entry_id in scene_character_ids:
        entry = entries.get(entry_id)
        if entry is None or entry.type != "character":
            continue
        forms = [entry.name] + [
            alias.strip() for alias in (entry.aliases_json or []) if alias.strip()
        ]
        if any(form and form in body for form in forms):
            continue
        issues.append(
            RuleIssue(
                kind="alias",
                severity="minor",
                quote="",
                rule_ref=f"出场人物：{entry.name}",
                explanation="这个人物在场景卡里出场，但正文里找不到他的名字或任何称呼；可能用了代词，请人工确认。",
                reader_impact="读者可能不知道这个人物在场，或把对白归错人。",
                options=["确认是否漏写", "补充称呼或动作", "确认用了代词，接受为特例"],
                fingerprint=f"rule:unmentioned:{entry_id}",
                target_entry_id=entry_id,
            )
        )
    return issues


def run_rule_checks(
    body: str,
    terms: list[dict],
    scene_character_ids: list[str],
    entries: dict[str, Any],
) -> list[RuleIssue]:
    if not (body or "").strip():
        return []
    return [
        *_repeat_issues(body),
        *_alias_issues(body, terms),
        *_unmentioned_issues(body, scene_character_ids, entries),
    ]
