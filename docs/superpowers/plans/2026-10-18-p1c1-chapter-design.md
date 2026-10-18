# P1c-1 章节结构（卷 / 章 / 场景卡 + 策划智能体）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付 P1c-1：卷 / 章 / 场景卡的数据库、手工编辑、伏笔与节奏指标数据底座，以及章纲策划 / 场景策划两个预置智能体和「可编辑草稿树 → 一次写入」的 AI 候选链路。

**Architecture:** 四张新表（`volume` / `chapter` / `scene` / `foreshadow`）全部归 `create_all`；场景卡与伏笔通过 `foreshadow` 表单一真相关联，不在场景表上复制 JSON。两个窄契约智能体分别产出卷章纲与场景卡候选；候选只落在 `generation_run`，前端编辑后由 `PUT` 接口一次事务写入。名称（人物/地点/伏笔）在契约里出现，写入时解析为 ID。

**Tech Stack:** Python 3.13 / uv / FastAPI / SQLAlchemy 2 / Pydantic 2 / pytest；React 18 + TypeScript + Vite + Tailwind 3 / pnpm。

**Spec:** `docs/superpowers/specs/2026-10-18-p1c1-chapter-design.md`

## Global Constraints

- 测试基线：改动前 `cd backend && uv run pytest -q` 应为 **292 passed**；前端 `pnpm vitest run` 8 passed、`pnpm build` 干净。每任务只许增加、不许回退。
- 计划里各步的「Expected: N passed」是估算；**绑定标准是「既有测试全绿 + 本任务新测试通过」**，实现者在报告里写实际数，最终以实际数为准。
- 后端分层：`api` 不写业务逻辑；`services` 不碰 HTTP；`runtime` 不依赖 FastAPI。
- 标识符与代码用英文；注释、界面文案、错误信息用中文。
- **新表归 `create_all`，本段不新增迁移。** 需要改已有表时另开迁移。
- 不引入新依赖；JSON Schema 子集校验器不支持 `minimum` / `maximum`，数值范围写进 `title` 并由服务层校验/钳制。
- 契约说明块由 `runtime/contract.py` 自动生成；提示词里不手抄字段键，也不出现未列入槽位的英文单词。
- 前端不写自动化测试；纯逻辑必须 pytest 覆盖。手工/无头走查是前端验收方式。
- 真实模型调用前必须确认阿里云百炼额度（记忆里的约定）；本章验证预计两次调用。
- 所有实现在隔离 worktree 内进行，不直接改 master。

---

## File Structure

**后端（新建）**

- `backend/app/db/models/chapter.py` —— `Volume` / `Chapter` / `Scene` / `Foreshadow`。
- `backend/app/chapter_types.py` —— 状态词表与校验。
- `backend/app/services/chapter_service.py` —— 卷 / 章的 CRUD、排序、树。
- `backend/app/services/foreshadow_service.py` —— 伏笔查找/新建（Task 3）与公开 CRUD（Task 4）。
- `backend/app/services/scene_service.py` —— 场景 CRUD、名称解析、伏笔挂接、批量写入。
- `backend/app/services/chapter_plan_service.py` —— 策划结果归一化、章纲写入。
- `backend/app/api/chapters.py` —— 树、卷/章/场景路由、策划运行、章纲写入。
- `backend/app/api/foreshadows.py` —— 伏笔路由。
- `backend/tests/test_chapter_models.py`
- `backend/tests/test_chapter_service.py`
- `backend/tests/test_scene_service.py`
- `backend/tests/test_foreshadow_service.py`
- `backend/tests/test_chapters_api.py`
- `backend/tests/test_foreshadows_api.py`
- `backend/tests/test_chapter_plan_service.py`

**后端（修改）**

- `backend/app/db/models/__init__.py` —— 导出四张表。
- `backend/app/runtime/context.py` —— 四个新槽位。
- `backend/app/services/slot_source.py` —— 四个新槽位的数据来源。
- `backend/app/agents/roster.py` —— `scene_plan` 任务类型、两个契约与提示词、两个预置条目。
- `backend/app/api/schemas.py` —— 卷/章/场景/伏笔/策划写入的 Pydantic 模型。
- `backend/app/main.py` —— 挂载两个新路由。
- `backend/tests/test_roster.py`、`test_slot_source.py`、`test_context.py`、`test_seed_service.py`（如需）。

**前端（新建）**

- `frontend/src/pages/Chapters.tsx` —— 章节设计页。
- `frontend/src/components/chapters/ChapterTree.tsx`
- `frontend/src/components/chapters/VolumeEditor.tsx`
- `frontend/src/components/chapters/ChapterEditor.tsx`
- `frontend/src/components/chapters/SceneEditor.tsx`
- `frontend/src/components/chapters/ChapterPlanDraft.tsx`
- `frontend/src/components/chapters/ScenePlanDraft.tsx`

**前端（修改）**

- `frontend/src/api/client.ts` —— 章节/伏笔/策划类型与方法。
- `frontend/src/App.tsx` —— 「章节设计」导航与路由。

**文档**

- `docs/superpowers/plans/2026-10-18-p1c1-walkthrough.md` —— 手工走查清单（Task 10）。
- `CLAUDE.md` —— P1c-1 阶段记录、变更记录、修正打包归属（Task 10）。

---

## Task 1: 四张表的模型

**Files:**
- Create: `backend/app/db/models/chapter.py`
- Modify: `backend/app/db/models/__init__.py`
- Create: `backend/app/chapter_types.py`
- Test: `backend/tests/test_chapter_models.py`

**Interfaces:**
- Produces: `Volume`、`Chapter`、`Scene`、`Foreshadow` 四个 ORM 模型；`STATUS_VALUES = {"planned", "confirmed"}` 与 `normalize_status`。

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_chapter_models.py`：

```python
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    Chapter,
    Foreshadow,
    Project,
    Scene,
    SettingEntry,
    Volume,
)
from app.db.session import SessionLocal


def _project(session) -> Project:
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    return project


def _volume(session, project) -> Volume:
    volume = Volume(project_id=project.id, seq=0, name="第一卷")
    session.add(volume)
    session.commit()
    return volume


def _chapter(session, volume) -> Chapter:
    chapter = Chapter(volume_id=volume.id, seq=0, title="第一章")
    session.add(chapter)
    session.commit()
    return chapter


def test_volume_and_chapter_defaults(session):
    project = _project(session)
    volume = _volume(session, project)
    chapter = _chapter(session, volume)

    assert volume.purpose == ""
    assert volume.summary == ""
    assert volume.act_seq is None
    assert volume.target_words is None
    assert volume.status == "planned"
    assert volume.source_run_id is None

    assert chapter.pov == ""
    assert chapter.lines_json == []
    assert chapter.conflict_level is None
    assert chapter.dialogue_ratio is None
    assert chapter.hook_strength is None
    assert chapter.status == "planned"


def test_scene_roundtrip_and_defaults(session):
    project = _project(session)
    volume = _volume(session, project)
    chapter = _chapter(session, volume)
    character = SettingEntry(project_id=project.id, type="character", name="陈默")
    place = SettingEntry(project_id=project.id, type="place", name="南滨")
    session.add_all([character, place])
    session.commit()

    scene = Scene(
        chapter_id=chapter.id,
        seq=0,
        goal="找到录音带",
        conflict="档案室有人",
        turn="录音带里是自己的声音",
        characters_json=[character.id],
        location_id=place.id,
        story_time="第三年·春",
        pov="陈默",
        target_words_min=800,
        target_words_max=1500,
    )
    session.add(scene)
    session.commit()

    stored = session.get(Scene, scene.id)
    assert stored.goal == "找到录音带"
    assert stored.characters_json == [character.id]
    assert stored.location_id == place.id
    assert stored.target_words_min == 800
    assert stored.status == "planned"


