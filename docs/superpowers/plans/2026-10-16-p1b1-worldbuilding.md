# P1b-1 设定与规则 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让作者能建立、编辑、检索一部作品的设定条目与规则硬度，并能让 AI 提出一批候选、逐条审后采纳。

**Architecture:** 新增一个聚合（世界）：一张 `setting_entry` 表承载设定条目 / 规则 / 术语（用 `type` 区分），一张 `entry_relation` 表承载有向关联。AI 候选复用 P1a 已验证的运行时链路 —— 候选落在 `generation_run.parsed_json`，只有采纳才写 `setting_entry`。前端沿用协作模式（左树 + 右编辑器）。

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy / SQLite；React + TypeScript + Vite + Tailwind；uv 与 pnpm（`CLAUDE.md` §6）。

**Spec:** `docs/superpowers/specs/2026-10-16-p1b1-worldbuilding-design.md`

## Global Constraints

- **分层硬约束**：`api` 不写业务逻辑；`services` 不碰 HTTP；`runtime` 不依赖 FastAPI（`CLAUDE.md` §5）。
- **标识符与代码用英文；注释、界面文案、提示词用中文**（`CLAUDE.md` §9）。注释密度跟随周围代码，只在「为什么」不明显处写注释。
- **不引入重型依赖。** JSON Schema 校验与字段说明都用自写子集，不加 `jsonschema`。
- **纯逻辑必须测（pytest），UI 不写自动化测试**（`CLAUDE.md` §9）。
- 后端测试在 `backend/` 下跑：`uv run pytest`；单测 `uv run pytest tests/<file>::<test> -v`。
- 前端在 `frontend/` 下跑：`pnpm build`、`pnpm vitest run`。
- `backend/tests/conftest.py` 用 `STORYFORGE_DATA_DIR` 指向临时目录，`session` 夹具每个用例重建表。
- JSON 列用 `from sqlalchemy.types import JSON`（既有模型用 `sqlalchemy.JSON`）。
- 本切片**只新建表**，不改已有表 —— `create_all` 够用，不需要迁移框架。

---

## File Structure

| 文件 | 职责 | 动作 |
|---|---|---|
| `backend/app/world_types.py` | 类型与硬度词表 + 归一化。**唯一真相**：接口、归一化、角色卡契约三处共用 | 新建 |
| `backend/app/db/models/world.py` | `SettingEntry` / `EntryRelation` 两个模型 | 新建 |
| `backend/app/db/models/__init__.py` | 注册新模型 | 改 |
| `backend/app/services/world_service.py` | 条目与关联的 CRUD、术语投影 | 新建 |
| `backend/app/api/world.py` | 世界观路由（条目 / 关联 / 类型 / 术语 / 候选生成） | 新建 |
| `backend/app/api/schemas.py` | 出入参模型 | 改 |
| `backend/app/main.py` | 挂载新路由 | 改 |
| `backend/app/agents/roster.py` | 新增「世界观构建师」角色卡 | 改 |
| `backend/tests/test_models.py` | 新模型的行为 | 改 |
| `backend/tests/test_world_service.py` | 服务层 | 新建 |
| `backend/tests/test_world_api.py` | 路由层 | 新建 |
| `backend/tests/test_world_types.py` | 归一化 | 新建 |
| `frontend/src/api/client.ts` | 接口封装与类型 | 改 |
| `frontend/src/components/EntryEditor.tsx` | 条目编辑器（页面与候选行共用） | 新建 |
| `frontend/src/components/CandidateList.tsx` | 候选列表 | 新建 |
| `frontend/src/pages/World.tsx` | 世界观主页面 | 新建 |
| `frontend/src/pages/Terms.tsx` | 术语表 | 新建 |
| `frontend/src/App.tsx` | 导航 | 改 |

---

### Task 1: 词表与数据模型

**Files:**
- Create: `backend/app/world_types.py`
- Create: `backend/app/db/models/world.py`
- Modify: `backend/app/db/models/__init__.py`
- Test: `backend/tests/test_world_types.py`（新建）、`backend/tests/test_models.py`（追加）

**Interfaces:**
- Consumes: `app.db.base` 的 `Base` / `IdMixin` / `TimestampMixin`
- Produces:
  - `ENTRY_TYPES: dict[str, str]`（key → 中文名，8 项）
  - `HARDNESS_LEVELS: dict[str, str]`（3 项）
  - `normalize_type(value: str) -> str`（未知值抛 `ValueError`）
  - `normalize_hardness(value: str | None) -> str | None`
  - `SettingEntry`：`project_id, type, name, aliases_json, tags_json, summary, description, hardness, source_run_id`
  - `EntryRelation`：`project_id, from_id, to_id, kind, note`

- [ ] **Step 1: Write the failing tests**

创建 `backend/tests/test_world_types.py`：

```python
import pytest

from app.world_types import (
    ENTRY_TYPES,
    HARDNESS_LEVELS,
    normalize_hardness,
    normalize_type,
)


def test_type_vocabulary_matches_the_spec():
    assert set(ENTRY_TYPES) == {
        "place",
        "faction",
        "organization",
        "rule",
        "event",
        "item",
        "concept",
        "term",
    }
    assert ENTRY_TYPES["rule"] == "规则体系"
    assert set(HARDNESS_LEVELS) == {"hard", "soft", "atmosphere"}


def test_normalize_type_accepts_both_the_key_and_the_chinese_label():
    assert normalize_type("faction") == "faction"
    assert normalize_type("势力") == "faction"
    assert normalize_type("  规则体系  ") == "rule"


def test_normalize_type_rejects_unknown_values_with_a_readable_reason():
    """报错而不是猜一个类型：猜错会把设定塞进错误的分类，作者可能很久之后才发现。"""
    with pytest.raises(ValueError) as excinfo:
        normalize_type("魔法体系")
    assert "魔法体系" in str(excinfo.value)
    assert "势力" in str(excinfo.value)  # 可读错误要列出可用值


def test_normalize_hardness_maps_labels_and_falls_back_to_none():
    assert normalize_hardness("hard") == "hard"
    assert normalize_hardness("硬规则") == "hard"
    assert normalize_hardness("氛围") == "atmosphere"
    assert normalize_hardness("") is None
    assert normalize_hardness(None) is None
    assert normalize_hardness("很硬") is None
```

追加到 `backend/tests/test_models.py`（沿用该文件既有的 `session` 夹具与直接断言风格）：

```python
def test_setting_entry_defaults_and_roundtrip(session):
    from app.db.models import SettingEntry

    project = Project(name="雾港")
    session.add(project)
    session.commit()

    entry = SettingEntry(project_id=project.id, type="faction", name="记忆交易局")
    session.add(entry)
    session.commit()

    stored = session.get(SettingEntry, entry.id)
    assert stored.aliases_json == []
    assert stored.tags_json == []
    assert stored.summary == ""
    assert stored.hardness is None
    assert stored.source_run_id is None


def test_entry_name_is_unique_within_a_project(session):
    from sqlalchemy.exc import IntegrityError

    from app.db.models import SettingEntry

    project = Project(name="雾港")
    other = Project(name="另一本")
    session.add_all([project, other])
    session.commit()

    session.add(SettingEntry(project_id=project.id, type="place", name="雾港旧城"))
    session.add(SettingEntry(project_id=other.id, type="place", name="雾港旧城"))
    session.commit()  # 跨项目同名是合法的

    session.add(SettingEntry(project_id=project.id, type="faction", name="雾港旧城"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_deleting_an_entry_removes_its_relations(session):
    from sqlalchemy import select

    from app.db.models import EntryRelation, SettingEntry

    project = Project(name="雾港")
    session.add(project)
    session.commit()
    a = SettingEntry(project_id=project.id, type="faction", name="甲")
    b = SettingEntry(project_id=project.id, type="place", name="乙")
    session.add_all([a, b])
    session.commit()
    session.add(EntryRelation(project_id=project.id, from_id=a.id, to_id=b.id, kind="位于"))
    session.commit()

    session.delete(a)
    session.commit()

    remaining = session.scalars(select(EntryRelation)).all()
    assert remaining == []


def test_relation_is_directional(session):
    from sqlalchemy import select

    from app.db.models import EntryRelation, SettingEntry

    project = Project(name="雾港")
    session.add(project)
    session.commit()
    a = SettingEntry(project_id=project.id, type="faction", name="甲")
    b = SettingEntry(project_id=project.id, type="place", name="乙")
    session.add_all([a, b])
    session.commit()
    session.add(EntryRelation(project_id=project.id, from_id=a.id, to_id=b.id, kind="位于"))
    session.commit()

    forward = session.scalars(select(EntryRelation).where(EntryRelation.from_id == a.id)).all()
    backward = session.scalars(select(EntryRelation).where(EntryRelation.from_id == b.id)).all()
    assert len(forward) == 1
    assert backward == []
```

`test_models.py` 顶部需要 `import pytest`（当前只有 `from app.db.base import new_id` 等导入）。

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_world_types.py tests/test_models.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'app.world_types'` 与 `ImportError: cannot import name 'SettingEntry'`

- [ ] **Step 3: Write the implementation**

创建 `backend/app/world_types.py`：

```python
"""世界观条目的类型与硬度词表，以及把模型产出归一化到词表的函数。

这里是唯一真相：接口下发给前端、归一化函数、角色卡契约三处都用它。
多一份就会漂移 —— 与 SLOT_REGISTRY 同一条教训。
"""

from __future__ import annotations

ENTRY_TYPES: dict[str, str] = {
    "place": "地理",
    "faction": "势力",
    "organization": "组织",
    "rule": "规则体系",
    "event": "历史事件",
    "item": "物品",
    "concept": "概念",
    "term": "术语",
}

HARDNESS_LEVELS: dict[str, str] = {
    "hard": "硬规则",
    "soft": "软规则",
    "atmosphere": "氛围",
}

_TYPE_BY_LABEL = {label: key for key, label in ENTRY_TYPES.items()}
_HARDNESS_BY_LABEL = {label: key for key, label in HARDNESS_LEVELS.items()}


def normalize_type(value: str) -> str:
    """中文名与英文键都归到同一个 key；未知值报错。

    报错而不是猜一个类型：猜错会把一条设定塞进错误的分类，而作者可能
    在很远之后才发现。报错只影响这一行，不拖垮整批候选。
    """
    key = (value or "").strip()
    if key in ENTRY_TYPES:
        return key
    if key in _TYPE_BY_LABEL:
        return _TYPE_BY_LABEL[key]
    raise ValueError(
        f"未知的设定类型「{value}」，可用值：{'、'.join(ENTRY_TYPES.values())}"
    )


def normalize_hardness(value: str | None) -> str | None:
    """只在规则类条目上保留硬度；非法值与空值一律归为 None。

    不报错：模型对非规则条目填了硬度、或填了「很硬」这类描述，都不该
    让一条本来可用的候选被拒。
    """
    key = (value or "").strip()
    if key in HARDNESS_LEVELS:
        return key
    if key in _HARDNESS_BY_LABEL:
        return _HARDNESS_BY_LABEL[key]
    return None
