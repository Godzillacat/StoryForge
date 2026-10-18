# FTS5 全文检索地基 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 StoryForge 接上 SQLite FTS5 全文检索：索引设定条目/章/场景，支持中文长词与短词查询，提供检索 API 与「相关设定条目（检索）」上下文槽位。

**Architecture:** FTS5 trigram 虚拟表由检索模块在 `create_all` 后幂等创建；写入事务内给项目标脏，首次检索按项目从基表重建。查询 ≥3 字走 FTS + bm25，<3 字走 `LIKE` 回退。查询服务、API 与槽位分层复用同一构建器。

**Tech Stack:** Python 3.13 + FastAPI + SQLAlchemy 2 + SQLite 3.45（FTS5 trigram）；pytest；无新依赖。

**Spec:** `docs/superpowers/specs/2026-10-18-fts5-search-foundation-design.md`

## Global Constraints

- 索引覆盖 **设定条目 / 章 / 场景**；伏笔、时间线、正文不索引。
- **不新增 `MIGRATIONS` 版本**；FTS 虚拟表由 `ensure_search_index` 在 `create_all` 后创建，`search_index_state` 由 `create_all` 建。
- 写入事务内标脏（`dirty=1`）；首次检索按项目重建；不做逐实体增量、不用触发器。
- 中文查询：**≥3 字走 FTS + bm25；<3 字走 `LIKE` 回退**；不引入分词依赖。
- 结果只返回 `entity_type` / `entity_id` / `subtype` / `title` / `snippet`；项目隔离；已删除实体丢弃。
- 检索可能触发惰性重建并提交索引状态；接口与槽位文档写明。
- `related_settings` 槽位是 **opt-in**；不改任何现有智能体的 `context_slots_json`。
- 既有后端 339 条测试必须全绿；前端不改，仍为 18 passed + build 干净。
- 不写作者真实库；手工验证用临时数据目录与作者库副本；不调用模型、不消耗额度。
- 标识符/代码用英文，注释/文案用中文；提交信息用中文。

---

## File Structure

| 文件 | 责任 |
|---|---|
| `backend/app/db/models/search.py` | `SearchIndexState` 普通表模型 |
| `backend/app/db/models/__init__.py` | 注册并导出 `SearchIndexState` |
| `backend/app/db/search.py` | FTS5 DDL、`ensure_search_index`、`clear_search_index`、版本号 |
| `backend/app/db/session.py` | `init_db` 两条路径接 `ensure_search_index` |
| `backend/app/services/search_service.py` | 文档构建、标脏、按项目重建、查询、项目删除清理 |
| `backend/app/api/search.py` | `GET /api/projects/{id}/search` |
| `backend/app/main.py` | 注册 search 路由 |
| `backend/app/runtime/context.py` | 协议与 `SLOT_REGISTRY` 加 `related_settings` |
| `backend/app/services/slot_source.py` | `DbSlotSource.related_settings()` |
| `backend/app/services/{world,chapter,scene,chapter_plan,project}_service.py` | 写入点标脏 / 项目删除清理 |
| `backend/tests/conftest.py` | 测试夹具清空 FTS 表 |
| `backend/tests/test_search_index.py` | 启动/DDL/清空测试 |
| `backend/tests/test_search_service.py` | 文档构建、重建、查询测试 |
| `backend/tests/test_search_maintenance.py` | 所有写入路径的标脏/重建测试 |
| `backend/tests/test_search_api.py` | 检索 API 测试 |
| `backend/tests/test_slot_source.py` / `test_context.py` | 槽位测试 |
| `docs/superpowers/plans/2026-10-18-fts5-walkthrough.md` | 手工验证清单 |
| `CLAUDE.md` | 路线图、阶段记录、变更记录 |

---

### Task 1: 索引表、启动装配与测试夹具

**Files:**
- Create: `backend/app/db/models/search.py`
- Create: `backend/app/db/search.py`
- Modify: `backend/app/db/models/__init__.py`
- Modify: `backend/app/db/session.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_search_index.py`

**Interfaces:**
- Produces:
  - `SearchIndexState`（`project_id` PK，`dirty`、`schema_version`、`rebuilt_at`）
  - `SEARCH_INDEX_VERSION = 1`
  - `SEARCH_DDL`
  - `ensure_search_index(engine) -> None`
  - `clear_search_index(engine) -> None`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_search_index.py`:

```python
import pytest
from sqlalchemy import text

from app.db import session as db_session
from app.db.search import clear_search_index, ensure_search_index


def _tables(engine) -> set[str]:
    with engine.connect() as conn:
        return {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }


def test_init_db_creates_search_objects(session):
    names = _tables(db_session.engine)
    assert "search_document" in names
    assert "search_index_state" in names


def test_ensure_search_index_is_idempotent(session):
    ensure_search_index(db_session.engine)
    ensure_search_index(db_session.engine)
    assert "search_document" in _tables(db_session.engine)


def test_existing_database_gets_fts_on_init(session):
    with db_session.engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS search_document")
    assert "search_document" not in _tables(db_session.engine)

    db_session.init_db()

    assert "search_document" in _tables(db_session.engine)


def test_clear_search_index(session):
    with db_session.engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO search_document"
            "(doc_id, project_id, entity_type, subtype, title, body) "
            "VALUES ('entry:x', 'p', 'entry', 'place', '旧城', '旧城')"
        )

    clear_search_index(db_session.engine)

    with db_session.engine.connect() as conn:
        count = conn.exec_driver_sql("SELECT COUNT(*) FROM search_document").scalar()
    assert count == 0


def test_fts_failure_is_reported_clearly(session, monkeypatch):
    import app.db.search as search_db

    monkeypatch.setattr(
        search_db,
        "SEARCH_DDL",
        "CREATE VIRTUAL TABLE broken USING fts5x(x)",
    )

    with pytest.raises(RuntimeError, match="FTS5"):
        search_db.ensure_search_index(db_session.engine)
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
uv run --directory backend pytest backend/tests/test_search_index.py -q
```

Expected: FAIL，`app.db.search` 不存在/导入失败。

- [ ] **Step 3: 写模型与 FTS 基础设施**

Create `backend/app/db/models/search.py`:

```python
from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SearchIndexState(Base):
    """每个项目一行的检索索引状态；没有行等价于需要重建。"""

    __tablename__ = "search_index_state"

    project_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dirty: Mapped[int] = mapped_column(Integer, default=1)
    schema_version: Mapped[int] = mapped_column(Integer, default=0)
    rebuilt_at: Mapped[str | None] = mapped_column(Text, default=None)
```

Modify `backend/app/db/models/__init__.py`: add

```python
from app.db.models.search import SearchIndexState
```

and add `"SearchIndexState",` to `__all__` (keep the list alphabetical).

Create `backend/app/db/search.py`:

```python
"""FTS5 检索基础设施。

FTS 虚拟表无法用 SQLAlchemy metadata 表达，因此不交给 create_all；
由 ensure_search_index 在每次 init_db 之后幂等创建。普通表
search_index_state 仍由模型负责。
"""

from __future__ import annotations

SEARCH_INDEX_VERSION = 1

SEARCH_DDL = """
CREATE VIRTUAL TABLE IF NOT EXISTS search_document USING fts5(
    doc_id UNINDEXED,
    project_id UNINDEXED,
    entity_type UNINDEXED,
    subtype UNINDEXED,
    title,
    body,
    tokenize='trigram'
)
"""


def ensure_search_index(engine) -> None:
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(SEARCH_DDL)
    except Exception as exc:
        raise RuntimeError(
            "无法创建 FTS5 全文检索索引：当前 SQLite 不支持 FTS5 或 DDL 执行失败。"
            f"（{exc}）"
        ) from exc


