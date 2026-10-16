from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app import config
from app.db import migrations
from app.db.base import Base

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


def init_db() -> None:
    from app.db import models  # noqa: F401  确保所有模型已注册到 metadata

    Base.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
