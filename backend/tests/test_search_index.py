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
