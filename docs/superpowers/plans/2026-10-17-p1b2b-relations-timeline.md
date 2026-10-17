# P1b 收尾（关系网、时间线、预置更新）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付 P1b-2b（关系网与时间线），修掉 `seed_agents` 预置更新到不了已有安装的交付阻塞，并补上 P1b-2a 的采纳路径验证与人物字段守卫。

**Architecture:** 关系网复用 `entry_relation` 并加一个可空强度列；时间线新建 `timeline_event` 表，用显式 `order_index` 排序、自由文本记录故事内时间；预置更新给 `agent` 加稳定 `preset_key`、给 `agent_version` 加内容指纹，启动时只认领与回填、绝不静默切换版本，由作者在工作室显式应用。

**Tech Stack:** Python 3.13 / uv / FastAPI / SQLAlchemy 2 / Pydantic 2 / pytest；React 18 + TypeScript + Vite + Tailwind 3 / pnpm。

**Spec:** `docs/superpowers/specs/2026-10-17-p1b2b-relations-timeline-design.md`

## Global Constraints

- 测试基线：改动前 `cd backend && uv run pytest -q` 应为 **243 passed**；每个任务结束时只许增加、不许回退。
- 后端分层：`api` 不写业务逻辑；`services` 不碰 HTTP；`runtime` 不依赖 FastAPI。
- 标识符与代码用英文；注释、界面文案、错误信息用中文。
- **迁移只做 `create_all` 做不到的事：改已有的表。新表永远归 `create_all`。**
- **迁移语句冻结成字面量**，不从任何可变常量派生；新增列一律新开一条迁移。
- 不引入新依赖。JSON Schema 子集、排序、指纹都用标准库手写。
- 前端不写自动化测试；纯逻辑必须 pytest 覆盖。每个前端任务附手工走查要点。
- 数据目录只在 `%LOCALAPPDATA%\StoryForge\` 或 `STORYFORGE_DATA_DIR`；不得把测试数据写进程序目录。
- 本计划默认不调用真实模型；只有 Task 8 在副本库里找不到可用人物候选时，才在确认阿里云百炼额度后补一次真实调用。
- 所有实现在隔离 worktree 内进行，不直接改 master。

---

## File Structure

**后端（新建）**

- `backend/app/db/models/timeline.py` —— `TimelineEvent` 聚合模型。
- `backend/app/services/timeline_service.py` —— 时间线 CRUD、排序、参与者 / 地点校验。
- `backend/app/services/preset_service.py` —— 预置查找、内容指纹、状态判定、应用预置。
- `backend/app/api/timeline.py` —— 时间线路由。
- `backend/tests/test_timeline_service.py`
- `backend/tests/test_timeline_api.py`
- `backend/tests/test_preset_service.py`
- `backend/tests/test_preset_api.py`

**后端（修改）**

- `backend/app/db/migrations.py` —— v2 / v3。
- `backend/app/db/models/world.py` —— `EntryRelation.strength`。
- `backend/app/db/models/agent.py` —— `Agent.preset_key`、`AgentVersion.preset_fingerprint`。
- `backend/app/db/models/__init__.py` —— 导出 `TimelineEvent`。
- `backend/app/services/world_service.py` —— 关系强度 / 更新 / 双向；删除条目时清理时间线参与者。
- `backend/app/services/seed_service.py` —— 按 `preset_key` 认领、回填指纹。
- `backend/app/services/agent_service.py` —— `get_agent`；`create_version` 显式处理指纹（默认不继承）。
- `backend/app/api/schemas.py` —— 关系强度 / 更新请求体。
- `backend/app/api/world.py` —— 关系 PATCH、强度输出。
- `backend/app/api/agents.py` —— 预置状态、`apply-preset`。
- `backend/app/main.py` —— 挂载时间线路由。
- `backend/tests/test_migrations.py`、`test_migration_runner.py`、`test_models.py`、`test_world_service.py`、`test_world_api.py`、`test_seed_service.py`、`test_agents_service.py`。

**前端（新建）**

- `frontend/src/pages/Relations.tsx` —— 关系网表格页。
- `frontend/src/pages/Timeline.tsx` —— 时间线页。

**前端（修改）**

- `frontend/src/api/client.ts` —— 关系强度、关系更新、时间线、预置状态与 `applyPreset`。
- `frontend/src/App.tsx` —— 两条导航与路由。
- `frontend/src/pages/World.tsx` —— 关系强度、人物字段守卫（保存与采纳）。
- `frontend/src/components/EntryEditor.tsx` —— `characterFieldsOf` 的守卫。
- `frontend/src/pages/Studio.tsx` —— 预置更新 / 恢复按钮。

**文档**

- `docs/superpowers/plans/2026-10-17-p1b2b-walkthrough.md` —— 手工走查清单（Task 8 新建）。
- `CLAUDE.md` —— 路线图、阶段记录、变更记录（Task 8）。

---

## Task 1: 数据基础（迁移 v2 / v3、四个模型字段、时间线模型）

**Files:**
- Modify: `backend/app/db/migrations.py`
- Modify: `backend/app/db/models/world.py`
- Modify: `backend/app/db/models/agent.py`
- Modify: `backend/app/db/models/__init__.py`
- Create: `backend/app/db/models/timeline.py`
- Test: `backend/tests/test_migrations.py`, `backend/tests/test_migration_runner.py`, `backend/tests/test_models.py`

**Interfaces:**
- Produces: `EntryRelation.strength: int | None`；`TimelineEvent`（字段见下）；`Agent.preset_key: str | None`；`AgentVersion.preset_fingerprint: str | None`；`MIGRATIONS` 到版本 3。

- [ ] **Step 1: 写失败测试 —— 迁移表**

把 `backend/tests/test_migrations.py` 中 `test_the_first_real_migration_adds_the_character_columns` 的版本断言改为三条，并新增两条冻结测试：

```python
def test_the_first_real_migration_adds_the_character_columns():
    assert [m.version for m in migrations.MIGRATIONS] == [1, 2, 3]

    step = migrations.MIGRATIONS[0]
    assert all(
        statement.startswith("ALTER TABLE setting_entry ADD COLUMN ")
        for statement in step.statements
    )
    assert migrations.latest_version() == 3


def test_v2_adds_the_relation_strength_column():
    step = migrations.MIGRATIONS[1]
    assert step.statements == (
        "ALTER TABLE entry_relation ADD COLUMN strength INTEGER",
    )


def test_v3_adds_preset_identity_and_fingerprint():
    step = migrations.MIGRATIONS[2]
    assert step.statements == (
        "ALTER TABLE agent ADD COLUMN preset_key VARCHAR(60)",
        "ALTER TABLE agent_version ADD COLUMN preset_fingerprint VARCHAR(64)",
        "CREATE UNIQUE INDEX uq_agent_preset_key ON agent(preset_key)",
    )
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_migrations.py -q`
Expected: FAIL（`latest_version()` 仍是 1、索引 2 不存在）。

- [ ] **Step 3: 实现迁移 v2 / v3**

在 `backend/app/db/migrations.py` 的 `MIGRATIONS` 元组中，v1 之后追加：

```python
    Migration(
        version=2,
        note="entry_relation 加关系强度",
        statements=(
            "ALTER TABLE entry_relation ADD COLUMN strength INTEGER",
        ),
    ),
    # 预置更新要靠两样东西：稳定的预置身份，以及「这个版本来自哪份预置」的指纹。
    # 唯一索引允许多个 NULL，只约束真正被认领的预置角色卡。
    Migration(
        version=3,
        note="agent 加预置身份与版本指纹",
        statements=(
            "ALTER TABLE agent ADD COLUMN preset_key VARCHAR(60)",
            "ALTER TABLE agent_version ADD COLUMN preset_fingerprint VARCHAR(64)",
            "CREATE UNIQUE INDEX uq_agent_preset_key ON agent(preset_key)",
        ),
    ),
```

并在 v1 的注释之后补一句：**v2 / v3 同样是冻结历史，日后加列只能新开版本。**

- [ ] **Step 4: 写失败测试 —— 模型字段**

在 `backend/tests/test_models.py` 末尾追加：

```python
def test_relation_strength_defaults_to_none(session):
    from app.db.models import EntryRelation, SettingEntry

    project = Project(name="雾港")
    session.add(project)
    session.commit()
    a = SettingEntry(project_id=project.id, type="character", name="甲")
    b = SettingEntry(project_id=project.id, type="character", name="乙")
    session.add_all([a, b])
    session.commit()
    relation = EntryRelation(project_id=project.id, from_id=a.id, to_id=b.id, kind="挚友")
    session.add(relation)
    session.commit()

    assert session.get(EntryRelation, relation.id).strength is None


def test_timeline_event_roundtrip(session):
    from app.db.models import SettingEntry, TimelineEvent

    project = Project(name="雾港")
    session.add(project)
    session.commit()
    character = SettingEntry(project_id=project.id, type="character", name="陈默")
    place = SettingEntry(project_id=project.id, type="place", name="南滨")
    session.add_all([character, place])
    session.commit()

    event = TimelineEvent(
        project_id=project.id,
        title="初遇",
        story_time="第三年·春",
        description="陈默在南滨旧城第一次听见那段声音。",
        participants_json=[character.id],
        location_id=place.id,
    )
    session.add(event)
    session.commit()

    stored = session.get(TimelineEvent, event.id)
    assert stored.title == "初遇"
    assert stored.story_time == "第三年·春"
    assert stored.participants_json == [character.id]
    assert stored.location_id == place.id
    assert stored.order_index == 0


def test_agent_preset_fields_default_to_none(session):
    agent = Agent(name="某智能体", task_type="idea_parse")
    session.add(agent)
    session.flush()
    version = AgentVersion(agent_id=agent.id, version_no=1)
    session.add(version)
    session.commit()

    assert agent.preset_key is None
    assert version.preset_fingerprint is None
```

- [ ] **Step 5: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_models.py -q`
Expected: FAIL（`EntryRelation` 没有 `strength`；`TimelineEvent` 导入失败）。

- [ ] **Step 6: 实现模型字段**

`backend/app/db/models/world.py`：
- 顶部 `from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint`。
- `EntryRelation` 在 `note` 之后加：

```python
    # 关系强度 1–5；None = 未评。旧行由迁移补成 NULL。
    strength: Mapped[int | None] = mapped_column(Integer, default=None)
```

`backend/app/db/models/agent.py`：
- 顶部 `from sqlalchemy import Boolean, ForeignKey, Index, JSON, String, Text`。
- `Agent` 加：

```python
    __table_args__ = (Index("uq_agent_preset_key", "preset_key", unique=True),)

    # 代码里的稳定预置 key。按名字判重会在作者改名后造出重复角色卡。
    preset_key: Mapped[str | None] = mapped_column(String(60), default=None)
```

- `AgentVersion` 加：

```python
    # 该版本来自哪一份预置内容；作者编辑出的版本永远为 None。
    preset_fingerprint: Mapped[str | None] = mapped_column(String(64), default=None)
```

新建 `backend/app/db/models/timeline.py`：

```python
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class TimelineEvent(IdMixin, TimestampMixin, Base):
    """故事内时间线的一条事件。

    顺序用显式 order_index，不解析 story_time：虚构历法与相对时间都没有
    可靠的字典序。story_time 只负责给人看。
    """

    __tablename__ = "timeline_event"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    story_time: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    order_index: Mapped[int] = mapped_column(Integer, default=0, index=True)
    participants_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    location_id: Mapped[str | None] = mapped_column(
        ForeignKey("setting_entry.id", ondelete="SET NULL"), default=None
    )
```

`backend/app/db/models/__init__.py`：
- 加 `from app.db.models.timeline import TimelineEvent`
- `__all__` 加 `"TimelineEvent"`。

- [ ] **Step 7: 跑模型测试确认通过**

Run: `cd backend && uv run pytest tests/test_models.py -q`
Expected: PASS。

- [ ] **Step 8: 写失败测试 —— 存量库迁移**

更新 `backend/tests/test_migration_runner.py` 的 `test_the_character_columns_are_added_to_a_pre_existing_database`。旧结构现在还必须包含 v2 / v3 要改的表；否则迁移会去 ALTER 一张不存在的表。把该测试的原始建表部分替换为：