def clear_search_index(engine) -> None:
    """测试与重建用：清空所有文档，不删表。调用前表必须已存在。"""
    with engine.begin() as conn:
        conn.exec_driver_sql("DELETE FROM search_document")
```

Modify `backend/app/db/session.py`:

- Add `from app.db.search import ensure_search_index` at the top imports.
- In `init_db()` fresh branch, after `Base.metadata.create_all(engine)` add `ensure_search_index(engine)` before `return`.
- In the existing branch, after `Base.metadata.create_all(engine)` add `ensure_search_index(engine)`.

The resulting `init_db` tail should be:

```python
        Base.metadata.create_all(engine)
        ensure_search_index(engine)
        return

    # 存量库：先补已有的表，再让模型建新加的表 —— 迁移不建表。
    run_migrations(engine)
    Base.metadata.create_all(engine)
    ensure_search_index(engine)
```

Modify `backend/tests/conftest.py`:

- In the `session` fixture, after `Base.metadata.create_all(db_session.engine)` add:

```python
    from app.db.search import clear_search_index

    clear_search_index(db_session.engine)
```

- In the `client` fixture, after `init_db()` add the same two lines (clear the FTS table so stale docs from other tests cannot leak in).

- [ ] **Step 4: 跑测试确认通过**

Run:

```bash
uv run --directory backend pytest backend/tests/test_search_index.py -q
uv run --directory backend pytest -q
```

Expected: 新增 5 条通过；全量既有 339 + 新增全绿。

- [ ] **Step 5: 提交**

```bash
git add backend/app/db/models/search.py backend/app/db/models/__init__.py backend/app/db/search.py backend/app/db/session.py backend/tests/conftest.py backend/tests/test_search_index.py
git commit -m "feat(search): FTS5 索引表与启动装配"
```

---

### Task 2: 文档构建、按项目重建、标脏与删除清理

**Files:**
- Create: `backend/app/services/search_service.py`
- Test: `backend/tests/test_search_service.py`

**Interfaces:**
- Consumes: `SearchIndexState`、`SEARCH_INDEX_VERSION`、`CHARACTER_FIELDS`、`ENTRY_TYPES`、`HARDNESS_LEVELS`、`STATUS_LABELS`。
- Produces:
  - `mark_dirty(session, project_id) -> None`
  - `delete_project(session, project_id) -> None`
  - `rebuild_project(session, project_id) -> None`
  - 文档构建器 `_build_docs(session, project_id)`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_search_service.py`:

```python
from sqlalchemy import text

from app.db.models import Chapter, Project, Scene, SearchIndexState, SettingEntry, Volume
from app.services import search_service


def _seed(session):
    project = Project(name="南滨")
    session.add(project)
    session.commit()

    place = SettingEntry(
        project_id=project.id,
        type="place",
        name="南滨旧城",
        aliases_json=["旧城"],
        tags_json=["据点"],
        summary="记忆清算网络的据点",
        description="湿带边缘的旧城区",
    )
    character = SettingEntry(
        project_id=project.id,
        type="character",
        name="沈砚",
        aliases_json=["阿砚"],
        desire="找回被抹去的记忆",
        current_state="被旧城通缉",
    )
    session.add_all([place, character])
    session.commit()

    volume = Volume(project_id=project.id, seq=0, name="第一卷")
    session.add(volume)
    session.commit()

    chapter = Chapter(
        volume_id=volume.id,
        seq=0,
        title="开端",
        summary="南滨旧城的雨夜",
        hook="旧城信标亮起",
        lines_json=["主线"],
        pov="沈砚",
    )
    session.add(chapter)
    session.commit()

    scene = Scene(
        chapter_id=chapter.id,
        seq=0,
        goal="找到旧城信标",
        conflict="记忆清算人追来",
        turn="信标是假的",
        characters_json=[character.id],
        location_id=place.id,
        story_time="第三夜",
        pov="沈砚",
    )
    session.add(scene)
    session.commit()

    return project, place, character, volume, chapter, scene


def _docs(session, project_id):
    rows = session.execute(
        text(
            "SELECT doc_id, entity_type, subtype, title, body "
            "FROM search_document WHERE project_id = :p"
        ),
        {"p": project_id},
    ).mappings().all()
    return [dict(row) for row in rows]


def test_rebuild_indexes_entries_chapters_and_scenes(session):
    project, place, character, _, chapter, _ = _seed(session)

    search_service.rebuild_project(session, project.id)
    docs = {doc["doc_id"]: doc for doc in _docs(session, project.id)}

    assert f"entry:{place.id}" in docs
    assert f"entry:{character.id}" in docs
    assert f"chapter:{chapter.id}" in docs
    assert any(key.startswith("scene:") for key in docs)

    place_doc = docs[f"entry:{place.id}"]
    assert place_doc["entity_type"] == "entry"
    assert place_doc["subtype"] == "place"
    assert place_doc["title"] == "南滨旧城"
    assert "记忆清算网络的据点" in place_doc["body"]

    character_doc = docs[f"entry:{character.id}"]
    assert "找回被抹去的记忆" in character_doc["body"]
    assert "别名：阿砚" in character_doc["body"]

    chapter_doc = docs[f"chapter:{chapter.id}"]
    assert chapter_doc["title"] == "第1卷 第1章 开端"
    assert "旧城信标亮起" in chapter_doc["body"]

    scene_doc = next(doc for doc in docs.values() if doc["entity_type"] == "scene")
    assert scene_doc["title"].startswith("第1卷 第1章 场景1 找到旧城信标")
    assert "沈砚" in scene_doc["body"]
    assert "南滨旧城" in scene_doc["body"]


def test_rebuild_replaces_old_documents(session):
    project, place, _, _, _, _ = _seed(session)
    search_service.rebuild_project(session, project.id)

    place.name = "新南滨"
    session.commit()
    search_service.rebuild_project(session, project.id)

    docs = _docs(session, project.id)
    titles = {doc["title"] for doc in docs}
    assert "新南滨" in titles
    assert "南滨旧城" not in titles


def test_rebuild_is_project_scoped(session):
    first, _, _, _, _, _ = _seed(session)
    second = Project(name="另一个项目")
    session.add(second)
    session.commit()
    session.add(SettingEntry(project_id=second.id, type="place", name="别处"))
    session.commit()

    search_service.rebuild_project(session, first.id)

    assert _docs(session, first.id)
    assert _docs(session, second.id) == []


def test_mark_dirty_creates_and_updates_state(session):
    project = Project(name="标记")
    session.add(project)
    session.commit()

    search_service.mark_dirty(session, project.id)
    session.commit()
    state = session.get(SearchIndexState, project.id)
    assert state is not None and state.dirty == 1

    state.dirty = 0
    session.commit()
    search_service.mark_dirty(session, project.id)
    session.commit()
    assert session.get(SearchIndexState, project.id).dirty == 1


def test_rebuild_sets_clean_state(session):
    project, _, _, _, _, _ = _seed(session)

    search_service.rebuild_project(session, project.id)

    state = session.get(SearchIndexState, project.id)
    assert state is not None
    assert state.dirty == 0
    assert state.schema_version == 1
    assert state.rebuilt_at


def test_delete_project_removes_docs_and_state(session):
    project, _, _, _, _, _ = _seed(session)
    search_service.rebuild_project(session, project.id)
    assert _docs(session, project.id)

    search_service.delete_project(session, project.id)
    session.commit()

    assert _docs(session, project.id) == []
    assert session.get(SearchIndexState, project.id) is None
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
uv run --directory backend pytest backend/tests/test_search_service.py -q
```

Expected: FAIL，`search_service` 不存在。

- [ ] **Step 3: 写实现**

Create `backend/app/services/search_service.py`:

