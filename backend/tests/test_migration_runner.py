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


def test_stamping_is_idempotent_when_only_the_migration_table_survives(clean_db):
    """「业务表没了、迁移表还在」的库仍被判为全新 —— `is_fresh_database` 刻意
    不把 `schema_migration` 算作业务表。于是它会被**再盖一次章**，而盖章撞主键
    就是应用启动即失败。幂等盖印章下这个状态的语义反而是对的：`create_all` 刚
    把表建成最新结构，「所有迁移已应用」正是事实。"""
    db_session.init_db()  # 第一次：建表 + 盖章

    Base.metadata.drop_all(clean_db)  # 业务表没了，schema_migration 残留下来

    db_session.init_db()  # 第二次：不该抛

    with clean_db.connect() as conn:
        assert conn.exec_driver_sql("SELECT version FROM schema_migration").fetchall() == [
            (migrations.latest_version(),)
        ]