```python
    with clean_db.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE project (id VARCHAR(36) PRIMARY KEY, name VARCHAR(200) NOT NULL,"
            " genre VARCHAR(60) NOT NULL DEFAULT '', created_at DATETIME NOT NULL,"
            " updated_at DATETIME NOT NULL)"
        )
        conn.exec_driver_sql(
            "CREATE TABLE setting_entry (id VARCHAR(36) PRIMARY KEY,"
            " project_id VARCHAR(36) NOT NULL, type VARCHAR(30) NOT NULL,"
            " name VARCHAR(200) NOT NULL, aliases_json JSON, tags_json JSON,"
            " summary TEXT, description TEXT, hardness VARCHAR(20),"
            " source_run_id VARCHAR(36))"
        )
        conn.exec_driver_sql(
            "CREATE TABLE entry_relation (id VARCHAR(36) PRIMARY KEY,"
            " project_id VARCHAR(36) NOT NULL, from_id VARCHAR(36) NOT NULL,"
            " to_id VARCHAR(36) NOT NULL, kind VARCHAR(60) NOT NULL, note TEXT)"
        )
        conn.exec_driver_sql(
            "CREATE TABLE agent (id VARCHAR(36) PRIMARY KEY, name VARCHAR(120) NOT NULL,"
            " role_label VARCHAR(60), color VARCHAR(20), task_type VARCHAR(40) NOT NULL,"
            " enabled BOOLEAN, builtin BOOLEAN, current_version_id VARCHAR(36))"
        )
        conn.exec_driver_sql(
            "CREATE TABLE agent_version (id VARCHAR(36) PRIMARY KEY,"
            " agent_id VARCHAR(36) NOT NULL, version_no INTEGER NOT NULL,"
            " system_prompt TEXT, model_binding_json JSON, param_profile VARCHAR(30),"
            " context_slots_json JSON, output_schema_json JSON, skills_json JSON,"
            " trigger_mode VARCHAR(20), note TEXT)"
        )
        conn.exec_driver_sql(
            "INSERT INTO setting_entry (id, project_id, type, name, summary)"
            " VALUES ('e1', 'p1', 'place', '南滨旧城', '小城')"
        )
        conn.exec_driver_sql(
            "INSERT INTO entry_relation (id, project_id, from_id, to_id, kind, note)"
            " VALUES ('r1', 'p1', 'e1', 'e2', '挚友', '旧关系')"
        )
        conn.exec_driver_sql(
            "INSERT INTO agent (id, name, task_type, builtin) VALUES ('a1', '旧架构师', 'architecture', 1)"
        )
        conn.exec_driver_sql(
            "INSERT INTO agent_version (id, agent_id, version_no, system_prompt)"
            " VALUES ('v1', 'a1', 1, '旧提示词')"
        )
```

把该测试末尾的迁移表断言改为：

```python
        assert conn.exec_driver_sql(
            "SELECT version FROM schema_migration ORDER BY version"
        ).fetchall() == [(0,), (1,), (2,), (3,)]
```

并在同一个测试里补断言：

```python
    relation_columns = {c["name"] for c in inspect(clean_db).get_columns("entry_relation")}
    agent_columns = {c["name"] for c in inspect(clean_db).get_columns("agent")}
    version_columns = {c["name"] for c in inspect(clean_db).get_columns("agent_version")}
    assert "strength" in relation_columns
    assert "preset_key" in agent_columns
    assert "preset_fingerprint" in version_columns
    assert "timeline_event" in inspect(clean_db).get_table_names()
    indexes = inspect(clean_db).get_indexes("agent")
    assert any(i["name"] == "uq_agent_preset_key" and i["unique"] for i in indexes)
    with clean_db.connect() as conn:
        assert conn.exec_driver_sql(
            "SELECT kind, strength FROM entry_relation WHERE id = 'r1'"
        ).fetchall() == [("挚友", None)]
        assert conn.exec_driver_sql(
            "SELECT system_prompt FROM agent_version WHERE id = 'v1'"
        ).fetchall() == [("旧提示词",)]
```

- [ ] **Step 9: 跑迁移测试确认失败再实现**

Run: `cd backend && uv run pytest tests/test_migration_runner.py::test_the_character_columns_are_added_to_a_pre_existing_database -q`
Expected: 先 FAIL（v2 不存在），补完 Step 3 / Step 6 后 PASS。

- [ ] **Step 10: 跑相关测试**

Run: `cd backend && uv run pytest tests/test_migrations.py tests/test_migration_runner.py tests/test_models.py -q`
Expected: PASS。注意 `test_migration_runner.py` 里其它用例用了 `no_pending_migrations` 或 monkeypatch，不应受影响。

- [ ] **Step 11: 提交**

```bash
git add backend/app/db/migrations.py backend/app/db/models/world.py backend/app/db/models/agent.py backend/app/db/models/timeline.py backend/app/db/models/__init__.py backend/tests/test_migrations.py backend/tests/test_migration_runner.py backend/tests/test_models.py
git commit -m "feat(db): 关系强度、时间线与预置指纹的数据基础"
```

---

## Task 2: 关系服务与 API（强度、更新、双向）

**Files:**
- Modify: `backend/app/services/world_service.py`
- Modify: `backend/app/api/schemas.py`
- Modify: `backend/app/api/world.py`
- Test: `backend/tests/test_world_service.py`, `backend/tests/test_world_api.py`

**Interfaces:**
- Produces:
  - `world_service.normalize_strength(value: int | None) -> int | None`
  - `world_service.get_relation(session, relation_id) -> EntryRelation | None`
  - `world_service.create_relation(session, project_id, create_reverse=False, **fields) -> EntryRelation`
  - `world_service.update_relation(session, relation_id, **fields) -> EntryRelation`
  - API `PATCH /api/relations/{relation_id}`；关系响应新增 `strength`。

- [ ] **Step 1: 写失败测试 —— 服务层**

在 `backend/tests/test_world_service.py` 末尾追加（顶部需要 `from app.db.models import EntryRelation, SettingEntry` 与 `from app.db.session import SessionLocal`；若已导入则复用）：

```python
def _two_characters(session, project):
    a = world_service.create_entry(session, project.id, type="character", name="陈默")
    b = world_service.create_entry(session, project.id, type="character", name="林晚")
    return a, b


def test_relation_strength_round_trip(session):
    project = _project(session)
    a, b = _two_characters(session, project)

    relation = world_service.create_relation(
        session, project.id, from_id=a.id, to_id=b.id, kind="挚友", strength=4
    )

    assert relation.strength == 4
    with SessionLocal() as fresh:
        assert fresh.get(EntryRelation, relation.id).strength == 4


def test_relation_rejects_self_loop(session):
    project = _project(session)
    a = world_service.create_entry(session, project.id, type="character", name="陈默")

    with pytest.raises(ValueError, match="不能是同一条目"):
        world_service.create_relation(
            session, project.id, from_id=a.id, to_id=a.id, kind="自恋"
        )


def test_relation_strength_must_be_one_to_five(session):
    project = _project(session)
    a, b = _two_characters(session, project)

    for bad in (0, 6, True):
        with pytest.raises(ValueError, match="1–5"):
            world_service.create_relation(
                session, project.id, from_id=a.id, to_id=b.id, kind="挚友", strength=bad
            )


def test_create_reverse_creates_both_directions(session):
    project = _project(session)
    a, b = _two_characters(session, project)

    forward = world_service.create_relation(
        session,
        project.id,
        from_id=a.id,
        to_id=b.id,
        kind="挚友",
        strength=4,
        create_reverse=True,
    )

    relations = world_service.list_relations(session, project.id)
    assert len(relations) == 2
    reverse = next(r for r in relations if r.from_id == b.id)
    assert reverse.to_id == a.id
    assert reverse.kind == "挚友"
    assert reverse.strength == 4

    world_service.update_relation(session, reverse.id, kind="陌路", strength=1)
    assert world_service.get_relation(session, forward.id).kind == "挚友"
    assert world_service.get_relation(session, reverse.id).kind == "陌路"
    assert world_service.get_relation(session, reverse.id).strength == 1


def test_update_relation_and_clear_strength(session):
    project = _project(session)
    a, b = _two_characters(session, project)
    relation = world_service.create_relation(
        session, project.id, from_id=a.id, to_id=b.id, kind="挚友", strength=3, note="旧"
    )

    updated = world_service.update_relation(
        session, relation.id, kind="师徒", strength=None, note="新"
    )

    assert updated.kind == "师徒"
    assert updated.strength is None
    assert updated.note == "新"


def test_update_relation_rejects_blank_kind(session):
    project = _project(session)
    a, b = _two_characters(session, project)
    relation = world_service.create_relation(
        session, project.id, from_id=a.id, to_id=b.id, kind="挚友"
    )

    with pytest.raises(ValueError):
        world_service.update_relation(session, relation.id, kind="   ")


def test_deleting_one_direction_keeps_the_other(session):
    project = _project(session)
    a, b = _two_characters(session, project)
    forward = world_service.create_relation(
        session, project.id, from_id=a.id, to_id=b.id, kind="挚友", create_reverse=True
    )
    reverse = next(
        r for r in world_service.list_relations(session, project.id) if r.from_id == b.id
    )

    world_service.delete_relation(session, forward.id)

    remaining = world_service.list_relations(session, project.id)
    assert [r.id for r in remaining] == [reverse.id]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_world_service.py -q`
Expected: FAIL（`create_relation` 不认 `strength` / `create_reverse`，`update_relation` 不存在）。

- [ ] **Step 3: 实现服务层**

在 `backend/app/services/world_service.py` 中，把 `create_relation` 替换为：

```python
def normalize_strength(value: int | None) -> int | None:
    """关系强度只收 1–5 的整数；None 表示未评。

    服务层再校验一次，不只依赖 Pydantic：服务层是纯逻辑、会被直接调用，
    而 router 的 422 只保护 HTTP 边界。bool 是 int 的子类，必须显式排除。
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
        raise ValueError("关系强度必须是 1–5 的整数")
    return value


def get_relation(session: Session, relation_id: str) -> EntryRelation | None:
    return session.get(EntryRelation, relation_id)


def _validate_relation_endpoints(
    session: Session, project_id: str, from_id: str, to_id: str
) -> None:
    if from_id == to_id:
        raise ValueError("关联的起点与终点不能是同一条目")
    for label, entry_id in (("起点", from_id), ("终点", to_id)):
        entry = session.get(SettingEntry, entry_id)
        if entry is None:
            raise ValueError(f"关联的{label}条目不存在：{entry_id}")
        # 跨项目的关联会让「这个项目有哪些关联」失去意义
        if entry.project_id != project_id:
            raise ValueError(f"关联的{label}条目不属于这个项目：{entry_id}")


def create_relation(
    session: Session, project_id: str, create_reverse: bool = False, **fields
) -> EntryRelation:
    """收 **fields 而不是显式签名：路由用 model_dump 展开，schema 一加字段
    显式签名就会变成运行期 TypeError。create_reverse 是显式参数，不进库。"""
    from_id = fields.get("from_id")
    to_id = fields.get("to_id")
    kind = (fields.get("kind") or "").strip()
    if not kind:
        raise ValueError("关联必须写明是什么关系")
    strength = normalize_strength(fields.get("strength"))
    note = fields.get("note") or ""
    _validate_relation_endpoints(session, project_id, from_id, to_id)

    relation = EntryRelation(
        project_id=project_id,
        from_id=from_id,
        to_id=to_id,
        kind=kind,
        strength=strength,
        note=note,
    )
    session.add(relation)
    if create_reverse:
        session.add(
            EntryRelation(
                project_id=project_id,
                from_id=to_id,
                to_id=from_id,
                kind=kind,
                strength=strength,
                note=note,
            )
        )
    session.commit()
    return relation


def update_relation(session: Session, relation_id: str, **fields) -> EntryRelation:
    """只改 kind / strength / note；端点不可改（要换端点就删了重建）。"""
    relation = session.get(EntryRelation, relation_id)
    if relation is None:
        raise ValueError(f"关联不存在：{relation_id}")
    if "kind" in fields:
        kind = (fields.get("kind") or "").strip()
        if not kind:
            raise ValueError("关联必须写明是什么关系")
        relation.kind = kind
    if "strength" in fields:
        relation.strength = normalize_strength(fields.get("strength"))
    if "note" in fields:
        relation.note = fields.get("note") or ""
    session.commit()
    return relation
```

- [ ] **Step 4: 跑服务层测试**

Run: `cd backend && uv run pytest tests/test_world_service.py -q`
Expected: PASS。

- [ ] **Step 5: 写失败测试 —— API**

在 `backend/tests/test_world_api.py` 末尾追加：

