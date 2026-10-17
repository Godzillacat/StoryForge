from app.db import migrations
from app.world_types import CHARACTER_FIELDS


def test_the_first_real_migration_adds_the_character_columns():
    """框架自建好以来 MIGRATIONS 一直是空的 —— 这是它的第一条。

    只加可空列：SQLite 的 ALTER TABLE ADD COLUMN 对可空列是原地操作，
    作者的存量数据不受影响，也不触发改列类型所需的 12 步重建。"""
    assert [m.version for m in migrations.MIGRATIONS] == [1]

    step = migrations.MIGRATIONS[0]
    assert set(CHARACTER_FIELDS) == {
        statement.split("ADD COLUMN ")[1].split()[0] for statement in step.statements
    }
    assert all(
        statement.startswith("ALTER TABLE setting_entry ADD COLUMN ")
        for statement in step.statements
    )
    assert migrations.latest_version() == 1


def test_schema_migration_baseline_still_zero():
    assert migrations.BASELINE_VERSION == 0


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
