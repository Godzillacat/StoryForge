"""设定投放曲线的只读投影。

按卷 → 章 → 场景的阅读顺序把正文扫一遍，统计每章「新出现的设定条目数 /
总提及 / 每千字密度」。不调用模型、不判断投放好坏，也不落库缓存 —— 每次现算。

词表与术语表同一套白名单：条目名 ∪ 别名。一个 form 命中多个条目时按
「名字相等优先，否则最早创建」归属，并把这一处重名计入 `ambiguities`。
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chapter, Project, Scene, SettingEntry, Volume
from app.services import chapter_service
from app.text_stats import count_words


def _clean_form(value) -> str:
    """只接受字符串；trim 后为空的一律当没有这个 form。"""
    if not isinstance(value, str):
        return ""
    return value.strip()


def _entry_forms(entry: SettingEntry) -> list[str]:
    """条目名 + 别名，trim、去空、去重（同名别名不重复算）。

    `aliases_json` 是 JSON 列，历史数据或手工改库可能不是数组、元素也可能不是
    字符串 —— 这类值直接跳过，既不炸，也不把 `3` 当成词。
    """
    forms: list[str] = []
    seen: set[str] = set()
    name = _clean_form(entry.name)
    if name:
        forms.append(name)
        seen.add(name)
    aliases = entry.aliases_json
    if isinstance(aliases, (list, tuple)):
        for raw in aliases:
            form = _clean_form(raw)
            if form and form not in seen:
                forms.append(form)
                seen.add(form)
    return forms


def _wordlist(
    entries: list[SettingEntry],
) -> tuple[dict[str, list[SettingEntry]], dict[str, set[str]], dict[str, SettingEntry]]:
    """构造 form → 归属条目、条目 → 自己的 form。

    条目按 `created_at` 排序传入，「最早创建」就是同一 form 的候选列表里的第一个；
    名字恰好等于 form 的条目优先于它（即便创建得更晚）。
    """
    owners: dict[str, list[SettingEntry]] = {}
    forms_by_entry: dict[str, set[str]] = {}
    for entry in entries:
        forms = _entry_forms(entry)
        forms_by_entry[entry.id] = set(forms)
        for form in forms:
            owners.setdefault(form, []).append(entry)
    targets = {
        form: next(
            (entry for entry in candidates if _clean_form(entry.name) == form),
            candidates[0],
        )
        for form, candidates in owners.items()
    }
    return owners, forms_by_entry, targets


def _chapter_bodies(session: Session, project_id: str) -> dict[str, str | None]:
    """一次查询取全项目场景正文，按 scene_id 查 —— 避免逐场景回库（N+1）。"""
    rows = session.execute(
        select(Scene.id, Scene.body)
        .join(Chapter, Chapter.id == Scene.chapter_id)
        .join(Volume, Volume.id == Chapter.volume_id)
        .where(Volume.project_id == project_id)
    ).all()
    return {scene_id: body for scene_id, body in rows}


def _compile_pattern(owners: dict[str, list[SettingEntry]]) -> re.Pattern[str] | None:
    """把全部 form 拼成**一个**正则，长度降序 —— 长 form 先试，短 form 不会截胡。

    每个场景只扫一遍正文；逐 form 做 `in` 会退化成 O(场景 × 词条)。
    转义是必须的：form 里出现 `.` `(` `|` 之类的元字符时不能当语法解释。
    """
    if not owners:
        return None
    alternatives = "|".join(
        re.escape(form) for form in sorted(owners, key=lambda form: (-len(form), form))
    )
    return re.compile(alternatives)


def _density(mentions: int, chars: int) -> float:
    """每千字提及数，保留一位小数；没有正文时是 0 而不是除零。"""
    if chars <= 0:
        return 0.0
    return round(mentions * 1000 / chars, 1)


def build_load(session: Session, project_id: str) -> dict:
    """项目 → 「按章投放」只读投影。项目不存在抛 ValueError（路由翻成 404）。"""
    if session.get(Project, project_id) is None:
        raise ValueError(f"项目不存在：{project_id}")

    entries = list(
        session.scalars(
            select(SettingEntry)
            .where(SettingEntry.project_id == project_id)
            .order_by(SettingEntry.created_at, SettingEntry.id)
        )
    )
    owners, forms_by_entry, targets = _wordlist(entries)
    # 没有名字也没有别名的条目无法在正文里被找到 —— 它们不进词表、不参与扫描，
    # 但仍是「条目」：计入 entries / never_seen，否则「从未出现」会漏掉它们。
    pattern = _compile_pattern(owners)

    tree = chapter_service.build_tree(session, project_id)
    bodies = _chapter_bodies(session, project_id)

    seen_forms: set[str] = set()
    first_seen: set[str] = set()
    # 条目在阅读顺序里第一次被提到过没有。柱状图数的是**条目**：同一角色的多个
    # 称呼各按 form 列进 new_terms，但这个角色只在首次出现的那一章计 1 ——
    # 否则「11 个称呼」会让柱状之和远超顶部的已投放条目数。
    entry_first_seen: set[str] = set()
    chapters: list[dict] = []
    for volume in tree:
        for chapter in volume["chapters"]:
            mentions = 0
            chars = 0
            has_body = False
            new_terms: list[dict] = []
            new_entry_ids: set[str] = set()
            for scene in chapter["scenes"]:
                body = bodies.get(scene["id"]) or ""
                chars += count_words(body)
                # 与 `build_tree` 的 has_body 同一判据：空白不算正文。
                if not body.strip():
                    continue
                has_body = True
                if pattern is None:
                    continue
                for match in pattern.finditer(body):
                    form = match.group(0)
                    mentions += 1
                    seen_forms.add(form)
                    # 按阅读顺序扫描，form 第一次命中的章就是它的首次投放章；
                    # 同一章里出现多次也只列一次。
                    if form in first_seen:
                        continue
                    first_seen.add(form)
                    entry = targets[form]
                    new_terms.append(
                        {"entry_id": entry.id, "name": entry.name, "form": form}
                    )
                    if entry.id not in entry_first_seen:
                        entry_first_seen.add(entry.id)
                        new_entry_ids.add(entry.id)
            chapters.append(
                {
                    "id": chapter["id"],
                    "label": f"第{chapter['seq'] + 1}章 {chapter['title']}".strip(),
                    "volume_label": volume["name"],
                    "has_body": has_body,
                    "chars": chars,
                    "new_terms": new_terms,
                    "new_count": len(new_entry_ids),
                    "mentions": mentions,
                    "density": _density(mentions, chars),
                }
            )

    # 已投放 / 从未出现按**条目**判定：只要它的一个 form 在正文里出现过就算投放，
    # 与 form 最后归到哪个条目无关（重名由 ambiguities 交代）。没有可用 form 的
    # 条目永远不可能命中，自然落在 never_seen 里。
    delivered = sum(1 for entry in entries if forms_by_entry[entry.id] & seen_forms)
    totals = {
        "entries": len(entries),
        "delivered": delivered,
        "never_seen": len(entries) - delivered,
        "ambiguities": sum(1 for candidates in owners.values() if len(candidates) > 1),
    }

    if not entries:
        reason = "还没有设定条目"
    elif not any(chapter["has_body"] for chapter in chapters):
        reason = "还没有已采纳正文"
    else:
        reason = ""

    return {"chapters": chapters, "totals": totals, "reason": reason}