```python
def test_relation_strength_and_reverse_over_http(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    a = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "人物", "name": "陈默"}
    ).json()
    b = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "人物", "name": "林晚"}
    ).json()

    created = client.post(
        f"/api/projects/{project['id']}/relations",
        json={
            "from_id": a["id"],
            "to_id": b["id"],
            "kind": "挚友",
            "strength": 4,
            "create_reverse": True,
        },
    ).json()
    assert created["strength"] == 4

    relations = client.get(f"/api/projects/{project['id']}/relations").json()
    assert len(relations) == 2
    reverse = next(r for r in relations if r["from_id"] == b["id"])

    updated = client.patch(
        f"/api/relations/{reverse['id']}",
        json={"kind": "陌路", "strength": 1, "note": "渐生忌惮"},
    ).json()
    assert updated["kind"] == "陌路"
    assert updated["strength"] == 1
    assert updated["note"] == "渐生忌惮"


def test_relation_strength_out_of_range_is_422(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    a = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "人物", "name": "甲"}
    ).json()
    b = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "人物", "name": "乙"}
    ).json()

    response = client.post(
        f"/api/projects/{project['id']}/relations",
        json={"from_id": a["id"], "to_id": b["id"], "kind": "挚友", "strength": 6},
    )

    assert response.status_code == 422


def test_relation_update_can_clear_strength(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    a = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "人物", "name": "甲"}
    ).json()
    b = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "人物", "name": "乙"}
    ).json()
    relation = client.post(
        f"/api/projects/{project['id']}/relations",
        json={"from_id": a["id"], "to_id": b["id"], "kind": "挚友", "strength": 3},
    ).json()

    updated = client.patch(
        f"/api/relations/{relation['id']}", json={"strength": None}
    ).json()

    assert updated["strength"] is None


def test_updating_a_missing_relation_is_404(client):
    response = client.patch("/api/relations/nope", json={"kind": "挚友"})
    assert response.status_code == 404
```

- [ ] **Step 6: 跑 API 测试确认失败**

Run: `cd backend && uv run pytest tests/test_world_api.py -q`
Expected: FAIL（PATCH 路由不存在、响应没有 strength）。

- [ ] **Step 7: 实现 schema 与路由**

`backend/app/api/schemas.py`：把 `RelationCreate` 替换为：

```python
class RelationCreate(BaseModel):
    from_id: str
    to_id: str
    kind: str = Field(min_length=1, max_length=60)
    strength: int | None = Field(default=None, ge=1, le=5)
    note: str = ""
    create_reverse: bool = False


class RelationUpdate(BaseModel):
    kind: str | None = Field(default=None, min_length=1, max_length=60)
    strength: int | None = Field(default=None, ge=1, le=5)
    note: str | None = None
```

`backend/app/api/world.py`：
- 导入改为 `from app.api.schemas import EntryCreate, EntryUpdate, RelationCreate, RelationUpdate`。
- `_relation_out` 增加 `"strength": relation.strength,`。
- 在 `create_relation` 之后加：

```python
@router.patch("/relations/{relation_id}")
def update_relation(
    relation_id: str, payload: RelationUpdate, session: Session = Depends(get_session)
) -> dict:
    if world_service.get_relation(session, relation_id) is None:
        raise HTTPException(status_code=404, detail=f"关联不存在：{relation_id}")
    try:
        relation = world_service.update_relation(
            session, relation_id, **payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _relation_out(relation)
```

**注意：** `create_relation` 路由的 `**payload.model_dump()` 会同时展开 `create_reverse`，服务层已把它作为显式关键字参数接住，不需要改路由。

- [ ] **Step 8: 跑测试**

Run: `cd backend && uv run pytest tests/test_world_service.py tests/test_world_api.py -q`
Expected: PASS。

- [ ] **Step 9: 提交**

```bash
git add backend/app/services/world_service.py backend/app/api/schemas.py backend/app/api/world.py backend/tests/test_world_service.py backend/tests/test_world_api.py
git commit -m "feat(world): 关系强度、双向创建与关系编辑"
```

---

## Task 3: 时间线服务与 API（CRUD、排序、删除清理）

**Files:**
- Create: `backend/app/services/timeline_service.py`
- Create: `backend/app/api/timeline.py`
- Modify: `backend/app/services/world_service.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_timeline_service.py`, `backend/tests/test_timeline_api.py`

**Interfaces:**
- Consumes: Task 1 的 `TimelineEvent`。
- Produces:
  - `timeline_service.list_events(session, project_id) -> list[TimelineEvent]`
  - `timeline_service.get_event(session, event_id) -> TimelineEvent | None`
  - `timeline_service.create_event(session, project_id, **fields) -> TimelineEvent`
  - `timeline_service.update_event(session, event_id, **fields) -> TimelineEvent`
  - `timeline_service.move_event(session, event_id, direction: str) -> TimelineEvent`
  - `timeline_service.delete_event(session, event_id) -> None`
  - HTTP：`GET/POST /api/projects/{id}/timeline`、`PATCH/DELETE /api/timeline/{id}`、`POST /api/timeline/{id}/move`。

- [ ] **Step 1: 写失败测试 —— 服务层**

新建 `backend/tests/test_timeline_service.py`：

```python
import pytest

from app.db.models import Project, SettingEntry, TimelineEvent
from app.db.session import SessionLocal
from app.services import timeline_service, world_service


def _project(session) -> Project:
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    return project


def _entry(session, project, type_: str, name: str) -> SettingEntry:
    return world_service.create_entry(session, project.id, type=type_, name=name)


def test_create_appends_in_order(session):
    project = _project(session)
    timeline_service.create_event(session, project.id, title="第一")
    timeline_service.create_event(session, project.id, title="第二")
    timeline_service.create_event(session, project.id, title="第三")

    events = timeline_service.list_events(session, project.id)

    assert [e.title for e in events] == ["第一", "第二", "第三"]
    assert [e.order_index for e in events] == [0, 1, 2]


def test_move_up_and_down_reorders(session):
    project = _project(session)
    first = timeline_service.create_event(session, project.id, title="第一")
    second = timeline_service.create_event(session, project.id, title="第二")
    third = timeline_service.create_event(session, project.id, title="第三")

    timeline_service.move_event(session, third.id, "up")
    assert [e.title for e in timeline_service.list_events(session, project.id)] == [
        "第一",
        "第三",
        "第二",
    ]

    timeline_service.move_event(session, first.id, "down")
    assert [e.title for e in timeline_service.list_events(session, project.id)] == [
        "第三",
        "第一",
        "第二",
    ]
    assert [e.order_index for e in timeline_service.list_events(session, project.id)] == [0, 1, 2]


def test_move_at_boundary_is_a_no_op(session):
    project = _project(session)
    first = timeline_service.create_event(session, project.id, title="第一")
    timeline_service.create_event(session, project.id, title="第二")

    timeline_service.move_event(session, first.id, "up")

    assert [e.title for e in timeline_service.list_events(session, project.id)] == ["第一", "第二"]


def test_participants_must_be_characters_in_the_same_project(session):
    project = _project(session)
    other = Project(name="另一本")
    session.add(other)
    session.commit()
    place = _entry(session, project, "place", "南滨")
    outsider = _entry(session, other, "character", "外人")

    with pytest.raises(ValueError, match="不是人物"):
        timeline_service.create_event(
            session, project.id, title="事件", participants=[place.id]
        )
    with pytest.raises(ValueError, match="不属于这个项目"):
        timeline_service.create_event(
            session, project.id, title="事件", participants=[outsider.id]
        )
    with pytest.raises(ValueError, match="不存在"):
        timeline_service.create_event(
            session, project.id, title="事件", participants=["nope"]
        )


def test_participants_are_deduped(session):
    project = _project(session)
    character = _entry(session, project, "character", "陈默")

    event = timeline_service.create_event(
        session, project.id, title="事件", participants=[character.id, character.id]
    )

    assert event.participants_json == [character.id]


def test_location_must_exist_in_the_same_project(session):
    project = _project(session)
    other = Project(name="另一本")
    session.add(other)
    session.commit()
    outsider = _entry(session, other, "place", "境外")

    with pytest.raises(ValueError, match="不属于这个项目"):
        timeline_service.create_event(
            session, project.id, title="事件", location_id=outsider.id
        )
    with pytest.raises(ValueError, match="不存在"):
        timeline_service.create_event(session, project.id, title="事件", location_id="nope")


def test_update_fields_and_clear_location(session):
    project = _project(session)
    place = _entry(session, project, "place", "南滨")
    character = _entry(session, project, "character", "陈默")
    event = timeline_service.create_event(
        session,
        project.id,
        title="初遇",
        story_time="第三年·春",
        location_id=place.id,
        participants=[character.id],
    )

    updated = timeline_service.update_event(
        session,
        event.id,
        title="初遇（改）",
        story_time="第三年·夏",
        description="改了",
        location_id=None,
        participants=[],
    )

    assert updated.title == "初遇（改）"
    assert updated.story_time == "第三年·夏"
    assert updated.description == "改了"
    assert updated.location_id is None
    assert updated.participants_json == []


def test_delete_entry_removes_it_from_participants_and_clears_location(session):
    project = _project(session)
    character = _entry(session, project, "character", "陈默")
    place = _entry(session, project, "place", "南滨")
    event = timeline_service.create_event(
        session,
        project.id,
        title="初遇",
        participants=[character.id],
        location_id=place.id,
    )

    world_service.delete_entry(session, character.id)
    with SessionLocal() as fresh:
        assert fresh.get(TimelineEvent, event.id).participants_json == []

    world_service.delete_entry(session, place.id)
    with SessionLocal() as fresh:
        assert fresh.get(TimelineEvent, event.id).location_id is None


def test_events_do_not_leak_across_projects(session):
    a = _project(session)
    b = Project(name="另一本")
    session.add(b)
    session.commit()
    timeline_service.create_event(session, b.id, title="别处")

    assert timeline_service.list_events(session, a.id) == []


def test_delete_event(session):
    project = _project(session)
    event = timeline_service.create_event(session, project.id, title="甲")

    timeline_service.delete_event(session, event.id)

    assert timeline_service.list_events(session, project.id) == []
    with pytest.raises(ValueError):
        timeline_service.delete_event(session, event.id)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_timeline_service.py -q`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 实现时间线服务**

新建 `backend/app/services/timeline_service.py`：

```python
"""故事内时间线：有序事件、参与者与地点。纯手工维护，不经过模型。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SettingEntry, TimelineEvent


def list_events(session: Session, project_id: str) -> list[TimelineEvent]:
    return list(
        session.scalars(
            select(TimelineEvent)
            .where(TimelineEvent.project_id == project_id)
            .order_by(TimelineEvent.order_index, TimelineEvent.created_at)
        )
    )


def get_event(session: Session, event_id: str) -> TimelineEvent | None:
    return session.get(TimelineEvent, event_id)


def _clean_title(value: str | None) -> str:
    title = (value or "").strip()
    if not title:
        raise ValueError("时间线事件必须有标题")
    return title


def _validated_participants(
    session: Session, project_id: str, values: list[str] | None
) -> list[str]:
    out: list[str] = []
    for entry_id in values or []:
        entry = session.get(SettingEntry, entry_id)
        if entry is None:
            raise ValueError(f"参与者条目不存在：{entry_id}")
        if entry.project_id != project_id:
            raise ValueError(f"参与者条目不属于这个项目：{entry_id}")
        if entry.type != "character":
            raise ValueError(f"「{entry.name}」不是人物，不能作为时间线事件的参与者")
        if entry_id not in out:
            out.append(entry_id)
    return out


def _validated_location(
    session: Session, project_id: str, value: str | None
) -> str | None:
    if not value:
        return None
    entry = session.get(SettingEntry, value)
    if entry is None:
        raise ValueError(f"地点条目不存在：{value}")
    if entry.project_id != project_id:
        raise ValueError(f"地点条目不属于这个项目：{value}")
    return value


def create_event(session: Session, project_id: str, **fields) -> TimelineEvent:
    title = _clean_title(fields.get("title"))
    participants = _validated_participants(session, project_id, fields.get("participants"))
    location_id = _validated_location(session, project_id, fields.get("location_id"))
    last = session.scalars(
        select(TimelineEvent)
        .where(TimelineEvent.project_id == project_id)
        .order_by(TimelineEvent.order_index.desc())
    ).first()
    event = TimelineEvent(
        project_id=project_id,
        title=title,
        story_time=(fields.get("story_time") or "").strip(),
        description=fields.get("description") or "",
        order_index=(last.order_index + 1) if last else 0,
        participants_json=participants,
        location_id=location_id,
    )
    session.add(event)
    session.commit()
    return event


def update_event(session: Session, event_id: str, **fields) -> TimelineEvent:
    event = session.get(TimelineEvent, event_id)
    if event is None:
        raise ValueError(f"时间线事件不存在：{event_id}")
    if "title" in fields:
        event.title = _clean_title(fields.get("title"))
    if "story_time" in fields:
        event.story_time = (fields.get("story_time") or "").strip()
    if "description" in fields:
        event.description = fields.get("description") or ""
    if "participants" in fields:
        event.participants_json = _validated_participants(
            session, event.project_id, fields.get("participants")
        )
    if "location_id" in fields:
        event.location_id = _validated_location(
            session, event.project_id, fields.get("location_id")
        )
    session.commit()
    return event


def move_event(session: Session, event_id: str, direction: str) -> TimelineEvent:
    if direction not in ("up", "down"):
        raise ValueError("移动方向只能是 up 或 down")
    event = session.get(TimelineEvent, event_id)
    if event is None:
        raise ValueError(f"时间线事件不存在：{event_id}")
    ordered = list_events(session, event.project_id)
    index = next(i for i, item in enumerate(ordered) if item.id == event_id)
    target = index - 1 if direction == "up" else index + 1
    if target < 0 or target >= len(ordered):
        return event
    ordered.insert(target, ordered.pop(index))
    # 重排整条链，顺便把历史数据里可能的同序也归并成连续序号。
    for position, item in enumerate(ordered):
        item.order_index = position
    session.commit()
    return event


def delete_event(session: Session, event_id: str) -> None:
    event = session.get(TimelineEvent, event_id)
    if event is None:
        raise ValueError(f"时间线事件不存在：{event_id}")
    session.delete(event)
    session.commit()
```

