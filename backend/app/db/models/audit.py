from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, IdMixin, TimestampMixin


class AuditIssue(IdMixin, TimestampMixin, Base):
    """一条审计问题。规则层与 LLM 层共用这张表，用 source 区分。

    问题只挂在一个场景上；project_id 用于整项目删除级联与后续汇总。
    `scene_id` 的索引由下面的复合索引承担（它是前导列），不另建一份。
    """

    __tablename__ = "audit_issue"
    __table_args__ = (
        Index("ix_audit_issue_scene_status", "scene_id", "status"),
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    scene_id: Mapped[str] = mapped_column(
        ForeignKey("scene.id", ondelete="CASCADE")
    )
    # 规则层问题没有运行记录；删除运行记录不该带走作者还没处理的问题。
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("generation_run.id", ondelete="SET NULL"), default=None
    )
    # rule | llm
    source: Mapped[str] = mapped_column(String(20))
    # repetition | alias | setting | character | timeline | term | other
    kind: Mapped[str] = mapped_column(String(30))
    # critical | major | minor
    severity: Mapped[str] = mapped_column(String(20))
    quote: Mapped[str] = mapped_column(Text, default="")
    rule_ref: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")
    reader_impact: Mapped[str] = mapped_column(Text, default="")
    # 2–3 条修正方向；只展示给作者，不自动执行
    options_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    # 能可靠映射到设定条目时填写；LLM 用名称/别名精确匹配，匹配不到就是 NULL
    target_entry_id: Mapped[str | None] = mapped_column(
        ForeignKey("setting_entry.id", ondelete="SET NULL"), default=None
    )
    # 稳定指纹：特例抑制与重复上报判定都以它为准。LLM 指纹会把冲突对象
    # 一并编进去，长度不设上限（与 rule_ref 一样用 TEXT）。
    fingerprint: Mapped[str] = mapped_column(Text, index=True)
    # open | resolved | exception | superseded
    status: Mapped[str] = mapped_column(String(20), default="open")
    # story | setting | character | exception；未处理时为 NULL
    resolution: Mapped[str | None] = mapped_column(String(20), default=None)