```python
"""全文检索：文档构建、按项目重建、脏标记与删除清理。

FTS5 表只由本模块写入；查询入口在 Task 3 追加。
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.chapter_types import STATUS_LABELS
from app.db.models import (
    Chapter,
    Scene,
    SearchIndexState,
    SettingEntry,
    Volume,
)
from app.db.search import SEARCH_INDEX_VERSION
from app.world_types import CHARACTER_FIELDS, ENTRY_TYPES, HARDNESS_LEVELS


def mark_dirty(session: Session, project_id: str) -> None:
    """在写入事务内标记该项目需要重建；由调用方提交/回滚。"""
    state = session.get(SearchIndexState, project_id)
    if state is None:
        session.add(
            SearchIndexState(
                project_id=project_id,
                dirty=1,
                schema_version=0,
                rebuilt_at=None,
            )
        )
    else:
        state.dirty = 1


def delete_project(session: Session, project_id: str) -> None:
    """删除项目的检索文档与状态；由调用方提交。"""
    session.execute(
        text("DELETE FROM search_document WHERE project_id = :pid"),
        {"pid": project_id},
    )
    state = session.get(SearchIndexState, project_id)
    if state is not None:
        session.delete(state)


def rebuild_project(session: Session, project_id: str) -> None:
    """按基表重建一个项目的全部文档，并把状态置为干净。"""
    try:
        _replace_docs(session, project_id)
        state = session.get(SearchIndexState, project_id)
        if state is None:
            state = SearchIndexState(project_id=project_id)
            session.add(state)
        state.dirty = 0
        state.schema_version = SEARCH_INDEX_VERSION
        state.rebuilt_at = dt.datetime.now(dt.timezone.utc).isoformat()
        session.commit()
    except Exception:
        session.rollback()
        raise


def _replace_docs(session: Session, project_id: str) -> None:
    session.execute(
        text("DELETE FROM search_document WHERE project_id = :pid"),
        {"pid": project_id},
    )
    docs = list(_build_docs(session, project_id))
    if docs:
        session.execute(
            text(
                "INSERT INTO search_document"
                "(doc_id, project_id, entity_type, subtype, title, body) "
                "VALUES (:doc_id, :project_id, :entity_type, :subtype, :title, :body)"
            ),
            docs,
        )


def _build_docs(session: Session, project_id: str):
    entries = list(
        session.scalars(
            select(SettingEntry).where(SettingEntry.project_id == project_id)
        )
    )
    volumes = {
        volume.id: volume
        for volume in session.scalars(
            select(Volume).where(Volume.project_id == project_id)
        )
    }
    chapters = list(
        session.scalars(
            select(Chapter)
            .join(Volume, Chapter.volume_id == Volume.id)
            .where(Volume.project_id == project_id)
        )
    )
    chapter_by_id = {chapter.id: chapter for chapter in chapters}
    scenes = list(
        session.scalars(
            select(Scene)
            .join(Chapter, Scene.chapter_id == Chapter.id)
            .join(Volume, Chapter.volume_id == Volume.id)
            .where(Volume.project_id == project_id)
        )
    )
    entry_names = {entry.id: entry.name for entry in entries}

    for entry in entries:
        yield _entry_doc(entry)
    for chapter in chapters:
        yield _chapter_doc(volumes[chapter.volume_id], chapter)
    for scene in scenes:
        chapter = chapter_by_id[scene.chapter_id]
        yield _scene_doc(volumes[chapter.volume_id], chapter, scene, entry_names)


def _entry_doc(entry: SettingEntry) -> dict:
    parts = [f"类型：{ENTRY_TYPES.get(entry.type, entry.type)}"]
    if entry.aliases_json:
        parts.append("别名：" + "、".join(str(item) for item in entry.aliases_json))
    if entry.tags_json:
        parts.append("标签：" + "、".join(str(item) for item in entry.tags_json))
    if entry.summary:
        parts.append("摘要：" + entry.summary)
    if entry.description:
        parts.append("描述：" + entry.description)
    if entry.hardness:
        parts.append("硬度：" + HARDNESS_LEVELS.get(entry.hardness, entry.hardness))
    for key, (label, _multiline) in CHARACTER_FIELDS.items():
        value = getattr(entry, key, None)
        if value:
            parts.append(f"{label}：" + str(value))
    return {
        "doc_id": f"entry:{entry.id}",
        "project_id": entry.project_id,
        "entity_type": "entry",
        "subtype": entry.type,
        "title": entry.name,
        "body": " ".join(parts),
    }


def _chapter_doc(volume: Volume, chapter: Chapter) -> dict:
    parts: list[str] = []
    if chapter.pov:
        parts.append("视角：" + chapter.pov)
    if chapter.target_words:
        parts.append(f"目标字数：{chapter.target_words}")
    if chapter.emotional_tone:
        parts.append("情绪基调：" + chapter.emotional_tone)
    if chapter.lines_json:
        parts.append("推进的线：" + "、".join(str(item) for item in chapter.lines_json))
    if chapter.hook:
        parts.append("钩子：" + chapter.hook)
    if chapter.summary:
        parts.append("摘要：" + chapter.summary)
    if chapter.status:
        parts.append("状态：" + STATUS_LABELS.get(chapter.status, chapter.status))
    return {
        "doc_id": f"chapter:{chapter.id}",
        "project_id": volume.project_id,
        "entity_type": "chapter",
        "subtype": "",
        "title": f"第{volume.seq + 1}卷 第{chapter.seq + 1}章 {chapter.title}",
        "body": " ".join(parts),
    }


def _scene_doc(
    volume: Volume,
    chapter: Chapter,
    scene: Scene,
    entry_names: dict[str, str],
) -> dict:
    parts = ["目标：" + (scene.goal or "（未写目标）")]
    if scene.conflict:
        parts.append("冲突：" + scene.conflict)
    if scene.turn:
        parts.append("转折：" + scene.turn)
    people = [
        entry_names[item]
        for item in (scene.characters_json or [])
        if item in entry_names
    ]
    if people:
        parts.append("出场人物：" + "、".join(people))
    location = entry_names.get(scene.location_id) if scene.location_id else None
    if location:
        parts.append("地点：" + location)
    if scene.story_time:
        parts.append("时间：" + scene.story_time)
    if scene.pov:
        parts.append("视角：" + scene.pov)
    if scene.target_words_min is not None or scene.target_words_max is not None:
        parts.append(
            f"字数区间：{scene.target_words_min or '?'}–{scene.target_words_max or '?'}"
        )
    if scene.status:
        parts.append("状态：" + STATUS_LABELS.get(scene.status, scene.status))
    return {
        "doc_id": f"scene:{scene.id}",
        "project_id": volume.project_id,
        "entity_type": "scene",
        "subtype": "",
        "title": (
            f"第{volume.seq + 1}卷 第{chapter.seq + 1}章 场景{scene.seq + 1} "
            f"{scene.goal or '（未写目标）'}"
        ),
        "body": " ".join(parts),
    }
```

- [ ] **Step 4: 跑测试确认通过**

Run:

```bash
uv run --directory backend pytest backend/tests/test_search_service.py -q
uv run --directory backend pytest -q
```