- [ ] **Step 4: 实现删除条目时的参与者清理**

`backend/app/services/world_service.py`：
- 顶部导入改为 `from app.db.models import EntryRelation, SettingEntry, TimelineEvent`。
- `delete_entry` 替换为：

```python
def delete_entry(session: Session, entry_id: str) -> None:
    entry = session.get(SettingEntry, entry_id)
    if entry is None:
        raise ValueError(f"设定条目不存在：{entry_id}")
    # 时间线的参与者是 JSON 列表，外键管不到 —— 显式剔除。JSON 列必须
    # **赋新列表**再提交，原地 mutate 不会被 SQLAlchemy 跟踪。
    # 地点由 FK 的 ON DELETE SET NULL 处理。
    events = session.scalars(
        select(TimelineEvent).where(TimelineEvent.project_id == entry.project_id)
    ).all()
    for event in events:
        participants = list(event.participants_json or [])
        if entry_id in participants:
            event.participants_json = [pid for pid in participants if pid != entry_id]
    session.delete(entry)
    session.commit()
```

- [ ] **Step 5: 跑服务层测试**

Run: `cd backend && uv run pytest tests/test_timeline_service.py -q`
Expected: PASS。

- [ ] **Step 6: 写失败测试 —— API**

新建 `backend/tests/test_timeline_api.py`：

```python
def _project(client, name: str = "雾港") -> dict:
    return client.post("/api/projects", json={"name": name}).json()


def _entry(client, project_id: str, type_: str, name: str) -> dict:
    return client.post(
        f"/api/projects/{project_id}/entries", json={"type": type_, "name": name}
    ).json()


def test_timeline_crud_and_order_over_http(client):
    project = _project(client)
    character = _entry(client, project["id"], "人物", "陈默")
    place = _entry(client, project["id"], "地理", "南滨")

    first = client.post(
        f"/api/projects/{project['id']}/timeline",
        json={"title": "初遇", "story_time": "第三年·春"},
    ).json()
    second = client.post(
        f"/api/projects/{project['id']}/timeline",
        json={
            "title": "离别",
            "story_time": "第三年·冬",
            "participants": [character["id"]],
            "location_id": place["id"],
        },
    ).json()

    listed = client.get(f"/api/projects/{project['id']}/timeline").json()
    assert [e["title"] for e in listed] == ["初遇", "离别"]
    assert listed[1]["participants"] == [character["id"]]
    assert listed[1]["location_id"] == place["id"]

    moved = client.post(
        f"/api/timeline/{second['id']}/move", json={"direction": "up"}
    ).json()
    assert moved["title"] == "离别"
    assert [e["title"] for e in client.get(f"/api/projects/{project['id']}/timeline").json()] == [
        "离别",
        "初遇",
    ]

    updated = client.patch(
        f"/api/timeline/{first['id']}",
        json={"title": "初遇（改）", "location_id": None},
    ).json()
    assert updated["title"] == "初遇（改）"
    assert updated["location_id"] is None

    assert client.delete(f"/api/timeline/{first['id']}").status_code == 204
    assert len(client.get(f"/api/projects/{project['id']}/timeline").json()) == 1


def test_timeline_rejects_a_non_character_participant(client):
    project = _project(client)
    place = _entry(client, project["id"], "地理", "南滨")

    response = client.post(
        f"/api/projects/{project['id']}/timeline",
        json={"title": "事件", "participants": [place["id"]]},
    )

    assert response.status_code == 400
    assert "不是人物" in response.json()["detail"]


def test_timeline_unknown_event_is_404(client):
    assert client.patch("/api/timeline/nope", json={"title": "X"}).status_code == 404
    assert client.post("/api/timeline/nope/move", json={"direction": "up"}).status_code == 404
    assert client.delete("/api/timeline/nope").status_code == 404


def test_timeline_move_rejects_an_unknown_direction(client):
    project = _project(client)
    event = client.post(
        f"/api/projects/{project['id']}/timeline", json={"title": "事件"}
    ).json()

    response = client.post(f"/api/timeline/{event['id']}/move", json={"direction": "left"})

    assert response.status_code == 422
```

- [ ] **Step 7: 跑 API 测试确认失败**

Run: `cd backend && uv run pytest tests/test_timeline_api.py -q`
Expected: FAIL（路由不存在）。

- [ ] **Step 8: 实现时间线路由并挂载**

新建 `backend/app/api/timeline.py`：

```python
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.services import timeline_service

router = APIRouter(prefix="/api", tags=["timeline"])


class TimelineEventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    story_time: str = ""
    description: str = ""
    participants: list[str] = Field(default_factory=list)
    location_id: str | None = None


class TimelineEventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    story_time: str | None = None
    description: str | None = None
    participants: list[str] | None = None
    location_id: str | None = None


class TimelineMove(BaseModel):
    direction: Literal["up", "down"]


def _event_out(event) -> dict:
    return {
        "id": event.id,
        "project_id": event.project_id,
        "title": event.title,
        "story_time": event.story_time,
        "description": event.description,
        "participants": event.participants_json,
        "location_id": event.location_id,
        "order_index": event.order_index,
        "created_at": event.created_at.isoformat(),
    }


@router.get("/projects/{project_id}/timeline")
def list_timeline(project_id: str, session: Session = Depends(get_session)) -> list[dict]:
    return [_event_out(e) for e in timeline_service.list_events(session, project_id)]


@router.post("/projects/{project_id}/timeline", status_code=201)
def create_event(
    project_id: str, payload: TimelineEventCreate, session: Session = Depends(get_session)
) -> dict:
    try:
        event = timeline_service.create_event(
            session, project_id, **payload.model_dump()
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _event_out(event)


@router.patch("/timeline/{event_id}")
def update_event(
    event_id: str, payload: TimelineEventUpdate, session: Session = Depends(get_session)
) -> dict:
    if timeline_service.get_event(session, event_id) is None:
        raise HTTPException(status_code=404, detail=f"时间线事件不存在：{event_id}")
    try:
        event = timeline_service.update_event(
            session, event_id, **payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _event_out(event)


@router.post("/timeline/{event_id}/move")
def move_event(
    event_id: str, payload: TimelineMove, session: Session = Depends(get_session)
) -> dict:
    if timeline_service.get_event(session, event_id) is None:
        raise HTTPException(status_code=404, detail=f"时间线事件不存在：{event_id}")
    try:
        event = timeline_service.move_event(session, event_id, payload.direction)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _event_out(event)


@router.delete("/timeline/{event_id}", status_code=204)
def delete_event(event_id: str, session: Session = Depends(get_session)) -> None:
    try:
        timeline_service.delete_event(session, event_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

`backend/app/main.py`：
- 导入行加 `timeline`。
- 最后的 `for module in (...)` 元组末尾加 `timeline`。

- [ ] **Step 9: 跑全部测试**

Run: `cd backend && uv run pytest -q`
Expected: PASS（原 243 + 本轮新增）。

- [ ] **Step 10: 提交**

```bash
git add backend/app/services/timeline_service.py backend/app/api/timeline.py backend/app/services/world_service.py backend/app/main.py backend/tests/test_timeline_service.py backend/tests/test_timeline_api.py
git commit -m "feat(timeline): 有序时间线事件与参与者/地点关联"
```

---

## Task 4: 预置指纹、认领与应用

**Files:**
- Create: `backend/app/services/preset_service.py`
- Modify: `backend/app/services/seed_service.py`
- Modify: `backend/app/services/agent_service.py`
- Modify: `backend/app/api/agents.py`
- Test: `backend/tests/test_preset_service.py`, `backend/tests/test_seed_service.py`, `backend/tests/test_agents_service.py`, `backend/tests/test_preset_api.py`

**Interfaces:**
- Consumes: Task 1 的 `Agent.preset_key` / `AgentVersion.preset_fingerprint`。
- Produces:
  - `preset_service.preset_by_key(key) -> dict | None`
  - `preset_service.fingerprint_for_preset(preset) -> str`
  - `preset_service.fingerprint_for_version(version) -> str`
  - `preset_service.version_matches_preset(version, preset) -> bool`
  - `preset_service.status_for(agent, version) -> dict`
  - `preset_service.apply_preset(session, agent) -> AgentVersion`
  - `agent_service.get_agent(session, agent_id) -> Agent | None`
  - `agent_service.create_version(..., preset_fingerprint=None)`（内部参数，不给 HTTP）
  - API `POST /api/agents/{id}/apply-preset`；`GET /api/agents` 的每项带 `preset` 状态。

- [ ] **Step 1: 写失败测试 —— 预置服务**

新建 `backend/tests/test_preset_service.py`：

```python
import pytest

from app.agents.roster import DEFAULT_ROSTER
from app.db.models import Agent, AgentVersion
from app.services import preset_service

PRESET = DEFAULT_ROSTER[0]


def _agent_with_version(session, prompt: str | None = None, fingerprint: str | None = None):
    agent = Agent(
        name=PRESET["name"],
        role_label=PRESET["role_label"],
        color=PRESET["color"],
        task_type=PRESET["task_type"],
        builtin=True,
        preset_key=PRESET["key"],
    )
    session.add(agent)
    session.flush()
    version = AgentVersion(
        agent_id=agent.id,
        version_no=1,
        system_prompt=prompt if prompt is not None else PRESET["system_prompt"],
        context_slots_json=PRESET["context_slots"],
        output_schema_json=PRESET["output_schema"],
        param_profile=PRESET["param_profile"],
        trigger_mode=PRESET.get("trigger_mode", "manual"),
        model_binding_json={"model": "作者的模型"},
        preset_fingerprint=fingerprint,
    )
    session.add(version)
    session.flush()
    agent.current_version_id = version.id
    session.commit()
    return agent, version


def test_fingerprint_ignores_model_binding_and_note(session):
    agent, version = _agent_with_version(session)
    version.model_binding_json = {"model": "另一个"}
    version.note = "注释不同"
    session.commit()

    assert preset_service.fingerprint_for_version(version) == preset_service.fingerprint_for_preset(
        PRESET
    )


def test_status_for_up_to_date(session):
    preset_fp = preset_service.fingerprint_for_preset(PRESET)
    agent, version = _agent_with_version(session, fingerprint=preset_fp)

    status = preset_service.status_for(agent, version)

    assert status == {
        "key": PRESET["key"],
        "update_available": False,
        "can_restore": False,
        "up_to_date": True,
    }


def test_status_for_a_legacy_version_without_fingerprint(session):
    agent, version = _agent_with_version(session, fingerprint=None)

    status = preset_service.status_for(agent, version)

    assert status["update_available"] is False
    assert status["can_restore"] is True
    assert status["up_to_date"] is False