```

创建 `backend/app/db/models/world.py`：

```python
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
```

`backend/app/db/models/__init__.py` 加两行导入与 `__all__` 两项（保持字母序）：

```python
from app.db.models.world import EntryRelation, SettingEntry
```

```python
    "EntryRelation",
    "SettingEntry",
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_world_types.py tests/test_models.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/world_types.py backend/app/db/models/world.py backend/app/db/models/__init__.py backend/tests/test_world_types.py backend/tests/test_models.py
git commit -m "feat(world): 设定条目与关联的数据模型，以及类型词表与归一化"
```

---

### Task 2: 条目 CRUD

**Files:**
- Create: `backend/app/services/world_service.py`
- Create: `backend/app/api/world.py`
- Modify: `backend/app/api/schemas.py`、`backend/app/main.py`
- Test: `backend/tests/test_world_service.py`（新建）

**Interfaces:**
- Consumes: `normalize_type` / `normalize_hardness`（Task 1）、`SettingEntry` / `EntryRelation`（Task 1）
- Produces:
  - `world_service.list_entries(session, project_id, type=None) -> list[SettingEntry]`
  - `world_service.create_entry(session, project_id, **fields) -> SettingEntry`
  - `world_service.get_entry(session, entry_id) -> SettingEntry | None`
  - `world_service.update_entry(session, entry_id, **fields) -> SettingEntry`
  - `world_service.delete_entry(session, entry_id) -> None`
  - `EntryCreate` / `EntryUpdate`（schemas）

- [ ] **Step 1: Write the failing test**

创建 `backend/tests/test_world_service.py`：

```python
import pytest
from sqlalchemy import select

from app.db.models import Project, SettingEntry
from app.services import world_service


def _project(session) -> Project:
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    return project


def test_create_normalizes_type_and_hardness(session):
    """模型（或手工输入）写「势力」还是「faction」都落到同一个 key。"""
    project = _project(session)

    entry = world_service.create_entry(
        session,
        project.id,
        type="规则体系",
        name="记忆不可复活",
        hardness="硬规则",
    )

    assert entry.type == "rule"
    assert entry.hardness == "hard"


def test_create_rejects_an_unknown_type(session):
    project = _project(session)
    with pytest.raises(ValueError) as excinfo:
        world_service.create_entry(session, project.id, type="魔法体系", name="X")
    assert "魔法体系" in str(excinfo.value)


def test_non_rule_entries_drop_the_hardness(session):
    project = _project(session)
    entry = world_service.create_entry(
        session, project.id, type="place", name="雾港旧城", hardness="hard"
    )
    assert entry.hardness is None


def test_duplicate_name_returns_a_readable_reason(session):
    """唯一约束在数据库上，但作者要看到中文原因而不是 IntegrityError 堆栈。"""
    project = _project(session)
    world_service.create_entry(session, project.id, type="place", name="雾港旧城")

    with pytest.raises(ValueError) as excinfo:
        world_service.create_entry(session, project.id, type="faction", name="雾港旧城")
    assert "雾港旧城" in str(excinfo.value)


def test_list_filters_by_type_and_keeps_creation_order(session):
    project = _project(session)
    world_service.create_entry(session, project.id, type="place", name="甲")
    world_service.create_entry(session, project.id, type="faction", name="乙")
    world_service.create_entry(session, project.id, type="place", name="丙")

    places = world_service.list_entries(session, project.id, type="place")

    assert [e.name for e in places] == ["甲", "丙"]


def test_update_and_delete(session):
    project = _project(session)
    entry = world_service.create_entry(session, project.id, type="item", name="旧名")

    updated = world_service.update_entry(
        session, entry.id, name="新名", aliases=["别名一"], tags=["道具"]
    )
    assert updated.name == "新名"
    assert updated.aliases_json == ["别名一"]
    assert updated.tags_json == ["道具"]

    world_service.delete_entry(session, entry.id)
    assert session.scalars(select(SettingEntry)).all() == []


def test_update_unknown_entry_raises(session):
    with pytest.raises(ValueError):
        world_service.update_entry(session, "nope", name="X")


def test_type_change_re_normalizes(session):
    """改成规则类时，类型与硬度两个字段都要走归一化。

    注意必须改成 **rule**：硬度只在规则类条目上有意义（spec §2.1），
    拿 faction 去断言 hardness 保留，与那条不变量冲突。
    """
    project = _project(session)
    entry = world_service.create_entry(session, project.id, type="place", name="某地")

    updated = world_service.update_entry(session, entry.id, type="规则体系", hardness="软规则")

    assert updated.type == "rule"
    assert updated.hardness == "soft"


def test_changing_away_from_rule_clears_hardness(session):
    """不变量在 update 路径上同样成立：一条规则改成「势力」就不再带硬度。"""
    project = _project(session)
    entry = world_service.create_entry(
        session, project.id, type="rule", name="死者不能复活", hardness="hard"
    )
    assert entry.hardness == "hard"

    updated = world_service.update_entry(session, entry.id, type="势力")

    assert updated.type == "faction"
    assert updated.hardness is None


def test_update_rejects_a_blank_name(session):
    """与 create 对称：纯空白的名字是从 Pydantic 的 min_length=1 漏过来的。"""
    project = _project(session)
    entry = world_service.create_entry(session, project.id, type="place", name="雾港旧城")

    with pytest.raises(ValueError):
        world_service.update_entry(session, entry.id, name="   ")

    assert world_service.get_entry(session, entry.id).name == "雾港旧城"