def test_foreshadow_name_is_unique_within_a_project(session):
    a = _project(session)
    b = Project(name="另一本")
    session.add(b)
    session.commit()

    session.add(Foreshadow(project_id=a.id, name="失忆的录音带"))
    session.add(Foreshadow(project_id=b.id, name="失忆的录音带"))
    session.commit()  # 跨项目同名合法

    session.add(Foreshadow(project_id=a.id, name="失忆的录音带"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_deleting_a_volume_cascades_to_chapters_and_scenes(session):
    project = _project(session)
    volume = _volume(session, project)
    chapter = _chapter(session, volume)
    scene = Scene(chapter_id=chapter.id, seq=0, goal="目标")
    session.add(scene)
    session.commit()
    scene_id = scene.id

    session.delete(volume)
    session.commit()

    with SessionLocal() as fresh:
        assert fresh.get(Chapter, chapter.id) is None
        assert fresh.get(Scene, scene_id) is None


def test_deleting_a_scene_clears_foreshadow_links(session):
    project = _project(session)
    volume = _volume(session, project)
    chapter = _chapter(session, volume)
    plant = Scene(chapter_id=chapter.id, seq=0, goal="埋")
    pay = Scene(chapter_id=chapter.id, seq=1, goal="收")
    session.add_all([plant, pay])
    session.commit()
    foreshadow = Foreshadow(
        project_id=project.id,
        name="失忆的录音带",
        plant_scene_id=plant.id,
        plan_pay_scene_id=pay.id,
    )
    session.add(foreshadow)
    session.commit()

    session.delete(plant)
    session.commit()

    with SessionLocal() as fresh:
        stored = fresh.get(Foreshadow, foreshadow.id)
        assert stored.plant_scene_id is None
        assert stored.plan_pay_scene_id == pay.id


def test_deleting_an_entry_clears_scene_location(session):
    project = _project(session)
    volume = _volume(session, project)
    chapter = _chapter(session, volume)
    place = SettingEntry(project_id=project.id, type="place", name="南滨")
    session.add(place)
    session.commit()
    scene = Scene(chapter_id=chapter.id, seq=0, goal="目标", location_id=place.id)
    session.add(scene)
    session.commit()

    session.delete(place)
    session.commit()

    with SessionLocal() as fresh:
        assert fresh.get(Scene, scene.id).location_id is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_chapter_models.py -q`
Expected: FAIL（模型不存在）。

- [ ] **Step 3: 实现模型与状态词表**

新建 `backend/app/chapter_types.py`：

```python
"""章节结构的状态词表与校验。

P1c-1 只允许「规划中 / 已确认」；P2 写正文时扩展 written，P4 扩展伏笔闭环
状态。扩展时必须同步服务层校验与前端下拉 —— 与 ENTRY_TYPES 的教训一致。
"""

from __future__ import annotations

STATUS_VALUES: tuple[str, ...] = ("planned", "confirmed")
STATUS_LABELS: dict[str, str] = {
    "planned": "规划中",
    "confirmed": "已确认",
}


def normalize_status(value: str | None, *, default: str = "planned") -> str:
    key = (value or "").strip() or default
    if key not in STATUS_VALUES:
        raise ValueError(f"未知的章节状态「{value}」，可用值：planned / confirmed")
    return key
```

新建 `backend/app/db/models/chapter.py`：

```python
from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
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
    status: Mapped[str] = mapped_column(String(20), default="planned")
    source_run_id: Mapped[str | None] = mapped_column(String(36), default=None)
```

`backend/app/db/models/__init__.py`：导入四个模型并加入 `__all__`。

- [ ] **Step 4: 跑测试**

Run: `cd backend && uv run pytest tests/test_chapter_models.py -q`
Expected: PASS。

- [ ] **Step 5: 跑完整套件并提交**

Run: `cd backend && uv run pytest -q`
Expected: 292 + 6 = 298 passed。

```bash
git add backend/app/db/models/chapter.py backend/app/db/models/__init__.py backend/app/chapter_types.py backend/tests/test_chapter_models.py
git commit -m "feat(db): 卷/章/场景/伏笔四张表"
```

---

## Task 2: 卷 / 章服务、树与 API

**Files:**
- Create: `backend/app/services/chapter_service.py`
- Create: `backend/app/api/chapters.py`
- Modify: `backend/app/api/schemas.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_chapter_service.py`, `backend/tests/test_chapters_api.py`

**Interfaces:**
- Produces:
  - `chapter_service.build_tree(session, project_id) -> list[dict]`
  - `create_volume/update_volume/delete_volume/move_volume`
  - `create_chapter/update_chapter/delete_chapter/move_chapter`
  - `get_project_for_volume/get_project_for_chapter`（供 Task 3 校验）
  - API：`GET /api/projects/{id}/chapters/tree`，卷/章 CRUD 与移动。

- [ ] **Step 1: 写失败测试 —— 服务层**

新建 `backend/tests/test_chapter_service.py`：

```python
import pytest

from app.db.models import Project, SettingEntry
from app.services import chapter_service


def _project(session) -> Project:
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    return project


def test_create_volume_appends_and_tree_orders(session):
    project = _project(session)
    first = chapter_service.create_volume(session, project.id, name="第一卷")
    second = chapter_service.create_volume(session, project.id, name="第二卷")

    assert (first.seq, second.seq) == (0, 1)
    tree = chapter_service.build_tree(session, project.id)
    assert [v["name"] for v in tree] == ["第一卷", "第二卷"]


def test_create_chapter_appends_and_tree_nests(session):
    project = _project(session)
    volume = chapter_service.create_volume(session, project.id, name="第一卷")
    first = chapter_service.create_chapter(session, volume.id, title="第一章")
    second = chapter_service.create_chapter(session, volume.id, title="第二章")

    assert (first.seq, second.seq) == (0, 1)
    tree = chapter_service.build_tree(session, project.id)
    assert [c["title"] for c in tree[0]["chapters"]] == ["第一章", "第二章"]


def test_move_volume_and_chapter(session):
    project = _project(session)
    a = chapter_service.create_volume(session, project.id, name="甲")
    b = chapter_service.create_volume(session, project.id, name="乙")
    chapter_service.move_volume(session, b.id, "up")
    assert [v["name"] for v in chapter_service.build_tree(session, project.id)] == ["乙", "甲"]

    c1 = chapter_service.create_chapter(session, a.id, title="一")
    c2 = chapter_service.create_chapter(session, a.id, title="二")
    chapter_service.move_chapter(session, c2.id, "up")
    tree = chapter_service.build_tree(session, project.id)
    volume_a = next(v for v in tree if v["id"] == a.id)
    assert [c["title"] for c in volume_a["chapters"]] == ["二", "一"]


def test_move_at_boundary_is_a_no_op(session):
    project = _project(session)
    volume = chapter_service.create_volume(session, project.id, name="唯一")
    chapter_service.move_volume(session, volume.id, "up")
    assert [v["name"] for v in chapter_service.build_tree(session, project.id)] == ["唯一"]


def test_update_and_delete_volume_cascade(session):
    project = _project(session)
    volume = chapter_service.create_volume(session, project.id, name="旧名")
    chapter = chapter_service.create_chapter(session, volume.id, title="章")
    updated = chapter_service.update_volume(
        session, volume.id, name="新名", purpose="本卷目标", act_seq=1, target_words=30000
    )
    assert updated.name == "新名"
    assert updated.act_seq == 1

    chapter_service.delete_volume(session, volume.id)
    assert chapter_service.build_tree(session, project.id) == []
    assert session.get(type(chapter), chapter.id) is None


def test_validation_rejects_empty_name_and_bad_status(session):
    project = _project(session)
    with pytest.raises(ValueError, match="名称"):
        chapter_service.create_volume(session, project.id, name="   ")
    with pytest.raises(ValueError, match="状态"):
        chapter_service.create_volume(
            session, project.id, name="卷", status="unknown"
        )


def test_validation_rejects_bad_rhythm_ranges(session):
    project = _project(session)
    volume = chapter_service.create_volume(session, project.id, name="卷")
    with pytest.raises(ValueError):
        chapter_service.create_chapter(
            session, volume.id, title="章", conflict_level=6
        )
    with pytest.raises(ValueError):
        chapter_service.create_chapter(
            session, volume.id, title="章", dialogue_ratio=1.5
        )


def test_tree_includes_empty_scene_and_foreshadow_slots(session):
    project = _project(session)
    volume = chapter_service.create_volume(session, project.id, name="卷")
    chapter_service.create_chapter(session, volume.id, title="章")

    tree = chapter_service.build_tree(session, project.id)

    assert tree[0]["chapters"][0]["scenes"] == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_chapter_service.py -q`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 实现 `chapter_service.py`**

```python
"""卷 / 章的业务：CRUD、顺序、树。场景与伏笔的树节点由本模块统一查询。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chapter_types import normalize_status
from app.db.models import Chapter, Foreshadow, Project, Scene, Volume


def _ordered_volumes(session: Session, project_id: str) -> list[Volume]:
    return list(
        session.scalars(
            select(Volume)
            .where(Volume.project_id == project_id)
            .order_by(Volume.seq, Volume.created_at)
        )
    )


def _ordered_chapters(session: Session, volume_id: str) -> list[Chapter]:
    return list(
        session.scalars(
            select(Chapter)
            .where(Chapter.volume_id == volume_id)
            .order_by(Chapter.seq, Chapter.created_at)
        )
    )


def _ordered_scenes(session: Session, chapter_id: str) -> list[Scene]:
    return list(
        session.scalars(
            select(Scene)
            .where(Scene.chapter_id == chapter_id)
            .order_by(Scene.seq, Scene.created_at)
        )
    )


def _project(session: Session, project_id: str) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError(f"项目不存在：{project_id}")
    return project


def get_project_for_volume(session: Session, volume_id: str) -> Project:
    volume = session.get(Volume, volume_id)
    if volume is None:
        raise ValueError(f"卷不存在：{volume_id}")
    return _project(session, volume.project_id)


def get_project_for_chapter(session: Session, chapter_id: str) -> Project:
    chapter = session.get(Chapter, chapter_id)
    if chapter is None:
        raise ValueError(f"章不存在：{chapter_id}")
    return get_project_for_volume(session, chapter.volume_id)


def _clean_name(value: str | None, label: str) -> str:
    name = (value or "").strip()
    if not name:
        raise ValueError(f"{label}不能为空")
    return name


def _positive_int(value, label: str) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label}必须是正整数")
    return value


def _level(value, label: str, maximum: int) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ValueError(f"{label}必须是 1–{maximum} 的整数")
    return value


def _ratio(value) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ValueError("对话占比必须是 0–1 之间的数")
    return float(value)


def create_volume(session: Session, project_id: str, **fields) -> Volume:
    _project(session, project_id)
    name = _clean_name(fields.get("name"), "卷名")
    last = session.scalars(
        select(Volume)
        .where(Volume.project_id == project_id)
        .order_by(Volume.seq.desc())
    ).first()
    volume = Volume(
        project_id=project_id,
        seq=(last.seq + 1) if last else 0,
        name=name,
        purpose=fields.get("purpose") or "",
        summary=fields.get("summary") or "",
        act_seq=fields.get("act_seq"),
        target_words=_positive_int(fields.get("target_words"), "目标字数"),
        status=normalize_status(fields.get("status")),
        source_run_id=fields.get("source_run_id"),
    )
    session.add(volume)
    session.commit()
    return volume


def update_volume(session: Session, volume_id: str, **fields) -> Volume:
    volume = session.get(Volume, volume_id)
    if volume is None:
        raise ValueError(f"卷不存在：{volume_id}")
    # 先验后改：后面的校验失败时不能留下半截改动。任一步抛错都回滚。
    try:
        if "name" in fields:
            volume.name = _clean_name(fields.get("name"), "卷名")
        if "purpose" in fields:
            volume.purpose = fields.get("purpose") or ""
        if "summary" in fields:
            volume.summary = fields.get("summary") or ""
        if "act_seq" in fields:
            value = fields.get("act_seq")
            volume.act_seq = None if value in (None, "") else int(value)
        if "target_words" in fields:
            volume.target_words = _positive_int(fields.get("target_words"), "目标字数")
        if "status" in fields:
            volume.status = normalize_status(fields.get("status"))
        if "source_run_id" in fields:
            volume.source_run_id = fields.get("source_run_id")
        session.commit()
    except Exception:
        session.rollback()
        raise
    return volume


def delete_volume(session: Session, volume_id: str) -> None:
    volume = session.get(Volume, volume_id)
    if volume is None:
        raise ValueError(f"卷不存在：{volume_id}")
    session.delete(volume)
    session.commit()


def move_volume(session: Session, volume_id: str, direction: str) -> Volume:
    volume = session.get(Volume, volume_id)
    if volume is None:
        raise ValueError(f"卷不存在：{volume_id}")
    if direction not in ("up", "down"):
        raise ValueError("移动方向只能是 up 或 down")
    ordered = _ordered_volumes(session, volume.project_id)
    index = next(i for i, item in enumerate(ordered) if item.id == volume_id)
    target = index - 1 if direction == "up" else index + 1
    if target < 0 or target >= len(ordered):
        return volume
    ordered.insert(target, ordered.pop(index))
    for position, item in enumerate(ordered):
        item.seq = position
    session.commit()
    return volume


def create_chapter(session: Session, volume_id: str, **fields) -> Chapter:
    volume = session.get(Volume, volume_id)
    if volume is None:
        raise ValueError(f"卷不存在：{volume_id}")
    title = _clean_name(fields.get("title"), "章标题")
    last = session.scalars(
        select(Chapter)
        .where(Chapter.volume_id == volume_id)
        .order_by(Chapter.seq.desc())
    ).first()
    chapter = Chapter(
        volume_id=volume_id,
        seq=(last.seq + 1) if last else 0,
        title=title,
        pov=fields.get("pov") or "",
        target_words=_positive_int(fields.get("target_words"), "目标字数"),
        emotional_tone=fields.get("emotional_tone") or "",
        lines_json=[str(item) for item in (fields.get("lines") or []) if str(item).strip()],
        hook=fields.get("hook") or "",
        summary=fields.get("summary") or "",
        conflict_level=_level(fields.get("conflict_level"), "冲突强度", 5),
        dialogue_ratio=_ratio(fields.get("dialogue_ratio")),
        hook_strength=_level(fields.get("hook_strength"), "钩子强度", 5),
        status=normalize_status(fields.get("status")),
        source_run_id=fields.get("source_run_id"),
    )
    session.add(chapter)
    session.commit()
    return chapter


def update_chapter(session: Session, chapter_id: str, **fields) -> Chapter:
    chapter = session.get(Chapter, chapter_id)
    if chapter is None:
        raise ValueError(f"章不存在：{chapter_id}")
    try:
        if "title" in fields:
            chapter.title = _clean_name(fields.get("title"), "章标题")
        if "pov" in fields:
            chapter.pov = fields.get("pov") or ""
        if "target_words" in fields:
            chapter.target_words = _positive_int(fields.get("target_words"), "目标字数")
        if "emotional_tone" in fields:
            chapter.emotional_tone = fields.get("emotional_tone") or ""
        if "lines" in fields:
            chapter.lines_json = [
                str(item) for item in (fields.get("lines") or []) if str(item).strip()
            ]
        if "hook" in fields:
            chapter.hook = fields.get("hook") or ""
        if "summary" in fields:
            chapter.summary = fields.get("summary") or ""
        if "conflict_level" in fields:
            chapter.conflict_level = _level(fields.get("conflict_level"), "冲突强度", 5)
        if "dialogue_ratio" in fields:
            chapter.dialogue_ratio = _ratio(fields.get("dialogue_ratio"))
        if "hook_strength" in fields:
            chapter.hook_strength = _level(fields.get("hook_strength"), "钩子强度", 5)
        if "status" in fields:
            chapter.status = normalize_status(fields.get("status"))
        if "source_run_id" in fields:
            chapter.source_run_id = fields.get("source_run_id")
        session.commit()
    except Exception:
        session.rollback()
        raise
    return chapter


def delete_chapter(session: Session, chapter_id: str) -> None:
    chapter = session.get(Chapter, chapter_id)
    if chapter is None:
        raise ValueError(f"章不存在：{chapter_id}")
    session.delete(chapter)
    session.commit()


def move_chapter(session: Session, chapter_id: str, direction: str) -> Chapter:
    chapter = session.get(Chapter, chapter_id)
    if chapter is None:
        raise ValueError(f"章不存在：{chapter_id}")
    if direction not in ("up", "down"):
        raise ValueError("移动方向只能是 up 或 down")
    ordered = _ordered_chapters(session, chapter.volume_id)
    index = next(i for i, item in enumerate(ordered) if item.id == chapter_id)
    target = index - 1 if direction == "up" else index + 1
    if target < 0 or target >= len(ordered):
        return chapter
    ordered.insert(target, ordered.pop(index))
    for position, item in enumerate(ordered):
        item.seq = position
    session.commit()
    return chapter


def _scene_foreshadows(
    foreshadows: list[Foreshadow], scene_id: str
) -> dict[str, list[dict]]:
    return {
        "plants": [
            {"id": item.id, "name": item.name}
            for item in foreshadows
            if item.plant_scene_id == scene_id
        ],
        "pays": [
            {"id": item.id, "name": item.name}
            for item in foreshadows
            if item.plan_pay_scene_id == scene_id
        ],
    }


def build_tree(session: Session, project_id: str) -> list[dict]:
    """一次查询整棵树；场景内嵌伏笔的埋设/回收。"""
    foreshadows = list(
        session.scalars(select(Foreshadow).where(Foreshadow.project_id == project_id))
    )
    volumes = []
    for volume in _ordered_volumes(session, project_id):
        chapters = []
        for chapter in _ordered_chapters(session, volume.id):
            scenes = [
                {
                    "id": scene.id,
                    "chapter_id": scene.chapter_id,
                    "seq": scene.seq,
                    "goal": scene.goal,
                    "conflict": scene.conflict,
                    "turn": scene.turn,
                    "characters": scene.characters_json,
                    "location_id": scene.location_id,
                    "story_time": scene.story_time,
                    "pov": scene.pov,
                    "target_words_min": scene.target_words_min,
                    "target_words_max": scene.target_words_max,
                    "status": scene.status,
                    "source_run_id": scene.source_run_id,
                    "foreshadows": _scene_foreshadows(foreshadows, scene.id),
                }
                for scene in _ordered_scenes(session, chapter.id)
            ]
            chapters.append(
                {
                    "id": chapter.id,
                    "volume_id": chapter.volume_id,
                    "seq": chapter.seq,
                    "title": chapter.title,
                    "pov": chapter.pov,
                    "target_words": chapter.target_words,
                    "emotional_tone": chapter.emotional_tone,
                    "lines": chapter.lines_json,
                    "hook": chapter.hook,
                    "summary": chapter.summary,
                    "conflict_level": chapter.conflict_level,
                    "dialogue_ratio": chapter.dialogue_ratio,
                    "hook_strength": chapter.hook_strength,
                    "status": chapter.status,
                    "source_run_id": chapter.source_run_id,
                    "scenes": scenes,
                }
            )
        volumes.append(
            {
                "id": volume.id,
                "project_id": volume.project_id,
                "seq": volume.seq,
                "name": volume.name,
                "purpose": volume.purpose,
                "summary": volume.summary,
                "act_seq": volume.act_seq,
                "target_words": volume.target_words,
                "status": volume.status,
                "source_run_id": volume.source_run_id,
                "chapters": chapters,
            }
        )
    return volumes
```

- [ ] **Step 4: 跑服务层测试**

Run: `cd backend && uv run pytest tests/test_chapter_service.py -q`
Expected: PASS。

- [ ] **Step 5: 写 API 与 schema**

`backend/app/api/schemas.py` 追加：

```python
class VolumeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    purpose: str = ""
    summary: str = ""
    act_seq: int | None = None
    target_words: int | None = None
    status: str = "planned"


class VolumeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    purpose: str | None = None
    summary: str | None = None
    act_seq: int | None = None
    target_words: int | None = None
    status: str | None = None


class ChapterCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    pov: str = ""
    target_words: int | None = None
    emotional_tone: str = ""
    lines: list[str] = Field(default_factory=list)
    hook: str = ""
    summary: str = ""
    conflict_level: int | None = None
    dialogue_ratio: float | None = None
    hook_strength: int | None = None
    status: str = "planned"


class ChapterUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    pov: str | None = None
    target_words: int | None = None
    emotional_tone: str | None = None
    lines: list[str] | None = None
    hook: str | None = None
    summary: str | None = None
    conflict_level: int | None = None
    dialogue_ratio: float | None = None
    hook_strength: int | None = None
    status: str | None = None


class MoveRequest(BaseModel):
    direction: Literal["up", "down"]
```

`backend/app/api/chapters.py`：

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import ChapterCreate, ChapterUpdate, MoveRequest, VolumeCreate, VolumeUpdate
from app.db.session import get_session
from app.services import chapter_service

router = APIRouter(prefix="/api", tags=["chapters"])


def _volume_out(volume) -> dict:
    return {
        "id": volume.id,
        "project_id": volume.project_id,
        "seq": volume.seq,
        "name": volume.name,
        "purpose": volume.purpose,
        "summary": volume.summary,
        "act_seq": volume.act_seq,
        "target_words": volume.target_words,
        "status": volume.status,
        "source_run_id": volume.source_run_id,
    }


def _chapter_out(chapter) -> dict:
    return {
        "id": chapter.id,
        "volume_id": chapter.volume_id,
        "seq": chapter.seq,
        "title": chapter.title,
        "pov": chapter.pov,
        "target_words": chapter.target_words,
        "emotional_tone": chapter.emotional_tone,
        "lines": chapter.lines_json,
        "hook": chapter.hook,
        "summary": chapter.summary,
        "conflict_level": chapter.conflict_level,
        "dialogue_ratio": chapter.dialogue_ratio,
        "hook_strength": chapter.hook_strength,
        "status": chapter.status,
        "source_run_id": chapter.source_run_id,
    }


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/chapter-types")
def list_chapter_types() -> dict:
    """状态词表的唯一真相在 app/chapter_types.py；前端不硬编第二份。"""
    from app.chapter_types import STATUS_LABELS

    return {
        "statuses": [
            {"key": key, "label": label} for key, label in STATUS_LABELS.items()
        ]
    }


@router.get("/projects/{project_id}/chapters/tree")
def get_tree(project_id: str, session: Session = Depends(get_session)) -> dict:
    return {"volumes": chapter_service.build_tree(session, project_id)}


@router.post("/projects/{project_id}/volumes", status_code=201)
def create_volume(
    project_id: str, payload: VolumeCreate, session: Session = Depends(get_session)
) -> dict:
    try:
        volume = chapter_service.create_volume(session, project_id, **payload.model_dump())
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return _volume_out(volume)


@router.patch("/volumes/{volume_id}")
def update_volume(
    volume_id: str, payload: VolumeUpdate, session: Session = Depends(get_session)
) -> dict:
    try:
        volume = chapter_service.update_volume(
            session, volume_id, **payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        if "不存在" in str(exc):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise _bad_request(exc) from exc
    return _volume_out(volume)


@router.delete("/volumes/{volume_id}", status_code=204)
def delete_volume(volume_id: str, session: Session = Depends(get_session)) -> None:
    try:
        chapter_service.delete_volume(session, volume_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/volumes/{volume_id}/move")
def move_volume(
    volume_id: str, payload: MoveRequest, session: Session = Depends(get_session)
) -> dict:
    try:
        volume = chapter_service.move_volume(session, volume_id, payload.direction)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _volume_out(volume)


@router.post("/volumes/{volume_id}/chapters", status_code=201)
def create_chapter(
    volume_id: str, payload: ChapterCreate, session: Session = Depends(get_session)
) -> dict:
    try:
        chapter = chapter_service.create_chapter(session, volume_id, **payload.model_dump())
    except ValueError as exc:
        if "不存在" in str(exc):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise _bad_request(exc) from exc
    return _chapter_out(chapter)


@router.patch("/chapters/{chapter_id}")
def update_chapter(
    chapter_id: str, payload: ChapterUpdate, session: Session = Depends(get_session)
) -> dict:
    try:
        chapter = chapter_service.update_chapter(
            session, chapter_id, **payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        if "不存在" in str(exc):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise _bad_request(exc) from exc
    return _chapter_out(chapter)


@router.delete("/chapters/{chapter_id}", status_code=204)
def delete_chapter(chapter_id: str, session: Session = Depends(get_session)) -> None:
    try:
        chapter_service.delete_chapter(session, chapter_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/chapters/{chapter_id}/move")
def move_chapter(
    chapter_id: str, payload: MoveRequest, session: Session = Depends(get_session)
) -> dict:
    try:
        chapter = chapter_service.move_chapter(session, chapter_id, payload.direction)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _chapter_out(chapter)
```

`main.py`：导入 `chapters` 并加入 include 元组。

- [ ] **Step 6: 写 API 测试**

`backend/tests/test_chapters_api.py`：

```python
def test_tree_and_volume_chapter_crud_over_http(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()

    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "第一卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "第一章"}
    ).json()

    tree = client.get(f"/api/projects/{project['id']}/chapters/tree").json()["volumes"]
    assert tree[0]["name"] == "第一卷"
    assert tree[0]["chapters"][0]["title"] == "第一章"
    assert tree[0]["chapters"][0]["scenes"] == []

    updated = client.patch(
        f"/api/chapters/{chapter['id']}",
        json={"hook": "门后有人", "conflict_level": 4, "dialogue_ratio": 0.3},
    ).json()
    assert updated["hook"] == "门后有人"
    assert updated["conflict_level"] == 4

    moved = client.post(
        f"/api/volumes/{volume['id']}/move", json={"direction": "down"}
    )
    assert moved.status_code == 200

    assert client.delete(f"/api/chapters/{chapter['id']}").status_code == 204
    assert client.delete(f"/api/volumes/{volume['id']}").status_code == 204


def test_chapter_types_lists_the_status_vocabulary(client):
    payload = client.get("/api/chapter-types").json()
    assert payload["statuses"] == [
        {"key": "planned", "label": "规划中"},
        {"key": "confirmed", "label": "已确认"},
    ]


def test_volume_validation_is_a_readable_400(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    response = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "   "}
    )
    assert response.status_code == 400
    assert "卷名" in response.json()["detail"]


def test_chapter_bad_rhythm_is_a_readable_400(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "卷"}
    ).json()

    response = client.post(
        f"/api/volumes/{volume['id']}/chapters",
        json={"title": "章", "conflict_level": 9},
    )
    assert response.status_code == 400
    assert "冲突强度" in response.json()["detail"]


def test_missing_volume_is_404(client):
    assert client.patch("/api/volumes/nope", json={"name": "X"}).status_code == 404
    assert client.post("/api/volumes/nope/move", json={"direction": "up"}).status_code == 404
```

- [ ] **Step 7: 跑完整套件并提交**

Run: `cd backend && uv run pytest -q`
Expected: 298 + 11 = 309 passed。

```bash
git add backend/app/services/chapter_service.py backend/app/api/chapters.py backend/app/api/schemas.py backend/app/main.py backend/tests/test_chapter_service.py backend/tests/test_chapters_api.py
git commit -m "feat(chapters): 卷章服务、树与 API"
```

---

## Task 3: 场景服务、名称解析与伏笔挂接

**Files:**
- Create: `backend/app/services/foreshadow_service.py`（先放查找/新建的内部 helper）
- Create: `backend/app/services/scene_service.py`
- Modify: `backend/app/api/chapters.py`（场景路由与批量写入）
- Modify: `backend/app/api/schemas.py`（场景请求体）
- Test: `backend/tests/test_scene_service.py`, `backend/tests/test_chapters_api.py`（追加）

**Interfaces:**
- Produces:
  - `foreshadow_service.find_by_name(session, project_id, name) -> Foreshadow | None`
  - `foreshadow_service.find_or_create(session, project_id, name, source_run_id=None) -> Foreshadow`
  - `scene_service.resolve_entry_name(session, project_id, name, *, character_only=False) -> SettingEntry | None`（不抛错的查找，供计划 warning）
  - `scene_service.create_scene/update_scene/delete_scene/move_scene`
  - `scene_service.write_scenes(session, chapter_id, scenes, mode, source_run_id=None)`
  - `scene_service.scene_payload(session, scene) -> dict`

- [ ] **Step 1: 写失败测试 —— 名称解析与伏笔挂接**

新建 `backend/tests/test_scene_service.py`：

```python
import pytest

from app.db.models import Project, SettingEntry
from app.db.session import SessionLocal
from app.services import chapter_service, scene_service, world_service


def _project(session) -> Project:
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    return project


def _chapter(session, project):
    volume = chapter_service.create_volume(session, project.id, name="第一卷")
    return chapter_service.create_chapter(session, volume.id, title="第一章")


def _entries(session, project):
    chen = world_service.create_entry(
        session, project.id, type="character", name="陈默", aliases=["阿默"]
    )
    lin = world_service.create_entry(session, project.id, type="character", name="林晚")
    place = world_service.create_entry(session, project.id, type="place", name="南滨旧城")
    return chen, lin, place


def test_create_scene_resolves_names_and_links(session):
    project = _project(session)
    chapter = _chapter(session, project)
    chen, lin, place = _entries(session, project)

    scene = scene_service.create_scene(
        session,
        chapter.id,
        goal="找到录音带",
        conflict="档案室有人",
        turn="录音带里是自己的声音",
        characters=["陈默", "阿默"],
        location="南滨旧城",
        story_time="第三年·春",
        target_words_min=800,
        target_words_max=1500,
        foreshadow_plants=["失忆的录音带"],
    )

    assert scene.characters_json == [chen.id]
    assert scene.location_id == place.id
    with SessionLocal() as fresh:
        payload = scene_service.scene_payload(fresh, fresh.get(type(scene), scene.id))
        assert payload["foreshadows"]["plants"][0]["name"] == "失忆的录音带"


def test_alias_and_ambiguous_and_non_character(session):
    project = _project(session)
    chapter = _chapter(session, project)
    _entries(session, project)
    world_service.create_entry(
        session, project.id, type="faction", name="记忆交易局", aliases=["交易局"]
    )

    with pytest.raises(ValueError, match="不是人物"):
        scene_service.resolve_character_names(session, project.id, ["交易局"])

    with pytest.raises(ValueError, match="找不到"):
        scene_service.resolve_character_names(session, project.id, ["不存在"])


def test_ambiguous_alias_is_rejected(session):
    project = _project(session)
    _chapter(session, project)
    world_service.create_entry(
        session, project.id, type="character", name="甲", aliases=["阿明"]
    )
    world_service.create_entry(
        session, project.id, type="character", name="乙", aliases=["阿明"]
    )

    with pytest.raises(ValueError, match="同时匹配"):
        scene_service.resolve_character_names(session, project.id, ["阿明"])


def test_foreshadow_conflict_is_rejected_before_mutation(session):
    project = _project(session)
    chapter = _chapter(session, project)
    _entries(session, project)
    first = scene_service.create_scene(
        session, chapter.id, goal="埋", foreshadow_plants=["失忆的录音带"]
    )
    second = scene_service.create_scene(session, chapter.id, goal="收", foreshadow_pays=["失忆的录音带"])
    assert second.id != first.id

    with pytest.raises(ValueError, match="已经"):
        scene_service.create_scene(
            session, chapter.id, goal="重复埋", foreshadow_plants=["失忆的录音带"]
        )


def test_update_scene_clears_removed_links(session):
    project = _project(session)
    chapter = _chapter(session, project)
    _entries(session, project)
    scene = scene_service.create_scene(
        session, chapter.id, goal="埋", foreshadow_plants=["失忆的录音带"]
    )

    scene_service.update_scene(
        session, scene.id, foreshadow_plants=[]
    )

    with SessionLocal() as fresh:
        payload = scene_service.scene_payload(fresh, fresh.get(type(scene), scene.id))
        assert payload["foreshadows"]["plants"] == []


def test_write_scenes_replace_and_append_are_atomic(session):
    project = _project(session)
    chapter = _chapter(session, project)
    chen, _lin, place = _entries(session, project)

    first = scene_service.write_scenes(
        session,
        chapter.id,
        [
            {"goal": "开场", "characters": ["陈默"], "location": "南滨旧城"},
            {"goal": "转折", "characters": ["陈默"]},
        ],
        "replace",
    )
    assert [s.goal for s in first] == ["开场", "转折"]

    second = scene_service.write_scenes(
        session, chapter.id, [{"goal": "追加"}], "append"
    )
    assert second[-1].seq == 2

    with pytest.raises(ValueError, match="找不到"):
        scene_service.write_scenes(
            session, chapter.id, [{"goal": "坏", "characters": ["不存在"]}], "replace"
        )
    with SessionLocal() as fresh:
        goals = [s.goal for s in fresh.query(type(first[0])).filter_by(chapter_id=chapter.id).order_by("seq")]
        assert goals == ["开场", "转折", "追加"]


def test_move_scene_and_delete(session):
    project = _project(session)
    chapter = _chapter(session, project)
    a = scene_service.create_scene(session, chapter.id, goal="一")
    b = scene_service.create_scene(session, chapter.id, goal="二")

    scene_service.move_scene(session, b.id, "up")
    with SessionLocal() as fresh:
        rows = list(fresh.query(type(a)).filter_by(chapter_id=chapter.id).order_by("seq"))
        assert [row.goal for row in rows] == ["二", "一"]

    scene_service.delete_scene(session, a.id)
    with SessionLocal() as fresh:
        assert fresh.get(type(a), a.id) is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_scene_service.py -q`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 实现名称解析与场景服务**

`backend/app/services/foreshadow_service.py`（本任务先放查找/新建）：

```python
"""伏笔的唯一真相：按名称查找/新建（本任务），公开 CRUD 在 Task 4 补齐。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Foreshadow


def find_by_name(session: Session, project_id: str, name: str) -> Foreshadow | None:
    return session.scalars(
        select(Foreshadow).where(
            Foreshadow.project_id == project_id, Foreshadow.name == name.strip()
        )
    ).first()


def find_or_create(
    session: Session, project_id: str, name: str, source_run_id: str | None = None
) -> Foreshadow:
    clean = name.strip()
    if not clean:
        raise ValueError("伏笔名不能为空")
    existing = find_by_name(session, project_id, clean)
    if existing is not None:
        return existing
    foreshadow = Foreshadow(
        project_id=project_id, name=clean, source_run_id=source_run_id
    )
    session.add(foreshadow)
    session.flush()
    return foreshadow
```

`backend/app/services/scene_service.py`：

```python
"""场景的 CRUD、名称解析、伏笔挂接与批量写入。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chapter_types import normalize_status
from app.db.models import Chapter, Foreshadow, Scene, SettingEntry
from app.services import chapter_service, foreshadow_service


def _chapter(session: Session, chapter_id: str) -> Chapter:
    chapter = session.get(Chapter, chapter_id)
    if chapter is None:
        raise ValueError(f"章不存在：{chapter_id}")
    return chapter


def _entries(session: Session, project_id: str) -> list[SettingEntry]:
    return list(
        session.scalars(select(SettingEntry).where(SettingEntry.project_id == project_id))
    )


def resolve_entry_name(
    session: Session,
    project_id: str,
    name: str,
    *,
    character_only: bool = False,
) -> SettingEntry | None:
    """精确名或别名匹配；找不到返回 None，歧义抛 ValueError。

    计划阶段用 None 收集 warning；写入阶段调用方把 None 变成 400。
    """
    clean = (name or "").strip()
    if not clean:
        return None
    entries = _entries(session, project_id)
    by_name = [entry for entry in entries if entry.name == clean]
    if by_name:
        matches = by_name
    else:
        matches = [
            entry
            for entry in entries
            if clean in (entry.aliases_json or [])
        ]
    if not matches:
        return None
    if len(matches) > 1:
        labels = "、".join(entry.name for entry in matches)
        raise ValueError(f"名称「{clean}」同时匹配多个条目：{labels}")
    entry = matches[0]
    if character_only and entry.type != "character":
        raise ValueError(f"「{entry.name}」不是人物")
    return entry


def resolve_character_names(session: Session, project_id: str, names: list[str]) -> list[str]:
    out: list[str] = []
    for name in names or []:
        entry = resolve_entry_name(session, project_id, name, character_only=True)
        if entry is None:
            raise ValueError(f"人物「{name}」在世界观里找不到")
        if entry.id not in out:
            out.append(entry.id)
    return out


def resolve_location(session: Session, project_id: str, name: str | None) -> str | None:
    clean = (name or "").strip()
    if not clean:
        return None
    entry = resolve_entry_name(session, project_id, clean)
    if entry is None:
        raise ValueError(f"地点「{clean}」在世界观里找不到")
    return entry.id


def _foreshadow_conflicts(
    session: Session,
    project_id: str,
    desired: list[tuple[str, str]],
    scene_ids_to_replace: set[str],
) -> list[Foreshadow]:
    """校验并返回按名称需要的伏笔行（不存在的不在此处创建）。

    desired 是 (name, 'plant'|'pay') 列表；同一场景内重复先由调用方去重。
    同一名称不能出现在两个「埋设」或两个「计划回收」里。
    """
    seen_plant: dict[str, int] = {}
    seen_pay: dict[str, int] = {}
    for name, kind in desired:
        bucket = seen_plant if kind == "plant" else seen_pay
        bucket[name] = bucket.get(name, 0) + 1
    for name, count in seen_plant.items():
        if count > 1:
            raise ValueError(f"伏笔「{name}」在一次写入里被重复埋设")
    for name, count in seen_pay.items():
        if count > 1:
            raise ValueError(f"伏笔「{name}」在一次写入里被重复计划回收")

    rows: list[Foreshadow] = []
    for name, kind in desired:
        existing = foreshadow_service.find_by_name(session, project_id, name)
        if existing is None:
            continue
        linked = existing.plant_scene_id if kind == "plant" else existing.plan_pay_scene_id
        if linked is not None and linked not in scene_ids_to_replace:
            label = "埋设" if kind == "plant" else "计划回收"
            raise ValueError(f"伏笔「{name}」已经在另一个场景{label}")
        rows.append(existing)
    return rows


def _apply_scene_values(scene: Scene, fields: dict) -> None:
    if "goal" in fields:
        scene.goal = fields.get("goal") or ""
    if "conflict" in fields:
        scene.conflict = fields.get("conflict") or ""
    if "turn" in fields:
        scene.turn = fields.get("turn") or ""
    if "story_time" in fields:
        scene.story_time = fields.get("story_time") or ""
    if "pov" in fields:
        scene.pov = fields.get("pov") or ""
    if "target_words_min" in fields:
        scene.target_words_min = _positive_or_none(fields.get("target_words_min"), "字数下限")
    if "target_words_max" in fields:
        scene.target_words_max = _positive_or_none(fields.get("target_words_max"), "字数上限")
    if "status" in fields:
        scene.status = normalize_status(fields.get("status"))


def _positive_or_none(value, label: str) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label}必须是正整数")
    return value


def _validate_word_range(scene: Scene) -> None:
    if (
        scene.target_words_min is not None
        and scene.target_words_max is not None
        and scene.target_words_min > scene.target_words_max
    ):
        raise ValueError("目标字数下限不能大于上限")


def _apply_links(
    session: Session,
    project_id: str,
    scene: Scene,
    plant_names: list[str],
    pay_names: list[str],
    source_run_id: str | None,
    *,
    replaced_scene_ids: set[str] | None = None,
) -> None:
    """把本场景的埋设/回收名落到 foreshadow 表；先验后改。"""
    plant_names = [name.strip() for name in plant_names if name.strip()]
    pay_names = [name.strip() for name in pay_names if name.strip()]
    desired = [(name, "plant") for name in plant_names] + [(name, "pay") for name in pay_names]
    _foreshadow_conflicts(
        session, project_id, desired, replaced_scene_ids or set()
    )

    # 先清掉本场景不再需要的旧链接（只清指向本场景的）
    existing = session.scalars(
        select(Foreshadow).where(Foreshadow.project_id == project_id)
    ).all()
    for row in existing:
        if row.plant_scene_id == scene.id and row.name not in plant_names:
            row.plant_scene_id = None
        if row.plan_pay_scene_id == scene.id and row.name not in pay_names:
            row.plan_pay_scene_id = None

    for name in plant_names:
        row = foreshadow_service.find_or_create(session, project_id, name, source_run_id)
        row.plant_scene_id = scene.id
    for name in pay_names:
        row = foreshadow_service.find_or_create(session, project_id, name, source_run_id)
        row.plan_pay_scene_id = scene.id


def create_scene(session: Session, chapter_id: str, **fields) -> Scene:
    chapter = _chapter(session, chapter_id)
    project = chapter_service.get_project_for_chapter(session, chapter_id)
    # 先把所有外部名称解析完，再改库 —— 失败不留半截。
    character_ids = resolve_character_names(
        session, project.id, fields.get("characters") or []
    )
    location_id = resolve_location(session, project.id, fields.get("location"))
    plant_names = [
        name.strip() for name in (fields.get("foreshadow_plants") or []) if name.strip()
    ]
    pay_names = [
        name.strip() for name in (fields.get("foreshadow_pays") or []) if name.strip()
    ]
    _foreshadow_conflicts(
        session,
        project.id,
        [(name, "plant") for name in plant_names]
        + [(name, "pay") for name in pay_names],
        set(),
    )

    try:
        last = session.scalars(
            select(Scene).where(Scene.chapter_id == chapter_id).order_by(Scene.seq.desc())
        ).first()
        scene = Scene(
            chapter_id=chapter_id,
            seq=(last.seq + 1) if last else 0,
            characters_json=character_ids,
            location_id=location_id,
            status=normalize_status(fields.get("status")),
            source_run_id=fields.get("source_run_id"),
        )
        _apply_scene_values(scene, fields)
        _validate_word_range(scene)
        session.add(scene)
        session.flush()
        _apply_links(
            session, project.id, scene, plant_names, pay_names, fields.get("source_run_id")
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return scene


def update_scene(session: Session, scene_id: str, **fields) -> Scene:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise ValueError(f"场景不存在：{scene_id}")
    chapter = _chapter(session, scene.chapter_id)
    project = chapter_service.get_project_for_chapter(session, scene.chapter_id)

    character_ids = None
    if "characters" in fields:
        character_ids = resolve_character_names(session, project.id, fields.get("characters") or [])
    location_id = None
    if "location" in fields:
        location_id = resolve_location(session, project.id, fields.get("location"))
    plant_names = fields.get("foreshadow_plants")
    pay_names = fields.get("foreshadow_pays")
    if plant_names is not None:
        plant_names = [name.strip() for name in plant_names if name.strip()]
    if pay_names is not None:
        pay_names = [name.strip() for name in pay_names if name.strip()]
    if plant_names is not None or pay_names is not None:
        _foreshadow_conflicts(
            session,
            project.id,
            [(name, "plant") for name in (plant_names or [])]
            + [(name, "pay") for name in (pay_names or [])],
            {scene.id},
        )

    try:
        # 全部校验通过后才动 ORM 对象
        _apply_scene_values(scene, fields)
        if character_ids is not None:
            scene.characters_json = character_ids
        if "location" in fields:
            scene.location_id = location_id
        _validate_word_range(scene)
        if plant_names is not None or pay_names is not None:
            current_plants = [
                row.name
                for row in session.scalars(
                    select(Foreshadow).where(Foreshadow.plant_scene_id == scene.id)
                )
            ] if plant_names is None else plant_names
            current_pays = [
                row.name
                for row in session.scalars(
                    select(Foreshadow).where(Foreshadow.plan_pay_scene_id == scene.id)
                )
            ] if pay_names is None else pay_names
            _apply_links(
                session,
                project.id,
                scene,
                current_plants,
                current_pays,
                fields.get("source_run_id"),
                replaced_scene_ids={scene.id},
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return scene


def delete_scene(session: Session, scene_id: str) -> None:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise ValueError(f"场景不存在：{scene_id}")
    session.delete(scene)
    session.commit()


def move_scene(session: Session, scene_id: str, direction: str) -> Scene:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise ValueError(f"场景不存在：{scene_id}")
    if direction not in ("up", "down"):
        raise ValueError("移动方向只能是 up 或 down")
    ordered = list(
        session.scalars(
            select(Scene)
            .where(Scene.chapter_id == scene.chapter_id)
            .order_by(Scene.seq, Scene.created_at)
        )
    )
    index = next(i for i, item in enumerate(ordered) if item.id == scene_id)
    target = index - 1 if direction == "up" else index + 1
    if target < 0 or target >= len(ordered):
        return scene
    ordered.insert(target, ordered.pop(index))
    for position, item in enumerate(ordered):
        item.seq = position
    session.commit()
    return scene


def write_scenes(
    session: Session,
    chapter_id: str,
    scenes: list[dict],
    mode: str,
    source_run_id: str | None = None,
) -> list[Scene]:
    """批量替换/追加场景；所有名称与伏笔冲突先验完，再改库。"""
    if mode not in ("replace", "append"):
        raise ValueError("写入模式只能是 replace 或 append")
    chapter = _chapter(session, chapter_id)
    project = chapter_service.get_project_for_chapter(session, chapter_id)
    existing = list(
        session.scalars(select(Scene).where(Scene.chapter_id == chapter_id))
    )
    replaced_ids = {scene.id for scene in existing} if mode == "replace" else set()

    prepared = []
    all_plant: list[str] = []
    all_pay: list[str] = []
    for item in scenes:
        character_ids = resolve_character_names(
            session, project.id, item.get("characters") or []
        )
        location_id = resolve_location(session, project.id, item.get("location"))
        plants = [name.strip() for name in (item.get("foreshadow_plants") or []) if name.strip()]
        pays = [name.strip() for name in (item.get("foreshadow_pays") or []) if name.strip()]
        all_plant.extend(plants)
        all_pay.extend(pays)
        prepared.append((item, character_ids, location_id, plants, pays))

    # 同一批里重复埋设/回收在 _apply_links 里会被发现；这里先整体查一次冲突。
    _foreshadow_conflicts(
        session,
        project.id,
        [(name, "plant") for name in all_plant] + [(name, "pay") for name in all_pay],
        replaced_ids,
    )

    created: list[Scene] = []
    try:
        if mode == "replace":
            for scene in existing:
                session.delete(scene)
            session.flush()
            # FK SET NULL 是在库里发生的；identity map 里的旧伏笔对象仍带着
            # 指向已删场景的 ID。强制过期，避免随后 build_tree 读到旧链接。
            session.expire_all()
            start = 0
        else:
            last = session.scalars(
                select(Scene).where(Scene.chapter_id == chapter_id).order_by(Scene.seq.desc())
            ).first()
            start = (last.seq + 1) if last else 0

        for offset, (item, character_ids, location_id, plants, pays) in enumerate(prepared):
            scene = Scene(
                chapter_id=chapter_id,
                seq=start + offset,
                characters_json=character_ids,
                location_id=location_id,
                status=normalize_status(item.get("status")),
                source_run_id=source_run_id,
            )
            _apply_scene_values(scene, item)
            _validate_word_range(scene)
            session.add(scene)
            session.flush()
            _apply_links(
                session,
                project.id,
                scene,
                plants,
                pays,
                source_run_id,
                replaced_scene_ids=replaced_ids,
            )
            created.append(scene)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return created


def scene_payload(session: Session, scene: Scene) -> dict:
    rows = session.scalars(
        select(Foreshadow).where(Foreshadow.project_id == _project_id(session, scene))
    ).all()
    return {
        "id": scene.id,
        "chapter_id": scene.chapter_id,
        "seq": scene.seq,
        "goal": scene.goal,
        "conflict": scene.conflict,
        "turn": scene.turn,
        "characters": scene.characters_json,
        "location_id": scene.location_id,
        "story_time": scene.story_time,
        "pov": scene.pov,
        "target_words_min": scene.target_words_min,
        "target_words_max": scene.target_words_max,
        "status": scene.status,
        "source_run_id": scene.source_run_id,
        "foreshadows": {
            "plants": [
                {"id": row.id, "name": row.name}
                for row in rows
                if row.plant_scene_id == scene.id
            ],
            "pays": [
                {"id": row.id, "name": row.name}
                for row in rows
                if row.plan_pay_scene_id == scene.id
            ],
        },
    }


def _project_id(session: Session, scene: Scene) -> str:
    return chapter_service.get_project_for_chapter(session, scene.chapter_id).id
```

- [ ] **Step 4: 跑服务层测试**

Run: `cd backend && uv run pytest tests/test_scene_service.py -q`
Expected: PASS（若测试暴露 `update_scene` 的“当前 plants/pays”逻辑问题，按 spec 的「先验后改、移除清链接」修正实现，不改测试意图）。

- [ ] **Step 5: 加场景路由**

`api/schemas.py` 追加：

```python
class SceneCreate(BaseModel):
    goal: str = ""
    conflict: str = ""
    turn: str = ""
    characters: list[str] = Field(default_factory=list)  # 名称
    location: str | None = None                            # 名称
    story_time: str = ""
    pov: str = ""
    target_words_min: int | None = None
    target_words_max: int | None = None
    foreshadow_plants: list[str] = Field(default_factory=list)
    foreshadow_pays: list[str] = Field(default_factory=list)
    status: str = "planned"


class SceneUpdate(BaseModel):
    goal: str | None = None
    conflict: str | None = None
    turn: str | None = None
    characters: list[str] | None = None
    location: str | None = None
    story_time: str | None = None
    pov: str | None = None
    target_words_min: int | None = None
    target_words_max: int | None = None
    foreshadow_plants: list[str] | None = None
    foreshadow_pays: list[str] | None = None
    status: str | None = None


class SceneWrite(BaseModel):
    mode: Literal["replace", "append"]
    source_run_id: str | None = None
    scenes: list[dict[str, Any]] = Field(default_factory=list)
```

`api/chapters.py` 追加：

```python
@router.post("/chapters/{chapter_id}/scenes", status_code=201)
def create_scene(
    chapter_id: str, payload: SceneCreate, session: Session = Depends(get_session)
) -> dict:
    try:
        scene = scene_service.create_scene(session, chapter_id, **payload.model_dump())
    except ValueError as exc:
        if "不存在" in str(exc):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise _bad_request(exc) from exc
    return scene_service.scene_payload(session, scene)


@router.patch("/scenes/{scene_id}")
def update_scene(
    scene_id: str, payload: SceneUpdate, session: Session = Depends(get_session)
) -> dict:
    try:
        scene = scene_service.update_scene(
            session, scene_id, **payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        if "不存在" in str(exc):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise _bad_request(exc) from exc
    return scene_service.scene_payload(session, scene)


@router.delete("/scenes/{scene_id}", status_code=204)
def delete_scene(scene_id: str, session: Session = Depends(get_session)) -> None:
    try:
        scene_service.delete_scene(session, scene_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/scenes/{scene_id}/move")
def move_scene(
    scene_id: str, payload: MoveRequest, session: Session = Depends(get_session)
) -> dict:
    try:
        scene = scene_service.move_scene(session, scene_id, payload.direction)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return scene_service.scene_payload(session, scene)


@router.put("/chapters/{chapter_id}/scenes")
def write_scenes(
    chapter_id: str, payload: SceneWrite, session: Session = Depends(get_session)
) -> dict:
    try:
        scene_service.write_scenes(
            session, chapter_id, payload.scenes, payload.mode, payload.source_run_id
        )
    except ValueError as exc:
        if "不存在" in str(exc):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise _bad_request(exc) from exc
    return {"volumes": chapter_service.build_tree(session, chapter_service.get_project_for_chapter(session, chapter_id).id)}
```

导入 `scene_service`；`SceneWrite.scenes` 用 `dict` 保持计划/手工两种来源的弹性（手工路径仍走 `SceneCreate`，写入路径由服务层校验）。

- [ ] **Step 6: 追加 API 测试**

在 `backend/tests/test_chapters_api.py` 追加：

```python
def test_scene_crud_and_name_resolution_over_http(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    chen = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "人物", "name": "陈默"}
    ).json()
    place = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "地理", "name": "南滨"}
    ).json()
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "第一卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "第一章"}
    ).json()

    scene = client.post(
        f"/api/chapters/{chapter['id']}/scenes",
        json={
            "goal": "找到录音带",
            "characters": ["陈默"],
            "location": "南滨",
            "foreshadow_plants": ["失忆的录音带"],
        },
    ).json()
    assert scene["characters"] == [chen["id"]]
    assert scene["location_id"] == place["id"]
    assert scene["foreshadows"]["plants"][0]["name"] == "失忆的录音带"

    tree = client.get(f"/api/projects/{project['id']}/chapters/tree").json()["volumes"]
    assert tree[0]["chapters"][0]["scenes"][0]["goal"] == "找到录音带"


def test_unknown_character_name_is_a_readable_400(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "章"}
    ).json()

    response = client.post(
        f"/api/chapters/{chapter['id']}/scenes",
        json={"goal": "目标", "characters": ["不存在"]},
    )
    assert response.status_code == 400
    assert "找不到" in response.json()["detail"]
```

追加真正的写入测试：

```python
def test_scene_bulk_write_replace_and_append(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "人物", "name": "陈默"}
    )
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "章"}
    ).json()

    first = client.put(
        f"/api/chapters/{chapter['id']}/scenes",
        json={
            "mode": "replace",
            "scenes": [{"goal": "开场", "characters": ["陈默"]}],
        },
    )
    assert first.status_code == 200

    second = client.put(
        f"/api/chapters/{chapter['id']}/scenes",
        json={"mode": "append", "scenes": [{"goal": "追加"}]},
    )
    assert second.status_code == 200
    scenes = second.json()["volumes"][0]["chapters"][0]["scenes"]
    assert [scene["goal"] for scene in scenes] == ["开场", "追加"]
```

- [ ] **Step 7: 跑完整套件并提交**

Run: `cd backend && uv run pytest -q`
Expected: 309 + 9 = 318 passed。

```bash
git add backend/app/services/foreshadow_service.py backend/app/services/scene_service.py backend/app/api/chapters.py backend/app/api/schemas.py backend/tests/test_scene_service.py backend/tests/test_chapters_api.py
git commit -m "feat(scenes): 场景服务、名称解析与伏笔挂接"
```

---

## Task 4: 伏笔的公开 CRUD 与 API

**Files:**
- Modify: `backend/app/services/foreshadow_service.py`
- Create: `backend/app/api/foreshadows.py`
- Modify: `backend/app/api/schemas.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_foreshadow_service.py`, `backend/tests/test_foreshadows_api.py`

**Interfaces:**
- Produces:
  - `list_foreshadows(session, project_id) -> list[Foreshadow]`
  - `create_foreshadow(session, project_id, **fields) -> Foreshadow`
  - `update_foreshadow(session, foreshadow_id, **fields) -> Foreshadow`
  - `delete_foreshadow(session, foreshadow_id) -> None`
  - API `/api/projects/{id}/foreshadows`（GET/POST）、`/api/foreshadows/{id}`（PATCH/DELETE）。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_foreshadow_service.py`：

```python
import pytest

from app.db.models import Project
from app.services import chapter_service, foreshadow_service, scene_service


def _project(session):
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    return project


def _chapter(session, project):
    volume = chapter_service.create_volume(session, project.id, name="卷")
    return chapter_service.create_chapter(session, volume.id, title="章")


def test_create_list_update_delete(session):
    project = _project(session)
    created = foreshadow_service.create_foreshadow(
        session, project.id, name="失忆的录音带", note="主角的过去"
    )
    assert [row.id for row in foreshadow_service.list_foreshadows(session, project.id)] == [created.id]

    updated = foreshadow_service.update_foreshadow(
        session, created.id, name="录音带", status="confirmed"
    )
    assert updated.name == "录音带"
    assert updated.status == "confirmed"

    foreshadow_service.delete_foreshadow(session, created.id)
    assert foreshadow_service.list_foreshadows(session, project.id) == []


def test_duplicate_name_is_a_readable_error(session):
    project = _project(session)
    foreshadow_service.create_foreshadow(session, project.id, name="录音带")
    with pytest.raises(ValueError, match="已经"):
        foreshadow_service.create_foreshadow(session, project.id, name="录音带")


def test_plan_pay_scene_must_belong_to_the_project(session):
    project = _project(session)
    chapter = _chapter(session, project)
    scene = scene_service.create_scene(session, chapter.id, goal="收")
    foreshadow = foreshadow_service.create_foreshadow(session, project.id, name="录音带")

    updated = foreshadow_service.update_foreshadow(
        session, foreshadow.id, plan_pay_scene_id=scene.id
    )
    assert updated.plan_pay_scene_id == scene.id

    with pytest.raises(ValueError, match="场景不存在"):
        foreshadow_service.update_foreshadow(
            session, foreshadow.id, plan_pay_scene_id="nope"
        )
```

`backend/tests/test_foreshadows_api.py`：

```python
def test_foreshadow_crud_over_http(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()

    created = client.post(
        f"/api/projects/{project['id']}/foreshadows",
        json={"name": "失忆的录音带", "note": "主角的过去"},
    ).json()
    assert created["name"] == "失忆的录音带"

    listed = client.get(f"/api/projects/{project['id']}/foreshadows").json()
    assert [row["id"] for row in listed] == [created["id"]]

    updated = client.patch(
        f"/api/foreshadows/{created['id']}",
        json={"name": "录音带", "status": "confirmed"},
    ).json()
    assert updated["name"] == "录音带"
    assert updated["status"] == "confirmed"

    assert client.delete(f"/api/foreshadows/{created['id']}").status_code == 204
    assert client.get(f"/api/projects/{project['id']}/foreshadows").json() == []
```

- [ ] **Step 2: 实现服务**

在 `foreshadow_service.py` 追加：

```python
from app.chapter_types import normalize_status
from app.db.models import Scene


def list_foreshadows(session: Session, project_id: str) -> list[Foreshadow]:
    return list(
        session.scalars(
            select(Foreshadow)
            .where(Foreshadow.project_id == project_id)
            .order_by(Foreshadow.created_at)
        )
    )


def _clean_name(value: str | None) -> str:
    name = (value or "").strip()
    if not name:
        raise ValueError("伏笔名不能为空")
    return name


def create_foreshadow(session: Session, project_id: str, **fields) -> Foreshadow:
    name = _clean_name(fields.get("name"))
    if find_by_name(session, project_id, name) is not None:
        raise ValueError(f"这个项目里已经有叫「{name}」的伏笔了")
    row = Foreshadow(
        project_id=project_id,
        name=name,
        note=fields.get("note") or "",
        status=normalize_status(fields.get("status")),
        source_run_id=fields.get("source_run_id"),
    )
    session.add(row)
    session.commit()
    return row


def update_foreshadow(session: Session, foreshadow_id: str, **fields) -> Foreshadow:
    row = session.get(Foreshadow, foreshadow_id)
    if row is None:
        raise ValueError(f"伏笔不存在：{foreshadow_id}")
    try:
        if "name" in fields:
            name = _clean_name(fields.get("name"))
            other = find_by_name(session, row.project_id, name)
            if other is not None and other.id != row.id:
                raise ValueError(f"这个项目里已经有叫「{name}」的伏笔了")
            row.name = name
        if "note" in fields:
            row.note = fields.get("note") or ""
        if "plan_pay_scene_id" in fields:
            scene_id = fields.get("plan_pay_scene_id")
            if scene_id:
                scene = session.get(Scene, scene_id)
                if scene is None:
                    raise ValueError(f"场景不存在：{scene_id}")
                if get_project_for_scene(session, scene) != row.project_id:
                    raise ValueError(f"场景不属于这个项目：{scene_id}")
            row.plan_pay_scene_id = scene_id or None
        if "status" in fields:
            row.status = normalize_status(fields.get("status"))
        session.commit()
    except Exception:
        session.rollback()
        raise
    return row


def delete_foreshadow(session: Session, foreshadow_id: str) -> None:
    row = session.get(Foreshadow, foreshadow_id)
    if row is None:
        raise ValueError(f"伏笔不存在：{foreshadow_id}")
    session.delete(row)
    session.commit()


def get_project_for_scene(session: Session, scene: Scene) -> str:
    from app.services.chapter_service import get_project_for_chapter

    return get_project_for_chapter(session, scene.chapter_id).id
```

- [ ] **Step 3: 实现 API**

`api/schemas.py` 追加：

```python
class ForeshadowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    note: str = ""
    status: str = "planned"


class ForeshadowUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    note: str | None = None
    plan_pay_scene_id: str | None = None
    status: str | None = None
```

`api/foreshadows.py`：

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import ForeshadowCreate, ForeshadowUpdate
from app.db.session import get_session
from app.services import foreshadow_service

router = APIRouter(prefix="/api", tags=["foreshadows"])


def _out(row) -> dict:
    return {
        "id": row.id,
        "project_id": row.project_id,
        "name": row.name,
        "note": row.note,
        "plant_scene_id": row.plant_scene_id,
        "plan_pay_scene_id": row.plan_pay_scene_id,
        "status": row.status,
        "source_run_id": row.source_run_id,
    }


@router.get("/projects/{project_id}/foreshadows")
def list_foreshadows(project_id: str, session: Session = Depends(get_session)) -> list[dict]:
    return [_out(row) for row in foreshadow_service.list_foreshadows(session, project_id)]


@router.post("/projects/{project_id}/foreshadows", status_code=201)
def create_foreshadow(
    project_id: str, payload: ForeshadowCreate, session: Session = Depends(get_session)
) -> dict:
    try:
        row = foreshadow_service.create_foreshadow(session, project_id, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _out(row)


@router.patch("/foreshadows/{foreshadow_id}")
def update_foreshadow(
    foreshadow_id: str, payload: ForeshadowUpdate, session: Session = Depends(get_session)
) -> dict:
    try:
        row = foreshadow_service.update_foreshadow(
            session, foreshadow_id, **payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        if "不存在" in str(exc):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _out(row)


@router.delete("/foreshadows/{foreshadow_id}", status_code=204)
def delete_foreshadow(foreshadow_id: str, session: Session = Depends(get_session)) -> None:
    try:
        foreshadow_service.delete_foreshadow(session, foreshadow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

`main.py` 导入并挂载 `foreshadows`。

- [ ] **Step 4: 跑完整套件并提交**

Run: `cd backend && uv run pytest -q`
Expected: 318 + 5 = 323 passed。

```bash
git add backend/app/services/foreshadow_service.py backend/app/api/foreshadows.py backend/app/api/schemas.py backend/app/main.py backend/tests/test_foreshadow_service.py backend/tests/test_foreshadows_api.py
git commit -m "feat(foreshadows): 伏笔 CRUD 与 API"
```

---

## Task 5: 四个上下文槽位

**Files:**
- Modify: `backend/app/runtime/context.py`
- Modify: `backend/app/services/slot_source.py`
- Test: `backend/tests/test_slot_source.py`, `backend/tests/test_context.py`

**Interfaces:**
- Produces: `world_context()`、`timeline()`、`volume_outline()`、`chapter_outline()` on `DbSlotSource`/`SlotSource`; four `SlotSpec`s.

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_slot_source.py` 追加：

```python
def test_world_context_lists_entries_with_character_fields(session):
    project = _seed(session)
    from app.db.models import SettingEntry
    from app.world_types import CHARACTER_FIELDS

    session.add(SettingEntry(project_id=project.id, type="character", name="陈默",
                             aliases_json=["阿默"], summary="主角",
                             desire="找回记忆", fear="想起自己做过的事",
                             current_state="暂居南滨"))
    session.add(SettingEntry(project_id=project.id, type="rule", name="死者不能复活",
                             hardness="hard", summary="体系根基"))
    session.commit()

    text = DbSlotSource(session, project.id).world_context()

    assert "陈默" in text and "阿默" in text
    assert "欲望" in text and "找回记忆" in text
    assert "硬规则" in text
    assert "死者不能复活" in text


def test_timeline_renders_events(session):
    project = _seed(session)
    from app.db.models import SettingEntry, TimelineEvent

    character = SettingEntry(project_id=project.id, type="character", name="陈默")
    session.add(character)
    session.commit()
    session.add(TimelineEvent(project_id=project.id, title="初遇", story_time="第三年·春",
                              participants_json=[character.id], description="录音带"))
    session.commit()

    text = DbSlotSource(session, project.id).timeline()

    assert "初遇" in text and "第三年·春" in text and "陈默" in text


def test_volume_and_chapter_outline_are_scoped(session):
    project = _seed(session)
    from app.services import chapter_service, scene_service

    volume = chapter_service.create_volume(session, project.id, name="第一卷", purpose="立目标")
    chapter = chapter_service.create_chapter(session, volume.id, title="第一章", pov="陈默")
    scene_service.create_scene(session, chapter.id, goal="找到录音带")

    volume_text = DbSlotSource(session, project.id, extra_slots={"volume_id": volume.id}).volume_outline()
    chapter_text = DbSlotSource(
        session, project.id, extra_slots={"chapter_id": chapter.id, "volume_id": volume.id}
    ).chapter_outline()

    assert "第一卷" in volume_text and "第一章" in volume_text
    assert "第一章" in chapter_text and "找到录音带" in chapter_text
    assert DbSlotSource(session, project.id).volume_outline() is None
    assert DbSlotSource(session, project.id).chapter_outline() is None
```

在 `backend/tests/test_context.py` 追加：

```python
def test_new_slots_are_registered():
    for key in ("world_context", "timeline", "volume_outline", "chapter_outline"):
        assert key in SLOT_REGISTRY
```

- [ ] **Step 2: 实现槽位**

`runtime/context.py`：
- `SlotSource` 协议加四个方法。
- `SLOT_REGISTRY` 加：
```python
SlotSpec("world_context", "世界观摘要", P_HIGH, "summarize"),
SlotSpec("chapter_outline", "本章章纲", P_HIGH, "summarize"),
SlotSpec("volume_outline", "本卷纲要", P_HIGH, "summarize"),
SlotSpec("timeline", "故事内时间线", P_MID, "summarize"),
```

`services/slot_source.py`：
- 导入 `Chapter`, `Foreshadow`, `Scene`, `SettingEntry`, `TimelineEvent`, `Volume`, `ENTRY_TYPES`, `HARDNESS_LEVELS`.
- 加 `_FIELD_LIMIT = 160`, `_clip`.
- `world_context`：
```python
def world_context(self) -> str | None:
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
        aliases = f"（别名：{'、'.join(entry.aliases_json or [])}）" if entry.aliases_json else ""
        parts = [f"【{label}】{entry.name}{aliases}"]
        summary = entry.summary or entry.description
        if summary:
            parts.append(f"概述：{_clip(summary)}")
        if entry.type == "character":
            for key, label in (("desire", "欲望"), ("fear", "恐惧"), ("current_state", "当前状态")):
                value = getattr(entry, key)
                if value:
                    parts.append(f"{label}：{_clip(value)}")
        if entry.type == "rule" and entry.hardness:
            parts.append(HARDNESS_LEVELS.get(entry.hardness, entry.hardness))
        lines.append(" — ".join(parts))
    return "\n".join(lines)
```
- `timeline`：
```python
def timeline(self) -> str | None:
    events = self._session.scalars(
        select(TimelineEvent)
        .where(TimelineEvent.project_id == self._project_id)
        .order_by(TimelineEvent.order_index, TimelineEvent.created_at)
    ).all()
    if not events:
        return None
    entries = {entry.id: entry.name for entry in self._session.scalars(
        select(SettingEntry).where(SettingEntry.project_id == self._project_id)
    )}
    lines = []
    for event in events:
        people = "、".join(entries.get(pid, "（已删除）") for pid in (event.participants_json or []))
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
```
- `volume_outline`:
```python
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
```
- `chapter_outline`:
```python
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
```
- `_clip` helper at module level.

- [ ] **Step 3: 跑测试与全套件**

Run: `cd backend && uv run pytest tests/test_slot_source.py tests/test_context.py -q`
Expected: PASS。
Run: `cd backend && uv run pytest -q`
Expected: 323 + 5 = 328 passed。

- [ ] **Step 4: 提交**

```bash
git add backend/app/runtime/context.py backend/app/services/slot_source.py backend/tests/test_slot_source.py backend/tests/test_context.py
git commit -m "feat(context): 世界观/时间线/本卷/本章四个槽位"
```

---

## Task 6: 两个预置智能体

**Files:**
- Modify: `backend/app/agents/roster.py`
- Test: `backend/tests/test_roster.py`

**Interfaces:**
- Produces: `CHAPTER_PLANNER_SCHEMA`、`SCENE_PLANNER_SCHEMA`、两段提示词、两个 `DEFAULT_ROSTER` 条目；`TASK_TYPES` 增加 `scene_plan`。

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_roster.py`：
- 把 `test_task_types_cover_documented_roster` 的任务列表加上 `"scene_plan"`。
- 追加：

```python
def test_chapter_planner_is_in_the_default_roster():
    entry = next(e for e in DEFAULT_ROSTER if e["key"] == "chapter_planner")
    assert entry["task_type"] == "chapter_plan"
    assert entry["context_slots"] == [
        "project_core",
        "story_bible",
        "architecture",
        "parsed_idea",
        "world_context",
        "tool_library",
    ]
    props = entry["output_schema"]["properties"]
    assert set(props) == {"volumes", "open_questions"}
    chapter = props["volumes"]["items"]["properties"]["chapters"]["items"]
    assert {"title", "pov", "target_words", "conflict_level", "dialogue_ratio", "hook_strength"} <= set(
        chapter["properties"]
    )
    assert "编造" in entry["system_prompt"]


def test_scene_planner_is_in_the_default_roster():
    entry = next(e for e in DEFAULT_ROSTER if e["key"] == "scene_planner")
    assert entry["task_type"] == "scene_plan"
    assert entry["context_slots"] == [
        "project_core",
        "story_bible",
        "architecture",
        "world_context",
        "timeline",
        "volume_outline",
        "chapter_outline",
        "tool_library",
    ]
    props = entry["output_schema"]["properties"]
    assert set(props) == {"scenes", "open_questions"}
    scene = props["scenes"]["items"]
    assert {"goal", "conflict", "turn", "characters", "location", "foreshadow_plants", "foreshadow_pays"} <= set(
        scene["properties"]
    )
    assert "编造" in entry["system_prompt"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_roster.py -q`
Expected: FAIL（两个条目不存在、`scene_plan` 不在任务类型里）。

- [ ] **Step 3: 实现契约与提示词**

在 `backend/app/agents/roster.py`：
- `TASK_TYPES` 加 `"scene_plan"`。
- 在 `WORLDBUILDER...` 之后加两个契约与两段提示词（提示词里只出现中文与 `{{ 槽位 }}`，不出现未列入槽位的英文单词）：

```python
CHAPTER_PLANNER_SCHEMA = {
    "type": "object",
    "required": ["volumes", "open_questions"],
    "properties": {
        "volumes": {
            "type": "array",
            "minItems": 1,
            "title": "卷",
            "items": {
                "type": "object",
                "required": ["name", "chapters"],
                "properties": {
                    "name": {"type": "string", "title": "卷名"},
                    "purpose": {"type": "string", "title": "本卷要做什么"},
                    "act_seq": {"type": "integer", "title": "对应第几幕（没有就省略）"},
                    "target_words": {"type": "integer", "title": "本卷目标字数"},
                    "summary": {"type": "string", "title": "本卷摘要"},
                    "chapters": {
                        "type": "array",
                        "minItems": 1,
                        "title": "章",
                        "items": {
                            "type": "object",
                            "required": ["title"],
                            "properties": {
                                "title": {"type": "string", "title": "章标题"},
                                "pov": {"type": "string", "title": "视角"},
                                "target_words": {"type": "integer", "title": "目标字数"},
                                "emotional_tone": {"type": "string", "title": "情绪基调"},
                                "lines": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "title": "推进的线",
                                },
                                "hook": {"type": "string", "title": "章末钩子"},
                                "summary": {"type": "string", "title": "本章摘要"},
                                "conflict_level": {"type": "integer", "title": "冲突强度（1–5）"},
                                "dialogue_ratio": {"type": "number", "title": "对话占比（0–1）"},
                                "hook_strength": {"type": "integer", "title": "钩子强度（1–5）"},
                            },
                        },
                    },
                },
            },
        },
        "open_questions": {
            "type": "array",
            "items": {"type": "string"},
            "title": "没把握的问题",
        },
    },
}

SCENE_PLANNER_SCHEMA = {
    "type": "object",
    "required": ["scenes", "open_questions"],
    "properties": {
        "scenes": {
            "type": "array",
            "minItems": 1,
            "title": "场景",
            "items": {
                "type": "object",
                "required": ["goal", "conflict", "turn"],
                "properties": {
                    "goal": {"type": "string", "title": "场景目标"},
                    "conflict": {"type": "string", "title": "冲突"},
                    "turn": {"type": "string", "title": "转折"},
                    "characters": {
                        "type": "array",
                        "items": {"type": "string"},
                        "title": "出场人物（用标准名）",
                    },
                    "location": {"type": "string", "title": "地点（用标准名）"},
                    "story_time": {"type": "string", "title": "故事内时间"},
                    "pov": {"type": "string", "title": "视角"},
                    "target_words_min": {"type": "integer", "title": "目标字数下限"},
                    "target_words_max": {"type": "integer", "title": "目标字数上限"},
                    "foreshadow_plants": {
                        "type": "array",
                        "items": {"type": "string"},
                        "title": "埋设的伏笔名",
                    },
                    "foreshadow_pays": {
                        "type": "array",
                        "items": {"type": "string"},
                        "title": "回收的伏笔名",
                    },
                },
            },
        },
        "open_questions": {
            "type": "array",
            "items": {"type": "string"},
            "title": "没把握的问题",
        },
    },
}

CHAPTER_PLANNER_PROMPT = """你是长篇小说章纲策划，服务对象是作者。你的产出是卷章纲候选，不是正文。

【项目核心】
{{ project_core }}

【故事圣经】
{{ story_bible }}

【幕骨架】
{{ architecture }}

【灵感解析卡】
{{ parsed_idea }}

【世界观】
{{ world_context }}

【可用结构工具】
{{ tool_library }}

要求：
1. 按幕骨架排卷；每卷要有本卷目标与卷末高潮，卷首承接上一卷；
2. 每卷排章；每章写视角、目标字数、情绪基调、推进的线、章末钩子、摘要，并估计冲突强度、对话占比、钩子强度；
3. 只用【世界观】里已有的人物、势力、地点、规则，不编造；没有合适素材时写进待确认问题；
4. 章数与字数符合项目目标；卷和章的目标字数要与项目目标量级一致；
5. 卷的幕序号只在能明确对应时填，不确定就省略并写进待确认问题；
6. 不写正文；没把握的写进待确认问题；返回符合输出契约的结构化结果。"""

SCENE_PLANNER_PROMPT = """你是长篇小说场景策划，服务对象是作者。你的产出是本章的场景卡候选，不是正文。

【项目核心】
{{ project_core }}

【故事圣经】
{{ story_bible }}

【幕骨架】
{{ architecture }}

【世界观】
{{ world_context }}

【故事内时间线】
{{ timeline }}

【本卷纲要】
{{ volume_outline }}

【本章章纲】
{{ chapter_outline }}

【可用结构工具】
{{ tool_library }}

要求：
1. 把本章拆成 3–6 个场景；每场有具体目标、冲突与转折；转折要让处境更糟或更难；
2. 只用【世界观】里已有的人物与地点名称，不编造；人物只用人物条目，地点可用任意条目；没有合适地点就省略并写进待确认问题；
3. 每场写故事内时间、视角、目标字数区间；沿用本章视角，除非有明确理由；
4. 埋设与回收的伏笔用名称；回收的伏笔必须是前文已埋设或本章埋设的；不确定的写进待确认问题；
5. 不写正文；返回符合输出契约的结构化结果。"""
```

- 在 `DEFAULT_ROSTER` 末尾加两个条目：

```python
    {
        "key": "chapter_planner",
        "name": "章纲策划",
        "role_label": "章节",
        "color": "#8b5cf6",
        "task_type": "chapter_plan",
        "system_prompt": CHAPTER_PLANNER_PROMPT,
        "context_slots": [
            "project_core",
            "story_bible",
            "architecture",
            "parsed_idea",
            "world_context",
            "tool_library",
        ],
        "output_schema": CHAPTER_PLANNER_SCHEMA,
        "param_profile": "strict",
        "note": "排卷章纲、标节奏，没把握就问，不编。",
    },
    {
        "key": "scene_planner",
        "name": "场景策划",
        "role_label": "场景",
        "color": "#f59e0b",
        "task_type": "scene_plan",
        "system_prompt": SCENE_PLANNER_PROMPT,
        "context_slots": [
            "project_core",
            "story_bible",
            "architecture",
            "world_context",
            "timeline",
            "volume_outline",
            "chapter_outline",
            "tool_library",
        ],
        "output_schema": SCENE_PLANNER_SCHEMA,
        "param_profile": "balanced",
        "note": "把一章拆成场景卡，只用世界观里已有的人物与地点。",
    },
```

- [ ] **Step 4: 跑测试**

Run: `cd backend && uv run pytest tests/test_roster.py tests/test_preset_service.py tests/test_seed_service.py -q`
Expected: PASS。特别注意 `test_preset_prompts_do_not_hand_list_field_keys`：提示词里只允许中文、槽位占位符与白名单里的 `v0`；上面两段提示词已避开 `POV` / `JSON` / `AI` 等英文词。

- [ ] **Step 5: 跑完整套件并提交**

Run: `cd backend && uv run pytest -q`
Expected: 328 + 2 = 330 passed。

```bash
git add backend/app/agents/roster.py backend/tests/test_roster.py
git commit -m "feat(agents): 章纲策划与场景策划预置角色卡"
```

---

## Task 7: 策划归一化、运行与章纲写入 API

**Files:**
- Create: `backend/app/services/chapter_plan_service.py`
- Modify: `backend/app/api/chapters.py`
- Modify: `backend/app/api/schemas.py`
- Test: `backend/tests/test_chapter_plan_service.py`
- Test: `backend/tests/test_chapters_api.py`（追加）

**Interfaces:**
- Produces:
  - `chapter_plan_service.normalize_chapter_plan(parsed, act_seqs)` → `(volumes, warnings)`
  - `chapter_plan_service.normalize_scene_plan(parsed, session, project_id)` → `(scenes, warnings)`
  - `chapter_plan_service.write_chapter_plan(session, project_id, volumes, mode, source_run_id)` → tree
  - API：`POST /api/projects/{id}/chapters/plan`、`POST /api/chapters/{id}/scenes/plan`、`PUT /api/projects/{id}/chapters`。

- [ ] **Step 1: 写失败测试 —— 归一化**

新建 `backend/tests/test_chapter_plan_service.py`：

```python
from app.db.models import Project
from app.services import chapter_plan_service


def test_normalize_chapter_plan_clamps_and_warns():
    parsed = {
        "volumes": [
            {
                "name": "第一卷",
                "act_seq": 9,
                "target_words": -3,
                "chapters": [
                    {
                        "title": "第一章",
                        "conflict_level": 9,
                        "dialogue_ratio": 2,
                        "hook_strength": 4,
                        "lines": ["主线"],
                    }
                ],
            }
        ],
        "open_questions": ["第二卷要不要换视角？"],
    }

    volumes, warnings = chapter_plan_service.normalize_chapter_plan(parsed, {1, 2})

    assert volumes[0]["name"] == "第一卷"
    assert volumes[0]["act_seq"] is None
    assert volumes[0]["target_words"] is None
    chapter = volumes[0]["chapters"][0]
    assert chapter["conflict_level"] is None
    assert chapter["dialogue_ratio"] is None
    assert chapter["hook_strength"] == 4
    assert chapter["lines"] == ["主线"]
    assert len(warnings) >= 4


def test_normalize_scene_plan_warns_unknown_names(session):
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    from app.services import world_service

    world_service.create_entry(session, project.id, type="character", name="陈默")

    parsed = {
        "scenes": [
            {
                "goal": "找到录音带",
                "conflict": "档案室有人",
                "turn": "录音带里是自己的声音",
                "characters": ["陈默", "不存在"],
                "location": "不存在的地方",
                "target_words_min": 1500,
                "target_words_max": 800,
                "foreshadow_plants": ["失忆的录音带"],
            }
        ],
        "open_questions": [],
    }

    scenes, warnings = chapter_plan_service.normalize_scene_plan(parsed, session, project.id)

    assert scenes[0]["characters"] == ["陈默", "不存在"]
    assert scenes[0]["target_words_min"] == 800
    assert scenes[0]["target_words_max"] == 1500
    assert any("不存在" in warning for warning in warnings)
    assert any("交换" in warning for warning in warnings)
```

- [ ] **Step 2: 实现归一化与写入**

新建 `backend/app/services/chapter_plan_service.py`：

```python
"""策划结果归一化与章纲写入。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chapter_types import normalize_status
from app.db.models import Chapter, Project, Volume
from app.services import chapter_service, scene_service


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _positive(value, warnings: list[str], label: str) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        warnings.append(f"{label}不是正整数，已清空")
        return None
    return value


def _level(value, warnings: list[str], label: str) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
        warnings.append(f"{label}不在 1–5，已清空")
        return None
    return value


def _ratio(value, warnings: list[str]) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        warnings.append("对话占比不在 0–1，已清空")
        return None
    return float(value)


def normalize_chapter_plan(
    parsed: dict | None, act_seqs: set[int]
) -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    if not isinstance(parsed, dict):
        return [], warnings
    raw_volumes = parsed.get("volumes")
    if not isinstance(raw_volumes, list):
        return [], warnings

    volumes: list[dict] = []
    for v_index, raw in enumerate(raw_volumes, start=1):
        if not isinstance(raw, dict):
            warnings.append(f"第{v_index}卷不是对象，已跳过")
            continue
        name = _text(raw.get("name"))
        if not name:
            warnings.append(f"第{v_index}卷缺少卷名")
        act_seq = raw.get("act_seq")
        if act_seq is not None and act_seq not in act_seqs:
            warnings.append(f"第{v_index}卷的幕序号 {act_seq} 不在当前幕骨架里，已清空")
            act_seq = None
        raw_chapters = raw.get("chapters")
        if not isinstance(raw_chapters, list):
            warnings.append(f"第{v_index}卷没有章列表")
            raw_chapters = []
        chapters: list[dict] = []
        for c_index, chapter in enumerate(raw_chapters, start=1):
            if not isinstance(chapter, dict):
                warnings.append(f"第{v_index}卷第{c_index}章不是对象，已跳过")
                continue
            title = _text(chapter.get("title"))
            if not title:
                warnings.append(f"第{v_index}卷第{c_index}章缺少标题")
            raw_lines = chapter.get("lines")
            lines = (
                [str(item).strip() for item in raw_lines if str(item).strip()]
                if isinstance(raw_lines, list)
                else []
            )
            chapters.append(
                {
                    "title": title,
                    "pov": _text(chapter.get("pov")),
                    "target_words": _positive(
                        chapter.get("target_words"),
                        warnings,
                        f"第{v_index}卷第{c_index}章目标字数",
                    ),
                    "emotional_tone": _text(chapter.get("emotional_tone")),
                    "lines": lines,
                    "hook": _text(chapter.get("hook")),
                    "summary": _text(chapter.get("summary")),
                    "conflict_level": _level(
                        chapter.get("conflict_level"),
                        warnings,
                        f"第{v_index}卷第{c_index}章冲突强度",
                    ),
                    "dialogue_ratio": _ratio(chapter.get("dialogue_ratio"), warnings),
                    "hook_strength": _level(
                        chapter.get("hook_strength"),
                        warnings,
                        f"第{v_index}卷第{c_index}章钩子强度",
                    ),
                    "status": "planned",
                }
            )
        volumes.append(
            {
                "name": name,
                "purpose": _text(raw.get("purpose")),
                "summary": _text(raw.get("summary")),
                "act_seq": act_seq,
                "target_words": _positive(
                    raw.get("target_words"), warnings, f"第{v_index}卷目标字数"
                ),
                "status": "planned",
                "chapters": chapters,
            }
        )
    return volumes, warnings


def _warn_name(
    session: Session, project_id: str, name: str, warnings: list[str], label: str, index: int
) -> None:
    try:
        entry = scene_service.resolve_entry_name(
            session, project_id, name, character_only=(label == "人物")
        )
    except ValueError as exc:
        warnings.append(f"第{index}个场景：{exc}")
        return
    if entry is None:
        warnings.append(f"第{index}个场景：{label}「{name}」在世界观里找不到")


def normalize_scene_plan(
    parsed: dict | None, session: Session, project_id: str
) -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    if not isinstance(parsed, dict):
        return [], warnings
    raw_scenes = parsed.get("scenes")
    if not isinstance(raw_scenes, list):
        return [], warnings

    scenes: list[dict] = []
    for index, raw in enumerate(raw_scenes, start=1):
        if not isinstance(raw, dict):
            warnings.append(f"第{index}个场景不是对象，已跳过")
            continue
        raw_characters = raw.get("characters")
        characters = (
            [str(item).strip() for item in raw_characters if str(item).strip()]
            if isinstance(raw_characters, list)
            else []
        )
        for name in characters:
            _warn_name(session, project_id, name, warnings, "人物", index)
        location = _text(raw.get("location"))
        if location:
            _warn_name(session, project_id, location, warnings, "地点", index)
        min_words = _positive(
            raw.get("target_words_min"), warnings, f"第{index}个场景字数下限"
        )
        max_words = _positive(
            raw.get("target_words_max"), warnings, f"第{index}个场景字数上限"
        )
        if min_words is not None and max_words is not None and min_words > max_words:
            min_words, max_words = max_words, min_words
            warnings.append(f"第{index}个场景的字数区间上下限颠倒，已交换")

        def names(key: str) -> list[str]:
            value = raw.get(key)
            return (
                [str(item).strip() for item in value if str(item).strip()]
                if isinstance(value, list)
                else []
            )

        scenes.append(
            {
                "goal": _text(raw.get("goal")),
                "conflict": _text(raw.get("conflict")),
                "turn": _text(raw.get("turn")),
                "characters": characters,
                "location": location,
                "story_time": _text(raw.get("story_time")),
                "pov": _text(raw.get("pov")),
                "target_words_min": min_words,
                "target_words_max": max_words,
                "foreshadow_plants": names("foreshadow_plants"),
                "foreshadow_pays": names("foreshadow_pays"),
            }
        )
    return scenes, warnings


def _strict_text(value, label: str) -> str:
    text = (value or "").strip() if isinstance(value, str) else ""
    if not text:
        raise ValueError(f"{label}不能为空")
    return text


def _strict_positive(value, label: str) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label}必须是正整数")
    return value


def _strict_level(value, label: str) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
        raise ValueError(f"{label}必须是 1–5 的整数")
    return value


def _strict_ratio(value) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ValueError("对话占比必须是 0–1 之间的数")
    return float(value)


def write_chapter_plan(
    session: Session,
    project_id: str,
    volumes: list[dict],
    mode: str,
    source_run_id: str | None = None,
) -> list[dict]:
    if mode not in ("replace", "append"):
        raise ValueError("写入模式只能是 replace 或 append")
    if not volumes:
        raise ValueError("章纲写入至少需要一卷")
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError(f"项目不存在：{project_id}")

    prepared: list[dict] = []
    for v_index, raw in enumerate(volumes, start=1):
        name = _strict_text(raw.get("name"), f"第{v_index}卷卷名")
        chapters: list[dict] = []
        for c_index, chapter in enumerate(raw.get("chapters") or [], start=1):
            title = _strict_text(chapter.get("title"), f"第{v_index}卷第{c_index}章标题")
            raw_lines = chapter.get("lines")
            lines = (
                [str(item).strip() for item in raw_lines if str(item).strip()]
                if isinstance(raw_lines, list)
                else []
            )
            chapters.append(
                {
                    "title": title,
                    "pov": chapter.get("pov") or "",
                    "target_words": _strict_positive(
                        chapter.get("target_words"),
                        f"第{v_index}卷第{c_index}章目标字数",
                    ),
                    "emotional_tone": chapter.get("emotional_tone") or "",
                    "lines": lines,
                    "hook": chapter.get("hook") or "",
                    "summary": chapter.get("summary") or "",
                    "conflict_level": _strict_level(
                        chapter.get("conflict_level"),
                        f"第{v_index}卷第{c_index}章冲突强度",
                    ),
                    "dialogue_ratio": _strict_ratio(chapter.get("dialogue_ratio")),
                    "hook_strength": _strict_level(
                        chapter.get("hook_strength"),
                        f"第{v_index}卷第{c_index}章钩子强度",
                    ),
                    "status": normalize_status(chapter.get("status")),
                }
            )
        prepared.append(
            {
                "name": name,
                "purpose": raw.get("purpose") or "",
                "summary": raw.get("summary") or "",
                "act_seq": raw.get("act_seq"),
                "target_words": _strict_positive(
                    raw.get("target_words"), f"第{v_index}卷目标字数"
                ),
                "status": normalize_status(raw.get("status")),
                "chapters": chapters,
            }
        )

    try:
        if mode == "replace":
            for volume in session.scalars(
                select(Volume).where(Volume.project_id == project_id)
            ):
                session.delete(volume)
            session.flush()
            # FK 级联删场景、伏笔链接置空都发生在库里；过期掉 identity map。
            session.expire_all()
            start_seq = 0
        else:
            last = session.scalars(
                select(Volume)
                .where(Volume.project_id == project_id)
                .order_by(Volume.seq.desc())
            ).first()
            start_seq = (last.seq + 1) if last else 0

        for v_offset, volume_data in enumerate(prepared):
            volume = Volume(
                project_id=project_id,
                seq=start_seq + v_offset,
                name=volume_data["name"],
                purpose=volume_data["purpose"],
                summary=volume_data["summary"],
                act_seq=volume_data["act_seq"],
                target_words=volume_data["target_words"],
                status=volume_data["status"],
                source_run_id=source_run_id,
            )
            session.add(volume)
            session.flush()
            for c_offset, chapter_data in enumerate(volume_data["chapters"]):
                session.add(
                    Chapter(
                        volume_id=volume.id,
                        seq=c_offset,
                        title=chapter_data["title"],
                        pov=chapter_data["pov"],
                        target_words=chapter_data["target_words"],
                        emotional_tone=chapter_data["emotional_tone"],
                        lines_json=chapter_data["lines"],
                        hook=chapter_data["hook"],
                        summary=chapter_data["summary"],
                        conflict_level=chapter_data["conflict_level"],
                        dialogue_ratio=chapter_data["dialogue_ratio"],
                        hook_strength=chapter_data["hook_strength"],
                        status=chapter_data["status"],
                        source_run_id=source_run_id,
                    )
                )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return chapter_service.build_tree(session, project_id)
```

- [ ] **Step 3: 加 API**

`api/schemas.py` 追加：

```python
class PlanChapter(BaseModel):
    title: str = ""
    pov: str = ""
    target_words: int | None = None
    emotional_tone: str = ""
    lines: list[str] = Field(default_factory=list)
    hook: str = ""
    summary: str = ""
    conflict_level: int | None = None
    dialogue_ratio: float | None = None
    hook_strength: int | None = None
    status: str = "planned"


class PlanVolume(BaseModel):
    name: str = ""
    purpose: str = ""
    summary: str = ""
    act_seq: int | None = None
    target_words: int | None = None
    status: str = "planned"
    chapters: list[PlanChapter] = Field(default_factory=list)


class ChapterPlanWrite(BaseModel):
    mode: Literal["replace", "append"]
    source_run_id: str | None = None
    volumes: list[PlanVolume] = Field(default_factory=list)
```

`api/chapters.py` 追加：

```python
from app.api._serializers import _run_out
from app.services import agent_service, architecture_service, chapter_plan_service, scene_service
from app.services.runtime_service import RuntimeService


def _plan_reason(result, kind: str) -> str | None:
    if result.structured:
        return None
    if result.parse_error:
        return result.parse_error
    error = result.error or {}
    if error.get("kind") == "template":
        if kind == "chapter":
            return (
                "章纲策划需要故事圣经、幕骨架与世界观：先去「架构推荐」采纳一套结构，"
                "再到「世界观」建至少一条设定。"
                f"（运行记录里说缺的是：{error.get('message') or '未知变量'}）"
            )
        return (
            "场景策划需要本卷纲要与本章章纲：先选中一章，并确认它的卷章结构与世界观已建好。"
            f"（运行记录里说缺的是：{error.get('message') or '未知变量'}）"
        )
    return error.get("message") or "这次运行没有得到可用的返回"


def _acts(session: Session, project_id: str) -> set[int]:
    _arch, acts = architecture_service.get_architecture(session, project_id)
    return {act.seq for act in acts}


@router.post("/projects/{project_id}/chapters/plan")
def plan_chapters(project_id: str, session: Session = Depends(get_session)) -> dict:
    agent = agent_service.find_by_task_type(session, "chapter_plan")
    if agent is None:
        raise HTTPException(status_code=500, detail="找不到章纲策划，请重新预置阵容")
    try:
        run, result = RuntimeService(session).execute(project_id, agent.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    volumes, warnings = chapter_plan_service.normalize_chapter_plan(
        result.parsed, _acts(session, project_id)
    )
    parsed = result.parsed or {}
    return {
        "run": _run_out(run),
        "volumes": volumes,
        "open_questions": (parsed.get("open_questions") or []) if result.structured else [],
        "warnings": warnings,
        "structured": result.structured,
        "parse_error": _plan_reason(result, "chapter"),
        "raw_text": result.raw_output,
    }


@router.post("/chapters/{chapter_id}/scenes/plan")
def plan_scenes(chapter_id: str, session: Session = Depends(get_session)) -> dict:
    from app.db.models import Chapter

    chapter = session.get(Chapter, chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail=f"章不存在：{chapter_id}")
    project = chapter_service.get_project_for_chapter(session, chapter_id)
    agent = agent_service.find_by_task_type(session, "scene_plan")
    if agent is None:
        raise HTTPException(status_code=500, detail="找不到场景策划，请重新预置阵容")
    try:
        run, result = RuntimeService(session).execute(
            project.id,
            agent.id,
            {"chapter_id": chapter.id, "volume_id": chapter.volume_id},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    scenes, warnings = chapter_plan_service.normalize_scene_plan(
        result.parsed, session, project.id
    )
    parsed = result.parsed or {}
    return {
        "run": _run_out(run),
        "scenes": scenes,
        "open_questions": (parsed.get("open_questions") or []) if result.structured else [],
        "warnings": warnings,
        "structured": result.structured,
        "parse_error": _plan_reason(result, "scene"),
        "raw_text": result.raw_output,
    }


@router.put("/projects/{project_id}/chapters")
def write_chapters(
    project_id: str, payload: ChapterPlanWrite, session: Session = Depends(get_session)
) -> dict:
    try:
        tree = chapter_plan_service.write_chapter_plan(
            session,
            project_id,
            [volume.model_dump() for volume in payload.volumes],
            payload.mode,
            payload.source_run_id,
        )
    except ValueError as exc:
        if "项目不存在" in str(exc):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise _bad_request(exc) from exc
    return {"volumes": tree}
```

- [ ] **Step 4: 追加 API 测试**

在 `backend/tests/test_chapters_api.py` 追加（使用与 P1b `test_world_api.py` 相同的假运行时方式）：

```python
CHAPTER_PLAN = json.dumps(
    {
        "volumes": [
            {
                "name": "候选卷",
                "purpose": "立目标",
                "chapters": [
                    {
                        "title": "候选章",
                        "pov": "陈默",
                        "target_words": 3000,
                        "conflict_level": 3,
                        "dialogue_ratio": 0.4,
                        "hook_strength": 4,
                        "lines": ["主线"],
                    }
                ],
            }
        ],
        "open_questions": ["第二卷要不要换视角？"],
    },
    ensure_ascii=False,
)

SCENE_PLAN = json.dumps(
    {
        "scenes": [
            {
                "goal": "找到录音带",
                "conflict": "档案室有人",
                "turn": "录音带里是自己的声音",
                "characters": ["陈默"],
                "location": "南滨旧城",
                "target_words_min": 800,
                "target_words_max": 1500,
                "foreshadow_plants": ["失忆的录音带"],
            }
        ],
        "open_questions": [],
    },
    ensure_ascii=False,
)


def _plan_slots(project_id: str) -> None:
    from app.db.models import (
        Act,
        Architecture,
        Chapter,
        Idea,
        SettingEntry,
        TimelineEvent,
        Volume,
    )
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        idea = Idea(project_id=project_id, raw_text="能听见死者遗言的验尸官")
        idea.parsed_json = {"genre": "悬疑", "premise": "记忆可交易", "open_questions": []}
        session.add(idea)
        arch = Architecture(project_id=project_id, logline="记忆清洁工")
        session.add(arch)
        session.flush()
        session.add(Act(architecture_id=arch.id, seq=1, name="第一幕"))
        session.add(
            SettingEntry(project_id=project_id, type="character", name="陈默")
        )
        session.add(
            SettingEntry(project_id=project_id, type="place", name="南滨旧城")
        )
        session.add(
            TimelineEvent(project_id=project_id, title="初遇", story_time="第三年·春")
        )
        volume = Volume(project_id=project_id, seq=0, name="第一卷")
        session.add(volume)
        session.flush()
        session.add(Chapter(volume_id=volume.id, seq=0, title="第一章", pov="陈默"))
        session.commit()


def _patch_runtime(monkeypatch, content: str) -> None:
    import httpx

    from app.runtime.llm import HttpxChatClient
    from app.services.runtime_service import RuntimeService

    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 30, "completion_tokens": 15},
            },
        )

    fake = HttpxChatClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(RuntimeService, "_resolve_client", lambda self, timeout: fake)