def test_status_for_a_modified_preset_version(session):
    agent, version = _agent_with_version(session, fingerprint="旧指纹")

    status = preset_service.status_for(agent, version)

    assert status["update_available"] is True
    assert status["can_restore"] is True


def test_apply_preset_creates_a_new_version_and_preserves_model_binding(session):
    agent, old = _agent_with_version(session, fingerprint="旧指纹")

    new = preset_service.apply_preset(session, agent)

    assert new.version_no == 2
    assert new.system_prompt == PRESET["system_prompt"]
    assert new.preset_fingerprint == preset_service.fingerprint_for_preset(PRESET)
    assert new.model_binding_json == {"model": "作者的模型"}
    assert agent.current_version_id == new.id
    assert session.get(AgentVersion, old.id) is not None


def test_apply_preset_rejects_when_already_up_to_date(session):
    preset_fp = preset_service.fingerprint_for_preset(PRESET)
    agent, _version = _agent_with_version(session, fingerprint=preset_fp)

    with pytest.raises(ValueError, match="已是最新"):
        preset_service.apply_preset(session, agent)


def test_apply_preset_rejects_an_agent_without_preset(session):
    agent = Agent(name="自定义", task_type="idea_parse")
    session.add(agent)
    session.commit()

    with pytest.raises(ValueError, match="没有可用的预置"):
        preset_service.apply_preset(session, agent)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_preset_service.py -q`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 实现预置服务与版本指纹**

新建 `backend/app/services/preset_service.py`：

```python
"""预置角色卡的指纹、状态与显式应用。

指纹只覆盖**会影响行为**的版本内容：提示词、上下文槽位、输出契约、参数档、
触发方式。模型绑定、技能勾选、备注是作者侧配置或描述文字，改它们不该提示
「预置有更新」。
"""

from __future__ import annotations

import hashlib
import json

from app.agents.roster import DEFAULT_ROSTER
from app.db.models import Agent, AgentVersion
from app.services import agent_service

_FINGERPRINT_FIELDS = (
    "system_prompt",
    "context_slots_json",
    "output_schema_json",
    "param_profile",
    "trigger_mode",
)


def preset_by_key(key: str | None) -> dict | None:
    if not key:
        return None
    return next((preset for preset in DEFAULT_ROSTER if preset["key"] == key), None)


def _fingerprint(payload: dict) -> str:
    raw = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fingerprint_for_preset(preset: dict) -> str:
    return _fingerprint(
        {
            "system_prompt": preset["system_prompt"],
            "context_slots_json": preset["context_slots"],
            "output_schema_json": preset["output_schema"],
            "param_profile": preset["param_profile"],
            "trigger_mode": preset.get("trigger_mode", "manual"),
        }
    )


def fingerprint_for_version(version: AgentVersion) -> str:
    return _fingerprint(
        {field: getattr(version, field) for field in _FINGERPRINT_FIELDS}
    )


def version_matches_preset(version: AgentVersion, preset: dict) -> bool:
    return fingerprint_for_version(version) == fingerprint_for_preset(preset)


def status_for(agent: Agent, version: AgentVersion | None) -> dict:
    preset = preset_by_key(agent.preset_key)
    if preset is None:
        return {
            "key": None,
            "update_available": False,
            "can_restore": False,
            "up_to_date": False,
        }
    current = fingerprint_for_preset(preset)
    saved = version.preset_fingerprint if version else None
    if saved is None:
        return {
            "key": agent.preset_key,
            "update_available": False,
            "can_restore": True,
            "up_to_date": False,
        }
    if saved == current:
        return {
            "key": agent.preset_key,
            "update_available": False,
            "can_restore": False,
            "up_to_date": True,
        }
    return {
        "key": agent.preset_key,
        "update_available": True,
        "can_restore": True,
        "up_to_date": False,
    }


def apply_preset(session, agent: Agent) -> AgentVersion:
    preset = preset_by_key(agent.preset_key)
    if preset is None:
        raise ValueError("这个智能体没有可用的预置内容")
    current = (
        session.get(AgentVersion, agent.current_version_id)
        if agent.current_version_id
        else None
    )
    fingerprint = fingerprint_for_preset(preset)
    if current is not None and current.preset_fingerprint == fingerprint:
        raise ValueError("预置已是最新")
    # 不传 model_binding_json / skills_json：create_version 从当前版本继承，
    # 那是作者的配置，不该被预置覆盖。
    return agent_service.create_version(
        session,
        agent.id,
        system_prompt=preset["system_prompt"],
        context_slots_json=preset["context_slots"],
        output_schema_json=preset["output_schema"],
        param_profile=preset["param_profile"],
        trigger_mode=preset.get("trigger_mode", "manual"),
        note=preset.get("note", ""),
        preset_fingerprint=fingerprint,
    )
```

- [ ] **Step 4: 跑测试确认失败（create_version 还不认指纹）**

Run: `cd backend && uv run pytest tests/test_preset_service.py -q`
Expected: FAIL / TypeError（`create_version` 收到未知关键字 `preset_fingerprint` 或被忽略）。

- [ ] **Step 5: 改 `agent_service` 与 `seed_service`**

`backend/app/services/agent_service.py`：
- 在 `list_agents` 之后加：

```python
def get_agent(session: Session, agent_id: str) -> Agent | None:
    return session.get(Agent, agent_id)
```

- `create_version` 的 `AgentVersion(...)` 构造里加：

```python
        # **作者编辑出的版本永远没有指纹。** 若从 base 继承，作者改一版后
        # 系统会误以为它仍是未改动的预置，下一次更新就会覆盖作者的修改。
        preset_fingerprint=fields.get("preset_fingerprint"),
```

`backend/app/services/seed_service.py`：
- 在文件顶部导入区加 `from app.services import preset_service`。
- 把 `seed_agents` 附近替换为：

```python
def _claim_agent(session: Session, preset: dict) -> tuple[Agent | None, bool]:
    """按稳定身份认领已有角色卡；返回 (agent, 是否该新建)。

    认领顺序：preset_key → 名字 → 唯一 task_type。第三步专门应对作者改过
    内置角色卡名字的情况 —— 以前按名字判重会因此建出重复角色卡。
    多个候选时既不认领也不新建：制造重复比暂时不认领更糟。
    """
    key = preset["key"]
    keyed = session.scalars(
        select(Agent).where(Agent.preset_key == key, Agent.builtin.is_(True))
    ).first()
    if keyed is not None:
        return keyed, False

    candidates = session.scalars(
        select(Agent).where(Agent.builtin.is_(True), Agent.preset_key.is_(None))
    ).all()
    by_name = [agent for agent in candidates if agent.name == preset["name"]]
    if len(by_name) == 1:
        by_name[0].preset_key = key
        session.flush()
        return by_name[0], False

    by_task = [agent for agent in candidates if agent.task_type == preset["task_type"]]
    if len(by_task) == 1:
        by_task[0].preset_key = key
        session.flush()
        return by_task[0], False
    if len(by_task) > 1:
        return None, False
    return None, True


def seed_agents(session: Session) -> int:
    created = 0
    for entry in DEFAULT_ROSTER:
        agent, should_create = _claim_agent(session, entry)
        if should_create:
            agent = Agent(
                name=entry["name"],
                role_label=entry["role_label"],
                color=entry["color"],
                task_type=entry["task_type"],
                builtin=True,
                preset_key=entry["key"],
            )
            session.add(agent)
            session.flush()
            version = AgentVersion(
                agent_id=agent.id,
                version_no=1,
                system_prompt=entry["system_prompt"],
                context_slots_json=entry["context_slots"],
                output_schema_json=entry["output_schema"],
                param_profile=entry["param_profile"],
                trigger_mode=entry.get("trigger_mode", "manual"),
                note=entry.get("note", ""),
                preset_fingerprint=preset_service.fingerprint_for_preset(entry),
            )
            session.add(version)
            session.flush()
            agent.current_version_id = version.id
            created += 1
            continue

        if agent is None:
            # 认领歧义：既不认领也不新建，下一次启动再试。
            continue

        # 已有角色卡：只回填指纹，绝不新建或切换版本。
        version = (
            session.get(AgentVersion, agent.current_version_id)
            if agent.current_version_id
            else None
        )
        if (
            version is not None
            and version.preset_fingerprint is None
            and preset_service.version_matches_preset(version, entry)
        ):
            version.preset_fingerprint = preset_service.fingerprint_for_preset(entry)
    session.commit()
    return created
```

- [ ] **Step 6: 补测试 —— 认领、回填、编辑不继承指纹**

在 `backend/tests/test_seed_service.py` 顶部导入 `DEFAULT_ROSTER` 与 `preset_service`，追加：

```python
def _legacy_agent(session, preset, prompt: str | None = None):
    agent = Agent(
        name=preset["name"],
        role_label=preset["role_label"],
        color=preset["color"],
        task_type=preset["task_type"],
        builtin=True,
    )
    session.add(agent)
    session.flush()
    version = AgentVersion(
        agent_id=agent.id,
        version_no=1,
        system_prompt=prompt if prompt is not None else preset["system_prompt"],
        context_slots_json=preset["context_slots"],
        output_schema_json=preset["output_schema"],
        param_profile=preset["param_profile"],
        trigger_mode=preset.get("trigger_mode", "manual"),
        note=preset.get("note", ""),
    )
    session.add(version)
    session.flush()
    agent.current_version_id = version.id
    session.commit()
    return agent, version


def test_seed_claims_legacy_agents_and_backfills_fingerprints(session):
    from app.agents.roster import DEFAULT_ROSTER

    preset = DEFAULT_ROSTER[0]
    agent, version = _legacy_agent(session, preset)

    seed_agents(session)

    session.refresh(agent)
    session.refresh(version)
    assert agent.preset_key == preset["key"]
    assert version.preset_fingerprint == preset_service.fingerprint_for_preset(preset)
    assert session.query(AgentVersion).filter_by(agent_id=agent.id).count() == 1


def test_seed_does_not_backfill_an_edited_version(session):
    from app.agents.roster import DEFAULT_ROSTER

    preset = DEFAULT_ROSTER[0]
    agent, version = _legacy_agent(session, preset, prompt="作者改过的提示词")

    seed_agents(session)

    session.refresh(version)
    assert agent.preset_key == preset["key"]
    assert version.preset_fingerprint is None


def test_seed_claims_a_renamed_agent_by_task_type(session):
    from app.agents.roster import DEFAULT_ROSTER

    preset = DEFAULT_ROSTER[0]
    agent, _version = _legacy_agent(session, preset)
    agent.name = "我的解析师"
    session.commit()

    seed_agents(session)

    same_task = session.query(Agent).filter_by(task_type=preset["task_type"]).all()
    assert len(same_task) == 1
    assert same_task[0].preset_key == preset["key"]


def test_seed_does_not_create_when_claiming_is_ambiguous(session):
    from app.agents.roster import DEFAULT_ROSTER

    preset = DEFAULT_ROSTER[0]
    for name in ("甲", "乙"):
        session.add(Agent(name=name, task_type=preset["task_type"], builtin=True))
    session.commit()

    seed_agents(session)

    assert session.query(Agent).filter_by(task_type=preset["task_type"]).count() == 2
```

在 `backend/tests/test_agents_service.py` 追加：

```python
def test_create_version_never_inherits_preset_fingerprint(session):
    agent = Agent(name="预置智能体", task_type="idea_parse")
    session.add(agent)
    session.flush()
    version = AgentVersion(
        agent_id=agent.id, version_no=1, system_prompt="预置", preset_fingerprint="abc"
    )
    session.add(version)
    session.flush()
    agent.current_version_id = version.id
    session.commit()

    new = agent_service.create_version(session, agent.id, system_prompt="作者改过")

    assert new.preset_fingerprint is None
```

- [ ] **Step 7: 跑服务与种子测试**

Run: `cd backend && uv run pytest tests/test_preset_service.py tests/test_seed_service.py tests/test_agents_service.py -q`
Expected: PASS。

- [ ] **Step 8: 写失败测试 —— 预置 API**

新建 `backend/tests/test_preset_api.py`：

```python
def _seeded_agent(client, task_type: str) -> dict:
    agents = client.get("/api/agents").json()
    return next(agent for agent in agents if agent["task_type"] == task_type)


def test_seeded_agents_report_their_preset_status(client):
    agent = _seeded_agent(client, "idea_parse")

    assert agent["preset"]["key"] == "idea_parser"
    assert agent["preset"]["up_to_date"] is True
    assert agent["preset"]["can_restore"] is False


