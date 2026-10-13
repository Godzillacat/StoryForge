"""项目态的只读槽位视图。

runtime 只依赖 SlotSource 协议，这个类负责把数据库里的项目态
翻译成槽位文本。P1b/P1c 新增槽位时只扩展这里，不动编排。
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Act, Architecture, Idea, Project, ToolTemplate

_SUMMARY_LIMIT = 120


class DbSlotSource:
    def __init__(self, session: Session, project_id: str, tool_summary: str = "") -> None:
        self._session = session
        self._project_id = project_id
        self._tool_summary = tool_summary

    def _project(self) -> Project | None:
        return self._session.get(Project, self._project_id)

    def _idea(self) -> Idea | None:
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

    def summarize(self, slot_key: str, text: str) -> str:
        """超预算时的降级压缩。P1a 只截断，不调用模型，避免额外花钱。"""
        collapsed = " ".join(text.split())
        if len(collapsed) <= _SUMMARY_LIMIT:
            return collapsed
        return collapsed[:_SUMMARY_LIMIT] + "……"