def test_chapter_plan_returns_candidates_without_writing(client, monkeypatch):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    _plan_slots(project["id"])
    _patch_runtime(monkeypatch, CHAPTER_PLAN)

    body = client.post(f"/api/projects/{project['id']}/chapters/plan").json()

    assert body["structured"] is True
    assert body["volumes"][0]["chapters"][0]["title"] == "候选章"
    assert body["open_questions"] == ["第二卷要不要换视角？"]
    assert body["warnings"] == []
    # 候选只在运行记录里：树仍是 _plan_slots 建的「第一卷 / 第一章」
    tree = client.get(f"/api/projects/{project['id']}/chapters/tree").json()["volumes"]
    assert tree[0]["name"] == "第一卷"
    assert tree[0]["chapters"][0]["title"] == "第一章"


def test_chapter_plan_write_replace_and_append(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()

    first = client.put(
        f"/api/projects/{project['id']}/chapters",
        json={
            "mode": "replace",
            "source_run_id": "run-1",
            "volumes": [
                {"name": "第一卷", "chapters": [{"title": "第一章"}]}
            ],
        },
    )
    assert first.status_code == 200
    volume = first.json()["volumes"][0]
    assert volume["source_run_id"] == "run-1"
    assert volume["chapters"][0]["source_run_id"] == "run-1"

    second = client.put(
        f"/api/projects/{project['id']}/chapters",
        json={
            "mode": "append",
            "volumes": [{"name": "第二卷", "chapters": [{"title": "第二章"}]}],
        },
    )
    assert [v["name"] for v in second.json()["volumes"]] == ["第一卷", "第二卷"]


def test_scene_plan_returns_candidates_without_writing(client, monkeypatch):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    _plan_slots(project["id"])
    chapter = client.get(f"/api/projects/{project['id']}/chapters/tree").json()["volumes"][0]["chapters"][0]
    _patch_runtime(monkeypatch, SCENE_PLAN)

    body = client.post(f"/api/chapters/{chapter['id']}/scenes/plan").json()

    assert body["structured"] is True
    assert body["scenes"][0]["goal"] == "找到录音带"
    assert body["warnings"] == []
    tree = client.get(f"/api/projects/{project['id']}/chapters/tree").json()["volumes"]
    assert tree[0]["chapters"][0]["scenes"] == []
```

**注意：** `_plan_slots` 必须只建一套卷/章；`test_scene_plan_returns_candidates_without_writing` 从树里取的就是它建的那一章，`chapter_outline` / `volume_outline` 的 `extra_slots` 才能对上。

- [ ] **Step 5: 跑完整套件并提交**

Run: `cd backend && uv run pytest -q`
Expected: 330 + 9 = 339 passed。

```bash
git add backend/app/services/chapter_plan_service.py backend/app/api/chapters.py backend/app/api/schemas.py backend/tests/test_chapter_plan_service.py backend/tests/test_chapters_api.py
git commit -m "feat(chapters): 策划归一化、运行与章纲写入"
```

---

## Task 8: 前端章节页（树 + 卷/章编辑器 + 基础场景编辑器）

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/components/chapters/ChapterTree.tsx`
- Create: `frontend/src/components/chapters/VolumeEditor.tsx`
- Create: `frontend/src/components/chapters/ChapterEditor.tsx`
- Create: `frontend/src/components/chapters/SceneEditor.tsx`
- Create: `frontend/src/pages/Chapters.tsx`

**Interfaces:**
- Consumes: Task 2 的树/卷/章 API、Task 3 的场景 API、`/api/chapter-types`。
- Produces: 可手工建卷/章/场景、编辑、移动、删除的 `/chapters` 页。

- [ ] **Step 1: 客户端类型与方法**

在 `frontend/src/api/client.ts` 追加：

```ts
export interface ChapterStatusOption {
  key: string
  label: string
}

export interface ChapterTypesResponse {
  statuses: ChapterStatusOption[]
}

export interface SceneNode {
  id: string
  chapter_id: string
  seq: number
  goal: string
  conflict: string
  turn: string
  characters: string[]
  location_id: string | null
  story_time: string
  pov: string
  target_words_min: number | null
  target_words_max: number | null
  status: string
  source_run_id: string | null
  foreshadows: { plants: { id: string; name: string }[]; pays: { id: string; name: string }[] }
}

export interface ChapterNode {
  id: string
  volume_id: string
  seq: number
  title: string
  pov: string
  target_words: number | null
  emotional_tone: string
  lines: string[]
  hook: string
  summary: string
  conflict_level: number | null
  dialogue_ratio: number | null
  hook_strength: number | null
  status: string
  source_run_id: string | null
  scenes: SceneNode[]
}

export interface VolumeNode {
  id: string
  project_id: string
  seq: number
  name: string
  purpose: string
  summary: string
  act_seq: number | null
  target_words: number | null
  status: string
  source_run_id: string | null
  chapters: ChapterNode[]
}

export type VolumeView = Omit<VolumeNode, 'chapters'>
export type ChapterView = Omit<ChapterNode, 'scenes'>
```

在 `api` 对象里追加：

```ts
  listChapterTypes: () => request<ChapterTypesResponse>('/api/chapter-types'),
  getChapterTree: (projectId: string) =>
    request<{ volumes: VolumeNode[] }>(`/api/projects/${projectId}/chapters/tree`),
  createVolume: (projectId: string, body: Record<string, unknown>) =>
    request<VolumeView>(`/api/projects/${projectId}/volumes`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  updateVolume: (volumeId: string, body: Record<string, unknown>) =>
    request<VolumeView>(`/api/volumes/${volumeId}`, {
      method: 'PATCH',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  deleteVolume: (volumeId: string) => request<void>(`/api/volumes/${volumeId}`, { method: 'DELETE' }),
  moveVolume: (volumeId: string, direction: 'up' | 'down') =>
    request<VolumeView>(`/api/volumes/${volumeId}/move`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ direction }),
    }),
  createChapter: (volumeId: string, body: Record<string, unknown>) =>
    request<ChapterView>(`/api/volumes/${volumeId}/chapters`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  updateChapter: (chapterId: string, body: Record<string, unknown>) =>
    request<ChapterView>(`/api/chapters/${chapterId}`, {
      method: 'PATCH',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  deleteChapter: (chapterId: string) =>
    request<void>(`/api/chapters/${chapterId}`, { method: 'DELETE' }),
  moveChapter: (chapterId: string, direction: 'up' | 'down') =>
    request<ChapterView>(`/api/chapters/${chapterId}/move`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ direction }),
    }),
  createScene: (chapterId: string, body: Record<string, unknown>) =>
    request<SceneNode>(`/api/chapters/${chapterId}/scenes`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  updateScene: (sceneId: string, body: Record<string, unknown>) =>
    request<SceneNode>(`/api/scenes/${sceneId}`, {
      method: 'PATCH',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  deleteScene: (sceneId: string) => request<void>(`/api/scenes/${sceneId}`, { method: 'DELETE' }),
  moveScene: (sceneId: string, direction: 'up' | 'down') =>
    request<SceneNode>(`/api/scenes/${sceneId}/move`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ direction }),
    }),
```

- [ ] **Step 2: 树组件**

`frontend/src/components/chapters/ChapterTree.tsx`：

```tsx
import type { VolumeNode } from '../../api/client'

export interface Selection {
  kind: 'volume' | 'chapter' | 'scene'
  id: string
}

export default function ChapterTree({
  volumes,
  selected,
  onSelect,
  onAddVolume,
  onAddChapter,
  onAddScene,
  onMove,
}: {
  volumes: VolumeNode[]
  selected: Selection | null
  onSelect: (selection: Selection) => void
  onAddVolume: () => void
  onAddChapter: (volumeId: string) => void
  onAddScene: (chapterId: string) => void
  onMove: (kind: Selection['kind'], id: string, direction: 'up' | 'down') => void
}) {
  const active = (kind: Selection['kind'], id: string) =>
    selected?.kind === kind && selected.id === id ? 'bg-slate-800' : 'hover:bg-slate-900'

  return (
    <nav className="space-y-3 text-sm">
      <button className="rounded border border-slate-700 px-3 py-1.5" onClick={onAddVolume}>
        新建卷
      </button>
      {volumes.map((volume) => (
        <div key={volume.id}>
          <div className="flex items-center gap-1">
            <button
              className={`flex-1 rounded px-2 py-1.5 text-left ${active('volume', volume.id)}`}
              onClick={() => onSelect({ kind: 'volume', id: volume.id })}
            >
              第{volume.seq + 1}卷 {volume.name}
            </button>
            <button className="px-1 text-xs text-indigo-400" onClick={() => onMove('volume', volume.id, 'up')}>
              ↑
            </button>
            <button className="px-1 text-xs text-indigo-400" onClick={() => onMove('volume', volume.id, 'down')}>
              ↓
            </button>
            <button className="px-1 text-xs text-emerald-400" onClick={() => onAddChapter(volume.id)}>
              +章
            </button>
          </div>
          <ul className="ml-4 space-y-1">
            {volume.chapters.map((chapter) => (
              <li key={chapter.id}>
                <div className="flex items-center gap-1">
                  <button
                    className={`flex-1 rounded px-2 py-1 text-left ${active('chapter', chapter.id)}`}
                    onClick={() => onSelect({ kind: 'chapter', id: chapter.id })}
                  >
                    {chapter.seq + 1}. {chapter.title}
                  </button>
                  <button className="px-1 text-xs text-indigo-400" onClick={() => onMove('chapter', chapter.id, 'up')}>
                    ↑
                  </button>
                  <button className="px-1 text-xs text-indigo-400" onClick={() => onMove('chapter', chapter.id, 'down')}>
                    ↓
                  </button>
                  <button className="px-1 text-xs text-emerald-400" onClick={() => onAddScene(chapter.id)}>
                    +场景
                  </button>
                </div>
                <ul className="ml-4 space-y-1">
                  {chapter.scenes.map((scene) => (
                    <li key={scene.id} className="flex items-center gap-1">
                      <button
                        className={`flex-1 rounded px-2 py-1 text-left text-xs ${active('scene', scene.id)}`}
                        onClick={() => onSelect({ kind: 'scene', id: scene.id })}
                      >
                        场景{scene.seq + 1}：{scene.goal || '（未写目标）'}
                      </button>
                      <button className="px-1 text-xs text-indigo-400" onClick={() => onMove('scene', scene.id, 'up')}>
                        ↑
                      </button>
                      <button className="px-1 text-xs text-indigo-400" onClick={() => onMove('scene', scene.id, 'down')}>
                        ↓
                      </button>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </div>
      ))}
      {volumes.length === 0 && (
        <p className="text-sm text-slate-500">还没有卷。点「新建卷」开始。</p>
      )}
    </nav>
  )
}
```

- [ ] **Step 3: 卷 / 章编辑器**

`VolumeEditor.tsx`：

```tsx
import { useEffect, useState } from 'react'
import type { ChapterStatusOption, VolumeNode } from '../../api/client'

export default function VolumeEditor({
  volume,
  statuses,
  busy,
  onSave,
  onDelete,
}: {
  volume: VolumeNode
  statuses: ChapterStatusOption[]
  busy: boolean
  onSave: (fields: Record<string, unknown>) => Promise<void>
  onDelete: () => Promise<void>
}) {
  const [draft, setDraft] = useState({
    name: '',
    purpose: '',
    summary: '',
    actSeq: '',
    targetWords: '',
    status: 'planned',
  })

  useEffect(() => {
    setDraft({
      name: volume.name,
      purpose: volume.purpose,
      summary: volume.summary,
      actSeq: volume.act_seq == null ? '' : String(volume.act_seq),
      targetWords: volume.target_words == null ? '' : String(volume.target_words),
      status: volume.status,
    })
  }, [volume.id, volume.name, volume.purpose, volume.summary, volume.act_seq, volume.target_words, volume.status])

  const set = (patch: Partial<typeof draft>) => setDraft({ ...draft, ...patch })

  return (
    <section className="space-y-3 rounded border border-slate-800 p-4 text-sm">
      <h3 className="text-sm font-medium text-slate-300">卷</h3>
      <label className="block">
        <span className="text-slate-500">卷名</span>
        <input className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.name} onChange={(e) => set({ name: e.target.value })} />
      </label>
      <label className="block">
        <span className="text-slate-500">本卷要做什么</span>
        <textarea className="mt-1 h-20 w-full rounded border border-slate-700 bg-slate-900 p-3"
                  value={draft.purpose} onChange={(e) => set({ purpose: e.target.value })} />
      </label>
      <label className="block">
        <span className="text-slate-500">摘要</span>
        <textarea className="mt-1 h-20 w-full rounded border border-slate-700 bg-slate-900 p-3"
                  value={draft.summary} onChange={(e) => set({ summary: e.target.value })} />
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-slate-500">对应第几幕</label>
        <input className="w-24 rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.actSeq} onChange={(e) => set({ actSeq: e.target.value })} placeholder="快照，可空" />
        <label className="text-slate-500">目标字数</label>
        <input className="w-32 rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.targetWords} onChange={(e) => set({ targetWords: e.target.value })} />
        <label className="text-slate-500">状态</label>
        <select className="rounded border border-slate-700 bg-slate-900 px-3 py-2"
                value={draft.status} onChange={(e) => set({ status: e.target.value })}>
          {statuses.map((status) => (
            <option key={status.key} value={status.key}>{status.label}</option>
          ))}
        </select>
      </div>
      <div className="flex items-center gap-2">
        <button className="rounded bg-indigo-600 px-4 py-2 disabled:opacity-50" disabled={busy}
                onClick={() => onSave({
                  name: draft.name.trim(),
                  purpose: draft.purpose,
                  summary: draft.summary,
                  act_seq: draft.actSeq.trim() ? Number(draft.actSeq) : null,
                  target_words: draft.targetWords.trim() ? Number(draft.targetWords) : null,
                  status: draft.status,
                })}>
          保存
        </button>
        <button className="rounded border border-amber-700 px-4 py-2 text-amber-400" disabled={busy}
                onClick={onDelete}>
          删除
        </button>
      </div>
    </section>
  )
}
```

`ChapterEditor.tsx`：

```tsx
import { useEffect, useState } from 'react'
import type { ChapterNode, ChapterStatusOption } from '../../api/client'

export default function ChapterEditor({
  chapter,
  statuses,
  busy,
  onSave,
  onDelete,
}: {
  chapter: ChapterNode
  statuses: ChapterStatusOption[]
  busy: boolean
  onSave: (fields: Record<string, unknown>) => Promise<void>
  onDelete: () => Promise<void>
}) {
  const [draft, setDraft] = useState({
    title: '',
    pov: '',
    targetWords: '',
    emotionalTone: '',
    lines: '',
    hook: '',
    summary: '',
    conflictLevel: '',
    dialogueRatio: '',
    hookStrength: '',
    status: 'planned',
  })

  useEffect(() => {
    setDraft({
      title: chapter.title,
      pov: chapter.pov,
      targetWords: chapter.target_words == null ? '' : String(chapter.target_words),
      emotionalTone: chapter.emotional_tone,
      lines: chapter.lines.join('、'),
      hook: chapter.hook,
      summary: chapter.summary,
      conflictLevel: chapter.conflict_level == null ? '' : String(chapter.conflict_level),
      dialogueRatio:
        chapter.dialogue_ratio == null ? '' : String(Math.round(chapter.dialogue_ratio * 100)),
      hookStrength: chapter.hook_strength == null ? '' : String(chapter.hook_strength),
      status: chapter.status,
    })
  }, [chapter])

  const set = (patch: Partial<typeof draft>) => setDraft({ ...draft, ...patch })
  const levels = ['', '1', '2', '3', '4', '5']

  return (
    <section className="space-y-3 rounded border border-slate-800 p-4 text-sm">
      <h3 className="text-sm font-medium text-slate-300">章</h3>
      <label className="block">
        <span className="text-slate-500">标题</span>
        <input className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.title} onChange={(e) => set({ title: e.target.value })} />
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-slate-500">视角</label>
        <input className="w-40 rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.pov} onChange={(e) => set({ pov: e.target.value })} />
        <label className="text-slate-500">目标字数</label>
        <input className="w-32 rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.targetWords} onChange={(e) => set({ targetWords: e.target.value })} />
      </div>
      <label className="block">
        <span className="text-slate-500">情绪基调</span>
        <input className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.emotionalTone} onChange={(e) => set({ emotionalTone: e.target.value })} />
      </label>
      <label className="block">
        <span className="text-slate-500">推进的线（顿号分隔）</span>
        <input className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.lines} onChange={(e) => set({ lines: e.target.value })} />
      </label>
      <label className="block">
        <span className="text-slate-500">章末钩子</span>
        <input className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.hook} onChange={(e) => set({ hook: e.target.value })} />
      </label>
      <label className="block">
        <span className="text-slate-500">本章摘要</span>
        <textarea className="mt-1 h-24 w-full rounded border border-slate-700 bg-slate-900 p-3"
                  value={draft.summary} onChange={(e) => set({ summary: e.target.value })} />
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-slate-500">冲突强度</label>
        <select className="rounded border border-slate-700 bg-slate-900 px-2 py-1"
                value={draft.conflictLevel} onChange={(e) => set({ conflictLevel: e.target.value })}>
          {levels.map((value) => <option key={value} value={value}>{value || '未评'}</option>)}
        </select>
        <label className="text-slate-500">对话占比（%）</label>
        <input className="w-24 rounded border border-slate-700 bg-slate-900 px-2 py-1"
               value={draft.dialogueRatio} onChange={(e) => set({ dialogueRatio: e.target.value })} />
        <label className="text-slate-500">钩子强度</label>
        <select className="rounded border border-slate-700 bg-slate-900 px-2 py-1"
                value={draft.hookStrength} onChange={(e) => set({ hookStrength: e.target.value })}>
          {levels.map((value) => <option key={value} value={value}>{value || '未评'}</option>)}
        </select>
        <label className="text-slate-500">状态</label>
        <select className="rounded border border-slate-700 bg-slate-900 px-2 py-1"
                value={draft.status} onChange={(e) => set({ status: e.target.value })}>
          {statuses.map((status) => (
            <option key={status.key} value={status.key}>{status.label}</option>
          ))}
        </select>
      </div>
      <div className="flex items-center gap-2">
        <button className="rounded bg-indigo-600 px-4 py-2 disabled:opacity-50" disabled={busy}
                onClick={() => onSave({
                  title: draft.title.trim(),
                  pov: draft.pov,
                  target_words: draft.targetWords.trim() ? Number(draft.targetWords) : null,
                  emotional_tone: draft.emotionalTone,
                  lines: draft.lines.split(/[、,，]/).map((item) => item.trim()).filter(Boolean),
                  hook: draft.hook,
                  summary: draft.summary,
                  conflict_level: draft.conflictLevel ? Number(draft.conflictLevel) : null,
                  dialogue_ratio: draft.dialogueRatio.trim() ? Number(draft.dialogueRatio) / 100 : null,
                  hook_strength: draft.hookStrength ? Number(draft.hookStrength) : null,
                  status: draft.status,
                })}>
          保存
        </button>
        <button className="rounded border border-amber-700 px-4 py-2 text-amber-400" disabled={busy}
                onClick={onDelete}>
          删除
        </button>
      </div>
    </section>
  )
}
```

- [ ] **Step 4: 基础场景编辑器（Task 9 会扩展）**

`SceneEditor.tsx`（Task 8 版本）：

```tsx
import { useEffect, useState } from 'react'
import type { ChapterStatusOption, SceneNode } from '../../api/client'

export default function SceneEditor({
  scene,
  statuses,
  busy,
  onSave,
  onDelete,
}: {
  scene: SceneNode
  statuses: ChapterStatusOption[]
  busy: boolean
  onSave: (fields: Record<string, unknown>) => Promise<void>
  onDelete: () => Promise<void>
}) {
  const [draft, setDraft] = useState({
    goal: '',
    conflict: '',
    turn: '',
    storyTime: '',
    pov: '',
    minWords: '',
    maxWords: '',
    status: 'planned',
  })

  useEffect(() => {
    setDraft({
      goal: scene.goal,
      conflict: scene.conflict,
      turn: scene.turn,
      storyTime: scene.story_time,
      pov: scene.pov,
      minWords: scene.target_words_min == null ? '' : String(scene.target_words_min),
      maxWords: scene.target_words_max == null ? '' : String(scene.target_words_max),
      status: scene.status,
    })
  }, [scene])

  const set = (patch: Partial<typeof draft>) => setDraft({ ...draft, ...patch })

  return (
    <section className="space-y-3 rounded border border-slate-800 p-4 text-sm">
      <h3 className="text-sm font-medium text-slate-300">场景</h3>
      <label className="block">
        <span className="text-slate-500">场景目标</span>
        <textarea className="mt-1 h-20 w-full rounded border border-slate-700 bg-slate-900 p-3"
                  value={draft.goal} onChange={(e) => set({ goal: e.target.value })} />
      </label>
      <label className="block">
        <span className="text-slate-500">冲突</span>
        <textarea className="mt-1 h-20 w-full rounded border border-slate-700 bg-slate-900 p-3"
                  value={draft.conflict} onChange={(e) => set({ conflict: e.target.value })} />
      </label>
      <label className="block">
        <span className="text-slate-500">转折</span>
        <textarea className="mt-1 h-20 w-full rounded border border-slate-700 bg-slate-900 p-3"
                  value={draft.turn} onChange={(e) => set({ turn: e.target.value })} />
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-slate-500">故事内时间</label>
        <input className="w-44 rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.storyTime} onChange={(e) => set({ storyTime: e.target.value })} />
        <label className="text-slate-500">视角</label>
        <input className="w-40 rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.pov} onChange={(e) => set({ pov: e.target.value })} />
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-slate-500">字数下限</label>
        <input className="w-24 rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.minWords} onChange={(e) => set({ minWords: e.target.value })} />
        <label className="text-slate-500">字数上限</label>
        <input className="w-24 rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.maxWords} onChange={(e) => set({ maxWords: e.target.value })} />
        <label className="text-slate-500">状态</label>
        <select className="rounded border border-slate-700 bg-slate-900 px-2 py-1"
                value={draft.status} onChange={(e) => set({ status: e.target.value })}>
          {statuses.map((status) => (
            <option key={status.key} value={status.key}>{status.label}</option>
          ))}
        </select>
      </div>
      <div className="flex items-center gap-2">
        <button className="rounded bg-indigo-600 px-4 py-2 disabled:opacity-50" disabled={busy}
                onClick={() => onSave({
                  goal: draft.goal,
                  conflict: draft.conflict,
                  turn: draft.turn,
                  story_time: draft.storyTime,
                  pov: draft.pov,
                  target_words_min: draft.minWords.trim() ? Number(draft.minWords) : null,
                  target_words_max: draft.maxWords.trim() ? Number(draft.maxWords) : null,
                  status: draft.status,
                })}>
          保存
        </button>
        <button className="rounded border border-amber-700 px-4 py-2 text-amber-400" disabled={busy}
                onClick={onDelete}>
          删除
        </button>
      </div>
    </section>
  )
}
```

- [ ] **Step 5: 页面**

`frontend/src/pages/Chapters.tsx`：

```tsx
import { useEffect, useState } from 'react'
import { api, type ChapterStatusOption, type Project, type VolumeNode } from '../api/client'
import ChapterTree, { type Selection } from '../components/chapters/ChapterTree'
import ChapterEditor from '../components/chapters/ChapterEditor'
import SceneEditor from '../components/chapters/SceneEditor'
import VolumeEditor from '../components/chapters/VolumeEditor'

export default function Chapters() {
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [statuses, setStatuses] = useState<ChapterStatusOption[]>([])
  const [volumes, setVolumes] = useState<VolumeNode[]>([])
  const [selected, setSelected] = useState<Selection | null>(null)
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.listProjects().then((list) => {
      setProjects(list)
      if (list[0]) setProjectId(list[0].id)
    }).catch((error) => setNotice((error as Error).message))
    api.listChapterTypes().then((data) => setStatuses(data.statuses))
      .catch((error) => setNotice((error as Error).message))
  }, [])

  useEffect(() => {
    if (!projectId) return
    setSelected(null)
    setNotice('')
    setVolumes([])
    api.getChapterTree(projectId).then((data) => setVolumes(data.volumes))
      .catch((error) => setNotice((error as Error).message))
  }, [projectId])

  async function refresh() {
    const data = await api.getChapterTree(projectId)
    setVolumes(data.volumes)
  }

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setNotice('')
    try {
      await action()
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const volume = selected?.kind === 'volume' ? volumes.find((v) => v.id === selected.id) : undefined
  const chapter =
    selected?.kind === 'chapter'
      ? volumes.flatMap((v) => v.chapters).find((c) => c.id === selected.id)
      : undefined
  const scene =
    selected?.kind === 'scene'
      ? volumes.flatMap((v) => v.chapters).flatMap((c) => c.scenes).find((s) => s.id === selected.id)
      : undefined

  async function addVolume() {
    await run(async () => {
      const created = await api.createVolume(projectId, { name: '新卷' })
      await refresh()
      setSelected({ kind: 'volume', id: created.id })
    })
  }

  async function addChapter(volumeId: string) {
    await run(async () => {
      const created = await api.createChapter(volumeId, { title: '新章' })
      await refresh()
      setSelected({ kind: 'chapter', id: created.id })
    })
  }

  async function addScene(chapterId: string) {
    await run(async () => {
      const created = await api.createScene(chapterId, { goal: '' })
      await refresh()
      setSelected({ kind: 'scene', id: created.id })
    })
  }

  async function move(kind: Selection['kind'], id: string, direction: 'up' | 'down') {
    await run(async () => {
      if (kind === 'volume') await api.moveVolume(id, direction)
      else if (kind === 'chapter') await api.moveChapter(id, direction)
      else await api.moveScene(id, direction)
      await refresh()
    })
  }

  async function deleteSelected() {
    if (!selected) return
    if (!window.confirm('删除这一项？子项会一并删除。')) return
    await run(async () => {
      if (selected.kind === 'volume') await api.deleteVolume(selected.id)
      else if (selected.kind === 'chapter') await api.deleteChapter(selected.id)
      else await api.deleteScene(selected.id)
      setSelected(null)
      await refresh()
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-semibold">章节设计</h2>
        <select className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                value={projectId} onChange={(e) => setProjectId(e.target.value)}>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>{project.name}</option>
          ))}
        </select>
        {notice && <span className="text-sm text-slate-400">{notice}</span>}
      </div>

      <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
        <ChapterTree
          volumes={volumes}
          selected={selected}
          onSelect={setSelected}
          onAddVolume={addVolume}
          onAddChapter={addChapter}
          onAddScene={addScene}
          onMove={move}
        />

        <div className="space-y-4">
          {!selected && (
            <p className="rounded border border-slate-800 p-4 text-sm text-slate-500">
              从左边选一卷、一章或一个场景开始编辑；也可以先手工建卷。
            </p>
          )}
          {volume && (
            <VolumeEditor
              volume={volume}
              statuses={statuses}
              busy={busy}
              onSave={async (fields) => run(async () => {
                await api.updateVolume(volume.id, fields)
                await refresh()
                setNotice('已保存')
              })}
              onDelete={deleteSelected}
            />
          )}
          {chapter && (
            <ChapterEditor
              chapter={chapter}
              statuses={statuses}
              busy={busy}
              onSave={async (fields) => run(async () => {
                await api.updateChapter(chapter.id, fields)
                await refresh()
                setNotice('已保存')
              })}
              onDelete={deleteSelected}
            />
          )}
          {scene && (
            <SceneEditor
              scene={scene}
              statuses={statuses}
              busy={busy}
              onSave={async (fields) => run(async () => {
                await api.updateScene(scene.id, fields)
                await refresh()
                setNotice('已保存')
              })}
              onDelete={deleteSelected}
            />
          )}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 6: 导航与路由**

`frontend/src/App.tsx`：导入 `Chapters`；`NAV` 在术语表后加 `{ to: '/chapters', label: '章节设计' }`；`<Routes>` 加 `/chapters`。

- [ ] **Step 7: 构建与手工走查**

Run: `cd frontend && pnpm vitest run && pnpm build`
Expected: 8 passed、build 干净。

手工走查（可在任务报告记录步骤，最终 Task 10 在副本上再走一遍）：
- 建卷 → 改卷名/目标字数/状态 → 刷新后保持。
- 建章 → 改 POV/冲突强度/对话占比 → 树顺序正确。
- 建场景 → 改目标/冲突/转折/字数区间 → 树显示「场景 N：目标」。
- 上移/下移卷、章、场景；删除卷级联。
- 切项目清空选中与树。

- [ ] **Step 8: 提交**

```bash
git add frontend/src/api/client.ts frontend/src/App.tsx frontend/src/pages/Chapters.tsx frontend/src/components/chapters/ChapterTree.tsx frontend/src/components/chapters/VolumeEditor.tsx frontend/src/components/chapters/ChapterEditor.tsx frontend/src/components/chapters/SceneEditor.tsx
git commit -m "feat(frontend): 章节设计页的树与手工编辑器"
```

---

## Task 9: 场景编辑器的人物 / 地点 / 伏笔

**Files:**
- Modify: `frontend/src/api/client.ts`（伏笔类型与方法）
- Modify: `frontend/src/pages/Chapters.tsx`（加载条目与伏笔）
- Modify: `frontend/src/components/chapters/SceneEditor.tsx`（完整版）

**Interfaces:**
- Consumes: Task 3 的场景 API（名称解析）、Task 4 的伏笔 API。
- Produces: 场景编辑器可以选人物、地点、埋设/回收伏笔；写错名称时显示可读错误。

- [ ] **Step 1: 客户端类型与方法**

`client.ts` 追加：

```ts
export interface Foreshadow {
  id: string
  project_id: string
  name: string
  note: string
  plant_scene_id: string | null
  plan_pay_scene_id: string | null
  status: string
  source_run_id: string | null
}
```

API 方法：

```ts
  listForeshadows: (projectId: string) =>
    request<Foreshadow[]>(`/api/projects/${projectId}/foreshadows`),
  createForeshadow: (projectId: string, body: Record<string, unknown>) =>
    request<Foreshadow>(`/api/projects/${projectId}/foreshadows`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  updateForeshadow: (foreshadowId: string, body: Record<string, unknown>) =>
    request<Foreshadow>(`/api/foreshadows/${foreshadowId}`, {
      method: 'PATCH',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  deleteForeshadow: (foreshadowId: string) =>
    request<void>(`/api/foreshadows/${foreshadowId}`, { method: 'DELETE' }),
```

- [ ] **Step 2: 完整场景编辑器**

把 `SceneEditor.tsx` 替换为：

```tsx
import { useEffect, useState } from 'react'
import type {
  ChapterStatusOption,
  Foreshadow,
  SceneNode,
  SettingEntry,
} from '../../api/client'

export default function SceneEditor({
  scene,
  statuses,
  entries,
  entriesReady,
  foreshadows,
  busy,
  onSave,
  onDelete,
}: {
  scene: SceneNode
  statuses: ChapterStatusOption[]
  entries: SettingEntry[]
  entriesReady: boolean
  foreshadows: Foreshadow[]
  busy: boolean
  onSave: (fields: Record<string, unknown>) => Promise<void>
  onDelete: () => Promise<void>
}) {
  const [draft, setDraft] = useState({
    goal: '',
    conflict: '',
    turn: '',
    storyTime: '',
    pov: '',
    minWords: '',
    maxWords: '',
    status: 'planned',
    characterIds: [] as string[],
    locationId: '',
    plantNames: [] as string[],
    payNames: [] as string[],
  })
  const [plantInput, setPlantInput] = useState('')
  const [payInput, setPayInput] = useState('')

  useEffect(() => {
    setDraft({
      goal: scene.goal,
      conflict: scene.conflict,
      turn: scene.turn,
      storyTime: scene.story_time,
      pov: scene.pov,
      minWords: scene.target_words_min == null ? '' : String(scene.target_words_min),
      maxWords: scene.target_words_max == null ? '' : String(scene.target_words_max),
      status: scene.status,
      characterIds: scene.characters,
      locationId: scene.location_id ?? '',
      plantNames: scene.foreshadows.plants.map((item) => item.name),
      payNames: scene.foreshadows.pays.map((item) => item.name),
    })
    setPlantInput('')
    setPayInput('')
  }, [scene.id])

  const set = (patch: Partial<typeof draft>) => setDraft({ ...draft, ...patch })
  const characters = entries.filter((entry) => entry.type === 'character')
  const nameOf = (id: string) => entries.find((entry) => entry.id === id)?.name ?? '（已删除）'
  const resolvedNameOf = (id: string) => entries.find((entry) => entry.id === id)?.name

  function toggleCharacter(id: string) {
    set({
      characterIds: draft.characterIds.includes(id)
        ? draft.characterIds.filter((item) => item !== id)
        : [...draft.characterIds, id],
    })
  }

  function addName(kind: 'plant' | 'pay') {
    const raw = kind === 'plant' ? plantInput : payInput
    const name = raw.trim()
    if (!name) return
    if (kind === 'plant') {
      if (!draft.plantNames.includes(name)) set({ plantNames: [...draft.plantNames, name] })
      setPlantInput('')
    } else {
      if (!draft.payNames.includes(name)) set({ payNames: [...draft.payNames, name] })
      setPayInput('')
    }
  }

  function removeName(kind: 'plant' | 'pay', name: string) {
    if (kind === 'plant') {
      set({ plantNames: draft.plantNames.filter((item) => item !== name) })
    } else {
      set({ payNames: draft.payNames.filter((item) => item !== name) })
    }
  }

  return (
    <section className="space-y-3 rounded border border-slate-800 p-4 text-sm">
      <h3 className="text-sm font-medium text-slate-300">场景</h3>
      <label className="block">
        <span className="text-slate-500">场景目标</span>
        <textarea className="mt-1 h-20 w-full rounded border border-slate-700 bg-slate-900 p-3"
                  value={draft.goal} onChange={(e) => set({ goal: e.target.value })} />
      </label>
      <label className="block">
        <span className="text-slate-500">冲突</span>
        <textarea className="mt-1 h-20 w-full rounded border border-slate-700 bg-slate-900 p-3"
                  value={draft.conflict} onChange={(e) => set({ conflict: e.target.value })} />
      </label>
      <label className="block">
        <span className="text-slate-500">转折</span>
        <textarea className="mt-1 h-20 w-full rounded border border-slate-700 bg-slate-900 p-3"
                  value={draft.turn} onChange={(e) => set({ turn: e.target.value })} />
      </label>

      <div className="space-y-2">
        <div className="text-slate-400">出场人物（只列人物）</div>
        <div className="flex flex-wrap gap-2">
          {characters.map((character) => {
            const on = draft.characterIds.includes(character.id)
            return (
              <button key={character.id} onClick={() => toggleCharacter(character.id)}
                      className={`rounded border px-3 py-1 text-xs ${
                        on ? 'border-indigo-500 bg-slate-800' : 'border-slate-700'
                      }`}>
                {character.name}
              </button>
            )
          })}
          {characters.length === 0 && (
            <span className="text-xs text-slate-500">还没有人物，先去世界观里建一个。</span>
          )}
        </div>
        {draft.characterIds.length > 0 && (
          <div className="text-xs text-slate-500">
            已选：{draft.characterIds.map(nameOf).join('、')}
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <label className="text-slate-500">地点</label>
        <select className="rounded border border-slate-700 bg-slate-900 px-3 py-2"
                value={draft.locationId} onChange={(e) => set({ locationId: e.target.value })}>
          <option value="">（无地点）</option>
          {entries.map((entry) => (
            <option key={entry.id} value={entry.id}>{entry.name}</option>
          ))}
        </select>
        <label className="text-slate-500">故事内时间</label>
        <input className="w-44 rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.storyTime} onChange={(e) => set({ storyTime: e.target.value })} />
        <label className="text-slate-500">视角</label>
        <input className="w-40 rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.pov} onChange={(e) => set({ pov: e.target.value })} />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <label className="text-slate-500">字数下限</label>
        <input className="w-24 rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.minWords} onChange={(e) => set({ minWords: e.target.value })} />
        <label className="text-slate-500">字数上限</label>
        <input className="w-24 rounded border border-slate-700 bg-slate-900 px-3 py-2"
               value={draft.maxWords} onChange={(e) => set({ maxWords: e.target.value })} />
        <label className="text-slate-500">状态</label>
        <select className="rounded border border-slate-700 bg-slate-900 px-2 py-1"
                value={draft.status} onChange={(e) => set({ status: e.target.value })}>
          {statuses.map((status) => (
            <option key={status.key} value={status.key}>{status.label}</option>
          ))}
        </select>
      </div>

      <datalist id="foreshadow-names">
        {foreshadows.map((row) => <option key={row.id} value={row.name} />)}
      </datalist>

      {(['plant', 'pay'] as const).map((kind) => {
        const names = kind === 'plant' ? draft.plantNames : draft.payNames
        const input = kind === 'plant' ? plantInput : payInput
        const setInput = kind === 'plant' ? setPlantInput : setPayInput
        return (
          <div key={kind} className="space-y-1">
            <div className="text-slate-400">{kind === 'plant' ? '埋设的伏笔' : '回收的伏笔'}</div>
            <div className="flex flex-wrap gap-2">
              {names.map((name) => (
                <span key={name} className="rounded bg-slate-800 px-2 py-1 text-xs">
                  {name}
                  <button className="ml-2 text-amber-400" onClick={() => removeName(kind, name)}>
                    ×
                  </button>
                </span>
              ))}
            </div>
            <div className="flex items-center gap-2">
              <input className="w-64 rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs"
                     list="foreshadow-names" placeholder="已有伏笔名或新名字"
                     value={input} onChange={(e) => setInput(e.target.value)}
                     onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addName(kind) } }} />
              <button className="text-xs text-indigo-400" onClick={() => addName(kind)}>
                添加
              </button>
            </div>
          </div>
        )
      })}

      <div className="flex items-center gap-2">
        <button className="rounded bg-indigo-600 px-4 py-2 disabled:opacity-50" disabled={busy}
                onClick={() => {
                  const fields: Record<string, unknown> = {
                    goal: draft.goal,
                    conflict: draft.conflict,
                    turn: draft.turn,
                    story_time: draft.storyTime,
                    pov: draft.pov,
                    target_words_min: draft.minWords.trim() ? Number(draft.minWords) : null,
                    target_words_max: draft.maxWords.trim() ? Number(draft.maxWords) : null,
                    status: draft.status,
                    foreshadow_plants: draft.plantNames,
                    foreshadow_pays: draft.payNames,
                  }
                  // 只有条目确实属于当前项目且已加载时，才敢把 ID 映射成名称。
                  // 否则整键省略：后端 exclude_unset 会保留库里的原值，而明确
                  // 发送空值等于静默清空场景的人物与地点。
                  if (entriesReady) {
                    // 世界观里已删除的条目只剩一个解析不到名称的 ID；丢弃它，
                    // 免得一个残影让每次保存都被后端拒绝。
                    fields.characters = draft.characterIds
                      .map(resolvedNameOf)
                      .filter((name): name is string => Boolean(name))
                    fields.location = draft.locationId
                      ? resolvedNameOf(draft.locationId) ?? ''
                      : ''
                  }
                  onSave(fields)
                }}>
          保存
        </button>
        <button className="rounded border border-amber-700 px-4 py-2 text-amber-400" disabled={busy}
                onClick={onDelete}>
          删除
        </button>
      </div>
      <p className="text-xs text-slate-500">
        人物、地点、伏笔都按名称保存；名称找不到或与另一个场景冲突时，后端会列出原因。
      </p>
    </section>
  )
}
```

- [ ] **Step 3: 页面加载条目与伏笔（确切代码）**

`Chapters.tsx` 导入类型：

```tsx
import {
  api,
  type ChapterStatusOption,
  type Foreshadow,
  type Project,
  type SettingEntry,
  type VolumeNode,
} from '../api/client'
```

状态：

```tsx
  const [entries, setEntries] = useState<SettingEntry[]>([])
  // 条目属于哪个项目：entries 是异步加载的，空列表并不等于「这个项目没有条目」。
  // 只有 entriesProjectId === projectId 时，场景编辑器才敢用 entries 映射名称。
  const [entriesProjectId, setEntriesProjectId] = useState('')
  const [foreshadows, setForeshadows] = useState<Foreshadow[]>([])
  // 每次条目请求自增；迟到的旧项目响应凭 token 失效，不能覆盖当前项目的数据。
  const entriesRequestRef = useRef(0)
```

项目切换 effect 里加：

```tsx
    setEntries([])
    setEntriesProjectId('')
    setForeshadows([])
    // 每次条目请求自增；迟到的旧项目响应凭 token 失效，不能覆盖当前项目的数据。
    const token = ++entriesRequestRef.current
    api.listEntries(projectId).then((list) => {
      if (entriesRequestRef.current !== token) return
      setEntries(list)
      setEntriesProjectId(projectId)
    }).catch((error) => setNotice((error as Error).message))
    api.listForeshadows(projectId).then(setForeshadows).catch((error) => setNotice((error as Error).message))
```

`refresh` 改成：

```tsx
  async function refresh() {
    const requestProjectId = projectId
    const token = ++entriesRequestRef.current
    const [tree, entryList, foreshadowList] = await Promise.all([
      api.getChapterTree(requestProjectId),
      api.listEntries(requestProjectId),
      api.listForeshadows(requestProjectId),
    ])
    // 期间切了项目（或又发起了一次刷新）：这批数据属于旧请求，整批丢弃。
    if (entriesRequestRef.current !== token) return
    setVolumes(tree.volumes)
    setEntries(entryList)
    setEntriesProjectId(requestProjectId)
    setForeshadows(foreshadowList)
  }
```

场景编辑器传参：

```tsx
            <SceneEditor
              key={scene.id}
              scene={scene}
              statuses={statuses}
              entries={entries}
              entriesReady={entriesProjectId === projectId}
              foreshadows={foreshadows}
              busy={busy}
              onSave={async (fields) => run(async () => {
                await api.updateScene(scene.id, fields)
                await refresh()
                setNotice('已保存')
              })}
              onDelete={deleteSelected}
            />
```

其他编辑器不变。

- [ ] **Step 4: 构建与手工走查**

Run: `cd frontend && pnpm vitest run && pnpm build`
Expected: 8 passed、build 干净。

走查：
- 场景选两个人物、一个地点、一个已有伏笔 + 输入一个新伏笔名，保存后刷新保持。
- 把同一伏笔在第二个场景再埋设 → 后端 400，页面显示「已经...」，不静默。
- 从场景移除伏笔 → 保存后树里不再显示。
- 删除地点条目后场景地点为空；删除人物条目后场景人物列表里不再有它。
- 章节/卷/场景的上移下移、删除级联仍正常。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/api/client.ts frontend/src/pages/Chapters.tsx frontend/src/components/chapters/SceneEditor.tsx
git commit -m "feat(frontend): 场景编辑器的人物/地点/伏笔"
```

---

## Task 10: AI 草稿树、真实模型复验与文档

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/Chapters.tsx`
- Create: `frontend/src/components/chapters/ChapterPlanDraft.tsx`
- Create: `frontend/src/components/chapters/ScenePlanDraft.tsx`
- Create: `docs/superpowers/plans/2026-10-18-p1c1-walkthrough.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: Task 7 的章纲/场景策划与章纲写入 API、Task 3 的场景写入 API。
- Produces: 章纲草稿树 + 场景草稿列表 + 替换/追加写入；真实模型复验记录；阶段文档。

- [ ] **Step 1: 客户端类型与方法**

`client.ts` 追加：

```ts
export interface PlanChapter {
  title: string
  pov: string
  target_words: number | null
  emotional_tone: string
  lines: string[]
  hook: string
  summary: string
  conflict_level: number | null
  dialogue_ratio: number | null
  hook_strength: number | null
  status: string
}

export interface PlanVolume {
  name: string
  purpose: string
  summary: string
  act_seq: number | null
  target_words: number | null
  status: string
  chapters: PlanChapter[]
}

export interface ChapterPlanResponse {
  run: RunView
  volumes: PlanVolume[]
  open_questions: string[]
  warnings: string[]
  structured: boolean
  parse_error: string | null
  raw_text: string
}

export interface PlanScene {
  goal: string
  conflict: string
  turn: string
  characters: string[]
  location: string
  story_time: string
  pov: string
  target_words_min: number | null
  target_words_max: number | null
  foreshadow_plants: string[]
  foreshadow_pays: string[]
}

export interface ScenePlanResponse {
  run: RunView
  scenes: PlanScene[]
  open_questions: string[]
  warnings: string[]
  structured: boolean
  parse_error: string | null
  raw_text: string
}
```

API 方法：

```ts
  planChapters: (projectId: string) =>
    request<ChapterPlanResponse>(`/api/projects/${projectId}/chapters/plan`, { method: 'POST' }),
  planScenes: (chapterId: string) =>
    request<ScenePlanResponse>(`/api/chapters/${chapterId}/scenes/plan`, { method: 'POST' }),
  writeChapterPlan: (projectId: string, body: Record<string, unknown>) =>
    request<{ volumes: VolumeNode[] }>(`/api/projects/${projectId}/chapters`, {
      method: 'PUT',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  writeScenes: (chapterId: string, body: Record<string, unknown>) =>
    request<{ volumes: VolumeNode[] }>(`/api/chapters/${chapterId}/scenes`, {
      method: 'PUT',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
```

- [ ] **Step 2: 章纲草稿组件**

`ChapterPlanDraft.tsx`：

```tsx
import { useState } from 'react'
import type { PlanChapter, PlanVolume } from '../../api/client'

const EMPTY_CHAPTER: PlanChapter = {
  title: '',
  pov: '',
  target_words: null,
  emotional_tone: '',
  lines: [],
  hook: '',
  summary: '',
  conflict_level: null,
  dialogue_ratio: null,
  hook_strength: null,
  status: 'planned',
}

export default function ChapterPlanDraft({
  volumes: initial,
  warnings,
  openQuestions,
  busy,
  onWrite,
  onClose,
}: {
  volumes: PlanVolume[]
  warnings: string[]
  openQuestions: string[]
  busy: boolean
  onWrite: (volumes: PlanVolume[], mode: 'replace' | 'append') => Promise<void>
  onClose: () => void
}) {
  const [volumes, setVolumes] = useState<PlanVolume[]>(initial)
  const [mode, setMode] = useState<'replace' | 'append'>('replace')

  const updateVolume = (index: number, patch: Partial<PlanVolume>) =>
    setVolumes((prev) => prev.map((item, i) => (i === index ? { ...item, ...patch } : item)))
  const updateChapter = (vIndex: number, cIndex: number, patch: Partial<PlanChapter>) =>
    setVolumes((prev) => prev.map((volume, i) =>
      i === vIndex
        ? { ...volume, chapters: volume.chapters.map((c, j) => (j === cIndex ? { ...c, ...patch } : c)) }
        : volume,
    ))

  function write() {
    if (volumes.length === 0) return
    const message = mode === 'replace'
      ? '写入会删除本项目现有的卷、章、场景（伏笔名保留）。确定替换？'
      : '把这份草稿追加到现有结构之后？'
    if (!window.confirm(message)) return
    void onWrite(volumes, mode)
  }

  return (
    <section className="space-y-3 rounded border border-indigo-800 bg-slate-950/60 p-4 text-sm">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="font-medium text-indigo-300">章纲草稿（逐项可改）</h3>
        <button className="text-xs text-indigo-400" onClick={() => setVolumes([...volumes, {
          name: '新卷', purpose: '', summary: '', act_seq: null, target_words: null,
          status: 'planned', chapters: [{ ...EMPTY_CHAPTER, title: '新章' }],
        }])}>+卷</button>
        <button className="text-xs text-slate-400" onClick={onClose}>收起</button>
      </div>
      {warnings.map((warning) => (
        <p key={warning} className="text-xs text-amber-300">{warning}</p>
      ))}
      {openQuestions.map((question) => (
        <p key={question} className="text-xs text-slate-400">待确认：{question}</p>
      ))}

      {volumes.map((volume, vIndex) => (
        <div key={vIndex} className="space-y-2 rounded border border-slate-800 p-3">
          <div className="flex flex-wrap items-center gap-2">
            <input className="w-44 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                   value={volume.name} onChange={(e) => updateVolume(vIndex, { name: e.target.value })} />
            <input className="flex-1 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                   placeholder="本卷要做什么" value={volume.purpose}
                   onChange={(e) => updateVolume(vIndex, { purpose: e.target.value })} />
            <input className="w-24 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                   placeholder="幕序号" value={volume.act_seq ?? ''}
                   onChange={(e) => updateVolume(vIndex, {
                     act_seq: e.target.value.trim() ? Number(e.target.value) : null,
                   })} />
            <button className="text-xs text-slate-500" onClick={() => setVolumes(volumes.filter((_, i) => i !== vIndex))}>
              删卷
            </button>
            <button className="text-xs text-indigo-400" onClick={() => updateVolume(vIndex, {
              chapters: [...volume.chapters, { ...EMPTY_CHAPTER, title: '新章' }],
            })}>+章</button>
          </div>
          {volume.chapters.map((chapter, cIndex) => (
            <div key={cIndex} className="ml-4 space-y-1 rounded border border-slate-800 p-2">
              <div className="flex flex-wrap items-center gap-2">
                <input className="w-40 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                       value={chapter.title} onChange={(e) => updateChapter(vIndex, cIndex, { title: e.target.value })} />
                <input className="w-28 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                       placeholder="视角" value={chapter.pov}
                       onChange={(e) => updateChapter(vIndex, cIndex, { pov: e.target.value })} />
                <input className="w-24 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                       placeholder="目标字数" value={chapter.target_words ?? ''}
                       onChange={(e) => updateChapter(vIndex, cIndex, {
                         target_words: e.target.value.trim() ? Number(e.target.value) : null,
                       })} />
                <input className="w-24 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                       placeholder="冲突 1-5" value={chapter.conflict_level ?? ''}
                       onChange={(e) => updateChapter(vIndex, cIndex, {
                         conflict_level: e.target.value.trim() ? Number(e.target.value) : null,
                       })} />
                <input className="w-20 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                       placeholder="对话占比" value={chapter.dialogue_ratio ?? ''}
                       onChange={(e) => updateChapter(vIndex, cIndex, {
                         dialogue_ratio: e.target.value.trim() ? Number(e.target.value) : null,
                       })} />
                <input className="w-20 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                       placeholder="钩子强度" value={chapter.hook_strength ?? ''}
                       onChange={(e) => updateChapter(vIndex, cIndex, {
                         hook_strength: e.target.value.trim() ? Number(e.target.value) : null,
                       })} />
                <button className="text-xs text-slate-500"
                        onClick={() => updateVolume(vIndex, {
                          chapters: volume.chapters.filter((_, i) => i !== cIndex),
                        })}>删章</button>
              </div>
              <input className="w-full rounded border border-slate-700 bg-slate-900 px-2 py-1"
                     placeholder="情绪基调" value={chapter.emotional_tone}
                     onChange={(e) => updateChapter(vIndex, cIndex, { emotional_tone: e.target.value })} />
              <input className="w-full rounded border border-slate-700 bg-slate-900 px-2 py-1"
                     placeholder="推进的线（顿号分隔）" value={chapter.lines.join('、')}
                     onChange={(e) => updateChapter(vIndex, cIndex, {
                       lines: e.target.value.split(/[、,，]/).map((v) => v.trim()).filter(Boolean),
                     })} />
              <input className="w-full rounded border border-slate-700 bg-slate-900 px-2 py-1"
                     placeholder="章末钩子" value={chapter.hook}
                     onChange={(e) => updateChapter(vIndex, cIndex, { hook: e.target.value })} />
              <textarea className="h-14 w-full rounded border border-slate-700 bg-slate-900 p-2 text-xs"
                        placeholder="本章摘要" value={chapter.summary}
                        onChange={(e) => updateChapter(vIndex, cIndex, { summary: e.target.value })} />
            </div>
          ))}
        </div>
      ))}

      <div className="flex items-center gap-3">
        <select className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs"
                value={mode} onChange={(e) => setMode(e.target.value as 'replace' | 'append')}>
          <option value="replace">替换现有结构</option>
          <option value="append">追加到末尾</option>
        </select>
        <button className="rounded bg-indigo-600 px-4 py-2 disabled:opacity-50" disabled={busy}
                onClick={write}>
          写入项目
        </button>
      </div>
    </section>
  )
}
```

- [ ] **Step 3: 场景草稿组件**

`ScenePlanDraft.tsx`：

```tsx
import { useState } from 'react'
import type { PlanScene } from '../../api/client'

const EMPTY_SCENE: PlanScene = {
  goal: '', conflict: '', turn: '', characters: [], location: '', story_time: '', pov: '',
  target_words_min: null, target_words_max: null, foreshadow_plants: [], foreshadow_pays: [],
}

export default function ScenePlanDraft({
  scenes: initial,
  warnings,
  openQuestions,
  busy,
  onWrite,
  onClose,
}: {
  scenes: PlanScene[]
  warnings: string[]
  openQuestions: string[]
  busy: boolean
  onWrite: (scenes: PlanScene[], mode: 'replace' | 'append') => Promise<void>
  onClose: () => void
}) {
  const [scenes, setScenes] = useState<PlanScene[]>(initial)
  const [mode, setMode] = useState<'replace' | 'append'>('replace')

  const update = (index: number, patch: Partial<PlanScene>) =>
    setScenes((prev) => prev.map((item, i) => (i === index ? { ...item, ...patch } : item)))

  function write() {
    if (scenes.length === 0) return
    const message = mode === 'replace'
      ? '写入会删除本章现有场景（伏笔名保留）。确定替换？'
      : '把这份场景草稿追加到本章末尾？'
    if (!window.confirm(message)) return
    void onWrite(scenes, mode)
  }

  return (
    <section className="space-y-3 rounded border border-emerald-800 bg-slate-950/60 p-4 text-sm">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="font-medium text-emerald-300">场景草稿（逐项可改）</h3>
        <button className="text-xs text-emerald-400"
                onClick={() => setScenes([...scenes, { ...EMPTY_SCENE }])}>+场景</button>
        <button className="text-xs text-slate-400" onClick={onClose}>收起</button>
      </div>
      {warnings.map((warning) => <p key={warning} className="text-xs text-amber-300">{warning}</p>)}
      {openQuestions.map((question) => <p key={question} className="text-xs text-slate-400">待确认：{question}</p>)}

      {scenes.map((scene, index) => (
        <div key={index} className="space-y-1 rounded border border-slate-800 p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-slate-500">场景 {index + 1}</span>
            <input className="flex-1 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                   placeholder="场景目标" value={scene.goal}
                   onChange={(e) => update(index, { goal: e.target.value })} />
            <button className="text-xs text-slate-500"
                    onClick={() => setScenes(scenes.filter((_, i) => i !== index))}>删除</button>
          </div>
          <input className="w-full rounded border border-slate-700 bg-slate-900 px-2 py-1"
                 placeholder="冲突" value={scene.conflict}
                 onChange={(e) => update(index, { conflict: e.target.value })} />
          <input className="w-full rounded border border-slate-700 bg-slate-900 px-2 py-1"
                 placeholder="转折" value={scene.turn}
                 onChange={(e) => update(index, { turn: e.target.value })} />
          <div className="flex flex-wrap gap-2">
            <input className="w-52 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                   placeholder="人物（顿号分隔，用标准名）" value={scene.characters.join('、')}
                   onChange={(e) => update(index, {
                     characters: e.target.value.split(/[、,，]/).map((v) => v.trim()).filter(Boolean),
                   })} />
            <input className="w-40 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                   placeholder="地点（标准名）" value={scene.location}
                   onChange={(e) => update(index, { location: e.target.value })} />
            <input className="w-36 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                   placeholder="故事内时间" value={scene.story_time}
                   onChange={(e) => update(index, { story_time: e.target.value })} />
            <input className="w-28 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                   placeholder="视角" value={scene.pov}
                   onChange={(e) => update(index, { pov: e.target.value })} />
            <input className="w-24 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                   placeholder="字数下限" value={scene.target_words_min ?? ''}
                   onChange={(e) => update(index, {
                     target_words_min: e.target.value.trim() ? Number(e.target.value) : null,
                   })} />
            <input className="w-24 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                   placeholder="字数上限" value={scene.target_words_max ?? ''}
                   onChange={(e) => update(index, {
                     target_words_max: e.target.value.trim() ? Number(e.target.value) : null,
                   })} />
          </div>
          <div className="flex flex-wrap gap-2">
            <input className="w-40 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                   placeholder="埋设伏笔（顿号分隔）" value={scene.foreshadow_plants.join('、')}
                   onChange={(e) => update(index, {
                     foreshadow_plants: e.target.value.split(/[、,，]/).map((v) => v.trim()).filter(Boolean),
                   })} />
            <input className="w-40 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                   placeholder="回收伏笔（顿号分隔）" value={scene.foreshadow_pays.join('、')}
                   onChange={(e) => update(index, {
                     foreshadow_pays: e.target.value.split(/[、,，]/).map((v) => v.trim()).filter(Boolean),
                   })} />
          </div>
        </div>
      ))}

      <div className="flex items-center gap-3">
        <select className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs"
                value={mode} onChange={(e) => setMode(e.target.value as 'replace' | 'append')}>
          <option value="replace">替换本章场景</option>
          <option value="append">追加到本章末尾</option>
        </select>
        <button className="rounded bg-emerald-600 px-4 py-2 disabled:opacity-50" disabled={busy}
                onClick={write}>
          写入本章
        </button>
      </div>
    </section>
  )
}
```

- [ ] **Step 4: 页面接入 AI（确切代码）**

`Chapters.tsx` 顶部导入：

```tsx
import { useEffect, useRef, useState } from 'react'
import {
  api,
  type ChapterPlanResponse,
  type ChapterStatusOption,
  type PlanScene,
  type PlanVolume,
  type Project,
  type ScenePlanResponse,
  type VolumeNode,
} from '../api/client'
import RunTrace from '../components/RunTrace'
import ChapterPlanDraft from '../components/chapters/ChapterPlanDraft'
import ScenePlanDraft from '../components/chapters/ScenePlanDraft'
```

状态与 token：

```tsx
  const [chapterPlan, setChapterPlan] = useState<ChapterPlanResponse | null>(null)
  const [scenePlan, setScenePlan] = useState<ScenePlanResponse | null>(null)
  const [planning, setPlanning] = useState(false)
  const runToken = useRef(0)
```

项目切换的 effect 里加：

```tsx
    runToken.current++
    setChapterPlan(null)
    setScenePlan(null)
    setPlanning(false)
```

在 `scene` 的派生之后加：

```tsx
  const parentChapter =
    selected?.kind === 'scene'
      ? volumes.flatMap((v) => v.chapters).find((c) => c.scenes.some((s) => s.id === selected?.id))
      : undefined
  const activeChapter = chapter ?? parentChapter
```

函数：

```tsx
  async function runChapterPlan() {
    setPlanning(true)
    setNotice('')
    const token = runToken.current
    try {
      const result = await api.planChapters(projectId)
      if (token !== runToken.current) return
      setChapterPlan(result)
      if (!result.structured) setNotice(result.parse_error ?? '模型没有按契约返回')
    } catch (error) {
      if (token === runToken.current) setNotice((error as Error).message)
    } finally {
      if (token === runToken.current) setPlanning(false)
    }
  }

  async function runScenePlan(chapterId: string) {
    setPlanning(true)
    setNotice('')
    const token = runToken.current
    try {
      const result = await api.planScenes(chapterId)
      if (token !== runToken.current) return
      setScenePlan(result)
      if (!result.structured) setNotice(result.parse_error ?? '模型没有按契约返回')
    } catch (error) {
      if (token === runToken.current) setNotice((error as Error).message)
    } finally {
      if (token === runToken.current) setPlanning(false)
    }
  }

  async function writeChapterPlan(volumes: PlanVolume[], mode: 'replace' | 'append') {
    if (!chapterPlan) return
    setPlanning(true)
    setNotice('')
    try {
      const result = await api.writeChapterPlan(projectId, {
        mode,
        source_run_id: chapterPlan.run.id,
        volumes,
      })
      setVolumes(result.volumes)
      setChapterPlan(null)
      setNotice('章纲已写入')
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setPlanning(false)
    }
  }

  async function writeScenePlan(scenes: PlanScene[], mode: 'replace' | 'append') {
    if (!scenePlan || !activeChapter) return
    setPlanning(true)
    setNotice('')
    try {
      const result = await api.writeScenes(activeChapter.id, {
        mode,
        source_run_id: scenePlan.run.id,
        scenes,
      })
      setVolumes(result.volumes)
      setScenePlan(null)
      await refresh()
      setNotice('场景已写入')
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setPlanning(false)
    }
  }
```

顶部工具条加：

```tsx
        <button
          className="rounded bg-indigo-600 px-4 py-2 text-sm disabled:opacity-50"
          disabled={!projectId || planning}
          onClick={runChapterPlan}
        >
          {planning ? '生成中…' : 'AI 排卷章'}
        </button>
```

在网格之前渲染草稿（**必须用 `run.id` 作 key**，否则第二次运行时组件的本地草稿不会重置）：

```tsx
      {chapterPlan && (
        <>
          <ChapterPlanDraft
            key={chapterPlan.run.id}
            volumes={chapterPlan.volumes}
            warnings={chapterPlan.warnings}
            openQuestions={chapterPlan.open_questions}
            busy={planning}
            onWrite={writeChapterPlan}
            onClose={() => setChapterPlan(null)}
          />
          <RunTrace run={chapterPlan.run} />
        </>
      )}
      {scenePlan && (
        <>
          <ScenePlanDraft
            key={scenePlan.run.id}
            scenes={scenePlan.scenes}
            warnings={scenePlan.warnings}
            openQuestions={scenePlan.open_questions}
            busy={planning}
            onWrite={writeScenePlan}
            onClose={() => setScenePlan(null)}
          />
          <RunTrace run={scenePlan.run} />
        </>
      )}
```

在 `{chapter && (...)}` 或 `{scene && (...)}` 的编辑器上方加：

```tsx
          {activeChapter && (
            <div className="flex justify-end">
              <button
                className="rounded border border-emerald-700 px-3 py-1.5 text-sm text-emerald-300 disabled:opacity-50"
                disabled={planning}
                onClick={() => runScenePlan(activeChapter.id)}
              >
                AI 写场景卡
              </button>
            </div>
          )}
```

**不要**在切换项目时保留上一份草稿；token 与清空两件事都要做。

- [ ] **Step 5: 真实模型复验**

1. 确认阿里云百炼额度与 `qwen3.8-flash` 在额度内。
2. 用 SQLite 备份 API 把作者真实库复制到临时数据目录（不动原库）。
3. 用 `STORYFORGE_DATA_DIR=<临时目录>` 启动后端；前端 `pnpm dev`。
4. **在副本的工作室给两个新智能体绑定 `qwen3.8-flash`**（预置不带模型绑定）；若项目还没有时间线事件，先在副本的「时间线」页建一条（场景策划的 `timeline` 槽位需要它）。
5. 选有故事圣经/世界观的 `0cce…` 项目：
   - 点「AI 排卷章」，确认结构化、卷/章数量合理、引用真实人物/势力/地点、`open_questions` 有内容、无未匹配 warning；
   - 把草稿写入副本（替换），选一章点「AI 写场景卡」，确认场景数、人物/地点名匹配、伏笔名、warning；
   - 写入场景，刷新树与编辑器，确认落库。
6. 第二次启动确认不重复迁移（本段无迁移）、新智能体已在。
7. 验证结束删除临时副本与无头浏览器配置。

- [ ] **Step 6: 写走查清单**

新建 `docs/superpowers/plans/2026-10-18-p1c1-walkthrough.md`，至少包含：

```markdown
# P1c-1 手工走查清单

> 在作者真实库副本上执行，原库不动；验证后删除副本。
> `[C]` 控制方独立执行，`[I]` 实施者走查，`[A]` 合并后作者确认。

## 卷 / 章 / 场景
- [ ] 建卷、建章、建场景；改字段后刷新保持
- [ ] 上移 / 下移卷、章、场景；删除卷级联
- [ ] 章级节奏指标保存并读回（冲突 1–5、对话占比 0–100%、钩子 1–5）

## 场景卡
- [ ] 人物只列人物；地点列全部条目
- [ ] 伏笔可选已有或输入新名；同一伏笔不能在两个场景重复埋设/计划回收
- [ ] 删除人物/地点后场景引用按规则清理

## 章纲策划
- [ ] 候选不写库；草稿树可逐项编辑
- [ ] 写入替换 / 追加都成功；替换确认文案明确
- [ ] 未匹配的人物/地点 warning 可见

## 场景策划
- [ ] 只对选中章运行；候选不写库
- [ ] 场景草稿可编辑；写入本章成功
- [ ] 伏笔名与人物/地点解析正确

## 回归
- [ ] 既有关系网/时间线/术语表/工作室/模型页仍可用
- [ ] 前端构建干净，控制台 0 报错
```

- [ ] **Step 7: 更新 CLAUDE.md**

- 路线图：
  - P1c 拆成 **P1c-1 章节结构 + 策划智能体** ✅ 与 **P1c-2 节奏/伏笔视图** 未开始。
  - 修正 P1c 行：pywebview 外壳与打包归 **P5**。
  - 下一段 P1c-2。
- §7 阶段记录追加 `**2026-10-18 · P1c-1 章节结构（实施完成并通过真实模型复验）**`：产出、测试数、真实模型两次调用的结果、遗留。
- §8 变更记录追加：
  - P1c 拆分与打包归 P5；
  - 卷与幕不建外键、`act_seq` 快照；
  - 伏笔只保留 `foreshadow` 表、场景不复制 JSON；
  - 章级节奏指标在 P1c-1 落库、P1c-2 纯视图；
  - 剧情线先用 `lines_json`；
  - AI 契约用名称、写入解析 ID；
  - `replace` 保留伏笔行、界面确认；
  - 不建 `locked` / `actual_pay_scene_id`。

- [ ] **Step 8: 跑完整套件并提交**

```bash
cd backend && uv run pytest -q
cd frontend && pnpm vitest run && pnpm build
```

Expected: 后端全绿（记录实际数），前端 8 passed、build 干净。

```bash
git add frontend/src/api/client.ts frontend/src/pages/Chapters.tsx frontend/src/components/chapters/ChapterPlanDraft.tsx frontend/src/components/chapters/ScenePlanDraft.tsx docs/superpowers/plans/2026-10-18-p1c1-walkthrough.md CLAUDE.md
git commit -m "feat(frontend): AI 章纲/场景草稿；P1c-1 阶段记录与走查"
```

---

## Self-Review

**Spec coverage:**

| Spec 要求 | 对应任务 |
|---|---|
| 四张表 + 级联/唯一约束 | 1 |
| 卷/章 CRUD、树、顺序、状态词表 | 2 |
| 场景 CRUD、名称解析、伏笔挂接与冲突、批量写入 | 3 |
| 伏笔公开 CRUD 与 API | 4 |
| 四个新槽位 | 5 |
| 两个预置智能体与契约 | 6 |
| 策划归一化、运行、章纲写入、warning | 7 |
| 前端树 + 卷/章编辑器 + 基础场景编辑器 | 8 |
| 场景编辑器的人物/地点/伏笔 | 9 |
| AI 草稿树/场景草稿、真实模型复验、文档 | 10 |
| 既有 292 条全绿 | 每任务的完整套件 + Task 10 |

**Placeholder scan:** 没有 TBD / TODO /「类似上一个任务」；代码步骤都给出实际代码或确切改动。Task 8 的场景编辑器是基础版，Task 9 给出完整替换版；这是任务拆分，不是占位。

**Type consistency:**
- `EntryRelation.strength` 无关；本章新增 `Volume` / `Chapter` / `Scene` / `Foreshadow` 在模型、服务、API、前端类型中同名。
- API 的 `characters` / `location` / `foreshadow_plants` / `foreshadow_pays` 在计划与手工路径都用**名称**；树返回 `characters` IDs、`location_id`，前端用 `entries` 映射。
- `dialogue_ratio` 后端 0–1，前端百分比换算。
- `status` 词表只在 `chapter_types.py` 定义；前端从 `/api/chapter-types` 取。
- 契约字段 `pov` 的中文标题是「视角」；提示词里不写英文键。

**Known sequencing / risks:**
- Task 3 的 `write_scenes` 必须在删除旧场景后 `expire_all`，否则同一 session 的树会读到旧伏笔链接。
- Task 3 的 `update_scene` 在 `_apply_links` 时必须把当前场景视为「允许的旧链接」，否则更新会把自己判成冲突。
- Task 6 的提示词护栏会拦未列入槽位的英文单词；`POV` / `JSON` / `AI` 一律用中文。
- Task 7 的 `_plan_slots` 只建一套卷/章；场景策划的 `volume_outline` / `chapter_outline` 依赖它。
- 真实模型验证前确认额度；两次调用；不动作者原库。