def test_applying_a_preset_creates_a_new_version_and_keeps_model_binding(client):
    agent = _seeded_agent(client, "idea_parse")
    before = agent["current_version"]

    edited = client.post(
        f"/api/agents/{agent['id']}/versions",
        json={"system_prompt": "作者改过的提示词", "note": "手动编辑"},
    ).json()

    assert edited["version_no"] == before["version_no"] + 1
    listed = _seeded_agent(client, "idea_parse")
    assert listed["preset"]["can_restore"] is True
    assert listed["preset"]["update_available"] is False

    applied = client.post(f"/api/agents/{agent['id']}/apply-preset").json()

    assert applied["current_version"]["version_no"] == edited["version_no"] + 1
    assert applied["current_version"]["model_binding_json"] == edited["model_binding_json"]
    assert applied["preset"]["up_to_date"] is True

    again = client.post(f"/api/agents/{agent['id']}/apply-preset")
    assert again.status_code == 400
    assert "已是最新" in again.json()["detail"]


def test_applying_a_preset_to_an_unknown_agent_is_404(client):
    assert client.post("/api/agents/nope/apply-preset").status_code == 404
```

- [ ] **Step 9: 跑 API 测试确认失败**

Run: `cd backend && uv run pytest tests/test_preset_api.py -q`
Expected: FAIL（`preset` 字段与 `apply-preset` 路由不存在）。

- [ ] **Step 10: 实现 API**

`backend/app/api/agents.py`：
- 导入 `preset_service`。
- `_agent_out` 增加：

```python
        "preset": preset_service.status_for(agent, version),
```

- 末尾加：

```python
@router.post("/{agent_id}/apply-preset")
def apply_preset(agent_id: str, session: Session = Depends(get_session)) -> dict:
    agent = agent_service.get_agent(session, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"智能体不存在：{agent_id}")
    try:
        preset_service.apply_preset(session, agent)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    version = (
        agent_service.get_version(session, agent.current_version_id)
        if agent.current_version_id
        else None
    )
    return _agent_out(agent, version)
```

- [ ] **Step 11: 跑全部测试**

Run: `cd backend && uv run pytest -q`
Expected: PASS。

- [ ] **Step 12: 提交**

```bash
git add backend/app/services/preset_service.py backend/app/services/seed_service.py backend/app/services/agent_service.py backend/app/api/agents.py backend/tests/test_preset_service.py backend/tests/test_seed_service.py backend/tests/test_agents_service.py backend/tests/test_preset_api.py
git commit -m "feat(agents): 预置身份、内容指纹与显式应用预置"
```

---

## Task 5: 前端关系网与条目编辑器强度

**Files:**
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/src/pages/Relations.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/World.tsx`
- Modify: `frontend/src/components/EntryEditor.tsx`

**Interfaces:**
- Consumes: Task 2 的 `strength` 与 `PATCH /api/relations/{id}`。
- Produces: `/relations` 页面；世界观编辑器可录入 / 显示强度。

- [ ] **Step 1: 更新 API 客户端类型与方法**

`frontend/src/api/client.ts`：
- `EntryRelation` 加 `strength: number | null`。
- 在 `createRelation` 后加：

```ts
  updateRelation: (relationId: string, body: Record<string, unknown>) =>
    request<EntryRelation>(`/api/relations/${relationId}`, {
      method: 'PATCH',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
```

- [ ] **Step 2: 新建关系网页面**

新建 `frontend/src/pages/Relations.tsx`：

```tsx
import { useEffect, useMemo, useState } from 'react'
import { api, type EntryRelation, type Project, type SettingEntry } from '../api/client'

const STRENGTHS = [1, 2, 3, 4, 5]

interface Pair {
  key: string
  a: SettingEntry
  b: SettingEntry
  forward: EntryRelation[]
  backward: EntryRelation[]
}

export default function Relations() {
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [entries, setEntries] = useState<SettingEntry[]>([])
  const [relations, setRelations] = useState<EntryRelation[]>([])
  const [onlyCharacters, setOnlyCharacters] = useState(true)
  const [kindFilter, setKindFilter] = useState('')
  const [notice, setNotice] = useState('')
  const [draft, setDraft] = useState({
    from_id: '',
    to_id: '',
    kind: '',
    strength: '',
    note: '',
    reverse: true,
  })

  useEffect(() => {
    api.listProjects().then((list) => {
      setProjects(list)
      if (list[0]) setProjectId(list[0].id)
    })
  }, [])

  useEffect(() => {
    if (!projectId) return
    setNotice('')
    setDraft({ from_id: '', to_id: '', kind: '', strength: '', note: '', reverse: true })
    api.listEntries(projectId).then(setEntries).catch((e) => setNotice((e as Error).message))
    api.listRelations(projectId).then(setRelations).catch((e) => setNotice((e as Error).message))
  }, [projectId])

  const byId = useMemo(() => new Map(entries.map((e) => [e.id, e])), [entries])
  const selectable = onlyCharacters
    ? entries.filter((e) => e.type === 'character')
    : entries

  const pairs = useMemo(() => {
    const visible = relations.filter((relation) => {
      const from = byId.get(relation.from_id)
      const to = byId.get(relation.to_id)
      if (!from || !to) return false
      if (onlyCharacters && (from.type !== 'character' || to.type !== 'character')) return false
      if (kindFilter.trim() && !relation.kind.includes(kindFilter.trim())) return false
      return true
    })
    const map = new Map<string, Pair>()
    for (const relation of visible) {
      const from = byId.get(relation.from_id)!
      const to = byId.get(relation.to_id)!
      const [a, b] = [from, to].sort((x, y) => x.id.localeCompare(y.id))
      const key = `${a.id}:${b.id}`
      let pair = map.get(key)
      if (!pair) {
        pair = { key, a, b, forward: [], backward: [] }
        map.set(key, pair)
      }
      if (relation.from_id === a.id) pair.forward.push(relation)
      else pair.backward.push(relation)
    }
    return [...map.values()]
  }, [relations, byId, onlyCharacters, kindFilter])

  function nameOf(id: string) {
    return byId.get(id)?.name ?? '（已删除）'
  }

  async function refresh() {
    setEntries(await api.listEntries(projectId))
    setRelations(await api.listRelations(projectId))
  }

  async function add() {
    if (!draft.from_id || !draft.to_id || !draft.kind.trim()) {
      setNotice('起点、终点与关系类型都要填')
      return
    }
    try {
      await api.createRelation(projectId, {
        from_id: draft.from_id,
        to_id: draft.to_id,
        kind: draft.kind.trim(),
        strength: draft.strength ? Number(draft.strength) : null,
        note: draft.note,
        create_reverse: draft.reverse,
      })
      setDraft({ from_id: '', to_id: '', kind: '', strength: '', note: '', reverse: true })
      await refresh()
      setNotice('已建立关系')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function patch(relation: EntryRelation, body: Record<string, unknown>) {
    try {
      await api.updateRelation(relation.id, body)
      await refresh()
      setNotice('已更新')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function remove(relation: EntryRelation) {
    if (!window.confirm(`删除「${nameOf(relation.from_id)} → ${nameOf(relation.to_id)}」这条关系？`)) {
      return
    }
    try {
      await api.deleteRelation(relation.id)
      await refresh()
      setNotice('已删除')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function fillReverse(source: EntryRelation) {
    try {
      await api.createRelation(projectId, {
        from_id: source.to_id,
        to_id: source.from_id,
        kind: source.kind,
        strength: source.strength,
        note: source.note,
        create_reverse: false,
      })
      await refresh()
      setNotice('已补录反向关系；建议按语义改成对应的称谓')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  function directionRows(from: SettingEntry, to: SettingEntry, rows: EntryRelation[], other: EntryRelation[]) {
    return (
      <div className="space-y-2">
        <div className="text-xs text-slate-500">
          {from.name} → {to.name}
        </div>
        {rows.map((relation) => (
          <div key={relation.id} className="flex flex-wrap items-center gap-2 text-sm">
            <input
              className="w-32 rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm"
              defaultValue={relation.kind}
              onBlur={(e) => {
                if (e.target.value !== relation.kind) patch(relation, { kind: e.target.value })
              }}
            />
            <select
              className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm"
              value={relation.strength ?? ''}
              onChange={(e) =>
                patch(relation, { strength: e.target.value ? Number(e.target.value) : null })
              }
            >
              <option value="">未评</option>
              {STRENGTHS.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
            <input
              className="min-w-48 flex-1 rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm"
              defaultValue={relation.note}
              placeholder="备注"
              onBlur={(e) => {
                if (e.target.value !== relation.note) patch(relation, { note: e.target.value })
              }}
            />
            <button className="text-xs text-amber-400" onClick={() => remove(relation)}>
              删除
            </button>
          </div>
        ))}
        {rows.length === 0 && (
          <div className="flex items-center gap-3 text-xs text-slate-500">
            <span>未记录</span>
            {other[0] && (
              <button className="text-indigo-400" onClick={() => fillReverse(other[0])}>
                补录反向
              </button>
            )}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-semibold">关系网</h2>
        <select
          className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
        >
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm text-slate-400">
          <input
            type="checkbox"
            checked={onlyCharacters}
            onChange={(e) => setOnlyCharacters(e.target.checked)}
          />
          仅人物之间
        </label>
        <input
          className="w-40 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          placeholder="按关系类型筛"
          value={kindFilter}
          onChange={(e) => setKindFilter(e.target.value)}
        />
      </div>

      <section className="space-y-3 rounded border border-slate-800 p-4">
        <h3 className="text-sm font-medium text-slate-300">建立关系</h3>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <select
            className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm"
            value={draft.from_id}
            onChange={(e) => setDraft({ ...draft, from_id: e.target.value })}
          >
            <option value="">起点条目</option>
            {selectable.map((entry) => (
              <option key={entry.id} value={entry.id}>
                {entry.name}
              </option>
            ))}
          </select>
          <select
            className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm"
            value={draft.to_id}
            onChange={(e) => setDraft({ ...draft, to_id: e.target.value })}
          >
            <option value="">终点条目</option>
            {selectable
              .filter((entry) => entry.id !== draft.from_id)
              .map((entry) => (
                <option key={entry.id} value={entry.id}>
                  {entry.name}
                </option>
              ))}
          </select>
          <input
            className="w-32 rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm"
            placeholder="关系类型"
            value={draft.kind}
            onChange={(e) => setDraft({ ...draft, kind: e.target.value })}
          />
          <select
            className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm"
            value={draft.strength}
            onChange={(e) => setDraft({ ...draft, strength: e.target.value })}
          >
            <option value="">未评</option>
            {STRENGTHS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
          <input
            className="min-w-48 flex-1 rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm"
            placeholder="备注"
            value={draft.note}
            onChange={(e) => setDraft({ ...draft, note: e.target.value })}
          />
          <label className="flex items-center gap-2 text-slate-400">
            <input
              type="checkbox"
              checked={draft.reverse}
              onChange={(e) => setDraft({ ...draft, reverse: e.target.checked })}
            />
            同时建立反向关系
          </label>
          <button className="rounded bg-indigo-600 px-3 py-1.5 text-sm" onClick={add}>
            建立
          </button>
        </div>
        <p className="text-xs text-slate-500">
          反向那条初始与正向相同；按语义改成对应称谓（如「师父」的反向可能是「徒弟」），两侧可是不同强弱。
        </p>
      </section>

      {notice && <p className="text-sm text-slate-400">{notice}</p>}

      <div className="space-y-3">
        {pairs.map((pair) => (
          <section key={pair.key} className="space-y-3 rounded border border-slate-800 p-4">
            <h3 className="text-sm font-medium text-slate-300">
              {pair.a.name} ⇄ {pair.b.name}
            </h3>
            {directionRows(pair.a, pair.b, pair.forward, pair.backward)}
            {directionRows(pair.b, pair.a, pair.backward, pair.forward)}
          </section>
        ))}
        {pairs.length === 0 && (
          <p className="text-sm text-slate-500">
            还没有关系。先在世界观里建两个人物，再回这里建立关系。
          </p>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: 加导航与路由**

`frontend/src/App.tsx`：
- `import Relations from './pages/Relations'`
- `NAV` 在世界观后加 `{ to: '/relations', label: '关系网' }`。
- `<Routes>` 加 `<Route path="/relations" element={<Relations />} />`。

- [ ] **Step 4: 世界观页关系强度**

`frontend/src/pages/World.tsx`：
- `relationDraft` 初值与重置处加 `strength: ''`：

```tsx
  const [relationDraft, setRelationDraft] = useState({ to_id: '', kind: '', strength: '' })
