from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin
from sqlalchemy.types import JSON


class SettingEntry(IdMixin, TimestampMixin, Base):
    """设定条目。地理 / 势力 / 规则 / 术语等共用一张表，用 type 区分。

    一张表承载多种形态是刻意的取舍：别名、标签、关联、描述共用一套机制，
    日后做检索也只建一份索引。代价是术语类条目会很薄（可能只有名字）。
    """

    __tablename__ = "setting_entry"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_setting_entry_project_name"),
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str] = mapped_column(String(200))
    aliases_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    summary: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    # 仅 type == "rule" 有值
    hardness: Mapped[str | None] = mapped_column(String(20), default=None)
    # 从哪次运行采纳来的；手工新建的为 None（D-03 可追溯）
    source_run_id: Mapped[str | None] = mapped_column(String(36), default=None)


class EntryRelation(IdMixin, TimestampMixin, Base):
    """条目之间的有向关联。

    P1b-2 的关系网会复用这张表（人物之间的边，两端都是人物类条目），
    届时只加一个可空的强度列，已有行不受影响。kind 是自由文本而非枚举，
    正因为两层的词表（位于/下属 与 师徒/血缘）不该共用一个枚举。
    """

    __tablename__ = "entry_relation"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    from_id: Mapped[str] = mapped_column(
        ForeignKey("setting_entry.id", ondelete="CASCADE"), index=True
    )
    to_id: Mapped[str] = mapped_column(
        ForeignKey("setting_entry.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(60))
    note: Mapped[str] = mapped_column(Text, default="")