Expected: 新增 6 条通过；全量全绿。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/search_service.py backend/tests/test_search_service.py
git commit -m "feat(search): 文档构建与按项目重建"
```

---

### Task 3: 查询入口（FTS / LIKE / 片段 / 校验）

**Files:**
- Modify: `backend/app/services/search_service.py`
- Test: `backend/tests/test_search_service.py`

**Interfaces:**
- Consumes: `rebuild_project`、`SearchIndexState`、`SEARCH_INDEX_VERSION`。
- Produces:
  - `SearchHit`（`entity_type` / `entity_id` / `subtype` / `title` / `snippet`）
  - `search(session, project_id, query, entity_types=None, limit=20) -> list[SearchHit]`

- [ ] **Step 1: 追加失败测试**

Append to `backend/tests/test_search_service.py`:

```python
def test_long_chinese_query_returns_ranked_entry(session):
    project, place, _, _, _, _ = _seed(session)

    hits = search_service.search(session, project.id, "南滨旧城")

    assert any(hit.entity_type == "entry" and hit.entity_id == place.id for hit in hits)
    assert hits[0].title == "南滨旧城"
    assert "南滨旧城" in hits[0].snippet


def test_short_chinese_name_uses_like_fallback(session):
    project, _, character, _, _, _ = _seed(session)

    hits = search_service.search(session, project.id, "沈砚")

    assert any(hit.entity_type == "entry" and hit.entity_id == character.id for hit in hits)
    assert any(hit.entity_type == "scene" for hit in hits)


def test_entity_type_filter(session):
    project, place, _, _, _, _ = _seed(session)

    hits = search_service.search(session, project.id, "南滨旧城", entity_types=["entry"])

    assert hits
    assert {hit.entity_type for hit in hits} == {"entry"}


def test_search_is_project_scoped(session):
    first, place, _, _, _, _ = _seed(session)
    second = Project(name="另一个项目")
    session.add(second)
    session.commit()
    other = SettingEntry(project_id=second.id, type="place", name="南滨旧城")
    session.add(other)
    session.commit()

    hits = search_service.search(session, first.id, "南滨旧城")

    assert any(hit.entity_id == place.id for hit in hits)
    assert all(hit.entity_id != other.id for hit in hits)


def test_empty_query_returns_empty(session):
    project, _, _, _, _, _ = _seed(session)
    assert search_service.search(session, project.id, "   ") == []


def test_special_characters_do_not_crash(session):
    project, _, _, _, _, _ = _seed(session)
    for query in ('"旧城"', "%", "旧_城", '旧城 AND "信标'):
        search_service.search(session, project.id, query)


def test_limit_is_applied(session):
    project = Project(name="限额")
    session.add(project)
    session.commit()
    for index in range(5):
        session.add(
            SettingEntry(
                project_id=project.id,
                type="place",
                name=f"旧城{index}",
                summary="旧城",
            )
        )
    session.commit()

    hits = search_service.search(session, project.id, "旧城", limit=2)

    assert len(hits) == 2


def test_dirty_state_triggers_rebuild(session):
    project, place, _, _, _, _ = _seed(session)
    search_service.rebuild_project(session, project.id)

    place.name = "改名之后的旧城"
    session.commit()
    search_service.mark_dirty(session, project.id)
    session.commit()

    hits = search_service.search(session, project.id, "改名之后的旧城")
    assert any(hit.entity_id == place.id for hit in hits)


def test_schema_version_mismatch_triggers_rebuild(session):
    project, place, _, _, _, _ = _seed(session)
    search_service.rebuild_project(session, project.id)

    place.name = "版本之后的名字"
    session.commit()
    state = session.get(SearchIndexState, project.id)
    state.dirty = 0
    state.schema_version = 0
    session.commit()

    hits = search_service.search(session, project.id, "版本之后的名字")
    assert any(hit.entity_id == place.id for hit in hits)


def test_stale_document_is_skipped(session):
    project, place, _, _, _, _ = _seed(session)
    search_service.rebuild_project(session, project.id)
    state = session.get(SearchIndexState, project.id)
    state.dirty = 0
    session.commit()
    session.execute(
        text(
            "INSERT INTO search_document"
            "(doc_id, project_id, entity_type, subtype, title, body) "
            "VALUES ('entry:missing', :p, 'entry', 'place', '幽灵旧城', '幽灵旧城')"
        ),
        {"p": project.id},
    )
    session.commit()

    hits = search_service.search(session, project.id, "幽灵旧城")

    assert all(hit.entity_id != "missing" for hit in hits)
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
uv run --directory backend pytest backend/tests/test_search_service.py -q
```

Expected: FAIL，`search_service.search` 不存在。

- [ ] **Step 3: 追加查询实现**

Append to `backend/app/services/search_service.py`:

```python
from dataclasses import dataclass

from sqlalchemy.exc import OperationalError


@dataclass(frozen=True)
class SearchHit:
    entity_type: str
    entity_id: str
    subtype: str
    title: str
    snippet: str


_ALLOWED_TYPES = ("entry", "chapter", "scene")
_MODEL_BY_TYPE = {
    "entry": SettingEntry,
    "chapter": Chapter,
    "scene": Scene,
}


def search(
    session: Session,
    project_id: str,
    query: str,
    entity_types: list[str] | None = None,
    limit: int = 20,
) -> list[SearchHit]:
    normalized = " ".join((query or "").split())
    if not normalized:
        return []

    types = tuple(entity_types or _ALLOWED_TYPES)
    invalid = [item for item in types if item not in _ALLOWED_TYPES]
    if invalid:
        raise ValueError(f"未知的检索类型：{', '.join(invalid)}")
    limit = max(1, min(int(limit), 50))

    _ensure_fresh(session, project_id)

    terms = normalized.split()[:8]
    if all(len(term) >= 3 for term in terms):
        rows = _fts_rows(session, project_id, terms, types, limit)
    else:
        rows = _like_rows(session, project_id, terms, types, limit)

    hits: list[SearchHit] = []
    for row in rows:
        doc_id = str(row["doc_id"])
        if ":" not in doc_id:
            continue
        entity_type = row["entity_type"]
        entity_id = doc_id.split(":", 1)[1]
        if not _exists(session, entity_type, entity_id):
            continue
        hits.append(
            SearchHit(
                entity_type=entity_type,
                entity_id=entity_id,
                subtype=row["subtype"] or "",
                title=row["title"],
                snippet=_snippet(f"{row['title']} {row['body']}", terms),
            )
        )
    return hits


def _ensure_fresh(session: Session, project_id: str) -> None:
    state = session.get(SearchIndexState, project_id)
    if (
        state is not None
        and state.dirty == 0
        and state.schema_version == SEARCH_INDEX_VERSION
    ):
        return
    rebuild_project(session, project_id)


def _fts_rows(session, project_id, terms, types, limit):
    match = " AND ".join(
        '"' + term.replace('"', '""') + '"' for term in terms
    )
    placeholders = ", ".join(f":t{index}" for index in range(len(types)))
    params = {
        "match": match,
        "pid": project_id,
        "limit": limit,
        **{f"t{index}": item for index, item in enumerate(types)},
    }
    sql = (
        "SELECT doc_id, entity_type, subtype, title, body "
        "FROM search_document "
        "WHERE search_document MATCH :match AND project_id = :pid "
        f"AND entity_type IN ({placeholders}) "
        "ORDER BY bm25(search_document) LIMIT :limit"
    )
    try:
        return list(session.execute(text(sql), params).mappings())
    except OperationalError:
        # 全是引号/特殊符号时 FTS 语法可能报错；回退 LIKE，不把 500 抛给作者。
        return _like_rows(session, project_id, terms, types, limit)


def _like_rows(session, project_id, terms, types, limit):
    conditions = []
    params = {"pid": project_id, "scan": limit * 3}
    for index, term in enumerate(terms):
        params[f"p{index}"] = f"%{_escape_like(term)}%"
        conditions.append(
            f"(title LIKE :p{index} ESCAPE '\\' OR body LIKE :p{index} ESCAPE '\\')"
        )
    placeholders = ", ".join(f":t{index}" for index in range(len(types)))
    params.update({f"t{index}": item for index, item in enumerate(types)})
    sql = (
        "SELECT doc_id, entity_type, subtype, title, body "
        "FROM search_document "
        f"WHERE project_id = :pid AND {' AND '.join(conditions)} "
        f"AND entity_type IN ({placeholders}) LIMIT :scan"
    )
    rows = list(session.execute(text(sql), params).mappings())
    rows.sort(key=lambda row: _like_rank(row, terms))
    return rows[:limit]