```

- `addRelation` 的请求体加：

```tsx
        strength: relationDraft.strength ? Number(relationDraft.strength) : null,
```

- 新建成功后重置也带上 `strength: ''`。
- 指向别处的关联列表显示强度：

```tsx
                    <span className="text-slate-400">{relation.kind}</span>
                    <span className="text-xs text-slate-500">
                      强度 {relation.strength ?? '未评'}
                    </span>
```

- 关联表单在关系类型输入之后加：

```tsx
                <select
                  className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                  value={relationDraft.strength}
                  onChange={(e) => setRelationDraft({ ...relationDraft, strength: e.target.value })}
                >
                  <option value="">未评</option>
                  {[1, 2, 3, 4, 5].map((value) => (
                    <option key={value} value={value}>
                      强度 {value}
                    </option>
                  ))}
                </select>
```

- [ ] **Step 5: 手工走查**

启动 `cd backend && uv run uvicorn app.main:app --port 8756 --reload` 与 `cd frontend && pnpm dev`，打开 `/relations`：

- 默认只看人物↔人物；建一对人物，勾「同时建立反向」，确认出现两个方向。
- 把反向改成另一个类型与强度，刷新后保持。
- 清空一个方向的强度，显示「未评」。
- 切「仅人物之间」关闭，能看到势力/地点关联。
- 在世界观页给一条关联录入强度，关系网页能看到同一值。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/api/client.ts frontend/src/pages/Relations.tsx frontend/src/App.tsx frontend/src/pages/World.tsx
git commit -m "feat(frontend): 关系网页面与条目关系强度"
```

---

## Task 6: 前端时间线页面

**Files:**
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/src/pages/Timeline.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: Task 3 的时间线 API。
- Produces: `/timeline` 页面。

- [ ] **Step 1: 更新 API 客户端**

`frontend/src/api/client.ts`：
- 在 `listTerms` 附近加：

```ts
  listTimeline: (projectId: string) =>
    request<TimelineEvent[]>(`/api/projects/${projectId}/timeline`),
  createTimelineEvent: (projectId: string, body: Record<string, unknown>) =>
    request<TimelineEvent>(`/api/projects/${projectId}/timeline`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  updateTimelineEvent: (eventId: string, body: Record<string, unknown>) =>
    request<TimelineEvent>(`/api/timeline/${eventId}`, {
      method: 'PATCH',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  moveTimelineEvent: (eventId: string, direction: 'up' | 'down') =>
    request<TimelineEvent>(`/api/timeline/${eventId}/move`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ direction }),
    }),
  deleteTimelineEvent: (eventId: string) =>
    request<void>(`/api/timeline/${eventId}`, { method: 'DELETE' }),
```

- 类型区加：

```ts
export interface TimelineEvent {
  id: string
  project_id: string
  title: string
  story_time: string
  description: string
  participants: string[]
  location_id: string | null
  order_index: number
  created_at: string
}
```

- [ ] **Step 2: 新建时间线页面**

新建 `frontend/src/pages/Timeline.tsx`：

```tsx
import { useEffect, useMemo, useState } from 'react'
import { api, type Project, type SettingEntry, type TimelineEvent } from '../api/client'

interface Draft {
  title: string
  story_time: string
  description: string
  participants: string[]
  location_id: string
}

const EMPTY: Draft = {
  title: '',
  story_time: '',
  description: '',
  participants: [],
  location_id: '',
}

export default function Timeline() {
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [entries, setEntries] = useState<SettingEntry[]>([])
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [draft, setDraft] = useState<Draft>(EMPTY)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    api.listProjects().then((list) => {
      setProjects(list)
      if (list[0]) setProjectId(list[0].id)
    })
  }, [])

  useEffect(() => {
    if (!projectId) return
    setNotice('')
    setDraft(EMPTY)
    setEditingId(null)
    api.listEntries(projectId).then(setEntries).catch((e) => setNotice((e as Error).message))
    api.listTimeline(projectId).then(setEvents).catch((e) => setNotice((e as Error).message))
  }, [projectId])

  const byId = useMemo(() => new Map(entries.map((e) => [e.id, e])), [entries])
  const characters = entries.filter((e) => e.type === 'character')

  function nameOf(id: string) {
    return byId.get(id)?.name ?? '（已删除）'
  }

  async function refresh() {
    setEntries(await api.listEntries(projectId))
    setEvents(await api.listTimeline(projectId))
  }

  function startCreate() {
    setEditingId(null)
    setDraft(EMPTY)
    setNotice('')
  }

  function startEdit(event: TimelineEvent) {
    setEditingId(event.id)
    setDraft({
      title: event.title,
      story_time: event.story_time,
      description: event.description,
      participants: event.participants,
      location_id: event.location_id ?? '',
    })
    setNotice('')
  }

  async function save() {
    if (!draft.title.trim()) {
      setNotice('先给事件起个标题')
      return
    }
    const body = {
      title: draft.title.trim(),
      story_time: draft.story_time,
      description: draft.description,
      participants: draft.participants,
      location_id: draft.location_id || null,
    }
    try {
      if (editingId) await api.updateTimelineEvent(editingId, body)
      else await api.createTimelineEvent(projectId, body)
      await refresh()
      setDraft(EMPTY)
      setEditingId(null)
      setNotice(editingId ? '已保存' : '已新建')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function move(event: TimelineEvent, direction: 'up' | 'down') {
    try {
      await api.moveTimelineEvent(event.id, direction)
      await refresh()
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function remove(event: TimelineEvent) {
    if (!window.confirm(`删除事件「${event.title}」？`)) return
    try {
      await api.deleteTimelineEvent(event.id)
      if (editingId === event.id) {
        setEditingId(null)
        setDraft(EMPTY)
      }
      await refresh()
      setNotice('已删除')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  function toggleParticipant(id: string) {
    setDraft((prev) => ({
      ...prev,
      participants: prev.participants.includes(id)
        ? prev.participants.filter((item) => item !== id)
        : [...prev.participants, id],
    }))
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-semibold">时间线</h2>
        <select
          className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
        >
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
        <button className="rounded border border-slate-700 px-3 py-2 text-sm" onClick={startCreate}>
          新建事件
        </button>
      </div>

      {notice && <p className="text-sm text-slate-400">{notice}</p>}

      <section className="space-y-3 rounded border border-slate-800 p-4 text-sm">
        <h3 className="text-sm font-medium text-slate-300">
          {editingId ? '编辑事件' : '新建事件'}
        </h3>
        <div className="flex flex-wrap items-center gap-2">
          <input
            className="w-52 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            placeholder="标题"
            value={draft.title}
            onChange={(e) => setDraft({ ...draft, title: e.target.value })}
          />
          <input
            className="w-44 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            placeholder="故事内时间，如「第三年·春」"
            value={draft.story_time}
            onChange={(e) => setDraft({ ...draft, story_time: e.target.value })}
          />
          <select
            className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            value={draft.location_id}
            onChange={(e) => setDraft({ ...draft, location_id: e.target.value })}
          >
            <option value="">（无地点）</option>
            {entries.map((entry) => (
              <option key={entry.id} value={entry.id}>
                {entry.name}
              </option>
            ))}
          </select>
        </div>
        <textarea
          className="h-20 w-full rounded border border-slate-700 bg-slate-900 p-3 text-sm"
          placeholder="事件描述"
          value={draft.description}
          onChange={(e) => setDraft({ ...draft, description: e.target.value })}
        />
        <div className="space-y-2">
          <div className="text-slate-400">参与者（只列人物）</div>
          <div className="flex flex-wrap gap-2">
            {characters.map((character) => {
              const on = draft.participants.includes(character.id)
              return (
                <button
                  key={character.id}
                  onClick={() => toggleParticipant(character.id)}
                  className={`rounded border px-3 py-1 text-xs ${
                    on ? 'border-indigo-500 bg-slate-800' : 'border-slate-700'
                  }`}
                >
                  {character.name}
                </button>
              )
            })}
            {characters.length === 0 && (
              <span className="text-xs text-slate-500">还没有人物，先去世界观里建一个。</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button className="rounded bg-indigo-600 px-4 py-2 text-sm" onClick={save}>
            {editingId ? '保存' : '新建'}
          </button>
          {editingId && (
            <button
              className="rounded border border-slate-700 px-4 py-2 text-sm"
              onClick={startCreate}
            >
              取消编辑
            </button>
          )}
        </div>
        <p className="text-xs text-slate-500">
          时间线是故事内时序，不是写作顺序；顺序由列表里的上移 / 下移决定。
        </p>
      </section>

      <div className="space-y-2">
        {events.map((event, index) => (
          <article key={event.id} className="rounded border border-slate-800 p-4 text-sm">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-xs text-slate-500">#{index + 1}</span>
              {event.story_time && (
                <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
                  {event.story_time}
                </span>
              )}
              <span className="font-medium">{event.title}</span>
              {event.location_id && (
                <span className="text-xs text-slate-500">@ {nameOf(event.location_id)}</span>
              )}
              <button
                className="text-xs text-indigo-400 disabled:opacity-30"
                disabled={index === 0}
                onClick={() => move(event, 'up')}
              >
                上移
              </button>
              <button
                className="text-xs text-indigo-400 disabled:opacity-30"
                disabled={index === events.length - 1}
                onClick={() => move(event, 'down')}
              >
                下移
              </button>
              <button className="text-xs text-indigo-400" onClick={() => startEdit(event)}>
                编辑
              </button>
              <button className="text-xs text-amber-400" onClick={() => remove(event)}>
                删除
              </button>
            </div>
            {event.participants.length > 0 && (
              <p className="mt-1 text-xs text-slate-500">
                参与者：{event.participants.map(nameOf).join('、')}
              </p>
            )}
            {event.description && (
              <p className="mt-1 whitespace-pre-wrap text-slate-300">{event.description}</p>
            )}
          </article>
        ))}
        {events.length === 0 && (
          <p className="text-sm text-slate-500">
            还没有事件。时间线是故事内时序，不是写作顺序；顺序由这里的上下移动决定。
          </p>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: 加导航与路由**

`frontend/src/App.tsx`：
- `import Timeline from './pages/Timeline'`
- `NAV` 在关系网后加 `{ to: '/timeline', label: '时间线' }`。
- `<Routes>` 加 `<Route path="/timeline" element={<Timeline />} />`。

- [ ] **Step 4: 手工走查**

- 新建三条事件，确认追加在末尾；上移 / 下移按钮在首尾禁用。
- 给一条事件选两个人物与一个地点，刷新后保持。
- 把人物条目删掉，事件参与者列表里不再出现它；删地点后地点显示消失。
- 切换项目，事件列表跟着换。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/api/client.ts frontend/src/pages/Timeline.tsx frontend/src/App.tsx
git commit -m "feat(frontend): 时间线页面"
```

---

## Task 7: 前端预置更新与人物字段守卫

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/Studio.tsx`
- Modify: `frontend/src/pages/World.tsx`
- Modify: `frontend/src/components/EntryEditor.tsx`
- Test: `backend/tests/test_world_api.py`（补一条守卫契约测试）

**Interfaces:**
- Consumes: Task 4 的 `preset` 状态与 `POST /api/agents/{id}/apply-preset`。
- Produces: 工作室的「预置有更新 / 恢复预置」按钮；保存与采纳路径不再提交非人物字段。

- [ ] **Step 1: 更新 API 客户端**

`frontend/src/api/client.ts`：
- `Agent` 上加：

```ts
export interface AgentPresetStatus {
  key: string | null
  update_available: boolean
  can_restore: boolean
  up_to_date: boolean
}
```

- `Agent` 加 `preset: AgentPresetStatus`。
- `rollback` 之后加：

```ts
  applyPreset: (agentId: string) =>
    request<Agent>(`/api/agents/${agentId}/apply-preset`, { method: 'POST' }),
