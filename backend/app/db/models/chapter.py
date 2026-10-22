from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Volume(IdMixin, TimestampMixin, Base):
    __tablename__ = "volume"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer, default=0, index=True)
    name: Mapped[str] = mapped_column(String(200))
    purpose: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    # 对应第几幕的**快照**，不建外键：架构采纳会整批重建 act。
    act_seq: Mapped[int | None] = mapped_column(Integer, default=None)
    target_words: Mapped[int | None] = mapped_column(Integer, default=None)
    status: Mapped[str] = mapped_column(String(20), default="planned")
    source_run_id: Mapped[str | None] = mapped_column(String(36), default=None)
    # 锁定向下继承：卷被锁，其下所有章与场景都算锁定。
    locked: Mapped[bool] = mapped_column(Boolean, default=False)


class Chapter(IdMixin, TimestampMixin, Base):
    __tablename__ = "chapter"

    volume_id: Mapped[str] = mapped_column(
        ForeignKey("volume.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer, default=0, index=True)
    title: Mapped[str] = mapped_column(String(200))
    pov: Mapped[str] = mapped_column(String(100), default="")
    target_words: Mapped[int | None] = mapped_column(Integer, default=None)
    emotional_tone: Mapped[str] = mapped_column(String(100), default="")
    lines_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    hook: Mapped[str] = mapped_column(String(200), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    # 节奏视图的输入（P1c-2 只读）
    conflict_level: Mapped[int | None] = mapped_column(Integer, default=None)
    dialogue_ratio: Mapped[float | None] = mapped_column(Float, default=None)
    hook_strength: Mapped[int | None] = mapped_column(Integer, default=None)
    status: Mapped[str] = mapped_column(String(20), default="planned")
    source_run_id: Mapped[str | None] = mapped_column(String(36), default=None)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)


class Scene(IdMixin, TimestampMixin, Base):
    __tablename__ = "scene"

    chapter_id: Mapped[str] = mapped_column(
        ForeignKey("chapter.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer, default=0, index=True)
    goal: Mapped[str] = mapped_column(Text, default="")
    conflict: Mapped[str] = mapped_column(Text, default="")
    turn: Mapped[str] = mapped_column(Text, default="")
    characters_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    location_id: Mapped[str | None] = mapped_column(
        ForeignKey("setting_entry.id", ondelete="SET NULL"), default=None
    )
    story_time: Mapped[str] = mapped_column(String(200), default="")
    pov: Mapped[str] = mapped_column(String(100), default="")
    target_words_min: Mapped[int | None] = mapped_column(Integer, default=None)
    target_words_max: Mapped[int | None] = mapped_column(Integer, default=None)
    status: Mapped[str] = mapped_column(String(20), default="planned")
    source_run_id: Mapped[str | None] = mapped_column(String(36), default=None)
    body: Mapped[str | None] = mapped_column(Text, default=None)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    # 段落锁存**段落完整文本**而不是行号或偏移：Markdown 编辑会让偏移立刻失效，
    # 逐字文本在正文重排下仍然成立。代价是改一个字就等于换了一段 —— 那本来就是
    # 作者锁这一段的意图。
    locked_paragraphs_json: Mapped[list[str]] = mapped_column(JSON, default=list)


class Foreshadow(IdMixin, TimestampMixin, Base):
    """伏笔的唯一真相。场景通过本表关联，不在场景上复制一份 JSON。"""

    __tablename__ = "foreshadow"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_foreshadow_project_name"),
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    note: Mapped[str] = mapped_column(Text, default="")
    plant_scene_id: Mapped[str | None] = mapped_column(
        ForeignKey("scene.id", ondelete="SET NULL"), index=True, default=None
    )
    plan_pay_scene_id: Mapped[str | None] = mapped_column(
        ForeignKey("scene.id", ondelete="SET NULL"), index=True, default=None
    )
    # 实际回收场景：由回写建议经作者确认后写入；不改变规划状态。
    actual_pay_scene_id: Mapped[str | None] = mapped_column(
        ForeignKey("scene.id", ondelete="SET NULL"), index=True, default=None
    )
    status: Mapped[str] = mapped_column(String(20), default="planned")
    source_run_id: Mapped[str | None] = mapped_column(String(36), default=None)