def _escape_like(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def _like_rank(row, terms) -> tuple[int, str, str]:
    title = str(row["title"]).casefold()
    body = str(row["body"]).casefold()
    best = 3
    for term in terms:
        needle = term.casefold()
        if title == needle:
            best = min(best, 0)
        elif needle in title:
            best = min(best, 1)
        elif needle in body:
            best = min(best, 2)
    return (best, str(row["entity_type"]), str(row["title"]))


def _snippet(body: str, terms: list[str], width: int = 30) -> str:
    flat = " ".join((body or "").split())
    folded = flat.casefold()
    for term in terms:
        needle = term.casefold()
        index = folded.find(needle)
        if index >= 0:
            start = max(0, index - width)
            end = min(len(flat), index + len(term) + width)
            prefix = "…" if start > 0 else ""
            suffix = "…" if end < len(flat) else ""
            return prefix + flat[start:end] + suffix
    return flat[:80] + ("…" if len(flat) > 80 else "")


def _exists(session: Session, entity_type: str, entity_id: str) -> bool:
    model = _MODEL_BY_TYPE.get(entity_type)
    return model is not None and session.get(model, entity_id) is not None
```

在文件顶部 imports 中加：

```python
from dataclasses import dataclass

from sqlalchemy.exc import OperationalError
```

然后把上面的 `SearchHit` 与查询函数追加到文件末尾。不要保留未使用的导入。

- [ ] **Step 4: 跑测试确认通过**

Run:

```bash
uv run --directory backend pytest backend/tests/test_search_service.py -q
uv run --directory backend pytest -q
```

Expected: 新增查询测试全过；全量全绿。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/search_service.py backend/tests/test_search_service.py
git commit -m "feat(search): FTS 与短词友好查询"
```

---

### Task 4: 所有写入路径标脏

**Files:**
- Modify: `backend/app/services/world_service.py`
- Modify: `backend/app/services/chapter_service.py`
- Modify: `backend/app/services/scene_service.py`
- Modify: `backend/app/services/chapter_plan_service.py`
- Modify: `backend/app/services/project_service.py`
- Test: `backend/tests/test_search_maintenance.py`

**Interfaces:**
- Consumes: `search_service.mark_dirty(session, project_id)`、`search_service.delete_project(session, project_id)`。
- Produces: 每个写入事务在提交前标脏；项目删除清理文档。

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_search_maintenance.py`:

```python
from sqlalchemy import text

from app.db.models import Project, SearchIndexState
from app.services import (
    chapter_plan_service,
    chapter_service,
    project_service,
    scene_service,
    search_service,
    world_service,
)


def _project(session):
    project = Project(name="旧城")
    session.add(project)
    session.commit()
    return project


def _hits(session, project_id, query):
    return search_service.search(session, project_id, query)


def test_entry_writes_refresh_search(session):
    project = _project(session)
    entry = world_service.create_entry(
        session, project.id, type="place", name="旧城信标"
    )
    assert any(hit.entity_id == entry.id for hit in _hits(session, project.id, "旧城信标"))

    world_service.update_entry(session, entry.id, name="新信标")
    assert not any(hit.entity_id == entry.id for hit in _hits(session, project.id, "旧城信标"))
    assert any(hit.entity_id == entry.id for hit in _hits(session, project.id, "新信标"))

    world_service.delete_entry(session, entry.id)
    assert not any(hit.entity_id == entry.id for hit in _hits(session, project.id, "新信标"))


def test_volume_and_chapter_writes_refresh_search(session):
    project = _project(session)
    volume = chapter_service.create_volume(session, project.id, name="第一卷")
    chapter = chapter_service.create_chapter(session, volume.id, title="旧章")
    assert any("旧章" in hit.title for hit in _hits(session, project.id, "旧章"))

    chapter_service.update_chapter(session, chapter.id, title="新章")
    assert any("新章" in hit.title for hit in _hits(session, project.id, "新章"))
    assert not any("旧章" in hit.title for hit in _hits(session, project.id, "旧章"))

    chapter_service.move_chapter(session, chapter.id, "up")
    # 移动后仍可搜到；具体序号由重建后的标题体现
    assert any(hit.entity_type == "chapter" for hit in _hits(session, project.id, "新章"))

    chapter_service.delete_volume(session, volume.id)
    assert not any(hit.entity_type == "chapter" for hit in _hits(session, project.id, "新章"))


def test_scene_writes_refresh_search(session):
    project = _project(session)
    volume = chapter_service.create_volume(session, project.id, name="第一卷")
    chapter = chapter_service.create_chapter(session, volume.id, title="章")
    scene = scene_service.create_scene(session, chapter.id, goal="旧目标")
    assert any(hit.entity_id == scene.id for hit in _hits(session, project.id, "旧目标"))

    scene_service.update_scene(session, scene.id, goal="新目标")
    assert any(hit.entity_id == scene.id for hit in _hits(session, project.id, "新目标"))

    scene_service.delete_scene(session, scene.id)
    assert not any(hit.entity_id == scene.id for hit in _hits(session, project.id, "新目标"))


def test_write_scenes_replace_refreshes_search(session):
    project = _project(session)
    volume = chapter_service.create_volume(session, project.id, name="第一卷")
    chapter = chapter_service.create_chapter(session, volume.id, title="章")
    scene_service.write_scenes(
        session, chapter.id, [{"goal": "旧的批量目标"}], "replace"
    )
    assert any("旧的批量目标" in hit.title for hit in _hits(session, project.id, "旧的批量目标"))

    scene_service.write_scenes(
        session, chapter.id, [{"goal": "新的批量目标"}], "replace"
    )
    assert any("新的批量目标" in hit.title for hit in _hits(session, project.id, "新的批量目标"))
    assert not any("旧的批量目标" in hit.title for hit in _hits(session, project.id, "旧的批量目标"))


def test_write_chapter_plan_refreshes_search(session):
    project = _project(session)
    chapter_plan_service.write_chapter_plan(
        session,
        project.id,
        [
            {
                "name": "新卷",
                "chapters": [{"title": "策划出来的章"}],
            }
        ],
        "replace",
    )

    assert any("策划出来的章" in hit.title for hit in _hits(session, project.id, "策划出来的章"))


def test_project_delete_cleans_search(session):
    project = _project(session)
    world_service.create_entry(session, project.id, type="place", name="要删的旧城")
    assert _hits(session, project.id, "要删的旧城")

    project_service.delete_project(session, project.id)

    count = session.execute(
        text("SELECT COUNT(*) FROM search_document WHERE project_id = :p"),
        {"p": project.id},
    ).scalar()
    assert count == 0


def test_moves_and_deletes_mark_dirty(session):
    project = _project(session)
    first_volume = chapter_service.create_volume(session, project.id, name="甲")
    second_volume = chapter_service.create_volume(session, project.id, name="乙")
    first_chapter = chapter_service.create_chapter(session, first_volume.id, title="一")
    second_chapter = chapter_service.create_chapter(session, first_volume.id, title="二")
    scene_service.create_scene(session, first_chapter.id, goal="目标一")
    second_scene = scene_service.create_scene(session, first_chapter.id, goal="目标二")

    def reset():
        state = session.get(SearchIndexState, project.id)
        state.dirty = 0
        session.commit()

    assert session.get(SearchIndexState, project.id).dirty == 1
    reset()
    chapter_service.move_chapter(session, second_chapter.id, "up")
    assert session.get(SearchIndexState, project.id).dirty == 1

    reset()
    scene_service.move_scene(session, second_scene.id, "up")
    assert session.get(SearchIndexState, project.id).dirty == 1

    reset()
    chapter_service.move_volume(session, second_volume.id, "up")
    assert session.get(SearchIndexState, project.id).dirty == 1

    reset()
    chapter_service.update_volume(session, first_volume.id, name="丙")
    assert session.get(SearchIndexState, project.id).dirty == 1

    reset()
    chapter_service.delete_chapter(session, first_chapter.id)
    assert session.get(SearchIndexState, project.id).dirty == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
uv run --directory backend pytest backend/tests/test_search_maintenance.py -q
```

Expected: 至少首条失败 —— 写入后检索看不到新数据（没有标脏/重建入口）。

- [ ] **Step 3: 在每个写入事务提交前标脏**

Add `from app.services import search_service` to each modified service module.

Insert `search_service.mark_dirty(session, <project_id>)` immediately before every `session.commit()` in:

| 文件 | 函数 | project 表达式 |
|---|---|---|
| `world_service.py` | `create_entry` / `update_entry` / `delete_entry` | `project_id` / `entry.project_id` |
| `chapter_service.py` | `create_volume` / `update_volume` / `delete_volume` / `move_volume` | `project_id` / `volume.project_id` |
| `chapter_service.py` | `create_chapter` | `volume.project_id` |
| `chapter_service.py` | `update_chapter` / `delete_chapter` / `move_chapter` | 先取 `project = get_project_for_chapter(session, chapter_id)`，用 `project.id` |
| `scene_service.py` | `create_scene` / `update_scene` / `write_scenes` | `project.id` |
| `scene_service.py` | `delete_scene` / `move_scene` | `chapter_service.get_project_for_chapter(session, scene.chapter_id).id` |
| `chapter_plan_service.py` | `write_chapter_plan` | `project.id`（在 `try` 内的 `session.commit()` 前） |
| `project_service.py` | `delete_project` | 在 `session.delete(project)` 前调用 `search_service.delete_project(session, project_id)` |

Concrete insertion examples:

In `world_service.create_entry`, before `session.commit()`:

```python
    search_service.mark_dirty(session, project_id)
    session.commit()
```

In `world_service.update_entry` / `delete_entry`:

```python
    search_service.mark_dirty(session, entry.project_id)
    session.commit()
```

In `chapter_service.create_volume`:

```python
    search_service.mark_dirty(session, project_id)
    session.commit()
```

In `chapter_service.update_volume` / `delete_volume` / `move_volume`:

```python
    search_service.mark_dirty(session, volume.project_id)
    session.commit()
```

In `chapter_service.create_chapter`:

```python
    search_service.mark_dirty(session, volume.project_id)
    session.commit()
```

In `chapter_service.update_chapter` / `delete_chapter` / `move_chapter`, add near the top (after the entity lookup):

```python
    project = get_project_for_chapter(session, chapter_id)
```

and before the commit:

```python
    search_service.mark_dirty(session, project.id)
    session.commit()
```

In `scene_service.create_scene` / `update_scene` / `write_scenes`, before commit:

```python
    search_service.mark_dirty(session, project.id)
    session.commit()
```

In `scene_service.delete_scene` / `move_scene`, after the scene lookup:

```python
    project = chapter_service.get_project_for_chapter(session, scene.chapter_id)
```

and before commit:

```python
    search_service.mark_dirty(session, project.id)
    session.commit()
```

In `chapter_plan_service.write_chapter_plan`, before the `session.commit()` inside the `try`:

```python
        search_service.mark_dirty(session, project.id)
        session.commit()
```

In `project_service.delete_project`, before `session.delete(project)`:

```python
    search_service.delete_project(session, project_id)
    session.delete(project)
    session.commit()
```

- [ ] **Step 4: 跑测试确认通过**

Run:

```bash
uv run --directory backend pytest backend/tests/test_search_maintenance.py -q
uv run --directory backend pytest -q
```

Expected: 新增维护测试全过；全量全绿。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/world_service.py backend/app/services/chapter_service.py backend/app/services/scene_service.py backend/app/services/chapter_plan_service.py backend/app/services/project_service.py backend/tests/test_search_maintenance.py
git commit -m "feat(search): 写入路径标脏与级联维护"
```

---

### Task 5: 检索 API

**Files:**
- Create: `backend/app/api/search.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_search_api.py`

**Interfaces:**
- Consumes: `search_service.search`、`project_service.get_project`。
- Produces: `GET /api/projects/{project_id}/search`。

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_search_api.py`:

```python
def _project_with_entry(client, name="南滨旧城"):
    project = client.post("/api/projects", json={"name": "检索"}).json()
    entry = client.post(
        f"/api/projects/{project['id']}/entries",
        json={"name": name, "type": "place", "summary": "记忆清算网络的据点"},
    ).json()
    return project, entry


def test_search_returns_results(client):
    project, entry = _project_with_entry(client)

    response = client.get(
        f"/api/projects/{project['id']}/search", params={"q": "南滨旧城"}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "南滨旧城"
    assert any(item["entity_id"] == entry["id"] for item in payload["results"])
    hit = next(item for item in payload["results"] if item["entity_id"] == entry["id"])
    assert hit["entity_type"] == "entry"
    assert hit["subtype"] == "place"
    assert hit["title"] == "南滨旧城"
    assert "南滨旧城" in hit["snippet"]


def test_search_project_not_found(client):
    response = client.get("/api/projects/not-a-project/search", params={"q": "旧城"})
    assert response.status_code == 404


def test_search_rejects_blank_query(client):
    project, _ = _project_with_entry(client)
    assert client.get(
        f"/api/projects/{project['id']}/search", params={"q": "   "}
    ).status_code == 400


def test_search_rejects_unknown_types(client):
    project, _ = _project_with_entry(client)
    response = client.get(
        f"/api/projects/{project['id']}/search",
        params={"q": "旧城", "types": "entry,nope"},
    )
    assert response.status_code == 400


def test_search_rejects_bad_limit(client):
    project, _ = _project_with_entry(client)
    for limit in (0, 51):
        response = client.get(
            f"/api/projects/{project['id']}/search",
            params={"q": "旧城", "limit": limit},
        )
        assert response.status_code == 400


def test_search_types_filter(client):
    project, _ = _project_with_entry(client)

    entries = client.get(
        f"/api/projects/{project['id']}/search",
        params={"q": "旧城", "types": "entry"},
    ).json()
    chapters = client.get(
        f"/api/projects/{project['id']}/search",
        params={"q": "旧城", "types": "chapter"},
    ).json()

    assert entries["results"]
    assert chapters["results"] == []
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
uv run --directory backend pytest backend/tests/test_search_api.py -q
```

Expected: 404/405（路由不存在）。

- [ ] **Step 3: 写 API 并注册**

Create `backend/app/api/search.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.services import project_service, search_service

router = APIRouter(prefix="/api", tags=["search"])

_ALLOWED_TYPES = {"entry", "chapter", "scene"}


@router.get("/projects/{project_id}/search")
def search_project(
    project_id: str,
    q: str = Query(...),
    limit: int = Query(20),
    types: str | None = None,
    session: Session = Depends(get_session),
) -> dict:
    """全文检索。首次检索可能触发该项目的索引重建并提交索引状态。"""
    if project_service.get_project(session, project_id) is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not q.strip() or len(q) > 200:
        raise HTTPException(status_code=400, detail="检索词长度必须在 1–200 之间")
    if not 1 <= limit <= 50:
        raise HTTPException(status_code=400, detail="limit 必须在 1–50 之间")

    entity_types: list[str] | None = None
    if types:
        entity_types = [item.strip() for item in types.split(",") if item.strip()]
        invalid = [item for item in entity_types if item not in _ALLOWED_TYPES]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"未知的检索类型：{', '.join(invalid)}",
            )

    try:
        hits = search_service.search(
            session,
            project_id,
            q,
            entity_types=entity_types,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "query": q,
        "results": [
            {
                "entity_type": hit.entity_type,
                "entity_id": hit.entity_id,
                "subtype": hit.subtype,
                "title": hit.title,
                "snippet": hit.snippet,
            }
            for hit in hits
        ],
    }
```

Modify `backend/app/main.py`:

- Add `search,` to the `from app.api import ( ... )` tuple (alphabetically before `slots`).
- Add `search,` to the router tuple before `slots`.

- [ ] **Step 4: 跑测试确认通过**

Run:

```bash
uv run --directory backend pytest backend/tests/test_search_api.py -q
uv run --directory backend pytest -q
```

Expected: 新增 API 测试全过；全量全绿。

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/search.py backend/app/main.py backend/tests/test_search_api.py
git commit -m "feat(search): 检索 API"
```

---

### Task 6: 相关设定条目检索槽位

**Files:**
- Modify: `backend/app/runtime/context.py`
- Modify: `backend/app/services/slot_source.py`
- Modify: `backend/tests/test_context.py`
- Modify: `backend/tests/test_slot_source.py`

**Interfaces:**
- Consumes: `search_service.search`、`SearchHit`。
- Produces:
  - `SlotSource.related_settings` 协议方法
  - `SLOT_REGISTRY["related_settings"]`
  - `DbSlotSource.related_settings() -> str | None`

- [ ] **Step 1: 写失败测试**

Append to `backend/tests/test_context.py`:

```python
def test_related_settings_slot_registered():
    from app.runtime.context import P_MID, SLOT_REGISTRY

    spec = SLOT_REGISTRY["related_settings"]
    assert spec.label == "相关设定条目（检索）"
    assert spec.priority == P_MID
    assert spec.over_budget == "summarize"
```

Append to `backend/tests/test_slot_source.py`:

```python
from app.services import chapter_service, world_service


def _search_project(session, name="旧城"):
    project = Project(name="检索项目")
    session.add(project)
    session.commit()
    return project


def test_related_settings_uses_search_query(session):
    project = _search_project(session)
    world_service.create_entry(
        session,
        project.id,
        type="place",
        name="南滨旧城",
        summary="记忆清算网络的据点",
    )

    text = DbSlotSource(
        session,
        project.id,
        extra_slots={"search_query": "南滨旧城"},
    ).related_settings()

    assert text is not None
    assert "南滨旧城" in text
    assert "【地理】" in text


def test_related_settings_derives_query_from_chapter(session):
    project = _search_project(session)
    world_service.create_entry(
        session,
        project.id,
        type="place",
        name="旧城信标",
        summary="雨夜亮起",
    )
    volume = chapter_service.create_volume(session, project.id, name="第一卷")
    chapter = chapter_service.create_chapter(
        session, volume.id, title="旧城信标", summary="寻找信标"
    )

    text = DbSlotSource(
        session,
        project.id,
        extra_slots={"chapter_id": chapter.id},
    ).related_settings()

    assert text is not None
    assert "旧城信标" in text


def test_related_settings_none_without_query_or_chapter(session):
    project = _search_project(session)
    world_service.create_entry(session, project.id, type="place", name="甲")
    assert DbSlotSource(session, project.id).related_settings() is None


def test_related_settings_is_project_scoped(session):
    first = _search_project(session)
    second = _search_project(session)
    world_service.create_entry(session, first.id, type="place", name="旧城甲")
    world_service.create_entry(session, second.id, type="place", name="旧城乙")

    text = DbSlotSource(
        session, first.id, extra_slots={"search_query": "旧城"}
    ).related_settings()

    assert "旧城甲" in text
    assert "旧城乙" not in text
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
uv run --directory backend pytest backend/tests/test_context.py backend/tests/test_slot_source.py -q
```

Expected: FAIL，槽位未注册/方法不存在。

- [ ] **Step 3: 写槽位实现**

Modify `backend/app/runtime/context.py`:

- Add to `SlotSource` protocol after `chapter_outline`:

```python
    def related_settings(self) -> str | None: ...
```

- Add to `SLOT_REGISTRY`:

```python
        SlotSpec("related_settings", "相关设定条目（检索）", P_MID, "summarize"),
```

Modify `backend/app/services/slot_source.py`:

- Add `from app.services import search_service` to imports.
- Add the method after `word_context` or after `chapter_outline` (any position; `_chapter` is defined later and callable):

```python
    def related_settings(self) -> str | None:
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
```

Note: `search_service` imports no service module, so this does not create a cycle. The search may rebuild and commit during context assembly; document it.

- [ ] **Step 4: 跑测试确认通过**

Run:

```bash
uv run --directory backend pytest backend/tests/test_context.py backend/tests/test_slot_source.py -q
uv run --directory backend pytest -q
```

Expected: 新增槽位测试全过；全量全绿。

- [ ] **Step 5: 提交**

```bash
git add backend/app/runtime/context.py backend/app/services/slot_source.py backend/tests/test_context.py backend/tests/test_slot_source.py
git commit -m "feat(search): 相关设定条目检索槽位"
```

---

### Task 7: 手工验证、作者库副本与阶段文档

**Files:**
- Create: `docs/superpowers/plans/2026-10-18-fts5-walkthrough.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: 已启动的后端与 Task 1–6 的检索能力。

- [ ] **Step 1: 临时数据目录与 API 播种**

在 SDD 工作区写 `seed_fts.py`：

```python
"""FTS 走查夹具：只通过 HTTP API 写入临时数据目录。"""

import httpx

BASE = "http://127.0.0.1:8756"


def main() -> None:
    client = httpx.Client(base_url=BASE, timeout=30)

    def post(path: str, body: dict) -> dict:
        response = client.post(path, json=body)
        response.raise_for_status()
        return response.json()

    project = post("/api/projects", {"name": "FTS 走查"})
    pid = project["id"]
    place = post(
        f"/api/projects/{pid}/entries",
        {
            "name": "南滨旧城",
            "type": "place",
            "aliases": ["旧城"],
            "summary": "记忆清算网络的据点",
            "description": "湿带边缘的旧城区",
        },
    )
    character = post(
        f"/api/projects/{pid}/entries",
        {
            "name": "沈砚",
            "type": "character",
            "aliases": ["阿砚"],
            "desire": "找回被抹去的记忆",
        },
    )
    volume = post(f"/api/projects/{pid}/volumes", {"name": "第一卷"})
    chapter = post(
        f"/api/volumes/{volume['id']}/chapters",
        {"title": "开端", "summary": "南滨旧城的雨夜", "hook": "旧城信标亮起"},
    )
    scene = post(
        f"/api/chapters/{chapter['id']}/scenes",
        {
            "goal": "找到旧城信标",
            "conflict": "记忆清算人追来",
            "turn": "信标是假的",
            "characters": ["沈砚"],
            "location": "南滨旧城",
        },
    )
    print(f"project={pid}")
    print(f"place={place['id']} character={character['id']}")
    print(f"volume={volume['id']} chapter={chapter['id']} scene={scene['id']}")


if __name__ == "__main__":
    main()
```

起服务（后台）：

```bash
mkdir -p "$LOCALAPPDATA/StoryForge-fts-walkthrough"
STORYFORGE_DATA_DIR="$LOCALAPPDATA/StoryForge-fts-walkthrough" uv run --directory backend uvicorn app.main:app --port 8756
```

等 `/api/health` 后播种：

```bash
uv run --directory backend python "<worktree-root>/.superpowers/sdd/2026-10-18-fts5-search-foundation/seed_fts.py"
```

- [ ] **Step 2: curl 走查**

用任务输出的 project id：

```bash
curl -s "http://127.0.0.1:8756/api/projects/<pid>/search?q=%E5%8D%97%E6%BB%A8%E6%97%A7%E5%9F%8E"
curl -s "http://127.0.0.1:8756/api/projects/<pid>/search?q=%E6%B2%88%E7%A0%9A"
curl -s "http://127.0.0.1:8756/api/projects/<pid>/search?q=%E6%97%A7%E5%9F%8E&types=entry"
curl -s "http://127.0.0.1:8756/api/projects/<pid>/search?q=%E6%97%A7%E5%9F%8E&limit=1"
```

预期：

- `q=南滨旧城`（4 字）返回条目「南滨旧城」，snippet 含该词；
- `q=沈砚`（2 字）返回人物条目与场景（场景正文含出场人物）；
- `types=entry` 只返回条目；
- `limit=1` 只返回 1 条；
- 改条目名后再搜旧名无结果、新名有结果；删场景后再搜该场景目标无结果；
- 控制台/后端日志无 500。

把实际结果写入 `docs/superpowers/plans/2026-10-18-fts5-walkthrough.md`：

```markdown
# FTS5 全文检索手工走查

> 2026-10-18。临时数据目录 `<路径>`；后端 8756。

## 夹具
- 项目「FTS 走查」：条目「南滨旧城」（别名「旧城」）、人物「沈砚」（别名「阿砚」）、
  第一卷 / 第一章 / 场景「找到旧城信标」（人物沈砚、地点南滨旧城）。

## 检查项
- [ ] 4 字查询走 FTS，结果含条目且 snippet 命中。
- [ ] 2 字查询走 LIKE 回退，结果含人物条目与场景。
- [ ] types=entry 只返回条目。
- [ ] limit=1 只返回一条。
- [ ] 改条目名后：旧名无结果、新名有结果。
- [ ] 删场景后：该场景目标不再出现。
- [ ] 项目隔离：另一个项目的同名条目不出现。
- [ ] 控制台/日志 0 个 500。

## 结果
逐项勾选并填写实际观察；失败项记录复现命令。
```

- [ ] **Step 3: 作者库副本验证**

- 复制 `%LOCALAPPDATA%\StoryForge\storyforge.db`、存在的 `storyforge.db-wal` / `-shm`、
  `secrets.bin`、`settings.json` 到 `%LOCALAPPDATA%\StoryForge-fts-copy\`（原库不动）。
  只拷主文件会丢掉尚未落盘的 WAL 改动。
- 用该副本作为 `STORYFORGE_DATA_DIR` 启动后端；`GET /api/projects` 取第一个项目，
  `GET /api/projects/{id}/entries` 取一个条目名，调用
  `/search?q=<该名字>`，确认存量库首次检索能重建出结果（4 字与 2 字各试一次）。
- 验证后停止服务并删除副本目录。**不调用模型。**
- 把结果补进走查文档。

- [ ] **Step 4: 更新 CLAUDE.md**

路线图：在 P1c-2 行之后、P2 之前插入：

```markdown
| **FTS5 全文检索地基** | 条目 / 章 / 场景索引、中文查询、检索 API、相关设定条目槽位 | ✅ 完成（2026-10-18 通过临时数据目录与作者库副本验证；遗留见下方阶段记录） |
```

追加阶段记录：

```markdown
**2026-10-18 · FTS5 全文检索地基（实施完成）**

设计 `docs/superpowers/specs/2026-10-18-fts5-search-foundation-design.md`；实施计划 `docs/superpowers/plans/2026-10-18-fts5-search-foundation.md`。P2 的硬前置。

产出：

- **索引**：`search_document` FTS5 trigram 虚拟表 + `search_index_state` 普通表；`ensure_search_index` 在 `create_all` 后幂等创建；不新增迁移版本。
- **维护**：所有条目 / 卷 / 章 / 场景写入在事务内标脏；首次检索按项目从基表重建；项目删除清理文档与状态；已删除实体从结果中剔除。
- **查询**：≥3 字走 FTS + bm25；2 字人名/地名走 LIKE 回退；结果带标题与片段；项目隔离。
- **入口**：`GET /api/projects/{id}/search`；`related_settings` 槽位（opt-in，优先 `search_query`，否则当前章标题/摘要/钩子）。
- **测试夹具**：`drop_all` 不覆盖 FTS 虚拟表，测试在重建后清空 `search_document`。

验证：后端全绿（既有 339 + 本段新增，实际数见本次运行）；前端仍 18 passed + build 干净；临时数据目录走查与作者库副本验证通过；未调用模型、未写作者真实库。

遗留：伏笔 / 时间线 / 正文未入索引（正文待 P2）；前端搜索页留 P5；向量检索留二期。
```

在 §8 变更记录末尾追加：

```markdown
| 2026-10-18 | FTS5 索引覆盖**设定条目 / 章 / 场景**；伏笔、时间线、正文后续再加类型 | P2 需要的是相关设定条目；其余结构化实体已有查询 |
| 2026-10-18 | FTS 虚拟表**不放进迁移**：由 `ensure_search_index` 在 `create_all` 后幂等创建；`search_index_state` 走 `create_all` | FTS 虚拟表无法用 SQLAlchemy metadata 表达；迁移框架的规则是「迁移只改已有表」 |
| 2026-10-18 | 索引维护采用**写事务内标脏 + 首次检索按项目重建**，不做逐实体增量、不用触发器 | 字段清单只保留一个 Python 构建器，天然覆盖级联删除与批量写入；代价是写入后首次检索重建 |
| 2026-10-18 | 中文查询 **≥3 字 trigram + bm25；<3 字 LIKE 回退** | 本机实测 2 字人名/地名 trigram 不命中；不引入分词依赖 |
| 2026-10-18 | 检索可能触发索引重建并在读请求里提交状态 | 惰性重建没有后台队列；P2 上下文组装阶段没有待提交业务写入 |
| 2026-10-18 | `related_settings` 槽位 **opt-in**；P2 执笔智能体负责勾选并传 `search_query` | 不改变现有任何智能体的上下文；P2 才有场景查询 |
| 2026-10-18 | 不做前端搜索页；P5 阅读器检索复用同一接口 | 本段是 P2 前置；UI 属发行阶段 |
| 2026-10-18 | 测试夹具必须清空 FTS 虚拟表（`drop_all` 不覆盖它） | 否则跨用例文档累积，测试结果被污染 |
```

同时把 P1a 阶段记录里「SQLite FTS5 全文检索一次都没写」那条的首句改为：

```markdown
- **SQLite FTS5 全文检索（2026-10-18 已补齐，见「FTS5 全文检索地基」阶段记录）**。
```

- [ ] **Step 5: 最终验证**

Run:

```bash
uv run --directory backend pytest -q
cd frontend && pnpm vitest run && pnpm build
```

Expected: 后端全绿（既有 339 + 新增）；前端 18 passed；build 干净。

- [ ] **Step 6: 提交**

```bash
git add docs/superpowers/plans/2026-10-18-fts5-walkthrough.md CLAUDE.md
git commit -m "docs: 归档 FTS5 走查并同步阶段记录"
```

---

## Final Verification

- [ ] `uv run --directory backend pytest -q` → 全绿（既有 339 + 新增，记录实际数）。
- [ ] `cd frontend && pnpm vitest run` → 18 passed。
- [ ] `cd frontend && pnpm build` → 干净。
- [ ] 临时数据目录与作者库副本已删除；作者真实库未写入。
- [ ] `git status --porcelain` → 干净。