```

- [ ] **Step 2: 工作室预置更新界面**

`frontend/src/pages/Studio.tsx`：
- 在 `rollback` 函数之后加：

```tsx
  async function applyPreset() {
    if (!selected) return
    const message = selected.preset?.update_available
      ? '应用预置更新会新建一版并设为当前。旧版本保留，可回退。继续？'
      : '恢复预置会用当前预置新建一版并设为当前。旧版本保留，可回退。继续？'
    if (!window.confirm(message)) return
    try {
      await api.applyPreset(selected.id)
      await refreshAgents(selected.id)
      setNotice('已应用预置')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }
```

- 在「任务类型：… · 当前版本 v…」那一行之后插入：

```tsx
            {selected.preset?.update_available && (
              <section className="flex flex-wrap items-center gap-3 rounded border border-amber-700 bg-amber-950/30 p-3 text-sm">
                <span className="text-amber-300">预置有更新。</span>
                <span className="text-xs text-amber-200/70">
                  应用会新建一版并设为当前；旧版本保留，可回退。
                </span>
                <button
                  className="rounded bg-amber-600 px-3 py-1.5 text-sm"
                  onClick={applyPreset}
                >
                  应用预置更新
                </button>
              </section>
            )}
            {!selected.preset?.update_available && selected.preset?.can_restore && (
              <section className="flex flex-wrap items-center gap-3 rounded border border-slate-700 p-3 text-sm">
                <span className="text-slate-300">当前版本不是最新预置。</span>
                <button
                  className="rounded border border-slate-600 px-3 py-1.5 text-sm"
                  onClick={applyPreset}
                >
                  恢复预置
                </button>
              </section>
            )}
```

- [ ] **Step 3: 人物字段守卫**

`frontend/src/components/EntryEditor.tsx`：
把 `characterFieldsOf` 改为：

```tsx
export function characterFieldsOf(
  entry: object,
  fields: { key: string }[],
): Record<string, string> {
  const source = entry as Record<string, unknown>
  // 非人物条目不该初始化这八个键：它们会在保存时被当作「作者清空」提交，
  // 把「人物改成势力」时本应保留的八项静默抹掉。
  if (source.type !== 'character') return {}
  return Object.fromEntries(fields.map((field) => [field.key, String(source[field.key] ?? '')]))
}
```

`frontend/src/pages/World.tsx`：
- `payloadOf` 的 `...next.fields` 改为：

```tsx
      ...(next.type === 'character' ? next.fields : {}),
```

- `adoptCandidate` 里的 `...next.fields` 同样改为：

```tsx
        ...(next.type === 'character' ? next.fields : {}),
```

- [ ] **Step 4: 补后端契约测试**

在 `backend/tests/test_world_api.py` 末尾追加：

```python
def test_updating_an_entry_without_character_fields_keeps_them(client):
    """前端守卫依赖这条契约：省略八个键 = 不改，而不是清空。

    这正是「把人物改成势力再保存」时八项能保住的原因。
    """
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    created = client.post(
        f"/api/projects/{project['id']}/entries",
        json={"type": "人物", "name": "陈默", "appearance": "瘦高", "desire": "找回记忆"},
    ).json()

    updated = client.patch(f"/api/entries/{created['id']}", json={"type": "势力"}).json()

    assert updated["type"] == "faction"
    assert updated["appearance"] == "瘦高"
    assert updated["desire"] == "找回记忆"
```

- [ ] **Step 5: 跑后端测试**

Run: `cd backend && uv run pytest tests/test_world_api.py -q`
Expected: PASS。

- [ ] **Step 6: 手工走查**

在副本库（Task 8 会建）或开发库上：

1. 选一个内置角色卡，确认状态。若是「已是最新」，在工作室把提示词改一句并「保存为新版本」，确认出现「恢复预置」；点它并确认，版本号 +1、模型绑定仍在、旧版本可回滚。
2. 新建一个人物，填入外貌与欲望；把类型改成「势力」并保存；再改回「人物」，确认两项内容还在。
3. 从 AI 候选采纳一条非人物条目，确认它的八个人物列没有被写成空串（可在世界观编辑器里切到人物查看，或直接查库）。
4. 从 AI 候选采纳一条人物条目，确认八项按候选落库。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/api/client.ts frontend/src/pages/Studio.tsx frontend/src/pages/World.tsx frontend/src/components/EntryEditor.tsx backend/tests/test_world_api.py
git commit -m "feat(frontend): 预置更新入口与人物字段守卫"
```

---

## Task 8: 采纳路径验证、手工走查清单与 CLAUDE.md 同步

**Files:**
- Create: `docs/superpowers/plans/2026-10-17-p1b2b-walkthrough.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: 前七个任务的全部产出。
- Produces: 验收证据与项目进度记录。

- [ ] **Step 1: 复制作者真实库到临时目录**

在仓库根目录运行（Python 标准库，不依赖第三方）：

```python
import os, sqlite3, tempfile

src_path = os.path.join(os.environ["LOCALAPPDATA"], "StoryForge", "storyforge.db")
if not os.path.exists(src_path):
    raise SystemExit(f"找不到作者库：{src_path}")

target_dir = tempfile.mkdtemp(prefix="storyforge-p1b2b-verify-")
target_path = os.path.join(target_dir, "storyforge.db")
src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)
dst = sqlite3.connect(target_path)
src.backup(dst)
dst.close()
src.close()
print(target_dir)
```

Expected: 打印一个临时目录；原库未被写入。

- [ ] **Step 2: 在副本上跑应用**

```bash
cd backend
STORYFORGE_DATA_DIR="<上一步的临时目录>" uv run uvicorn app.main:app --port 8756
```

另开一个终端：

```bash
cd frontend && pnpm dev
```

预期：启动日志显示迁移 v2 / v3 执行一次（若副本是旧库），并生成 `backups/`；第二次启动不再执行、不再备份。

- [ ] **Step 3: 验证采纳路径**

用副本库的 SQLite 找上一轮真实模型人物候选：

```python
import json, sqlite3
conn = sqlite3.connect(r"<临时目录>/storyforge.db")
for run_id, project_id, raw in conn.execute(
    "SELECT id, project_id, parsed_json FROM generation_run "
    "WHERE parsed_json IS NOT NULL ORDER BY created_at DESC"
):
    parsed = json.loads(raw)
    for entry in parsed.get("entries", []):
        if entry.get("type") in ("人物", "character"):
            print(run_id, project_id, json.dumps(entry, ensure_ascii=False))
```

用浏览器打开 `http://localhost:5173/world`，选中对应项目，点「让 AI 提候选」不必要 —— 候选存在运行记录里但界面只显示当前批次。**改为直接走 API 采纳**，用 Python 或 curl：

```bash
curl -X POST "http://localhost:8756/api/projects/<project_id>/entries" \
  -H "content-type: application/json" \
  -d '{"type":"character","name":"...","appearance":"...","personality":"...","desire":"...","fear":"...","arc_type":"...","abilities":"...","speech_style":"...","current_state":"...","source_run_id":"<run_id>"}'
```

Expected：返回的条目带 `source_run_id`，八项与候选一致。随后在 `/world` 里选中该人物，编辑器显示八项。若副本里没有任何人物候选，**先确认阿里云百炼额度**，再用真实世界观构建师跑一次（一次调用即可），然后重复本条。

- [ ] **Step 4: 在副本上走查新功能**

- `/relations`：建一对人物、同时反向、改一侧强度、筛类型。
- `/timeline`：建三条事件、上移 / 下移、挂人物与地点、删人物条目后参与者消失。
- `/studio`：改一个内置角色卡的提示词并保存为新版本 → 出现「恢复预置」→ 应用 → 版本 +1、模型绑定保留。
- `/world`：人物改势力再改回来，八项仍在；采纳一条非人物候选，确认八项为空而非空串（可查库或用编辑器切换类型确认）。

- [ ] **Step 5: 写手工走查清单**

新建 `docs/superpowers/plans/2026-10-17-p1b2b-walkthrough.md`，内容至少包含：

```markdown
# P1b 收尾手工走查清单

> 在作者真实库的**副本**上执行，不动原库。副本由 Task 8 Step 1 生成。

## 关系网
- [ ] 默认只显示人物↔人物
- [ ] 同时建立反向生成两条，可独立改名与强度
- [ ] 清空强度显示「未评」
- [ ] 删一个方向，另一个还在
- [ ] 世界观页录入的强度在关系网页可见

## 时间线
- [ ] 新建追加到末尾
- [ ] 首尾的上移 / 下移按钮禁用
- [ ] 参与者只列人物，地点可空
- [ ] 删人物后事件参与者清理；删地点后地点置空
- [ ] 换项目列表跟着换

## 预置更新
- [ ] 启动不自动切换版本
- [ ] 改过的版本显示「恢复预置」
- [ ] 应用后版本 +1、模型绑定保留、旧版本可回退
- [ ] 已是最新时再次应用被拒

## 人物字段守卫
- [ ] 人物改势力再改回，八项保留
- [ ] 非人物保存不写八项
- [ ] 人物候选采纳后八项落库并在编辑器回显
```

- [ ] **Step 6: 更新 CLAUDE.md**

- §7 路线图：
  - `P1b-2b 关系网与时间线` 改为 ✅ 完成（2026-10-17，通过真实库副本走查）。
  - 加一行说明 **P1b 全部完成**，下一段 P1c。
- §7 阶段记录追加 `**2026-10-17 · P1b 收尾（关系网、时间线、预置更新）（实施完成）**`，写清：
  - 关系强度 1–5、时间线显式排序、参与者 / 地点；
  - 预置显式更新（`preset_key` + 指纹 + `apply-preset`）与它修掉的 `seed_agents` 交付阻塞；
  - 人物字段守卫与采纳路径验证；
  - 测试数量、迁移 v2 / v3 在作者副本库上的结果、未做 FTS5；
  - 遗留：FTS5（P2 前）、逐章状态推进（P1c）、关系图（D-19 二期）。
- §8 变更记录追加（日期 2026-10-17）：
  - 关系强度用 1–5 整数、双向各一条、允许不对称；
  - 时间线新建 `timeline_event`、手排顺序 + 自由文本时间；
  - 时间线参与者只收人物、地点任意条目；条目删除时清理参与者，类型事后改变不回洗；
  - 预置更新采用**显式应用**：`preset_key` 稳定认领 + 内容指纹；启动只认领与回填，绝不静默切换；
  - 指纹不计模型绑定 / 技能 / 备注；
  - 迁移 v2 / v3 冻结字面量，新增列一律新开迁移；
  - 人物字段守卫修的是「改类型清空八项」的前端路径；
  - `seed_agents` 交付阻塞已解决；
  - FTS5 仍顺延到 P2 之前。
- 把 P1b-2a 阶段记录里那条「`seed_agents` 预置更新到不了已有安装 —— 交付阻塞」标记为**已解决**，指向本段记录。

- [ ] **Step 7: 跑完整测试并提交**

```bash
cd backend && uv run pytest -q
```

Expected: 全部通过（原 243 + 新增；具体数写进 CLAUDE.md 阶段记录）。

```bash
git add docs/superpowers/plans/2026-10-17-p1b2b-walkthrough.md CLAUDE.md
git commit -m "docs: P1b 收尾阶段记录与手工走查清单"
```

---

## Self-Review

**Spec coverage：**

| Spec 要求 | 对应任务 |
|---|---|
| 迁移 v2 / v3、时间线新表 | 1 |
| 关系强度、更新、双向 | 2 |
| 时间线 CRUD、排序、参与者 / 地点、删除清理 | 3 |
| 预置认领、指纹、状态、显式应用 | 4 |
| 关系网页 + 编辑器强度 | 5 |
| 时间线页 | 6 |
| 工作室预置入口 + 人物字段守卫 | 7 |
| 采纳路径验证 + 走查清单 + CLAUDE.md | 8 |
| 既有 243 条全绿 | 每任务的完整测试步骤 + Task 8 |

**Placeholder scan：** 没有 TBD / TODO /「类似上一个任务」；所有代码步骤都带实际代码或确切改动。

**Type consistency：**
- `EntryRelation.strength` 在模型、schema、序列化、前端类型中同名。
- `TimelineEvent.participants_json` 存储、API 字段 `participants`、前端类型 `participants` 三处一致。
- `preset_service.status_for` 返回的四个键与前端 `AgentPresetStatus` 一致。
- `agent_service.create_version` 的 `preset_fingerprint` 只在服务内部使用，`VersionCreate` 不暴露。

**已知顺序约束：**
- Task 2 依赖 Task 1 的 `strength` 列。
- Task 3 依赖 Task 1 的 `TimelineEvent`。
- Task 4 依赖 Task 1 的 `preset_key` / `preset_fingerprint`。
- Task 5/6/7 依赖对应后端任务；Task 7 依赖 Task 4 的 API。
- Task 8 依赖全部。

**刻意保留的边界：** 关系网不强制双向各一条（只提供便利）；时间线不解析故事内时间；预置启动不自动切换；FTS5 不在本计划。
