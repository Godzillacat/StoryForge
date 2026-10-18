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