def test_update_duplicate_name_reports_the_name_the_author_typed(session):
    """报错里的名字必须是作者刚填的那个。

    rollback 会让实例 expire，若在 rollback 之后才读 entry.name，拿到的是
    改动前的旧名字 —— 于是消息会指着正在编辑的那条说「已经有叫它的条目了」。
    """
    project = _project(session)
    world_service.create_entry(session, project.id, type="place", name="甲")
    target = world_service.create_entry(session, project.id, type="place", name="乙")

    with pytest.raises(ValueError) as excinfo:
        world_service.update_entry(session, target.id, name="甲")

    assert "甲" in str(excinfo.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_world_service.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'app.services.world_service'`

- [ ] **Step 3: Write the minimal implementation**

创建 `backend/app/services/world_service.py`：

```python
"""世界观聚合的业务：设定条目、条目之间的关联、术语投影。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import EntryRelation, SettingEntry
from app.world_types import normalize_hardness, normalize_type

# 服务层说领域名（aliases / tags），存储层的 *_json 后缀不往上传 ——
# 与 idea_service.create_idea(..., tags) 的既有约定一致。
# type 与 hardness 不在此列：它们要归一化，单独处理。
_FIELD_TO_COLUMN = {
    "name": "name",
    "aliases": "aliases_json",
    "tags": "tags_json",
    "summary": "summary",
    "description": "description",
    "source_run_id": "source_run_id",
}


def _apply_entry_fields(entry: SettingEntry, fields: dict) -> None:
    """把外部字段落到条目上，途中的类型与硬度一律归一化。"""
    if fields.get("type") is not None:
        entry.type = normalize_type(fields["type"])
    if "hardness" in fields:
        entry.hardness = normalize_hardness(fields.get("hardness"))
    for name, column in _FIELD_TO_COLUMN.items():
        value = fields.get(name)
        if value is not None:
            setattr(entry, column, value)
    # 类型不是规则类时，硬度没有意义 —— 留着会让界面显示一个不存在的概念。
    # 这条在 update 路径上同样生效：把一条规则改成「势力」会清掉它的硬度。
    if entry.type != "rule":
        entry.hardness = None


def list_entries(
    session: Session, project_id: str, type: str | None = None
) -> list[SettingEntry]:
    query = select(SettingEntry).where(SettingEntry.project_id == project_id)
    if type:
        query = query.where(SettingEntry.type == normalize_type(type))
    return list(session.scalars(query.order_by(SettingEntry.created_at)))


def get_entry(session: Session, entry_id: str) -> SettingEntry | None:
    return session.get(SettingEntry, entry_id)


def create_entry(session: Session, project_id: str, **fields) -> SettingEntry:
    entry = SettingEntry(project_id=project_id, type="concept", name="")
    _apply_entry_fields(entry, fields)
    if not entry.name.strip():
        raise ValueError("设定条目必须有名称")
    name = entry.name
    session.add(entry)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        # 唯一约束在数据库上，但作者要看到中文原因而不是堆栈
        raise ValueError(f"这个项目里已经有叫「{name}」的条目了") from exc
    return entry


def update_entry(session: Session, entry_id: str, **fields) -> SettingEntry:
    entry = session.get(SettingEntry, entry_id)
    if entry is None:
        raise ValueError(f"设定条目不存在：{entry_id}")
    _apply_entry_fields(entry, fields)
    # 与 create 对称：Pydantic 的 min_length=1 只挡空串，挡不住纯空白。
    # 必须先 rollback 再抛 —— 上面那一步已经把持久对象改脏了，不回滚的话
    # 这个 session 里留着的就是那个非法值，后续读到的也是它。
    if not entry.name.strip():
        session.rollback()
        raise ValueError("设定条目必须有名称")
    # 先把名字取出来再提交：rollback 会让实例 expire，之后再读 entry.name
    # 会重新查库拿回改动前的旧名字，报错就会指着正在编辑的那条说「已经有它了」。
    name = entry.name
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ValueError(f"这个项目里已经有叫「{name}」的条目了") from exc
    return entry


def delete_entry(session: Session, entry_id: str) -> None:
    entry = session.get(SettingEntry, entry_id)
    if entry is None:
        raise ValueError(f"设定条目不存在：{entry_id}")
    session.delete(entry)
    session.commit()
```

`backend/app/api/schemas.py` 末尾追加：

```python
class EntryCreate(BaseModel):
    type: str
    name: str = Field(min_length=1, max_length=200)
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    summary: str = ""
    description: str = ""
    hardness: str | None = None
    source_run_id: str | None = None


class EntryUpdate(BaseModel):
    type: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    aliases: list[str] | None = None
    tags: list[str] | None = None
    summary: str | None = None
    description: str | None = None
    hardness: str | None = None
    source_run_id: str | None = None
```

创建 `backend/app/api/world.py`：

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.schemas import EntryCreate, EntryUpdate
from app.db.session import get_session
from app.services import world_service

router = APIRouter(prefix="/api", tags=["world"])


def _entry_out(entry) -> dict:
    return {
        "id": entry.id,
        "project_id": entry.project_id,
        "type": entry.type,
        "name": entry.name,
        "aliases": entry.aliases_json,
        "tags": entry.tags_json,
        "summary": entry.summary,
        "description": entry.description,
        "hardness": entry.hardness,
        "source_run_id": entry.source_run_id,
        "created_at": entry.created_at.isoformat(),
    }


def _entry_fields(payload: EntryCreate | EntryUpdate) -> dict:
    """只做「未传的字段别覆盖」这一件事；领域名到列名的映射在服务层内部。"""
    return payload.model_dump(exclude_unset=True)


@router.get("/projects/{project_id}/entries")
def list_entries(
    project_id: str,
    type: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[dict]:
    try:
        entries = world_service.list_entries(session, project_id, type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [_entry_out(e) for e in entries]


@router.post("/projects/{project_id}/entries", status_code=201)
def create_entry(
    project_id: str, payload: EntryCreate, session: Session = Depends(get_session)
) -> dict:
    try:
        entry = world_service.create_entry(session, project_id, **_entry_fields(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _entry_out(entry)


@router.patch("/entries/{entry_id}")
def update_entry(
    entry_id: str, payload: EntryUpdate, session: Session = Depends(get_session)
) -> dict:
    try:
        entry = world_service.update_entry(session, entry_id, **_entry_fields(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _entry_out(entry)


@router.delete("/entries/{entry_id}", status_code=204)
def delete_entry(entry_id: str, session: Session = Depends(get_session)) -> None:
    try:
        world_service.delete_entry(session, entry_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

`backend/app/main.py`：把 `world` 加进导入与挂载循环（保持字母序）：

```python
from app.api import agents, architecture, ideas, projects, providers, runs, slots, tools, world
```

```python
for module in (projects, ideas, architecture, agents, runs, tools, providers, slots, world):
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_world_service.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/world_service.py backend/app/api/world.py backend/app/api/schemas.py backend/app/main.py backend/tests/test_world_service.py
git commit -m "feat(world): 设定条目的 CRUD 服务与接口"
```

---

### Task 3: 关联 CRUD

**Files:**
- Modify: `backend/app/services/world_service.py`、`backend/app/api/world.py`、`backend/app/api/schemas.py`
- Test: `backend/tests/test_world_service.py`（追加）

**Interfaces:**
- Consumes: `EntryRelation`（Task 1）、`world_service.get_entry`（Task 2）
- Produces:
  - `world_service.list_relations(session, project_id) -> list[EntryRelation]`
  - `world_service.create_relation(session, project_id, from_id, to_id, kind, note="") -> EntryRelation`
  - `world_service.delete_relation(session, relation_id) -> None`
  - `RelationCreate`（schemas）

- [ ] **Step 1: Write the failing test**

追加到 `backend/tests/test_world_service.py`：

```python
def test_create_relation_between_two_entries(session):
    project = _project(session)
    a = world_service.create_entry(session, project.id, type="faction", name="记忆交易局")
    b = world_service.create_entry(session, project.id, type="place", name="雾港旧城")

    relation = world_service.create_relation(
        session, project.id, from_id=a.id, to_id=b.id, kind="位于", note="总部"
    )

    assert relation.kind == "位于"
    assert relation.note == "总部"
    assert [r.id for r in world_service.list_relations(session, project.id)] == [relation.id]


def test_relation_rejects_unknown_or_cross_project_entries(session):
    project = _project(session)
    other = Project(name="另一本")
    session.add(other)
    session.commit()
    a = world_service.create_entry(session, project.id, type="faction", name="甲")
    outside = world_service.create_entry(session, other.id, type="place", name="境外")

    with pytest.raises(ValueError):
        world_service.create_relation(
            session, project.id, from_id=a.id, to_id="nope", kind="位于"
        )
    with pytest.raises(ValueError):
        world_service.create_relation(
            session, project.id, from_id=a.id, to_id=outside.id, kind="位于"
        )


def test_relation_requires_a_kind(session):
    project = _project(session)
    a = world_service.create_entry(session, project.id, type="faction", name="甲")
    b = world_service.create_entry(session, project.id, type="place", name="乙")
    with pytest.raises(ValueError):
        world_service.create_relation(session, project.id, from_id=a.id, to_id=b.id, kind="  ")


def test_delete_relation(session):
    project = _project(session)
    a = world_service.create_entry(session, project.id, type="faction", name="甲")
    b = world_service.create_entry(session, project.id, type="place", name="乙")
    relation = world_service.create_relation(
        session, project.id, from_id=a.id, to_id=b.id, kind="位于"
    )

    world_service.delete_relation(session, relation.id)

    assert world_service.list_relations(session, project.id) == []
    with pytest.raises(ValueError):
        world_service.delete_relation(session, relation.id)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_world_service.py -v -k relation`
Expected: FAIL —— `AttributeError: module 'app.services.world_service' has no attribute 'create_relation'`

- [ ] **Step 3: Write the minimal implementation**

在 `backend/app/services/world_service.py` 末尾追加：

```python
def list_relations(session: Session, project_id: str) -> list[EntryRelation]:
    return list(
        session.scalars(
            select(EntryRelation)
            .where(EntryRelation.project_id == project_id)
            .order_by(EntryRelation.created_at)
        )
    )


def create_relation(
    session: Session,
    project_id: str,
    from_id: str,
    to_id: str,
    kind: str,
    note: str = "",
) -> EntryRelation:
    if not (kind or "").strip():
        raise ValueError("关联必须写明是什么关系")
    for label, entry_id in (("起点", from_id), ("终点", to_id)):
        entry = session.get(SettingEntry, entry_id)
        if entry is None:
            raise ValueError(f"关联的{label}条目不存在：{entry_id}")
        # 跨项目的关联会让「这个项目有哪些关联」失去意义
        if entry.project_id != project_id:
            raise ValueError(f"关联的{label}条目不属于这个项目：{entry_id}")
    relation = EntryRelation(
        project_id=project_id, from_id=from_id, to_id=to_id, kind=kind.strip(), note=note
    )
    session.add(relation)
    session.commit()
    return relation


def delete_relation(session: Session, relation_id: str) -> None:
    relation = session.get(EntryRelation, relation_id)
    if relation is None:
        raise ValueError(f"关联不存在：{relation_id}")
    session.delete(relation)
    session.commit()
```

`backend/app/api/schemas.py` 末尾追加：

```python
class RelationCreate(BaseModel):
    from_id: str
    to_id: str
    kind: str = Field(min_length=1, max_length=60)
    note: str = ""
```

在 `backend/app/api/world.py` 的删除条目路由之后追加：

```python
def _relation_out(relation) -> dict:
    return {
        "id": relation.id,
        "project_id": relation.project_id,
        "from_id": relation.from_id,
        "to_id": relation.to_id,
        "kind": relation.kind,
        "note": relation.note,
    }


@router.get("/projects/{project_id}/relations")
def list_relations(project_id: str, session: Session = Depends(get_session)) -> list[dict]:
    return [_relation_out(r) for r in world_service.list_relations(session, project_id)]


@router.post("/projects/{project_id}/relations", status_code=201)
def create_relation(
    project_id: str, payload: RelationCreate, session: Session = Depends(get_session)
) -> dict:
    try:
        relation = world_service.create_relation(session, project_id, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _relation_out(relation)


@router.delete("/relations/{relation_id}", status_code=204)
def delete_relation(relation_id: str, session: Session = Depends(get_session)) -> None:
    try:
        world_service.delete_relation(session, relation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

并把 `RelationCreate` 加进该文件顶部的 schemas 导入：

```python
from app.api.schemas import EntryCreate, EntryUpdate, RelationCreate
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_world_service.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/world_service.py backend/app/api/world.py backend/app/api/schemas.py backend/tests/test_world_service.py
git commit -m "feat(world): 条目之间的有向关联"
```

---

### Task 4: 类型清单与条目接口的 HTTP 层

**Files:**
- Modify: `backend/app/api/world.py`
- Test: `backend/tests/test_world_api.py`（新建）

**Interfaces:**
- Consumes: `ENTRY_TYPES` / `HARDNESS_LEVELS`（Task 1）、`app.main.app`（路由已挂载，Task 2）
- Produces: `GET /api/entry-types` 返回 `{"types": [{key, label}], "hardness": [{key, label}]}`

- [ ] **Step 1: Write the failing test**

创建 `backend/tests/test_world_api.py`：

```python
from app.world_types import ENTRY_TYPES, HARDNESS_LEVELS


def test_entry_types_endpoint_is_the_frontends_only_source(client):
    payload = client.get("/api/entry-types").json()

    assert {t["key"]: t["label"] for t in payload["types"]} == ENTRY_TYPES
    assert {h["key"]: h["label"] for h in payload["hardness"]} == HARDNESS_LEVELS
    # 顺序稳定，前端不必再排一次
    assert [t["key"] for t in payload["types"]] == list(ENTRY_TYPES)


def test_entry_crud_over_http(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()

    created = client.post(
        f"/api/projects/{project['id']}/entries",
        json={"type": "势力", "name": "记忆交易局", "aliases": ["交易局"], "tags": ["机构"]},
    ).json()
    assert created["type"] == "faction"  # 中文名被归一化
    assert created["aliases"] == ["交易局"]
    assert created["hardness"] is None

    listed = client.get(f"/api/projects/{project['id']}/entries", params={"type": "faction"}).json()
    assert [e["id"] for e in listed] == [created["id"]]

    updated = client.patch(f"/api/entries/{created['id']}", json={"summary": "管记忆买卖"}).json()
    assert updated["summary"] == "管记忆买卖"
    assert updated["name"] == "记忆交易局"  # 没传的字段不动

    assert client.delete(f"/api/entries/{created['id']}").status_code == 204
    assert client.get(f"/api/projects/{project['id']}/entries").json() == []


def test_duplicate_name_over_http_is_a_readable_400(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    body = {"type": "place", "name": "雾港旧城"}
    client.post(f"/api/projects/{project['id']}/entries", json=body)

    response = client.post(f"/api/projects/{project['id']}/entries", json=body)

    assert response.status_code == 400
    assert "雾港旧城" in response.json()["detail"]


def test_relation_crud_over_http(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    a = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "faction", "name": "甲"}
    ).json()
    b = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "place", "name": "乙"}
    ).json()

    relation = client.post(
        f"/api/projects/{project['id']}/relations",
        json={"from_id": a["id"], "to_id": b["id"], "kind": "位于"},
    ).json()
    assert relation["kind"] == "位于"

    assert client.get(f"/api/projects/{project['id']}/relations").json()[0]["id"] == relation["id"]
    assert client.delete(f"/api/relations/{relation['id']}").status_code == 204
    assert client.get(f"/api/projects/{project['id']}/relations").json() == []


def test_deleting_an_entry_removes_it_from_relations_list(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    a = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "faction", "name": "甲"}
    ).json()
    b = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "place", "name": "乙"}
    ).json()
    client.post(
        f"/api/projects/{project['id']}/relations",
        json={"from_id": a["id"], "to_id": b["id"], "kind": "位于"},
    )

    client.delete(f"/api/entries/{a['id']}")

    assert client.get(f"/api/projects/{project['id']}/relations").json() == []
```

**先做一件事：把 `client` 夹具从 `test_api.py` 搬进 `conftest.py`。**

它现在定义在 `backend/tests/test_api.py:13-32`，而 **pytest 的夹具不跨测试模块共享** —— 新建的 `test_world_api.py` 直接用它只会得到 `fixture 'client' not found`。搬进 `conftest.py` 是它本来就该在的地方。

`backend/tests/conftest.py` 末尾追加（连同它需要的导入）：

```python
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import AgentVersion, Provider
from app.db.session import SessionLocal, init_db
from app.main import app
from app.services.seed_service import seed_agents, seed_tools


@pytest.fixture()
def client():
    init_db()
    with SessionLocal() as session:
        seed_agents(session)
        seed_tools(session)
        # 跑智能体需要一家启用的服务商，这是产品行为不是测试特例。
        # 这里补上前置条件：真实 HTTP 调用被 _patch_client 替换，密钥留空即可。
        if session.scalars(select(Provider).where(Provider.enabled.is_(True))).first() is None:
            session.add(
                Provider(
                    name="测试服务商",
                    kind="custom",
                    base_url="https://api.example.com/v1",
                    enabled=True,
                )
            )
            session.commit()
        # 跑智能体同样需要智能体自身绑定了模型：运行时不再把服务商显示名
        # 当模型 ID 回落，没绑就会在解析阶段报错。预置阵容出厂不带模型名，
        # 由作者在工作室里指定 —— 这里替测试补上这个前置条件。
        for version in session.scalars(select(AgentVersion)):
            binding = dict(version.model_binding_json or {})
            if not binding.get("model"):
                version.model_binding_json = {**binding, "model": "test-model"}
                session.commit()
    with TestClient(app) as c:
        yield c
```

**这段必须与 `test_api.py` 里的原件逐字一致（包括上面那段绑定模型的循环）** —— 它是上一轮 P1a 收口时补的，因为运行时改成了「没绑模型就报错」。少抄它，`/parse` 与 `/runs` 的既有用例会当场变红。

（`conftest.py` 顶部已有 `import pytest`；`from app.db.base import Base` 等既有导入不动。）

**同时把 `backend/tests/test_api.py` 里那份删掉**（`@pytest.fixture()` + `def client()` 整段），并删掉因此不再使用的导入：`TestClient`、`SessionLocal`、`init_db`、`seed_agents`、`seed_tools`、`Provider`、`AgentVersion`、`select`、`from app.main import app`，以及 **`pytest`**（搬走之后该文件再无 `@pytest.fixture`，而 `monkeypatch` 是夹具参数、不需要 import pytest）。

该文件搬完后**只应剩三个导入**：`httpx`、`RuntimeService`（在 `_patch_client` 里局部导入）、`HttpxChatClient`（同样在 `_patch_client` 里）。实际留下的：

```python
import httpx
import pytest

from app.runtime.llm import HttpxChatClient
```

`pytest` 这一行此时已无人使用 —— 一并删掉。

搬完先跑一次全量，确认既有测试没被打破：

Run: `uv run pytest -q`
Expected: 全绿（此时代码未变，只是夹具换了位置）

**然后**，该文件只用 `client` 夹具，不要再请求 `session` 夹具 —— 两者各自重建表，混用会把数据冲掉。

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_world_api.py -v`
Expected: FAIL —— `/api/entry-types` 返回 404

- [ ] **Step 3: Write the minimal implementation**

`backend/app/api/world.py`：加导入并在最上方（`_entry_out` 之前）加类型清单路由：

```python
from app.world_types import ENTRY_TYPES, HARDNESS_LEVELS
```

```python
@router.get("/entry-types")
def list_entry_types() -> dict:
    """类型清单的唯一真相在 app/world_types.py，这里只做投影 ——
    前端不必再硬编一份，否则又会出现两份清单互相不一致的老问题。"""
    return {
        "types": [{"key": k, "label": v} for k, v in ENTRY_TYPES.items()],
        "hardness": [{"key": k, "label": v} for k, v in HARDNESS_LEVELS.items()],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_world_api.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/world.py backend/tests/test_world_api.py backend/tests/conftest.py backend/tests/test_api.py
git commit -m "feat(world): 类型清单接口与世界观的 HTTP 层测试；client 夹具移入 conftest"
```

---

### Task 5: 术语投影

**Files:**
- Modify: `backend/app/services/world_service.py`、`backend/app/api/world.py`
- Test: `backend/tests/test_world_service.py`（追加）

**Interfaces:**
- Consumes: `SettingEntry`（Task 1）、`_project` 辅助（测试内）
- Produces: `world_service.list_terms(session, project_id) -> list[dict]`，每项 `{entry_id, entry_name, type, form, is_primary}`；

- [ ] **Step 1: Write the failing test**

追加到 `backend/tests/test_world_service.py`：

```python
def test_terms_project_every_name_and_alias(session):
    project = _project(session)
    entry = world_service.create_entry(
        session,
        project.id,
        type="faction",
        name="记忆交易局",
        aliases=["交易局", "管理局"],
    )
    world_service.create_entry(session, project.id, type="term", name="一息")

    terms = world_service.list_terms(session, project.id)

    by_form = {t["form"]: t for t in terms}
    assert set(by_form) == {"记忆交易局", "交易局", "管理局", "一息"}
    assert by_form["记忆交易局"]["is_primary"] is True
    assert by_form["交易局"]["is_primary"] is False
    # 每一行都指回它的来源条目，作者才知道该去哪改
    assert by_form["交易局"]["entry_id"] == entry.id
    assert by_form["交易局"]["entry_name"] == "记忆交易局"


def test_terms_are_empty_for_an_empty_project(session):
    project = _project(session)
    assert world_service.list_terms(session, project.id) == []


def test_terms_do_not_leak_across_projects(session):
    a = _project(session)
    other = Project(name="另一本")
    session.add(other)
    session.commit()
    world_service.create_entry(session, other.id, type="place", name="别处")

    assert world_service.list_terms(session, a.id) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_world_service.py -v -k terms`
Expected: FAIL —— `AttributeError: ... has no attribute 'list_terms'`

- [ ] **Step 3: Write the minimal implementation**

在 `backend/app/services/world_service.py` 末尾追加：

```python
def list_terms(session: Session, project_id: str) -> list[dict]:
    """术语表是一个投影，不是第二张表。

    每个条目的名字与别名本来就是「专有名词的标准写法」；只有名字的裸术语
    （type == "term"）也是其中的一行。P2 的「正文出现表外新词时提醒」要查
    的就是这份白名单。
    """
    terms: list[dict] = []
    for entry in list_entries(session, project_id):
        terms.append(
            {
                "entry_id": entry.id,
                "entry_name": entry.name,
                "type": entry.type,
                "form": entry.name,
                "is_primary": True,
            }
        )
        for alias in entry.aliases_json or []:
            if not alias.strip() or alias == entry.name:
                continue
            terms.append(
                {
                    "entry_id": entry.id,
                    "entry_name": entry.name,
                    "type": entry.type,
                    "form": alias,
                    "is_primary": False,
                }
            )
    terms.sort(key=lambda t: t["form"])
    return terms
```

在 `backend/app/api/world.py` 末尾追加：

```python
@router.get("/projects/{project_id}/terms")
def list_terms(project_id: str, session: Session = Depends(get_session)) -> list[dict]:
    return world_service.list_terms(session, project_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_world_service.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/world_service.py backend/app/api/world.py backend/tests/test_world_service.py
git commit -m "feat(world): 术语表投影（名字 ∪ 别名 ∪ 裸术语）"
```

---

### Task 6: 世界观智能体进预置阵容

**Files:**
- Modify: `backend/app/agents/roster.py`
- Test: `backend/tests/test_roster.py`（追加）

**Interfaces:**
- Consumes: `ENTRY_TYPES` / `HARDNESS_LEVELS`（Task 1）
- Produces: `WORLDBUILDER_SCHEMA`、`WORLDBUILDER_PROMPT`，以及 `DEFAULT_ROSTER` 中 `key == "worldbuilder"` 的一项

- [ ] **Step 1: Write the failing test**

追加到 `backend/tests/test_roster.py`：

```python
def test_worldbuilder_is_in_the_default_roster():
    entry = next(e for e in DEFAULT_ROSTER if e["key"] == "worldbuilder")
    assert entry["task_type"] == "worldbuilding"
    assert entry["trigger_mode"] == "assist"
    assert entry["context_slots"] == ["parsed_idea", "story_bible", "project_core"]


def test_worldbuilder_prompt_forbids_inventing_settings():
    entry = next(e for e in DEFAULT_ROSTER if e["key"] == "worldbuilder")
    prompt = entry["system_prompt"]
    assert "编造" in prompt or "不许编" in prompt


def test_worldbuilder_schema_has_entries_and_open_questions():
    entry = next(e for e in DEFAULT_ROSTER if e["key"] == "worldbuilder")
    props = entry["output_schema"]["properties"]
    assert set(props) == {"entries", "open_questions"}
    assert entry["output_schema"]["required"] == ["entries"]
    item = props["entries"]["items"]
    assert set(item["properties"]) == {
        "type",
        "name",
        "aliases",
        "summary",
        "description",
        "hardness",
    }
    assert item["required"] == ["type", "name", "summary"]


def test_worldbuilder_type_descriptions_match_the_vocabulary():
    """契约里的字段说明必须把八类都讲到 —— 提示词里不许写英文键（护栏会拦），
    所以模型只可能从契约说明块里知道有哪些类型。"""
    from app.world_types import ENTRY_TYPES

    entry = next(e for e in DEFAULT_ROSTER if e["key"] == "worldbuilder")
    described = describe_contract(entry["output_schema"])

    for label in ENTRY_TYPES.values():
        assert label in described, f"契约说明块没有讲到类型「{label}」"
```

前三条依赖既有的 `DEFAULT_ROSTER` 导入与 `describe_contract` 导入（文件顶部已有 `from app.runtime.contract import describe_contract`）。

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_roster.py -v -k worldbuilder`
Expected: FAIL —— `StopIteration`（阵容里没有 worldbuilder）

- [ ] **Step 3: Write the minimal implementation**

`backend/app/agents/roster.py`：顶部加导入：

```python
from app.world_types import ENTRY_TYPES, HARDNESS_LEVELS
```

在 `ARCHITECTURE_SCHEMA` 之后加：

```python
_TYPE_TITLE = "、".join(ENTRY_TYPES.values())
_HARDNESS_TITLE = "、".join(HARDNESS_LEVELS.values())

WORLDBUILDER_SCHEMA = {
    "type": "object",
    "required": ["entries"],
    "properties": {
        "entries": {
            "type": "array",
            "minItems": 3,
            "title": "设定候选",
            "items": {
                "type": "object",
                "required": ["type", "name", "summary"],
                "properties": {
                    # 刻意不用 enum：契约说明块不渲染 enum 值的中文名，
                    # 而提示词里又不许写英文键（有护栏拦），模型将无从知道
                    # 哪个键对应哪一类。改由服务层归一化两种写法（见 world_types.py）。
                    "type": {
                        "type": "string",
                        "title": f"类型（只能是：{_TYPE_TITLE}）",
                    },
                    "name": {"type": "string", "title": "标准写法"},
                    "aliases": {
                        "type": "array",
                        "items": {"type": "string"},
                        "title": "别名与称呼",
                    },
                    "summary": {"type": "string", "title": "一句话概述"},
                    "description": {"type": "string", "title": "详细说明"},
                    "hardness": {
                        "type": "string",
                        "title": f"规则硬度（只有规则体系才填，可为：{_HARDNESS_TITLE}）",
                    },
                },
            },
        },
        "open_questions": {
            "type": "array",
            "items": {"type": "string"},
            "title": "你拿不准、需要作者确认的问题",
        },
    },
}

WORLDBUILDER_PROMPT = """你是长篇小说世界观构建师，服务对象是作者。你的产出是待作者审阅的设定候选，不是既定事实。

【灵感解析卡】
{{ parsed_idea }}

【故事圣经】
{{ story_bible }}

【项目信息】
{{ project_core }}

要求：
1. 提出 3 到 8 条这个故事的设定候选，覆盖故事真正需要的类别：地理、势力、组织、规则体系、历史事件、物品、概念、术语；
2. 每条候选的概述要说明它**为什么是这个故事需要的** —— 引用解析卡或故事圣经里的具体要素，不许泛泛而谈「丰富世界观」；
3. 规则体系类的候选必须标注硬度：硬规则是体系根基、不可违反，软规则需大体一致，氛围只为质感。其余类别的硬度留空；
4. 别名与称呼把所有叫法都列上（简称、旧称、别称、敌对方的贬称），后面查一致性靠它；
5. 你没把握的一律写进「你拿不准、需要作者确认的问题」，**不许编造设定填空**；
6. 不要替作者决定故事的走向，也不要在候选里写正文。"""
```

DEFAULT_ROSTER 列表末尾追加：

```python
    {
        "key": "worldbuilder",
        "name": "世界观构建师",
        "role_label": "设定",
        "color": "#14b8a6",
        "task_type": "worldbuilding",
        "system_prompt": WORLDBUILDER_PROMPT,
        "context_slots": ["parsed_idea", "story_bible", "project_core"],
        "output_schema": WORLDBUILDER_SCHEMA,
        "param_profile": "balanced",
        "trigger_mode": "assist",
        "note": "提设定候选，标注规则硬度，没把握就问，不编。",
    },
```

**还要改一处**：`seed_service.py` 的 `seed_agents` 目前构造 `AgentVersion` 时只传了 `version_no` / `system_prompt` / `context_slots_json` / `output_schema_json` / `param_profile` / `note`，**没有传 `trigger_mode`**，于是它会落到模型默认值 `manual` —— 新角色卡想要协同档就丢了。在 `AgentVersion(...)` 里 `param_profile` 那一行之后补一行：

```python
            trigger_mode=entry.get("trigger_mode", "manual"),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_roster.py -v`
Expected: 全部 PASS（含既有的跨产物一致性护栏 —— 它们会自动覆盖新角色卡）

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/roster.py backend/app/services/seed_service.py backend/tests/test_roster.py
git commit -m "feat(agents): 预置世界观构建师"
```

---

### Task 7: 候选生成接口

**Files:**
- Modify: `backend/app/api/world.py`
- Test: `backend/tests/test_world_api.py`（追加）

**Interfaces:**
- Consumes: `agent_service.find_by_task_type`、`RuntimeService.execute`、`_run_out`（均既有）
- Produces: `POST /api/projects/{project_id}/entries/suggest` 返回
  `{run, entries, open_questions, structured, parse_error, raw_text}`

- [ ] **Step 1: Write the failing test**

追加到 `backend/tests/test_world_api.py`：

```python
CANDIDATES = (
    '{"entries": ['
    '{"type": "faction", "name": "记忆交易局", "aliases": ["交易局"],'
    ' "summary": "管记忆买卖的机构", "description": "", "hardness": ""},'
    '{"type": "规则体系", "name": "记忆不可复活", "aliases": [],'
    ' "summary": "硬规则", "description": "", "hardness": "硬规则"},'
    '{"type": "place", "name": "雾港旧城", "aliases": ["旧城"],'
    ' "summary": "故事发生的南方小城", "description": "", "hardness": ""}],'
    ' "open_questions": ["记忆交易合法吗？"]}'
)
# 注意是 **3** 条：契约里 entries 有 minItems: 3，只给 2 条连校验都过不去。


def _seed_slots(project_id: str) -> None:
    """替测试补上世界观构建师要吃的前置条件：已解析的灵感与已采纳的架构。

    它的提示词引用了 parsed_idea 与 story_bible 两个槽位。槽位取不到值时
    build_context 会把它丢掉、render 随即抛 MissingVariableError，整个 run
    变成 template 错误 —— 这是产品行为（上游没做就别跑下游），不是测试
    特例，所以在这里补前置。与 client 夹具里补服务商、补模型绑定同一条路子。
    """
    from app.db.models import Architecture, Idea
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        idea = Idea(project_id=project_id, raw_text="能听见死者遗言的验尸官")
        idea.parsed_json = {
            "genre": "悬疑",
            "premise": "记忆可以被买卖的南方小城",
            "protagonist_desire": "查清那段声音的来处",
            "conflict_source": "个人真相与记忆交易秩序对撞",
            "open_questions": [],
        }
        session.add(idea)
        session.add(
            Architecture(
                project_id=project_id,
                logline="记忆清洁工在待销毁档案里听见自己的声音",
                theme="不被删除的记忆才证明一个人活过",
            )
        )
        session.commit()


def _patch_runtime(monkeypatch, content: str) -> None:
    """把运行时用的 HTTP 客户端换成固定响应的假实现。

    替换的是 RuntimeService._resolve_client 而不是 HttpxChatClient：
    后者在模块 import 时已被绑定，patch 模块属性不会影响已绑定的名字。
    """
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


def test_suggest_returns_structured_candidates(client, monkeypatch):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    _seed_slots(project["id"])
    _patch_runtime(monkeypatch, CANDIDATES)

    body = client.post(f"/api/projects/{project['id']}/entries/suggest").json()

    assert body["structured"] is True
    assert body["parse_error"] is None
    assert [e["name"] for e in body["entries"]] == ["记忆交易局", "记忆不可复活", "雾港旧城"]
    assert body["open_questions"] == ["记忆交易合法吗？"]
    assert body["run"]["rendered_prompt"]  # 调试台要能看完整链路


def test_suggest_degrades_without_losing_the_raw_text(client, monkeypatch):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    _seed_slots(project["id"])
    _patch_runtime(monkeypatch, "模型没按格式返回")

    body = client.post(f"/api/projects/{project['id']}/entries/suggest").json()

    assert body["structured"] is False
    assert body["entries"] == []
    assert body["parse_error"]
    assert body["raw_text"] == "模型没按格式返回"


def test_suggest_on_a_bare_project_tells_the_author_what_to_do_first(client, monkeypatch):
    """没解析过灵感、没采纳过架构时，世界观构建师的两个槽位是空的。

    这时不该给作者一句「模型没按契约返回」—— 模型根本没被调用，
    那是句假话，而且作者照它排查会找到错的方向。要给一句能照做的。
    """
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    _patch_runtime(monkeypatch, CANDIDATES)

    body = client.post(f"/api/projects/{project['id']}/entries/suggest").json()

    assert body["structured"] is False
    assert body["entries"] == []
    assert "灵感" in body["parse_error"]
    assert "架构" in body["parse_error"]


def test_suggest_writes_no_entries_until_adopted(client, monkeypatch):
    """候选只落在运行记录里（D-04）—— 跑一次不该往表里写任何东西。"""
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    _seed_slots(project["id"])
    _patch_runtime(monkeypatch, CANDIDATES)

    body = client.post(f"/api/projects/{project['id']}/entries/suggest").json()

    # 先确认这次真的产出了候选 —— 否则「没写库」可能只是因为跑失败了，
    # 这条测试就变成在断言「失败也不写库」，失去它想锁住的东西。
    assert body["structured"] is True
    assert len(body["entries"]) == 3
    assert client.get(f"/api/projects/{project['id']}/entries").json() == []


def test_adopting_a_candidate_records_its_source_run(client, monkeypatch):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    _seed_slots(project["id"])
    _patch_runtime(monkeypatch, CANDIDATES)
    body = client.post(f"/api/projects/{project['id']}/entries/suggest").json()
    run_id = body["run"]["id"]
    candidate = body["entries"][0]

    created = client.post(
        f"/api/projects/{project['id']}/entries",
        json={
            "type": candidate["type"],
            "name": candidate["name"],
            "aliases": candidate["aliases"],
            "summary": candidate["summary"],
            "source_run_id": run_id,
        },
    ).json()

    assert created["source_run_id"] == run_id
    assert created["type"] == "faction"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_world_api.py -v -k suggest`
Expected: FAIL —— 404（路由不存在）

- [ ] **Step 3: Write the minimal implementation**

`backend/app/api/world.py` 顶部补导入：

```python
from app.api._serializers import _run_out
from app.services import agent_service, world_service
from app.services.runtime_service import RuntimeService
```

（把原来的 `from app.services import world_service` 换成上面那行。）

在类型清单路由之后追加：

```python
def _reason(result) -> str | None:
    """未结构化时给作者一句**能照做**的话。

    契约失败有现成原因，直接用。但另外两种失败只有运行记录里的技术错误：
    - `template` 是上游还没做（提示词要的槽位取不到值），作者该去补前置；
    - 其余（网络、超时、鉴权）是调用本身出了问题。
    两者都不该被界面显示成「模型没按契约返回」—— 那可能是句假话，
    而且作者照它排查会找到错的方向。
    """
    if result.structured:
        return None
    if result.parse_error:
        return result.parse_error
    error = result.error or {}
    if error.get("kind") == "template":
        # 把运行时给出的缺失变量名附上：template 失败不只发生在「上游没做」，
        # 也发生在作者自己在工作室把提示词改坏时 —— 那种情况下上面这句指引是错的，
        # 而变量名能让作者分辨自己是哪一种。
        return (
            "这个智能体要吃灵感解析卡与故事圣经：先去「灵感与解析」跑一次解析，"
            "再到「架构推荐」采纳一套结构，然后回来生成设定。"
            f"（运行记录里说缺的是：{error.get('message') or '未知变量'}）"
        )
    return error.get("message") or "这次运行没有得到可用的返回"


@router.post("/projects/{project_id}/entries/suggest")
def suggest_entries(project_id: str, session: Session = Depends(get_session)) -> dict:
    """跑一次世界观构建师，返回候选供作者逐条审。

    候选只落在运行记录里，不写 setting_entry —— 只有作者采纳才写（D-04）。
    """
    builder = agent_service.find_by_task_type(session, "worldbuilding")
    if builder is None:
        raise HTTPException(status_code=500, detail="找不到世界观构建师，请重新预置阵容")

    service = RuntimeService(session)
    try:
        run, result = service.execute(project_id, builder.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    parsed = result.parsed or {}
    return {
        "run": _run_out(run),
        "entries": parsed.get("entries", []) if result.structured else [],
        "open_questions": parsed.get("open_questions", []) if result.structured else [],
        "structured": result.structured,
        "parse_error": _reason(result),
        "raw_text": result.raw_output,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_world_api.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 跑完整后端套件并提交**

Run: `uv run pytest -q`
Expected: 全绿（新增任务不该打破任何既有测试）

```bash
git add backend/app/api/world.py backend/tests/test_world_api.py
git commit -m "feat(world): 候选生成接口（候选只落运行记录，采纳才写库）"
```

---

### Task 8: 前端接口封装与类型

**Files:**
- Modify: `frontend/src/api/client.ts`

**Interfaces:**
- Consumes: Task 2–7 的接口
- Produces: `api.listEntries` / `createEntry` / `updateEntry` / `deleteEntry` / `listRelations` / `createRelation` / `deleteRelation` / `listEntryTypes` / `listTerms` / `suggestEntries`；类型 `SettingEntry` / `EntryRelation` / `EntryTypeOption` / `TermRow` / `SuggestResponse`

- [ ] **Step 1: 加接口与类型**

`frontend/src/api/client.ts`，在 `listTools` 之后插入：

```ts
  listEntryTypes: () => request<EntryTypesResponse>('/api/entry-types'),

  listEntries: (projectId: string, type?: string) =>
    request<SettingEntry[]>(
      `/api/projects/${projectId}/entries${type ? `?type=${encodeURIComponent(type)}` : ''}`,
    ),
  createEntry: (projectId: string, body: Record<string, unknown>) =>
    request<SettingEntry>(`/api/projects/${projectId}/entries`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  updateEntry: (entryId: string, body: Record<string, unknown>) =>
    request<SettingEntry>(`/api/entries/${entryId}`, {
      method: 'PATCH',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  deleteEntry: (entryId: string) => request<void>(`/api/entries/${entryId}`, { method: 'DELETE' }),

  listRelations: (projectId: string) =>
    request<EntryRelation[]>(`/api/projects/${projectId}/relations`),
  createRelation: (projectId: string, body: Record<string, unknown>) =>
    request<EntryRelation>(`/api/projects/${projectId}/relations`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  deleteRelation: (relationId: string) =>
    request<void>(`/api/relations/${relationId}`, { method: 'DELETE' }),

  listTerms: (projectId: string) => request<TermRow[]>(`/api/projects/${projectId}/terms`),
  suggestEntries: (projectId: string) =>
    request<SuggestResponse>(`/api/projects/${projectId}/entries/suggest`, { method: 'POST' }),
```

类型区末尾追加：

```ts
export interface EntryTypeOption {
  key: string
  label: string
}

export interface EntryTypesResponse {
  types: EntryTypeOption[]
  hardness: EntryTypeOption[]
}

export interface SettingEntry {
  id: string
  project_id: string
  type: string
  name: string
  aliases: string[]
  tags: string[]
  summary: string
  description: string
  hardness: string | null
  source_run_id: string | null
  created_at: string
}

export interface EntryRelation {
  id: string
  project_id: string
  from_id: string
  to_id: string
  kind: string
  note: string
}

export interface TermRow {
  entry_id: string
  entry_name: string
  type: string
  form: string
  is_primary: boolean
}

export interface SuggestedEntry {
  type?: string
  name?: string
  aliases?: string[]
  summary?: string
  description?: string
  hardness?: string | null
}

export interface SuggestResponse {
  run: RunView
  entries: SuggestedEntry[]
  open_questions: string[]
  structured: boolean
  parse_error: string | null
  raw_text: string
}
```

- [ ] **Step 2: 验证构建**

Run: `cd frontend && pnpm build`
Expected: 无 TypeScript 报错

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(frontend): 世界观接口封装与类型"
```

---

### Task 9: 条目编辑器组件

**Files:**
- Create: `frontend/src/components/EntryEditor.tsx`

**Interfaces:**
- Consumes: `SettingEntry` / `EntryTypesResponse`（Task 8）
- Produces: `<EntryEditor value draft onChange types />` —— 受控的**草稿表单**，不直接调接口；提交由调用方负责

- [ ] **Step 1: 写组件**

创建 `frontend/src/components/EntryEditor.tsx`：

```tsx
import type { EntryTypesResponse } from '../api/client'

/** 条目的草稿表单。受控、不调接口 —— 由 World 页与候选行各自决定怎么提交。 */
export interface EntryDraft {
  type: string
  name: string
  aliases: string
  tags: string
  summary: string
  description: string
  hardness: string
}

export const EMPTY_DRAFT: EntryDraft = {
  type: 'place',
  name: '',
  aliases: '',
  tags: '',
  summary: '',
  description: '',
  hardness: '',
}

/** 界面上别名与标签用顿号分隔 —— 作者一次输入一串比逐个添加省事。 */
export function splitList(text: string): string[] {
  return text
    .split(/[、,，]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

export function joinList(items: string[] | null | undefined): string {
  return (items ?? []).join('、')
}

export default function EntryEditor({
  draft,
  types,
  onChange,
}: {
  draft: EntryDraft
  types: EntryTypesResponse | null
  onChange: (next: EntryDraft) => void
}) {
  const set = (patch: Partial<EntryDraft>) => onChange({ ...draft, ...patch })

  return (
    <div className="space-y-3 text-sm">
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-slate-400">类型</label>
        <select
          className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          value={draft.type}
          onChange={(e) => set({ type: e.target.value })}
        >
          {(types?.types ?? []).map((t) => (
            <option key={t.key} value={t.key}>
              {t.label}
            </option>
          ))}
        </select>

        <label className="text-slate-400">标准写法</label>
        <input
          className="w-72 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          value={draft.name}
          onChange={(e) => set({ name: e.target.value })}
        />

        {draft.type === 'rule' && (
          <>
            <label className="text-slate-400">硬度</label>
            <select
              className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
              value={draft.hardness}
              onChange={(e) => set({ hardness: e.target.value })}
            >
              <option value="">（未定）</option>
              {(types?.hardness ?? []).map((h) => (
                <option key={h.key} value={h.key}>
                  {h.label}
                </option>
              ))}
            </select>
          </>
        )}
      </div>

      <label className="block">
        <span className="text-slate-500">别名与称呼（顿号分隔）</span>
        <input
          className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          value={draft.aliases}
          onChange={(e) => set({ aliases: e.target.value })}
        />
      </label>

      <label className="block">
        <span className="text-slate-500">标签（顿号分隔）</span>
        <input
          className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          value={draft.tags}
          onChange={(e) => set({ tags: e.target.value })}
        />
      </label>

      <label className="block">
        <span className="text-slate-500">一句话概述</span>
        <textarea
          className="mt-1 h-16 w-full rounded border border-slate-700 bg-slate-900 p-3 text-sm"
          value={draft.summary}
          onChange={(e) => set({ summary: e.target.value })}
        />
      </label>

      <label className="block">
        <span className="text-slate-500">详细说明</span>
        <textarea
          className="mt-1 h-40 w-full rounded border border-slate-700 bg-slate-900 p-3 text-sm"
          value={draft.description}
          onChange={(e) => set({ description: e.target.value })}
        />
      </label>

      {draft.type === 'rule' && (
        <p className="text-xs text-slate-500">
          硬规则是体系根基、不可违反；软规则需大体一致；氛围只为质感。这条标注决定日后检查环节的严格程度。
        </p>
      )}
    </div>
  )
}
```

- [ ] **Step 2: 验证构建**

Run: `cd frontend && pnpm build`
Expected: 无 TypeScript 报错

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/EntryEditor.tsx
git commit -m "feat(frontend): 条目编辑器组件"
```

---

### Task 10: 世界观主页面（树 + 编辑器 + 手工路径）

**Files:**
- Create: `frontend/src/pages/World.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `api.listEntryTypes` / `listEntries` / `createEntry` / `updateEntry` / `deleteEntry` / `listRelations` / `createRelation` / `deleteRelation`（Task 8）、`EntryEditor` / `EntryDraft` / `EMPTY_DRAFT` / `splitList` / `joinList`（Task 9）
- Produces: 路由 `/world`；供 Task 11 追加候选区的挂载点（本任务先建页面骨架与手工路径）

- [ ] **Step 1: 写页面**

创建 `frontend/src/pages/World.tsx`：

```tsx
import { useEffect, useMemo, useState } from 'react'
import {
  api,
  type EntryRelation,
  type EntryTypesResponse,
  type Project,
  type SettingEntry,
} from '../api/client'
import EntryEditor, {
  EMPTY_DRAFT,
  joinList,
  splitList,
  type EntryDraft,
} from '../components/EntryEditor'

function draftOf(entry: SettingEntry): EntryDraft {
  return {
    type: entry.type,
    name: entry.name,
    aliases: joinList(entry.aliases),
    tags: joinList(entry.tags),
    summary: entry.summary,
    description: entry.description,
    hardness: entry.hardness ?? '',
  }
}

export default function World() {
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [types, setTypes] = useState<EntryTypesResponse | null>(null)
  const [entries, setEntries] = useState<SettingEntry[]>([])
  const [relations, setRelations] = useState<EntryRelation[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [draft, setDraft] = useState<EntryDraft>(EMPTY_DRAFT)
  const [creating, setCreating] = useState(false)
  const [notice, setNotice] = useState('')
  const [relationDraft, setRelationDraft] = useState({ to_id: '', kind: '' })

  useEffect(() => {
    api.listEntryTypes().then(setTypes)
    api.listProjects().then((list) => {
      setProjects(list)
      if (list[0]) setProjectId(list[0].id)
    })
  }, [])

  const typeLabel = useMemo(() => {
    const map = new Map((types?.types ?? []).map((t) => [t.key, t.label]))
    return (key: string) => map.get(key) ?? key
  }, [types])

  useEffect(() => {
    if (!projectId) return
    // 换项目即整体重置：选中项、草稿、提示都跟着换，避免上一条目的内容
    // 留在编辑器里被误当成新项目的。
    setSelectedId(null)
    setCreating(false)
    setDraft(EMPTY_DRAFT)
    setNotice('')
    api.listEntries(projectId).then(setEntries).catch((e) => setNotice((e as Error).message))
    api.listRelations(projectId).then(setRelations).catch((e) => setNotice((e as Error).message))
  }, [projectId])

  function selectEntry(entry: SettingEntry) {
    setSelectedId(entry.id)
    setCreating(false)
    setDraft(draftOf(entry))
    setNotice('')
    setRelationDraft({ to_id: '', kind: '' })
  }

  function startCreating() {
    setSelectedId(null)
    setCreating(true)
    setDraft(EMPTY_DRAFT)
    setNotice('')
  }

  function payloadOf(next: EntryDraft) {
    return {
      type: next.type,
      name: next.name.trim(),
      aliases: splitList(next.aliases),
      tags: splitList(next.tags),
      summary: next.summary,
      description: next.description,
      hardness: next.hardness || null,
    }
  }

  async function refresh() {
    setEntries(await api.listEntries(projectId))
    setRelations(await api.listRelations(projectId))
  }

  async function save() {
    if (!draft.name.trim()) {
      setNotice('先给这条设定起个名字')
      return
    }
    try {
      if (creating) {
        const created = await api.createEntry(projectId, payloadOf(draft))
        await refresh()
        setCreating(false)
        setSelectedId(created.id)
      } else if (selectedId) {
        await api.updateEntry(selectedId, payloadOf(draft))
        await refresh()
      }
      setNotice('已保存')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function remove() {
    if (!selectedId) return
    if (!window.confirm('删除这条设定？指向它的关联也会一并删掉。')) return
    try {
      await api.deleteEntry(selectedId)
      setSelectedId(null)
      setDraft(EMPTY_DRAFT)
      await refresh()
      setNotice('已删除')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function addRelation() {
    if (!selectedId || !relationDraft.to_id || !relationDraft.kind.trim()) {
      setNotice('关联要选目标条目并写明是什么关系')
      return
    }
    try {
      await api.createRelation(projectId, {
        from_id: selectedId,
        to_id: relationDraft.to_id,
        kind: relationDraft.kind.trim(),
      })
      setRelationDraft({ to_id: '', kind: '' })
      await refresh()
      setNotice('已建立关联')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function removeRelation(relationId: string) {
    try {
      await api.deleteRelation(relationId)
      await refresh()
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  const grouped = useMemo(() => {
    const map = new Map<string, SettingEntry[]>()
    for (const entry of entries) {
      const list = map.get(entry.type) ?? []
      list.push(entry)
      map.set(entry.type, list)
    }
    return [...map.entries()].sort((a, b) => typeLabel(a[0]).localeCompare(typeLabel(b[0])))
  }, [entries, typeLabel])

  const outgoing = relations.filter((r) => r.from_id === selectedId)
  const nameOf = (id: string) => entries.find((e) => e.id === id)?.name ?? '（已删除）'

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-semibold">世界观</h2>
        <select
          className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
        >
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <button
          className="rounded border border-slate-700 px-4 py-2 text-sm disabled:opacity-50"
          onClick={startCreating}
          disabled={!projectId}
        >
          新建条目
        </button>
      </div>

      {notice && <p className="rounded bg-slate-900 p-3 text-sm text-slate-300">{notice}</p>}

      <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
        <nav className="space-y-3">
          {grouped.map(([type, list]) => (
            <div key={type}>
              <div className="mb-1 text-xs text-slate-500">{typeLabel(type)}</div>
              <ul className="space-y-1">
                {list.map((entry) => (
                  <li key={entry.id}>
                    <button
                      onClick={() => selectEntry(entry)}
                      className={`block w-full rounded px-3 py-1.5 text-left text-sm ${
                        selectedId === entry.id ? 'bg-slate-800' : 'hover:bg-slate-900'
                      }`}
                    >
                      {entry.name}
                      {entry.hardness && (
                        <span className="ml-2 text-xs text-slate-500">
                          {typeLabel(entry.hardness)}
                        </span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          {entries.length === 0 && (
            <p className="text-sm text-slate-500">
              还没有设定。点「新建条目」自己写，或者到上面的候选区让 AI 先提一批。
            </p>
          )}
        </nav>

        <div className="space-y-4">
          {(creating || selectedId) && (
            <section className="space-y-4 rounded border border-slate-800 p-4">
              <EntryEditor draft={draft} types={types} onChange={setDraft} />
              <div className="flex items-center gap-2">
                <button className="rounded bg-indigo-600 px-4 py-2 text-sm" onClick={save}>
                  {creating ? '创建' : '保存'}
                </button>
                {!creating && (
                  <button
                    className="rounded border border-slate-700 px-4 py-2 text-sm text-amber-400"
                    onClick={remove}
                  >
                    删除
                  </button>
                )}
              </div>
            </section>
          )}

          {selectedId && (
            <section className="space-y-3 rounded border border-slate-800 p-4 text-sm">
              <h3 className="text-sm font-medium text-slate-300">指向别处的关联</h3>
              <ul className="space-y-1">
                {outgoing.map((relation) => (
                  <li key={relation.id} className="flex items-center gap-3">
                    <span className="text-slate-400">{relation.kind}</span>
                    <span>{nameOf(relation.to_id)}</span>
                    <button
                      className="text-xs text-amber-400"
                      onClick={() => removeRelation(relation.id)}
                    >
                      删除
                    </button>
                  </li>
                ))}
                {outgoing.length === 0 && (
                  <li className="text-xs text-slate-500">还没有指向别处的关联。</li>
                )}
              </ul>
              <div className="flex flex-wrap items-center gap-2">
                <input
                  className="w-36 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                  placeholder="关系，如「位于」"
                  value={relationDraft.kind}
                  onChange={(e) => setRelationDraft({ ...relationDraft, kind: e.target.value })}
                />
                <select
                  className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                  value={relationDraft.to_id}
                  onChange={(e) => setRelationDraft({ ...relationDraft, to_id: e.target.value })}
                >
                  <option value="">选目标条目</option>
                  {entries
                    .filter((e) => e.id !== selectedId)
                    .map((e) => (
                      <option key={e.id} value={e.id}>
                        {e.name}
                      </option>
                    ))}
                </select>
                <button className="text-xs text-indigo-400" onClick={addRelation}>
                  建立关联
                </button>
              </div>
              <p className="text-xs text-slate-500">
                关联是有向的：「甲 位于 乙」与「乙 位于 甲」是两条不同的关系。
              </p>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}
```

`frontend/src/App.tsx`：导航加一项（放在「架构推荐」之后）：

```tsx
      <NavLink to="/world">世界观</NavLink>
```

并加路由：

```tsx
      <Route path="/world" element={<World />} />
```

（按该文件既有的 `NavLink` / `Route` 写法加，并 `import World from './pages/World'`。）

- [ ] **Step 2: 验证构建与手工走查**

Run: `cd frontend && pnpm build`
Expected: 无 TypeScript 报错

手工走查（服务在跑时）：
1. `/world` 空项目应看到「还没有设定」的空态。
2. 「新建条目」→ 类型选「规则体系」→ 硬度下拉出现；改成「地理」→ 硬度下拉消失。
3. 填名字与别名（顿号分隔两个）→ 创建 → 左树出现该条目，点它能回读全部字段。
4. 再建一条，给第一条加一条「位于」关联 → 列表出现；删掉目标条目 → 关联随之消失。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/World.tsx frontend/src/App.tsx
git commit -m "feat(frontend): 世界观主页面与手工建立路径"
```

---

### Task 11: 候选列表与逐条采纳

**Files:**
- Create: `frontend/src/components/CandidateList.tsx`
- Modify: `frontend/src/pages/World.tsx`

**Interfaces:**
- Consumes: `api.suggestEntries`（Task 8）、`EntryEditor` 的 `EntryDraft` / `splitList`（Task 9）、`SettingEntry[]`（Task 10 的 `entries`）
- Produces: `<CandidateList>` 与 World 页顶部的候选区

- [ ] **Step 1: 写组件**

创建 `frontend/src/components/CandidateList.tsx`：

```tsx
import { useState } from 'react'
import type { EntryTypesResponse, SettingEntry, SuggestedEntry } from '../api/client'
import EntryEditor, { joinList, type EntryDraft } from './EntryEditor'

function draftOf(candidate: SuggestedEntry): EntryDraft {
  return {
    type: candidate.type ?? 'concept',
    name: candidate.name ?? '',
    aliases: joinList(candidate.aliases),
    tags: '',
    summary: candidate.summary ?? '',
    description: candidate.description ?? '',
    hardness: candidate.hardness ?? '',
  }
}

export default function CandidateList({
  candidates,
  types,
  existing,
  busy,
  onAdopt,
  onDiscard,
}: {
  candidates: SuggestedEntry[]
  types: EntryTypesResponse | null
  existing: SettingEntry[]
  busy: boolean
  onAdopt: (draft: EntryDraft) => Promise<void>
  onDiscard: (index: number) => void
}) {
  const [openIndex, setOpenIndex] = useState<number | null>(null)
  const [draft, setDraft] = useState<EntryDraft | null>(null)

  const takenNames = new Set(existing.map((e) => e.name))

  function toggle(index: number, candidate: SuggestedEntry) {
    if (openIndex === index) {
      setOpenIndex(null)
      setDraft(null)
      return
    }
    setOpenIndex(index)
    setDraft(draftOf(candidate))
  }

  return (
    <section className="space-y-3 rounded border border-slate-800 p-4">
      <h3 className="text-sm font-medium text-slate-300">
        候选（{candidates.length} 条，逐条审）
      </h3>

      <ul className="space-y-2 text-sm">
        {candidates.map((candidate, index) => {
          const duplicated = takenNames.has(candidate.name ?? '')
          return (
            <li key={`${candidate.name}-${index}`} className="space-y-2 border-b border-slate-800 pb-2 last:border-0">
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-xs text-slate-500">{candidate.type ?? '?'}</span>
                <span className="font-medium">{candidate.name}</span>
                {duplicated && <span className="text-xs text-amber-400">已存在，默认跳过</span>}
                <button className="text-xs text-indigo-400" onClick={() => toggle(index, candidate)}>
                  {openIndex === index ? '收起' : '改后采纳'}
                </button>
                <button className="text-xs text-slate-500" onClick={() => onDiscard(index)}>
                  丢弃
                </button>
                {!duplicated && (
                  <button
                    className="text-xs text-emerald-400 disabled:opacity-50"
                    disabled={busy}
                    onClick={() => onAdopt(draftOf(candidate))}
                  >
                    采纳
                  </button>
                )}
              </div>
              <p className="text-xs text-slate-400">{candidate.summary}</p>

              {openIndex === index && draft && (
                <div className="space-y-3 rounded bg-slate-900/60 p-3">
                  <EntryEditor draft={draft} types={types} onChange={setDraft} />
                  <button
                    className="rounded bg-emerald-700 px-4 py-2 text-sm disabled:opacity-50"
                    disabled={busy}
                    onClick={async () => {
                      await onAdopt(draft)
                      setOpenIndex(null)
                      setDraft(null)
                    }}
                  >
                    按改后的内容采纳
                  </button>
                </div>
              )}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
```

（`splitList` 由调用方使用，这里不直接 import —— 若 lint 报未使用，从 import 中删掉它。）

- [ ] **Step 2: 接进 World 页**

`frontend/src/pages/World.tsx`：加导入：

```tsx
import CandidateList from '../components/CandidateList'
```

加状态：

```tsx
  const [candidates, setCandidates] = useState<SuggestedEntry[]>([])
  const [openQuestions, setOpenQuestions] = useState<string[]>([])
  const [suggesting, setSuggesting] = useState(false)
  const [lastRun, setLastRun] = useState<RunView | null>(null)
```

（`SuggestedEntry` 与 `RunView` 加进上面 `../api/client` 的类型导入。）

加动作：

```tsx
  async function suggest() {
    setSuggesting(true)
    setNotice('')
    try {
      const result = await api.suggestEntries(projectId)
      setLastRun(result.run)
      setCandidates(result.entries)
      setOpenQuestions(result.open_questions)
      if (!result.structured) {
        setNotice(`未结构化：${result.parse_error ?? '模型没有按契约返回'}`)
      }
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setSuggesting(false)
    }
  }

  async function adoptCandidate(next: EntryDraft) {
    try {
      await api.createEntry(projectId, {
        type: next.type,
        name: next.name.trim(),
        aliases: splitList(next.aliases),
        tags: splitList(next.tags),
        summary: next.summary,
        description: next.description,
        hardness: next.hardness || null,
        source_run_id: lastRun?.id ?? null,
      })
      await refresh()
      setNotice('已采纳')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  function discardCandidate(index: number) {
    setCandidates((prev) => prev.filter((_, i) => i !== index))
  }
```

在顶部的按钮组里加：

```tsx
        <button
          className="rounded bg-indigo-600 px-4 py-2 text-sm disabled:opacity-50"
          onClick={suggest}
          disabled={!projectId || suggesting}
        >
          {suggesting ? '生成中…' : '让 AI 提候选'}
        </button>
```

在 `<p>{notice}</p>` 之后、`<div className="grid ...">` 之前插入候选区与未把握的问题：

```tsx
      {candidates.length > 0 && (
        <CandidateList
          candidates={candidates}
          types={types}
          existing={entries}
          busy={suggesting}
          onAdopt={adoptCandidate}
          onDiscard={discardCandidate}
        />
      )}

      {openQuestions.length > 0 && (
        <section className="rounded border border-slate-800 p-4 text-sm">
          <h3 className="mb-2 text-sm font-medium text-slate-300">它没把握的问题，等你补</h3>
          <ul className="list-disc space-y-1 pl-5 text-slate-300">
            {openQuestions.map((question) => (
              <li key={question}>{question}</li>
            ))}
          </ul>
        </section>
      )}

      {lastRun && (
        <section className="space-y-2">
          <h3 className="text-sm font-medium text-slate-300">最近一次生成</h3>
          <RunTrace run={lastRun} />
        </section>
      )}
```

并加 `import RunTrace from '../components/RunTrace'`。

注意：候选区里的「已存在」判定用的是 `entries`（当前项目已加载的条目），所以**切换项目后 `entries` 会重载**，判定随之更新 —— 这与「采纳后 `refresh()`」是同一条路径，不需要额外维护。

- [ ] **Step 3: 验证构建与手工走查**

Run: `cd frontend && pnpm build`
Expected: 无 TypeScript 报错

手工走查：点「让 AI 提候选」→ 候选列表出现（每行带类型、名字、概述）→ 展开一行「改后采纳」可编辑 → 点「采纳」→ 左树出现该条目、候选行的名字被标「已存在」；「丢弃」把该行移出列表；未把握的问题单列一栏。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/CandidateList.tsx frontend/src/pages/World.tsx
git commit -m "feat(frontend): 候选列表与逐条采纳"
```

---

### Task 12: 术语表页面与导航

**Files:**
- Create: `frontend/src/pages/Terms.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `api.listTerms` / `api.listEntryTypes`（Task 8）
- Produces: 路由 `/terms`

- [ ] **Step 1: 写页面**

创建 `frontend/src/pages/Terms.tsx`：

```tsx
import { useEffect, useMemo, useState } from 'react'
import { api, type EntryTypesResponse, type Project, type TermRow } from '../api/client'

export default function Terms() {
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [terms, setTerms] = useState<TermRow[]>([])
  const [types, setTypes] = useState<EntryTypesResponse | null>(null)
  const [keyword, setKeyword] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    api.listEntryTypes().then(setTypes)
    api.listProjects().then((list) => {
      setProjects(list)
      if (list[0]) setProjectId(list[0].id)
    })
  }, [])

  useEffect(() => {
    if (!projectId) return
    setTerms([])
    api
      .listTerms(projectId)
      .then(setTerms)
      .catch((error) => setNotice((error as Error).message))
  }, [projectId])

  const typeLabel = useMemo(() => {
    const map = new Map((types?.types ?? []).map((t) => [t.key, t.label]))
    return (key: string) => map.get(key) ?? key
  }, [types])

  const visible = useMemo(() => {
    const needle = keyword.trim()
    if (!needle) return terms
    return terms.filter((t) => t.form.includes(needle))
  }, [terms, keyword])

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-semibold">术语表</h2>
        <select
          className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
        >
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <input
          className="w-64 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          placeholder="查标准写法"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
        />
        <span className="text-xs text-slate-500">
          这一页是投影：每个条目的名字与别名都算术语，只有名字的裸术语也在列。
        </span>
      </div>

      {notice && <p className="rounded bg-slate-900 p-3 text-sm text-slate-300">{notice}</p>}

      <table className="w-full text-left text-sm">
        <thead className="text-xs text-slate-500">
          <tr>
            <th className="py-2">写法</th>
            <th className="py-2">类型</th>
            <th className="py-2">来源条目</th>
          </tr>
        </thead>
        <tbody>
          {visible.map((term) => (
            <tr key={`${term.entry_id}-${term.form}`} className="border-t border-slate-800">
              <td className="py-2">
                {term.form}
                {!term.is_primary && <span className="ml-2 text-xs text-slate-500">别名</span>}
              </td>
              <td className="py-2 text-slate-400">{typeLabel(term.type)}</td>
              <td className="py-2 text-slate-400">{term.entry_name}</td>
            </tr>
          ))}
          {visible.length === 0 && (
            <tr>
              <td colSpan={3} className="py-4 text-slate-500">
                还没有术语。到「世界观」页建几条设定，它们的名字与别名会自动出现在这里。
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
```

`frontend/src/App.tsx`：导航与路由各加一项 `/terms`「术语表」。

- [ ] **Step 2: 验证构建与手工走查**

Run: `cd frontend && pnpm build`
Expected: 无 TypeScript 报错

手工走查：先在世界观页建一条带两个别名的设定 → 到术语表应看到 3 行（名字 + 2 个别名），别名行标「别名」，来源条目写的是该设定的名字；搜关键字能过滤。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Terms.tsx frontend/src/App.tsx
git commit -m "feat(frontend): 术语表页面"
```

---

### Task 13: 真实模型复验

**Files:** 无（验收任务）

**Interfaces:**
- Consumes: 前 12 个任务的全部产出
- Produces: 复验结论（写进 `CLAUDE.md` 由 Task 14 完成）

**前提**：真实服务商已配置（阿里云百炼），且**每次调用都要值回票价** —— 免费额度用完即停。做之前先报预算。

- [ ] **Step 1: 重建开发库并起服务**

预置阵容新增了一张角色卡，而 `seed_agents` 是按名字幂等的（已存在即跳过），旧库里不会凭空多出「世界观构建师」；但**其余角色卡不受影响**，所以不必重建整库。

优先做法：直接起服务，让 `seed_agents` 补上缺失的那一张卡。若发现角色卡内容陈旧（提示词/契约不含本切片的新内容），再按 `CLAUDE.md` 记的做法删 `agent` / `agent_version` / `generation_run` 让预置重建（保留 `provider` 与密钥）。

```bash
cd backend && uv run uvicorn app.main:app --port 8756
cd frontend && pnpm dev
```

- [ ] **Step 2: 走 spec §1.2 的八步**

在 `http://127.0.0.1:5173`：

1. 「智能体工作室」给**世界观构建师**绑定模型并保存为新版本；
2. 「世界观」页点「让 AI 提候选」→ 候选出现，**不出现「未结构化」**；
3. 逐条审：一条直接采纳、一条改后采纳（改名字或概述）、一条丢弃；
4. 手工新建一条（不经过 AI），确认也能存；
5. 给条目加别名与标签；
6. 建立一条有向关联；
7. 给一条规则类条目标硬度；
8. 「术语表」能看到第 4 步那条的全部名字与别名；
9. 调试台展开「渲染后的完整提示词」→ 末尾有【输出契约】块。

- [ ] **Step 3: 记录结论**

把复验结果（每次真实调用的耗时与 token、是否出现「未结构化」、候选质量、发现的新问题）写进 `CLAUDE.md` §7，**新增一条阶段记录**。

**只写这条记录**：路线图表与 §8 变更记录由 Task 14 负责，不要在这里一并改 —— 否则两个任务会改同一张表。

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: P1b-1 真实模型复验结论"
```

---

### Task 14: 同步工作指引

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: 前 13 个任务的结论
- Produces: 无（文档）

- [ ] **Step 1: 更新 §7 路线图**

把 P1b 一行拆成 P1b-1（本切片）与 P1b-2（后续），并标出 P1b-1 的状态。

- [ ] **Step 2: 更新 §8 变更记录**

记录本切片推翻/新增的决定，至少包括：

| 日期 | 变更 | 依据 |
|---|---|---|
| 2026-10-16 | P1b 拆为 P1b-1（设定条目 / 规则硬度 / 术语表）与 P1b-2（人物 / 关系网 / 时间线） | 六件事一次做完约 15–17 个任务，比 P1a 还大，而 P1a 的教训是切片越大真实验证越晚 |
| 2026-10-16 | 设定条目 / 规则 / 术语**共用一张表**，用 `type` 区分 | 三者同构，共用别名、标签、关联与编辑器；代价是术语类条目会很薄 |
| 2026-10-16 | 术语表**不单独建表**，做成条目名字 ∪ 别名的投影 | 每个条目本来就有名字与别名，它们天然就是术语 |
| 2026-10-16 | 契约里的 `type` 与 `hardness` **不用 `enum`，改由服务层归一化** | 契约说明块不渲染 enum 值的中文名，而提示词里不许写英文键（护栏会拦），模型将无从知道哪个键对应哪一类；报错只影响一行，不拖垮整批候选 |
| 2026-10-16 | FTS5 顺延到 P1b-2 之后 | 检索的价值集中在设定条目上；且 FTS5 默认分词器把整串中文当一词，需先探 `trigram` 或入库前分词 |
| 2026-10-16 | 数据迁移框架记为 P1b-1 与 P1b-2 之间的薄切片 | 本切片只新建表；P1b-2 几乎必然要给 `setting_entry` 加字段，届时没有迁移框架只能删库重建 |

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: 同步 P1b-1 的路线图与变更记录"
```

---

## 附：本计划明确不做的事

- 人物、关系网、时间线（P1b-2）。
- SQLite FTS5（P1b-2 之后）。
- 数据迁移框架（P1b-1 与 P1b-2 之间）。
- 关系图可视化（D-19：一期用表格）。
- 锁定、影响面分析、快照与分支（P4）。
- 三档介入的「自动」档（P3 的管线编排）。
- 流式生成（P2，P1a 收口的决定）。
