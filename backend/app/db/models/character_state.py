from __future__ import annotations

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class CharacterState(IdMixin, TimestampMixin, Base):
    """某章、某人、作者手记的当时状态。

    一行一条记录，`(chapter_id, entry_id)` 唯一、写入走 upsert —— 同一章同一人
    只该有一个状态，重复保存是改它而不是再记一条。与人物条目上的
    `current_state` 相互独立：那个是此刻，这张表是逐章历史。

    新表归 `create_all`，不写迁移（迁移只改已有表）。
    """

    __tablename__ = "character_state"
    __table_args__ = (
        UniqueConstraint(
            "chapter_id", "entry_id", name="uq_character_state_chapter_entry"
        ),
    )

    chapter_id: Mapped[str] = mapped_column(
        ForeignKey("chapter.id", ondelete="CASCADE"), index=True
    )
    entry_id: Mapped[str] = mapped_column(
        ForeignKey("setting_entry.id", ondelete="CASCADE"), index=True
    )
    note: Mapped[str] = mapped_column(Text)
