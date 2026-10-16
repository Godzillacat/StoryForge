# 迁移框架与契约容错 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `init_db()` 从「只建缺失的表」升级成「能改已有的表」，并让输出契约校验器容忍可选字段的 `null`。

**Architecture:** 新增 `app/db/migrations.py` 存手写的有序步骤，`schema_migration` 表记录执行到哪；`init_db()` 按「全新库 / 存量库」分派 —— 全新库由模型直接建并盖成最新版本，存量库盖基线后补跑历史迁移。契约校验器只在**父节点**放过可选字段的 `null`（必填不放过）。

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy 2.x / SQLite；uv（`CLAUDE.md` §6）。

**Spec:** `docs/superpowers/specs/2026-10-16-migration-and-contract-design.md`

## Global Constraints

- **分层硬约束**：`api` 不写业务逻辑；`services` 不碰 HTTP；`runtime` **不依赖 FastAPI**（`CLAUDE.md` §5）。
- **标识符与代码用英文；注释、界面文案、提示词用中文**（`CLAUDE.md` §9）。注释密度跟随周围代码，只在「为什么」不明显处写注释。
- **不引入重型依赖**（`CLAUDE.md` §9）—— 迁移框架手写，不加 alembic。
- **纯逻辑必须测（pytest）**。
- 测试命令在 `backend/` 下：`uv run pytest`。
- **迁移永不建表**：新表归 `create_all`，迁移只改已有的表。
- 数据目录：`%LOCALAPPDATA%\StoryForge\`，测试里由 `conftest.py` 的 `STORYFORGE_DATA_DIR` 指向临时目录。

---

## File Structure

| 文件 | 职责 | 动作 |
|---|---|---|
| `backend/app/db/migrations.py` | 迁移步骤表与 `pending()`。纯数据 + 纯函数，不碰 engine | 新建 |
| `backend/app/db/session.py` | `is_fresh_database` / `run_migrations` / 备份 / `init_db` 分派 | 改 |
| `backend/app/runtime/schema.py` | 对象分支放过可选字段的 `null` | 改 |
| `backend/tests/test_migrations.py` | 步骤表与 `pending` | 新建 |
| `backend/tests/test_migration_runner.py` | runner：全新库 / 存量库 / 执行一次 / 失败 / 备份 | 新建 |
| `backend/tests/test_schema.py` | 追加可选 `null` 的用例 | 改 |

---

### Task 1: 迁移步骤表

**Files:**
- Create: `backend/app/db/migrations.py`
- Test: `backend/tests/test_migrations.py`

**Interfaces:**
- Consumes: 无
- Produces: `Migration`（`version: int` / `note: str` / `statements: tuple[str, ...]`）、`MIGRATIONS: tuple[Migration, ...]`、`BASELINE_VERSION = 0`、`latest_version() -> int`、`pending(applied: int) -> tuple[Migration, ...]`

- [ ] **Step 1: Write the failing test**

创建 `backend/tests/test_migrations.py`：

```python
from app.db import migrations


def test_today_the_list_is_empty_and_that_is_fine():
    """当下没有需要改的已有表，所以列表是空的 —— 框架的第一次真正使用
    是 P1b-2 给 setting_entry 加列。空列表不该让它算崩。"""
    assert migrations.MIGRATIONS == ()
    assert migrations.BASELINE_VERSION == 0
    assert migrations.latest_version() == 0


def test_versions_are_unique_and_above_the_baseline():
    """版本号重复会在 schema_migration 上撞主键；基线本身不能被当成一条步骤。"""
    versions = [m.version for m in migrations.MIGRATIONS]

    assert len(versions) == len(set(versions))
    assert all(v > migrations.BASELINE_VERSION for v in versions)


def test_pending_returns_only_versions_after_the_applied_one(monkeypatch):
    monkeypatch.setattr(
        migrations,
        "MIGRATIONS",
        (
            migrations.Migration(1, "甲", ("SELECT 1",)),
            migrations.Migration(2, "乙", ("SELECT 1",)),
            migrations.Migration(3, "丙", ("SELECT 1",)),
        ),
    )

    assert [m.version for m in migrations.pending(0)] == [1, 2, 3]
    assert [m.version for m in migrations.pending(2)] == [3]
    assert migrations.pending(3) == ()


