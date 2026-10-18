from __future__ import annotations

import datetime as dt
import shutil
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app import config
from app.db import migrations
from app.db.base import Base
from app.db.search import ensure_search_index

engine = create_engine(
    f"sqlite:///{config.db_path()}",
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_connection, _record) -> None:
    # WAL 让读写并发不互相阻塞；外键约束 SQLite 默认关闭，必须显式打开
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


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
    """幂等盖章 —— 同一版本盖第二次只是把备注与时间刷新一遍。

    **必须幂等。** `is_fresh_database` 不把 `schema_migration` 算作业务表，于是
    「业务表被删、迁移表残留」的库会被判为全新、再盖一次章；普通 INSERT 会在这
    撞上主键，表现为**应用启动即失败**。而那个状态下幂等的语义恰恰是对的 ——
    `create_all` 刚把表建成最新结构，「所有迁移已应用」就是事实。
    """
    conn.exec_driver_sql(
        "INSERT OR REPLACE INTO schema_migration (version, note, applied_at) VALUES (?, ?, ?)",
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

    backup_database_before(todo[-1].version)

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


def init_db() -> None:
    from app.db import models  # noqa: F401  确保所有模型已注册到 metadata

    if is_fresh_database(engine):
        # 全新库：模型就是最新结构。它天然处于「所有迁移都已应用」的状态 ——
        # 盖最新版本，不假装要从头跑一遍历史迁移（那些迁移改的表，此刻还不
        # 存在，跑必然炸）。
        #
        # **先盖章、再建表**，这个顺序是刻意的。反过来（先建表、后盖章）一旦
        # 崩在中间（进程被杀、磁盘满、盖章本身抛错），库里会剩下「表是最新
        # 结构、却没有迁移记录」：下次启动 `is_fresh_database` 判存量、盖基线
        # 0，于是当 P1b-2 真加进第一条改表的迁移时，它会去对一张**已有该列**
        # 的表执行 ALTER —— 永久失败、应用拒绝启动，要人工介入作者的库。
        # 现在这个顺序崩在中间只留下「已盖最新版本、表可能不全」：下次启动判
        # 存量、pending 为空、create_all 补建缺表，能自愈。
        with engine.begin() as conn:
            _ensure_migration_table(conn)
            _stamp(conn, migrations.latest_version(), "全新库")
        Base.metadata.create_all(engine)
        ensure_search_index(engine)
        return

    # 存量库：先补已有的表，再让模型建新加的表 —— 迁移不建表。
    run_migrations(engine)
    Base.metadata.create_all(engine)
    ensure_search_index(engine)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
