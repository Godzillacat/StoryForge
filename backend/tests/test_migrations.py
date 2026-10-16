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