def test_pending_sorts_by_version_even_if_the_list_is_out_of_order(monkeypatch):
    """列表写乱了不该让执行顺序乱 —— 迁移必须按版本号升序跑。"""
    monkeypatch.setattr(
        migrations,
        "MIGRATIONS",
        (
            migrations.Migration(2, "乙", ("SELECT 1",)),
            migrations.Migration(1, "甲", ("SELECT 1",)),
        ),
    )

    assert [m.version for m in migrations.pending(0)] == [1, 2]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_migrations.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'app.db.migrations'`

- [ ] **Step 3: Write minimal implementation**

创建 `backend/app/db/migrations.py`：

```python
"""数据迁移的步骤表。

**迁移只做 create_all 做不到的事：改已有的表。** 新表仍由模型负责 ——
create_all 只建缺失的表，本来就够用。两套机制职责不重叠，就不会互相打架。

版本号从 1 开始、严格递增；baseline 记为 0（见 session.init_db 对存量库的盖章）。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Migration:
    version: int
    note: str
    statements: tuple[str, ...]  # 原始 SQL，按序执行


# 今天是空的：当下没有需要改的已有表。第一次真正使用是 P1b-2 给 setting_entry 加列。
MIGRATIONS: tuple[Migration, ...] = ()

BASELINE_VERSION = 0


def latest_version() -> int:
    """当前 schema 版本 —— 取**最大值**，不是列表末位。

    **是函数不是常量。** 常量在导入时就算好了，而测试要注入临时步骤只能
    monkeypatch `MIGRATIONS`，常量不会跟着变 —— 于是任何依赖它的代码路径
    都永远测不到（`init_db` 正是用它给全新库盖章，那是最该被测到的一步）。
    取 max 而非 `[-1]`：`pending()` 刻意容忍列表乱序，两者口径必须一致。
    """
    return max((m.version for m in MIGRATIONS), default=BASELINE_VERSION)


def pending(applied: int) -> tuple[Migration, ...]:
    """版本号大于 applied 的步骤，按版本号升序。**运行时现读**，不要缓存。"""
    return tuple(sorted((m for m in MIGRATIONS if m.version > applied), key=lambda m: m.version))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_migrations.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/migrations.py backend/tests/test_migrations.py
git commit -m "feat(db): 迁移步骤表与 pending"
```

---

### Task 2: 迁移 runner（存量库路径）

**Files:**
- Modify: `backend/app/db/session.py`
- Test: `backend/tests/test_migration_runner.py`

**Interfaces:**
- Consumes: `migrations.MIGRATIONS` / `BASELINE_VERSION` / `pending`（Task 1）
- Produces:
  - `is_fresh_database(engine: Engine) -> bool`
  - `run_migrations(engine: Engine) -> None`
  - 表 `schema_migration(version INTEGER PRIMARY KEY, note TEXT, applied_at TEXT)`

- [ ] **Step 1: Write the failing test**

创建 `backend/tests/test_migration_runner.py`：

```python
import pytest
from sqlalchemy import inspect, text

from app import config
from app.db import migrations
from app.db import models  # noqa: F401  注册模型到 metadata —— 见下方说明
from app.db import session as db_session
from app.db.base import Base


# 必须显式导入 app.db.models：它在生产代码里是在 init_db() **函数体内**导入的，
# 所以只 import session 是拿不到模型的。跑整个套件时别的测试文件会顺手把它注册
# 上，于是这文件看起来「能跑」；单独跑（本计划 Step 4 就是这么跑的）时
# metadata 是空的，create_all 什么都不建，测试当场红 —— 典型的一套绿、单跑红。


@pytest.fixture()
def clean_db():
    """给迁移测试一个真空的库。

    不能用 conftest 的 session 夹具：它的 drop_all 管不到 schema_migration
    （那不是 ORM 模型），而迁移测试恰恰关心「有没有那张表」。备份目录同理，
    它跨用例留着会让「该不该备份」的断言失真。
    """
    import shutil

    # ORM 表先交给 drop_all —— 它按依赖顺序删。**不能只按 sqlite_master 的
    # 顺序逐个 DROP**：session.py 开着 PRAGMA foreign_keys=ON，而 sqlite_master
    # 的顺序下 project 先于引用它的 setting_entry 被删，后者当场报
    # 「no such table: main.project」。
    Base.metadata.drop_all(db_session.engine)

    # 再清 drop_all 管不到的那些：测试探针表（_probe / _a / _b）是**原始 SQL**
    # 建的、不在 metadata 里，不清掉会泄漏到下一个用例（撞「table _probe
    # already exists」）；schema_migration 同理（它不是 ORM 模型，而迁移测试
    # 恰好在乎它在不在）。这两类都没有外键，删除顺序无所谓。
    with db_session.engine.begin() as conn:
        rows = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        for (name,) in rows:
            conn.exec_driver_sql(f'DROP TABLE IF EXISTS "{name}"')

    backups = config.data_dir() / "backups"
    if backups.exists():
        shutil.rmtree(backups)
    return db_session.engine


def _step(version: int, note: str, *statements: str) -> migrations.Migration:
    return migrations.Migration(version, note, statements)


def test_fresh_database_is_detected(clean_db):
    assert db_session.is_fresh_database(clean_db) is True


def test_existing_database_is_not_fresh(clean_db):
    Base.metadata.create_all(clean_db)

    assert db_session.is_fresh_database(clean_db) is False


def test_migration_table_alone_still_counts_as_fresh(clean_db):
    """迁移表是基础设施，不算业务表 —— 否则一个只跑过 runner 的空库会被
    误判成存量库，然后去跑一堆改不存在的表的迁移。"""
    with clean_db.begin() as conn:
        db_session._ensure_migration_table(conn)

    assert db_session.is_fresh_database(clean_db) is True


def test_existing_database_is_stamped_at_the_baseline(clean_db):
    Base.metadata.create_all(clean_db)

    db_session.run_migrations(clean_db)

    with clean_db.connect() as conn:
        rows = conn.exec_driver_sql("SELECT version, note FROM schema_migration").fetchall()
    assert rows == [(migrations.BASELINE_VERSION, "基线（迁移框架引入时的库结构）")]


def test_existing_database_keeps_its_rows(clean_db):
    """盖章不能碰数据 —— 这是整件事的意义所在。"""
    Base.metadata.create_all(clean_db)
    with clean_db.begin() as conn:
        # writing_lang / logic_check_level 是 NOT NULL，而它们的默认值只在
        # 客户端（ORM 层）—— 原生 INSERT 必须自己给。
        conn.exec_driver_sql(
            "INSERT INTO project (id, name, writing_lang, logic_check_level, created_at, updated_at) "
            "VALUES ('p1', '雾港', 'zh', 'loose', '2026-10-16', '2026-10-16')"
        )

    db_session.run_migrations(clean_db)

    with clean_db.connect() as conn:
        assert conn.exec_driver_sql("SELECT name FROM project").fetchall() == [("雾港",)]


def test_a_pending_step_runs_once_and_is_recorded(clean_db, monkeypatch):
    Base.metadata.create_all(clean_db)
    monkeypatch.setattr(
        migrations, "MIGRATIONS", (_step(1, "探针", "CREATE TABLE _probe (x INTEGER)"),)
    )

    db_session.run_migrations(clean_db)
    assert "_probe" in inspect(clean_db).get_table_names()

    # 再跑一次：不该重复执行（重复执行会因表已存在而抛错，这里没抛即为通过）
    db_session.run_migrations(clean_db)

    with clean_db.connect() as conn:
        assert conn.exec_driver_sql(
            "SELECT version FROM schema_migration ORDER BY version"
        ).fetchall() == [(0,), (1,)]


def test_a_failing_step_is_not_recorded(clean_db, monkeypatch):
    """半迁移的库比起不来的应用危险 —— 失败的步骤绝不能被记成已执行，
    否则下次启动会跳过它，应用带着与模型不符的结构跑。"""
    Base.metadata.create_all(clean_db)
    monkeypatch.setattr(
        migrations, "MIGRATIONS", (_step(1, "会炸的", "THIS IS NOT SQL"),)
    )

    with pytest.raises(Exception):
        db_session.run_migrations(clean_db)

    with clean_db.connect() as conn:
        assert conn.exec_driver_sql("SELECT MAX(version) FROM schema_migration").fetchone() == (0,)


def test_a_multi_statement_step_that_fails_leaves_nothing_behind(clean_db, monkeypatch):
    """DDL 不会因为 engine.begin() 的回滚而撤销 —— pysqlite 走 legacy 事务控制，
    真的 BEGIN 只在第一条 DML 之前发出，纯 DDL 在 autocommit 下直接执行。
    于是一个多语句步骤中途失败会留下「结构改了、版本没记」：下次启动重试它，
    撞上「表已存在」而永久失败。这个用例就是钉这一点。"""
    Base.metadata.create_all(clean_db)
    monkeypatch.setattr(
        migrations,
        "MIGRATIONS",
        (_step(1, "半截", "CREATE TABLE _probe (x INTEGER)", "THIS IS NOT SQL"),),
    )

    with pytest.raises(Exception, match="迁移 v1"):
        db_session.run_migrations(clean_db)

    assert "_probe" not in inspect(clean_db).get_table_names()
    with clean_db.connect() as conn:
        assert conn.exec_driver_sql("SELECT MAX(version) FROM schema_migration").fetchone() == (0,)


def test_steps_run_in_version_order(clean_db, monkeypatch):
    """后一条依赖前一条建的表 —— 顺序反了就当场炸。"""
    Base.metadata.create_all(clean_db)
    monkeypatch.setattr(
        migrations,
        "MIGRATIONS",
        (
            _step(1, "建表", "CREATE TABLE _probe (x INTEGER)"),
            _step(2, "写一行", "INSERT INTO _probe (x) VALUES (42)"),
        ),
    )

    db_session.run_migrations(clean_db)

    with clean_db.connect() as conn:
        assert conn.exec_driver_sql("SELECT x FROM _probe").fetchall() == [(42,)]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_migration_runner.py -v`
Expected: FAIL —— `AttributeError: module 'app.db.session' has no attribute 'is_fresh_database'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/db/session.py`：顶部补导入

```python
import datetime as dt
```

在 `SessionLocal` 之后、`init_db` 之前加：

```python
_MIGRATION_DDL = """
CREATE TABLE IF NOT EXISTS schema_migration (
    version    INTEGER PRIMARY KEY,
    note       TEXT NOT NULL DEFAULT '',
    applied_at TEXT NOT NULL
)
"""


def _ensure_migration_table(conn) -> None:
    conn.exec_driver_sql(_MIGRATION_DDL)


def _applied_version(conn) -> int | None:
    row = conn.exec_driver_sql("SELECT MAX(version) FROM schema_migration").fetchone()
    return row[0] if row and row[0] is not None else None


def _stamp(conn, version: int, note: str) -> None:
    conn.exec_driver_sql(
        "INSERT INTO schema_migration (version, note, applied_at) VALUES (?, ?, ?)",
        (version, note, dt.datetime.now(dt.timezone.utc).isoformat()),
    )


def is_fresh_database(engine) -> bool:
    """库里**一张业务表都没有**即为全新库。

    排除 sqlite_ 内部表与 schema_migration —— 后者是基础设施，只跑过 runner
    的空库仍算全新，否则它会被误判成存量库、去跑一堆改不存在的表的迁移。
    """
    with engine.connect() as conn:
        row = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name <> 'schema_migration'"
        ).fetchone()
    return not (row and row[0])


def run_migrations(engine) -> None:
    """存量库的迁移路径：建表 → 盖章 → （有步骤时）备份 → 按序执行。

    失败一律向上抛，不吞 —— 半迁移的库比起不来的应用危险得多。每步一个事务，
    所以失败的那步不会被记成已执行，下次启动会重试它。
    """
    with engine.begin() as conn:
        _ensure_migration_table(conn)
        applied = _applied_version(conn)
        if applied is None:
            # 有业务表才走得到这里（全新库由 init_db 直接建表并盖最新版本），
            # 所以这一条就是「迁移框架引入之前建的库」。
            _stamp(conn, migrations.BASELINE_VERSION, "基线（迁移框架引入时的库结构）")
            applied = migrations.BASELINE_VERSION

    todo = migrations.pending(applied)
    if not todo:
        return

    for step in todo:
        # **不能用 engine.begin()**：SQLAlchemy 的 pysqlite 走 legacy 事务控制，
        # 真的 BEGIN 只在第一条 DML 之前发出，而**纯 DDL 在 autocommit 下直接
        # 执行** —— 于是 engine.begin() 的回滚回不到它。一步里多条语句、靠前的
        # DDL 成功而靠后的失败时（`ALTER TABLE ADD COLUMN` + `UPDATE` 回填就是
        # 最经典的形状），会留下「结构改了、版本没记」的半迁移状态，下次启动
        # 在「表已存在」上永久失败，要人工介入作者的库。
        # 所以这里自己开事务：AUTOCOMMIT 让 SQLAlchemy 不发它自己的 BEGIN，
        # 手写的 BEGIN/COMMIT 才能真正生效。
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.exec_driver_sql("BEGIN")
            try:
                for sql in step.statements:
                    conn.exec_driver_sql(sql)
                _stamp(conn, step.version, step.note)
            except Exception as exc:
                conn.exec_driver_sql("ROLLBACK")
                # 带上版本号与说明：不然作者看到的是一个不带上下文的
                # OperationalError，不知道是哪一步炸的。
                raise RuntimeError(f"迁移 v{step.version}（{step.note}）执行失败：{exc}") from exc
            conn.exec_driver_sql("COMMIT")
```

并在该文件顶部导入 `migrations`：

```python
from app.db import migrations
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_migration_runner.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/session.py backend/tests/test_migration_runner.py
git commit -m "feat(db): 迁移 runner —— 盖章、按序执行、失败不记账"
```

---

### Task 3: 执行迁移前的自动备份

**Files:**
- Modify: `backend/app/db/session.py`
- Test: `backend/tests/test_migration_runner.py`（追加）

**Interfaces:**
- Consumes: `config.db_path()` / `config.data_dir()`、`run_migrations`（Task 2）
- Produces: `backup_database_before(target_version: int) -> Path | None`（返回备份目录，没备份时返回 `None`）

- [ ] **Step 1: Write the failing test**

追加到 `backend/tests/test_migration_runner.py`：

```python
def test_a_pending_step_backs_up_the_database_first(clean_db, monkeypatch):
    """单机单人，稿子就在这一个文件里；改表失败是不可接受的风险。"""
    Base.metadata.create_all(clean_db)
    monkeypatch.setattr(
        migrations, "MIGRATIONS", (_step(1, "探针", "CREATE TABLE _probe (x INTEGER)"),)
    )

    db_session.run_migrations(clean_db)

    backups = config.data_dir() / "backups"
    made = list(backups.glob("pre-migration-v1-*"))
    assert len(made) == 1
    assert (made[0] / "storyforge.db").exists()


def test_no_pending_step_means_no_backup(clean_db):
    """空跑不该产生垃圾 —— 每次启动都备份会把数据目录塞满。"""
    Base.metadata.create_all(clean_db)

    db_session.run_migrations(clean_db)

    assert not (config.data_dir() / "backups").exists()


def test_backup_records_the_target_version(clean_db, monkeypatch):
    """目录名带目标版本，出事时一眼看得出「这次升级到哪一步」。"""
    Base.metadata.create_all(clean_db)
    monkeypatch.setattr(
        migrations,
        "MIGRATIONS",
        (
            _step(1, "甲", "CREATE TABLE _a (x INTEGER)"),
            _step(2, "乙", "CREATE TABLE _b (x INTEGER)"),
        ),
    )

    db_session.run_migrations(clean_db)

    assert list((config.data_dir() / "backups").glob("pre-migration-v2-*"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_migration_runner.py -v -k backup`
Expected: FAIL —— 备份目录不存在

- [ ] **Step 3: Write minimal implementation**

`backend/app/db/session.py`：顶部补 `import shutil` 与 `from pathlib import Path`。

在 `run_migrations` 之前加：

```python
def backup_database_before(target_version: int) -> Path | None:
    """把整库复制到 backups/pre-migration-v<目标版本>-<时间戳>/。

    只在真有步骤要执行时才调用 —— 每次启动都备份会把数据目录塞满。
    连同 -wal / -shm 一起复制：只拷主文件会丢掉尚未落盘的那部分改动。
    """
    source = config.db_path()
    if not source.exists():
        return None  # 全新库没什么可备份的

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = config.data_dir() / "backups" / f"pre-migration-v{target_version}-{stamp}"
    target.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        current = source.with_name(source.name + suffix)
        if current.exists():
            shutil.copy2(current, target / current.name)
    return target
```

并把 `run_migrations` 里这句

```python
    todo = migrations.pending(applied)
    if not todo:
        return
```

改成

```python
    todo = migrations.pending(applied)
    if not todo:
        return

    backup_database_before(todo[-1].version)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_migration_runner.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/session.py backend/tests/test_migration_runner.py
git commit -m "feat(db): 执行迁移前自动备份数据库"
```

---

### Task 4: init_db 按「全新库 / 存量库」分派

**Files:**
- Modify: `backend/app/db/session.py`（`init_db`）
- Test: `backend/tests/test_migration_runner.py`（追加）

**Interfaces:**
- Consumes: `is_fresh_database` / `run_migrations`（Task 2）
- Produces: `init_db()` —— 全新库：建表 + 盖 `migrations.latest_version()`；存量库：跑迁移 + 建缺的表

- [ ] **Step 1: Write the failing test**

追加到 `backend/tests/test_migration_runner.py`：

```python
def test_a_fresh_database_is_stamped_at_the_latest_version(clean_db, monkeypatch):
    """全新库是由**当前模型**建出来的，它天然就是最新结构 —— 盖最新版本，
    不假装要从头跑一遍历史迁移。"""
    monkeypatch.setattr(
        migrations,
        "MIGRATIONS",
        (
            _step(1, "甲", "CREATE TABLE _a (x INTEGER)"),
            _step(2, "乙", "SELECT 2"),
        ),
    )

    db_session.init_db()

    with clean_db.connect() as conn:
        assert conn.exec_driver_sql("SELECT version FROM schema_migration").fetchall() == [(2,)]


def test_a_fresh_database_does_not_run_historical_migrations_at_all(clean_db, monkeypatch):
    """用一条**会炸**的迁移钉住这一点：全新库若真去跑它，这里就红了。

    这不是刁难 —— 历史迁移改的表，在全新库里本来就还不存在（那些表要等
    create_all 建）。让全新库跑历史迁移，它必然炸。
    """
    monkeypatch.setattr(migrations, "MIGRATIONS", (_step(1, "会炸的", "THIS IS NOT SQL"),))

    db_session.init_db()

    assert "_probe" not in inspect(clean_db).get_table_names()
    assert "project" in inspect(clean_db).get_table_names()


def test_an_existing_database_runs_its_pending_migrations(clean_db, monkeypatch):
    """存量库反过来：它停在引入时的结构，必须把历史迁移补上。"""
    Base.metadata.create_all(clean_db)
    monkeypatch.setattr(
        migrations, "MIGRATIONS", (_step(1, "探针", "CREATE TABLE _probe (x INTEGER)"),)
    )

    db_session.init_db()

    assert "_probe" in inspect(clean_db).get_table_names()
```

> 注意：这两条测试调的是 `db_session.init_db()`（不接受参数，内部用模块级 `engine`），而 `clean_db` 夹具清的也是同一个 `engine` —— 两者指向同一个库，所以断言成立。

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_migration_runner.py -v -k "fresh or existing"`
Expected: FAIL —— 全新库那条会因为跑了会炸的迁移而抛错

- [ ] **Step 3: Write minimal implementation**

`backend/app/db/session.py`，把 `init_db` 换成：

```python
def init_db() -> None:
    from app.db import models  # noqa: F401  确保所有模型已注册到 metadata

    if is_fresh_database(engine):
        # 全新库：模型就是最新结构。它天然处于「所有迁移都已应用」的状态 ——
        # 盖最新版本，不假装要从头跑一遍历史迁移（那些迁移改的表，此刻还不
        # 存在，跑必然炸）。
        with engine.begin() as conn:
            _ensure_migration_table(conn)
            _stamp(conn, migrations.latest_version(), "全新库")
        Base.metadata.create_all(engine)
        return

    # 存量库：先补已有的表，再让模型建新加的表 —— 迁移不建表。
    run_migrations(engine)
    Base.metadata.create_all(engine)
```

> 注意：全新库这一支**先盖章、再建表**，这个顺序是刻意的，别对调（本切片收口时的修复波对调过一次，本代码块已随实现同步）。反过来一旦崩在中间，库里会剩下「表是最新结构、却没有迁移记录」—— 下次启动判存量、盖基线 0，等 P1b-2 落地第一条改表的迁移时它会去对一张**已有该列**的表执行 `ALTER`，永久失败、应用起不来。现在的顺序崩在中间只留下「已盖最新版本、表可能不全」，下次启动判存量、补建缺表即可。

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_migration_runner.py tests/test_migrations.py -v`，再跑完整 `uv run pytest`
Expected: 全绿（含既有的 204 条）

- [ ] **Step 5: 在作者的真实的库上启动一次**

这不只是跑测试 —— 你本机的 `storyforge.db` 是**存量库**，它会被这条路真实走一遍。

```bash
cd backend && uv run uvicorn app.main:app --port 8756
```

Expected: 起得来；`%LOCALAPPDATA%\StoryForge\storyforge.db` 里出现 `schema_migration` 表且只有一行 `version=0`；**设定条目、项目、服务商一条不少**。

核对（另开一个终端）：

```bash
cd backend && uv run python -c "
import sqlite3, os
p = os.path.join(os.environ['LOCALAPPDATA'], 'StoryForge', 'storyforge.db')
c = sqlite3.connect(p)
print('迁移记录:', c.execute('select version, note from schema_migration').fetchall())
print('设定条目数:', c.execute('select count(*) from setting_entry').fetchone()[0])
print('服务商数:', c.execute('select count(*) from provider').fetchone()[0])
"
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/db/session.py backend/tests/test_migration_runner.py
git commit -m "feat(db): init_db 按全新库/存量库分派，全新库盖最新版本"
```

---

### Task 5: 契约校验器放过可选字段的 null

**Files:**
- Modify: `backend/app/runtime/schema.py:87-94`
- Test: `backend/tests/test_schema.py`（追加）

**Interfaces:**
- Consumes: 无
- Produces: `validate_json` / `apply_contract` 的行为变化 —— 可选字段的显式 `null` 判为通过；必填字段的 `null` 仍判失败

- [ ] **Step 1: Write the failing test**

追加到 `backend/tests/test_schema.py`。该文件顶部已有 `from app.runtime.schema import apply_contract, extract_json, validate_json`，下方代码直接用即可，只需**再补一行** `from app.agents.roster import DEFAULT_ROSTER`。

```python
from app.agents.roster import DEFAULT_ROSTER


def test_optional_fields_may_be_null():
    """模型把可选字段写成 null 是「这项为空」的常见写法 —— 契约里没有
    nullable 的表达方式，不该让整份 payload 因此降级成纯文本。"""
    parser = next(e for e in DEFAULT_ROSTER if e["key"] == "idea_parser")
    payload = {
        "genre": "悬疑",
        "premise": "p",
        "protagonist_desire": "d",
        "conflict_source": "c",
        "open_questions": [],
        # 以下全是可选字段
        "sub_genre": None,
        "emotional_core": None,
        "tone": None,
        "length_expectation": None,
        "comparable_works": None,
    }

    ok, errors = validate_json(payload, parser["output_schema"])

    assert ok, errors


def test_required_fields_may_not_be_null():
    """必填字段的 null 是真空缺，不是省略 —— 仍要按类型报错。"""
    parser = next(e for e in DEFAULT_ROSTER if e["key"] == "idea_parser")
    payload = {
        "genre": None,  # 必填
        "premise": "p",
        "protagonist_desire": "d",
        "conflict_source": "c",
        "open_questions": [],
    }

    ok, errors = validate_json(payload, parser["output_schema"])

    assert not ok
    assert any("genre" in error for error in errors)


def test_the_worldbuilders_optional_hardness_may_be_null():
    """世界观构建师的非规则类候选会填一个空的硬度 —— 契约把它声明为 string，
    而模型写成 null 是同一件事的另一种写法。"""
    builder = next(e for e in DEFAULT_ROSTER if e["key"] == "worldbuilder")
    payload = {
        "entries": [
            {
                "type": "地理",
                "name": "南滨旧城",
                "summary": "小城",
                "aliases": None,
                "description": None,
                "hardness": None,
            }
        ]
    }

    ok, errors = validate_json(payload, builder["output_schema"])

    assert ok, errors


def test_a_null_inside_an_array_item_is_still_checked():
    """放过的是「可选字段的 null」，不是「数组元素里的 null」—— 那里 null
    不是省略，是一个类型不对的元素。"""
    schema = {
        "type": "object",
        "required": ["items"],
        "properties": {"items": {"type": "array", "items": {"type": "string"}}},
    }

    ok, errors = validate_json({"items": ["甲", None]}, schema)

    assert not ok
    assert any("items[1]" in error for error in errors)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_schema.py -v -k null`
Expected: FAIL —— 前三条会说类型应为 string、实际为 NoneType

- [ ] **Step 3: Write minimal implementation**

`backend/app/runtime/schema.py`，把 `_validate_node` 里的对象分支

```python
    if expected == "object" or isinstance(value, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path} 缺少必填字段 {key}")
        for key, sub_schema in properties.items():
            if key in value:
                _validate_node(value[key], sub_schema, f"{path}.{key}", errors)
```

改成

```python
    if expected == "object" or isinstance(value, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path} 缺少必填字段 {key}")
        for key, sub_schema in properties.items():
            if key not in value:
                continue
            # 可选字段的显式 null 视同「没提供」：模型把「这项为空」写成 null
            # 是常见形态，而契约里没有 nullable 的表达方式。**必填不在此列** ——
            # 那里 null 是真的缺东西，仍要按类型报错。
            if value[key] is None and key not in required:
                continue
            _validate_node(value[key], sub_schema, f"{path}.{key}", errors)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_schema.py -v`，再跑完整 `uv run pytest`
Expected: 全绿（既有的合法/非法用例都不该变红 —— 这次改动只让校验更宽松）

- [ ] **Step 5: Commit**

```bash
git add backend/app/runtime/schema.py backend/tests/test_schema.py
git commit -m "fix(runtime): 契约放过可选字段的 null，必填不受影响"
```

---

### Task 6: 同步工作指引

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: 前五个任务
- Produces: 无（文档）

- [ ] **Step 1: 更新 §7 路线图**

在路线图表里，P1b-1 与 P1b-2 之间插入一行：

```
| **迁移框架与契约容错** | 手写有序迁移步骤 + `schema_migration`；契约放过可选字段的 null | ✅ 完成（2026-10-16） |
```

- [ ] **Step 2: 更新 §7 的阶段记录**

新增一条阶段记录，说清：为什么单独做这一段（两条欠账都属地基、都已发作过）、「迁移永不建表」的取舍、全新库与存量库的分派（以及**为什么全新库要盖最新版本而不是跑历史迁移** —— 这是引导问题，不是偷懒）、失败即拒绝启动、以及契约那条「可选 null 通过、必填 null 失败」的区分。

- [ ] **Step 3: 划掉已兑现的前置**

§7 里把「**没有数据迁移框架**：`init_db()` 用 `create_all`……打包前必须解决」那条改为已解决，并指向本切片的阶段记录。

- [ ] **Step 4: 更新 §8 变更记录**

至少包括：

| 日期 | 变更 | 依据 |
|---|---|---|
| 2026-10-16 | 迁移框架采用**手写有序步骤 + `schema_migration` 版本表**，不引入 alembic | 单机单人、从不回滚；`CLAUDE.md` §9 要求不用重型依赖解决本可手写的问题 |
| 2026-10-16 | **迁移永不建表**：新表归 `create_all`，迁移只改已有的表 | 两套机制职责不重叠、不会互相打架，框架因此只有百来行 |
| 2026-10-16 | **全新库盖 `LATEST_VERSION`，不跑历史迁移**；存量库盖基线后补跑 | 全新库由当前模型建出、天然就是最新结构；让它跑历史迁移必然炸（那些迁移改的表此刻还不存在）—— 这是引导问题，不是偷懒 |
| 2026-10-16 | 契约校验器放过**可选**字段的显式 `null`，**必填**字段的 `null` 仍判失败 | 前者是省略的另一种写法，后者是真空缺；真实模型复验实测未发作，但换模型或换服务商即可能引爆 |

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: 同步迁移框架与契约容错的阶段记录与变更记录"
```

---

## 附：本计划明确不做的事

- **迁移的 downgrade / 回滚** —— 单机单人、从不回滚；真需要时手工写一条反向步骤。
- **自动生成迁移** —— 手写有序步骤的代价，换取零依赖与「执行过什么」有记录。
- **表格重建的通用助手** —— SQLite 改列类型要 12 步重建，等真需要时再写。
- **SQLite FTS5 检索** —— 仍在 P1b-2 之后。
- **`create_all` 的角色变更** —— 它继续负责建新表。
