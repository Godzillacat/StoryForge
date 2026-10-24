"""项目态的只读槽位视图。

runtime 只依赖 SlotSource 协议，这个类负责把数据库里的项目态
翻译成槽位文本。P1b/P1c 新增槽位时只扩展这里，不动编排。
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Act,
    Architecture,
    Chapter,
    Foreshadow,
    Idea,
    Project,
    Scene,
    SettingEntry,
    TimelineEvent,
    ToolTemplate,
    Volume,
)
from app.services import search_service
from app.world_types import CHARACTER_FIELDS, ENTRY_TYPES, HARDNESS_LEVELS

_SUMMARY_LIMIT = 120
# 槽位里每个长文本字段的截断上限：上下文要的是够写场景的骨架，
# 不是把设定全文搬进提示词。
_FIELD_LIMIT = 160


def _clip(text: str) -> str:
    if len(text) <= _FIELD_LIMIT:
        return text
    return text[:_FIELD_LIMIT] + "……"


class DbSlotSource:
    def __init__(
        self,
        session: Session,
        project_id: str,
        tool_summary: str = "",
        extra_slots: dict | None = None,
    ) -> None:
        self._session = session
        self._project_id = project_id
        self._tool_summary = tool_summary
        # 调用方显式指定的槽位来源（如「解析这条灵感」里的 raw_idea_id），
        # 优先于按时间取默认值，避免解析结果与作者所指的原话对不上。
        self._extra = extra_slots or {}

    def __getattr__(self, name: str):
        """未显式实现的槽位从 `_extra` 里取。

        修订建议这类「只在该次运行里组装」的槽位不该逼着 RuntimeService 认
        槽位名字：调用方显式传 `extra_slots`，这里就按名字给一个取值函数。
        下划线开头的一律照旧报错，免得把内部的拼写错误吞成空槽位。
        """
        if name.startswith("_"):
            raise AttributeError(name)

        def _from_extra() -> str | None:
            value = self._extra.get(name)
            return str(value) if value else None

        return _from_extra

    def _project(self) -> Project | None:
        return self._session.get(Project, self._project_id)

    def _idea(self) -> Idea | None:
        requested = self._extra.get("raw_idea_id")
        if requested:
            idea = self._session.get(Idea, requested)
            if idea is not None:
                return idea
        return self._session.scalars(
            select(Idea).where(Idea.project_id == self._project_id).order_by(Idea.created_at)
        ).first()

    def _architecture(self) -> Architecture | None:
        return self._session.scalars(
            select(Architecture)
            .where(Architecture.project_id == self._project_id)
            .order_by(Architecture.created_at)
        ).first()

    def project_core(self) -> str | None:
        project = self._project()
        if project is None:
            return None
        lines = [f"项目名称：{project.name}"]
        if project.genre:
            lines.append(f"题材：{project.genre}")
        if project.sub_genre:
            lines.append(f"子类型：{project.sub_genre}")
        if project.tone:
            lines.append(f"调性：{project.tone}")
        if project.target_length:
            lines.append(f"目标字数：{project.target_length}")
        if project.summary:
            lines.append(f"项目简介：{project.summary}")
        return "\n".join(lines)

    def raw_idea(self) -> str | None:
        """作者原话，只读不改（D-04）。"""
        idea = self._idea()
        return idea.raw_text if idea else None

    def parsed_idea(self) -> str | None:
        idea = self._idea()
        if idea is None or not idea.parsed_json:
            return None
        return json.dumps(idea.parsed_json, ensure_ascii=False, indent=2)

    def story_bible(self) -> str | None:
        arch = self._architecture()
        if arch is None:
            return None
        lines = []
        if arch.logline:
            lines.append(f"logline：{arch.logline}")
        if arch.theme:
            lines.append(f"主题句：{arch.theme}")
        if arch.premise:
            lines.append(f"前提：{arch.premise}")
        if arch.ending_direction:
            lines.append(f"结局方向：{arch.ending_direction}")
        return "\n".join(lines) or None

    def architecture(self) -> str | None:
        arch = self._architecture()
        if arch is None:
            return None
        lines = [f"结构工具：{arch.tool_ref or '未指定'}"]
        acts = self._session.scalars(
            select(Act).where(Act.architecture_id == arch.id).order_by(Act.seq)
        ).all()
        for act in acts:
            purpose = f"（{act.purpose}）" if act.purpose else ""
            lines.append(f"第{act.seq}幕 {act.name}{purpose}")
        return "\n".join(lines)

    def tool_library(self) -> str | None:
        if self._tool_summary:
            return self._tool_summary
        tools = self._session.scalars(
            select(ToolTemplate).order_by(ToolTemplate.category, ToolTemplate.key)
        ).all()
        if not tools:
            return None
        return "\n".join(f"[{t.category}] {t.name}：{t.description}" for t in tools)

    def style_samples(self) -> str | None:
        return None  # P2 接入风格样本

    def world_context(self) -> str | None:
        """设定条目的摘要视图，按类型分组；不搬全文描述。"""
        entries = self._session.scalars(
            select(SettingEntry)
            .where(SettingEntry.project_id == self._project_id)
            .order_by(SettingEntry.type, SettingEntry.name)
        ).all()
        if not entries:
            return None
        lines = []
        for entry in entries:
            label = ENTRY_TYPES.get(entry.type, entry.type)
            aliases = (
                f"（别名：{'、'.join(entry.aliases_json)}）" if entry.aliases_json else ""
            )
            parts = [f"【{label}】{entry.name}{aliases}"]
            summary = entry.summary or entry.description
            if summary:
                parts.append(f"概述：{_clip(summary)}")
            if entry.type == "character":
                for key, label in (
                    ("desire", "欲望"),
                    ("fear", "恐惧"),
                    ("current_state", "当前状态"),
                ):
                    value = getattr(entry, key)
                    if value:
                        parts.append(f"{label}：{_clip(value)}")
            if entry.type == "rule" and entry.hardness:
                parts.append(HARDNESS_LEVELS.get(entry.hardness, entry.hardness))
            lines.append(" — ".join(parts))
        return "\n".join(lines)

    def timeline(self) -> str | None:
        events = self._session.scalars(
            select(TimelineEvent)
            .where(TimelineEvent.project_id == self._project_id)
            .order_by(TimelineEvent.order_index, TimelineEvent.created_at)
        ).all()
        if not events:
            return None
        entries = {
            entry.id: entry.name
            for entry in self._session.scalars(
                select(SettingEntry).where(SettingEntry.project_id == self._project_id)
            )
        }
        lines = []
        for event in events:
            people = "、".join(
                entries.get(pid, "（已删除）") for pid in (event.participants_json or [])
            )
            location = entries.get(event.location_id, "") if event.location_id else ""
            parts = [event.story_time or "（未标时间）", event.title]
            if people:
                parts.append(f"参与者：{people}")
            if location:
                parts.append(f"地点：{location}")
            if event.description:
                parts.append(f"描述：{_clip(event.description)}")
            lines.append("｜".join(parts))
        return "\n".join(lines)

    def _volume(self) -> Volume | None:
        volume_id = self._extra.get("volume_id")
        if not volume_id:
            return None
        volume = self._session.get(Volume, volume_id)
        if volume is None or volume.project_id != self._project_id:
            return None
        return volume

    def volume_outline(self) -> str | None:
        volume = self._volume()
        if volume is None:
            return None
        header = f"第{volume.seq + 1}卷 {volume.name}"
        if volume.purpose:
            header += f"（{volume.purpose}）"
        lines = [header]
        chapters = self._session.scalars(
            select(Chapter).where(Chapter.volume_id == volume.id).order_by(Chapter.seq)
        ).all()
        for chapter in chapters:
            line = f"第{chapter.seq + 1}章 {chapter.title}"
            extras = []
            if chapter.pov:
                extras.append(f"视角：{chapter.pov}")
            if chapter.summary:
                extras.append(_clip(chapter.summary))
            if chapter.hook:
                extras.append(f"钩子：{_clip(chapter.hook)}")
            if extras:
                line += " — " + "；".join(extras)
            lines.append(line)
        return "\n".join(lines)

    def _chapter(self) -> Chapter | None:
        chapter_id = self._extra.get("chapter_id")
        if not chapter_id:
            return None
        chapter = self._session.get(Chapter, chapter_id)
        if chapter is None:
            return None
        volume = self._session.get(Volume, chapter.volume_id)
        if volume is None or volume.project_id != self._project_id:
            return None
        return chapter

    def chapter_outline(self) -> str | None:
        chapter = self._chapter()
        if chapter is None:
            return None
        lines = [f"章标题：{chapter.title}"]
        for label, value in (
            ("视角", chapter.pov),
            ("目标字数", chapter.target_words),
            ("情绪基调", chapter.emotional_tone),
            ("章末钩子", chapter.hook),
            ("摘要", chapter.summary),
        ):
            if value not in (None, ""):
                lines.append(f"{label}：{_clip(str(value))}")
        if chapter.lines_json:
            lines.append(f"推进的线：{'、'.join(chapter.lines_json)}")
        scenes = self._session.scalars(
            select(Scene).where(Scene.chapter_id == chapter.id).order_by(Scene.seq)
        ).all()
        if scenes:
            foreshadows = self._session.scalars(
                select(Foreshadow).where(Foreshadow.project_id == self._project_id)
            ).all()
            plants_by_scene: dict[str, list[str]] = {}
            pays_by_scene: dict[str, list[str]] = {}
            for row in foreshadows:
                if row.plant_scene_id:
                    plants_by_scene.setdefault(row.plant_scene_id, []).append(row.name)
                if row.plan_pay_scene_id:
                    pays_by_scene.setdefault(row.plan_pay_scene_id, []).append(row.name)
            for scene in scenes:
                parts = [f"场景{scene.seq + 1}：{scene.goal or '（未写目标）'}"]
                if scene.conflict:
                    parts.append(f"冲突：{_clip(scene.conflict)}")
                if scene.turn:
                    parts.append(f"转折：{_clip(scene.turn)}")
                if plants_by_scene.get(scene.id):
                    parts.append(f"埋设：{'、'.join(plants_by_scene[scene.id])}")
                if pays_by_scene.get(scene.id):
                    parts.append(f"回收：{'、'.join(pays_by_scene[scene.id])}")
                lines.append("；".join(parts))
        return "\n".join(lines)

    def _scene_chain(self) -> tuple[Scene, Chapter, Volume] | None:
        scene_id = self._extra.get("scene_id")
        if not scene_id:
            return None
        scene = self._session.get(Scene, scene_id)
        if scene is None:
            return None
        chapter = self._session.get(Chapter, scene.chapter_id)
        if chapter is None:
            return None
        volume = self._session.get(Volume, chapter.volume_id)
        if volume is None or volume.project_id != self._project_id:
            return None
        return scene, chapter, volume

    def _scene_entries(self) -> dict[str, SettingEntry]:
        return {
            entry.id: entry
            for entry in self._session.scalars(
                select(SettingEntry).where(SettingEntry.project_id == self._project_id)
            )
        }

    def scene_card(self) -> str | None:
        chain = self._scene_chain()
        if chain is None:
            return None
        scene, chapter, volume = chain
        entries = self._scene_entries()
        people = [
            entries[item].name
            for item in (scene.characters_json or [])
            if item in entries
        ]
        location = entries.get(scene.location_id).name if scene.location_id in entries else ""
        foreshadows = self._session.scalars(
            select(Foreshadow).where(Foreshadow.project_id == self._project_id)
        ).all()
        plants = [row.name for row in foreshadows if row.plant_scene_id == scene.id]
        pays = [row.name for row in foreshadows if row.plan_pay_scene_id == scene.id]

        lines = [
            f"第{volume.seq + 1}卷 {volume.name} / 第{chapter.seq + 1}章 {chapter.title} / 场景{scene.seq + 1}",
            f"目标：{scene.goal or '（未写目标）'}",
        ]
        if scene.conflict:
            lines.append(f"冲突：{scene.conflict}")
        if scene.turn:
            lines.append(f"转折：{scene.turn}")
        if people:
            lines.append("出场人物：" + "、".join(people))
        if location:
            lines.append("地点：" + location)
        if scene.story_time:
            lines.append("故事内时间：" + scene.story_time)
        pov = scene.pov or chapter.pov
        if pov:
            lines.append("视角：" + pov)
        if scene.target_words_min is not None or scene.target_words_max is not None:
            lines.append(
                f"目标字数：{scene.target_words_min or '?'}–{scene.target_words_max or '?'}"
            )
        if plants:
            lines.append("埋设伏笔：" + "、".join(plants))
        if pays:
            lines.append("计划回收伏笔：" + "、".join(pays))
        return "\n".join(lines)

    def scene_characters(self) -> str | None:
        chain = self._scene_chain()
        if chain is None:
            return None
        scene, _chapter, _volume = chain
        entries = self._scene_entries()
        lines: list[str] = []
        for item in scene.characters_json or []:
            entry = entries.get(item)
            if entry is None or entry.type != "character":
                continue
            parts = [f"【人物】{entry.name}"]
            if entry.aliases_json:
                parts.append("别名与称呼：" + "、".join(entry.aliases_json))
            if entry.summary:
                parts.append("概述：" + entry.summary)
            if entry.description:
                parts.append("说明：" + entry.description)
            for key, (label, _multiline) in CHARACTER_FIELDS.items():
                value = getattr(entry, key, None)
                if value:
                    parts.append(f"{label}：" + str(value))
            lines.append("；".join(parts))
        return "\n".join(lines) or None

    def recent_text(self) -> str | None:
        chain = self._scene_chain()
        if chain is None:
            return None
        scene, chapter, _volume = chain
        previous = self._session.scalars(
            select(Scene)
            .where(Scene.chapter_id == chapter.id, Scene.seq < scene.seq)
            .order_by(Scene.seq.desc())
        ).all()
        chunks = [
            item.body.strip()
            for item in previous
            if item.body and item.body.strip()
        ][:2]
        if not chunks:
            return None
        text = "\n\n".join(reversed(chunks))
        if len(text) > 1200:
            return "……" + text[-1200:]
        return text

    def scene_text(self) -> str | None:
        """当前场景的已采纳正文；草稿不算正式稿，不进审校上下文。

        逻辑自检的「开写前」阶段显式跳过正文：那时正文可能来自上一版，
        拿它当待审材料会让检查对象错位。
        """
        if self._extra.get("skip_scene_text"):
            return None
        chain = self._scene_chain()
        if chain is None:
            return None
        scene, _chapter, _volume = chain
        body = (scene.body or "").strip()
        return body or None

    def related_settings(self) -> str | None:
        """检索与本章相关的设定条目（可选槽位）。

        查询词优先取调用方显式给的 search_query，否则只用本章标题
        （摘要与钩子不拼进去：它们会把检索带偏到本章的情节词，而不是
        场景里真正要引用的设定）。检索可能按脏标记重建索引并提交，
        这是文档化的行为 —— 上下文组装时就地刷新，避免读到旧索引。
        """
        query = str(self._extra.get("search_query") or "").strip()
        if not query:
            chapter = self._chapter()
            if chapter is None:
                return None
            query = (chapter.title or "").strip()
        if not query:
            return None
        hits = search_service.search(
            self._session,
            self._project_id,
            query,
            entity_types=["entry"],
            limit=8,
        )
        if not hits:
            return None
        lines = []
        for hit in hits:
            label = ENTRY_TYPES.get(hit.subtype, hit.subtype) if hit.subtype else "设定"
            lines.append(f"【{label}】{hit.title} — {_clip(hit.snippet)}")
        return "\n".join(lines)

    def foreshadow_ledger(self) -> str | None:
        """全部伏笔的名称与埋设/回收位置。

        回写助手靠它把正文里实际兑现的伏笔对上标准名；没有这份清单，
        模型只能猜名字，匹配不到任何一个已有伏笔。
        """
        rows = self._session.scalars(
            select(Foreshadow)
            .where(Foreshadow.project_id == self._project_id)
            .order_by(Foreshadow.created_at)
        ).all()
        if not rows:
            return None

        labels: dict[str, str] = {}
        scenes = self._session.scalars(
            select(Scene)
            .join(Chapter, Scene.chapter_id == Chapter.id)
            .join(Volume, Chapter.volume_id == Volume.id)
            .where(Volume.project_id == self._project_id)
        ).all()
        chapters = {
            row.id: row
            for row in self._session.scalars(
                select(Chapter).join(Volume, Chapter.volume_id == Volume.id).where(
                    Volume.project_id == self._project_id
                )
            )
        }
        volumes = {
            row.id: row
            for row in self._session.scalars(
                select(Volume).where(Volume.project_id == self._project_id)
            )
        }
        for scene in scenes:
            chapter = chapters.get(scene.chapter_id)
            volume = volumes.get(chapter.volume_id) if chapter else None
            if chapter is None or volume is None:
                continue
            labels[scene.id] = (
                f"第{volume.seq + 1}卷 第{chapter.seq + 1}章 场景{scene.seq + 1}"
            )

        def where(scene_id: str | None) -> str:
            if not scene_id:
                return "未安排"
            return labels.get(scene_id, "（场景已删除）")

        lines = []
        for row in rows:
            parts = [row.name]
            parts.append(f"埋设：{where(row.plant_scene_id)}")
            parts.append(f"计划回收：{where(row.plan_pay_scene_id)}")
            parts.append(f"实际回收：{where(row.actual_pay_scene_id)}")
            if row.note:
                parts.append(f"备注：{_clip(row.note)}")
            lines.append("｜".join(parts))
        return "\n".join(lines)

    def summarize(self, slot_key: str, text: str) -> str:
        """超预算时的降级压缩。P1a 只截断，不调用模型，避免额外花钱。"""
        collapsed = " ".join(text.split())
        if len(collapsed) <= _SUMMARY_LIMIT:
            return collapsed
        return collapsed[:_SUMMARY_LIMIT] + "……"


def scene_search_query(session: Session, project_id: str, scene: Scene) -> str:
    """用场景卡里的情节词与实体名拼检索词。"""
    entries = {
        entry.id: entry.name
        for entry in session.scalars(
            select(SettingEntry).where(SettingEntry.project_id == project_id)
        )
    }
    parts = [scene.goal or "", scene.conflict or "", scene.turn or ""]
    parts.extend(entries.get(item, "") for item in (scene.characters_json or []))
    if scene.location_id:
        parts.append(entries.get(scene.location_id, ""))
    return " ".join(part.strip() for part in parts if part and part.strip())
