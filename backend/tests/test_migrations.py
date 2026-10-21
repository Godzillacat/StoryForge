from app.db import migrations


def test_the_first_real_migration_adds_the_character_columns():
    """框架自建好以来 MIGRATIONS 一直是空的 —— 这是它的第一条。

    只加可空列：SQLite 的 ALTER TABLE ADD COLUMN 对可空列是原地操作，
    作者的存量数据不受影响，也不触发改列类型所需的 12 步重建。"""
    assert [m.version for m in migrations.MIGRATIONS] == [1, 2, 3, 4, 5]

    step = migrations.MIGRATIONS[0]
    assert all(
        statement.startswith("ALTER TABLE setting_entry ADD COLUMN ")
        for statement in step.statements
    )
    assert migrations.latest_version() == 5


def test_the_first_real_migration_is_frozen_history():
    """v1 的列写死、不从 CHARACTER_FIELDS 派生 —— 迁移是历史记录。

    这条断言把冻结的内容钉成字面量：日后要加人物字段，必须**新开一条迁移**，
    而不是改这一条、也不是改那份常量。

    刻意**不**与 CHARACTER_FIELDS 对拍：那是对拍一个可变常量，两边同源、一起变，
    等于同义反复 —— 恰恰是它要防的形状（防的就是「常量长了一项、迁移跟着长」）。
    列与常量的关系改由 test_migration_runner 的 `set(CHARACTER_FIELDS) <= columns`
    在**真实迁移后的库上**验，那里才是这条关系真正成立、也真会分叉的地方。"""
    step = migrations.MIGRATIONS[0]
    assert step.statements == (
        "ALTER TABLE setting_entry ADD COLUMN appearance TEXT",
        "ALTER TABLE setting_entry ADD COLUMN personality TEXT",
        "ALTER TABLE setting_entry ADD COLUMN desire TEXT",
        "ALTER TABLE setting_entry ADD COLUMN fear TEXT",
        "ALTER TABLE setting_entry ADD COLUMN arc_type TEXT",
        "ALTER TABLE setting_entry ADD COLUMN abilities TEXT",
        "ALTER TABLE setting_entry ADD COLUMN speech_style TEXT",
        "ALTER TABLE setting_entry ADD COLUMN current_state TEXT",
    )


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


def test_v4_adds_the_scene_body_column():
    step = migrations.MIGRATIONS[3]
    assert step.statements == ("ALTER TABLE scene ADD COLUMN body TEXT",)


def test_v5_adds_logic_columns_to_audit_issue():
    step = migrations.MIGRATIONS[4]
    assert step.requires == ("audit_issue",)
    assert step.statements == (
        "ALTER TABLE audit_issue ADD COLUMN check_type VARCHAR(20) NOT NULL DEFAULT 'consistency'",
        "ALTER TABLE audit_issue ADD COLUMN layer VARCHAR(30)",
        "ALTER TABLE audit_issue ADD COLUMN stage VARCHAR(10) NOT NULL DEFAULT 'text'",
        "CREATE INDEX ix_audit_issue_scene_check ON audit_issue(scene_id, check_type, stage, status)",
    )


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
