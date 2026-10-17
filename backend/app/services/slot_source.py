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
from app.world_types import ENTRY_TYPES, HARDNESS_LEVELS

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

    def summarize(self, slot_key: str, text: str) -> str:
        """超预算时的降级压缩。P1a 只截断，不调用模型，避免额外花钱。"""
        collapsed = " ".join(text.split())
        if len(collapsed) <= _SUMMARY_LIMIT:
            return collapsed
        return collapsed[:_SUMMARY_LIMIT] + "……"
