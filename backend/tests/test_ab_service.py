"""A/B 并排生成的地基：`ab_group` 列与普通分支列表的过滤（迁移 v12）。

本任务只钉两件事：

1. 带 `ab_group` 的分支**不出现在普通分支列表里**（它是一次 A/B 会话的
   临时产物，用完即删，作者不该在分支列表里看到它们）；
2. 存量库跑到 v12 后 `scene_branch` 真的多出 `ab_group` 列 —— 迁移是历史
   记录，冻结的字面量必须在**已有的表**上真能执行。

迁移用例用**自己的一次性库**（`tmp_path`），不碰 conftest 的共享 engine：
共享库是整进程共用的，迁移测试留下的 `schema_migration` 会被别的用例的
`init_db` 判成存量库、把改表步骤重放一遍 —— 测试污染会伪装成产品缺陷。
"""

from sqlalchemy import create_engine

from app.db import migrations
from app.db import session as db_session
from app.db.models import Chapter, Project, Scene, SceneBranch, Volume
from app.services import branch_service


def _scene(session, body: str = "主版正文。"):
    """与既有分支测试同一套最小结构：项目 → 卷 → 章 → 场景。"""
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    volume = Volume(project_id=project.id, seq=0, name="第一卷")
    session.add(volume)
    session.commit()
    chapter = Chapter(volume_id=volume.id, seq=0, title="第一章")
    session.add(chapter)
    session.commit()
    scene = Scene(chapter_id=chapter.id, seq=0, goal="开场", body=body)
    session.add(scene)
    session.commit()
    return scene


def test_ab_branches_are_hidden_from_the_regular_list(session):
    scene = _scene(session)

    a = branch_service.create_branch(session, scene.id, "A")
    a.ab_group = "g1"
    session.commit()
    b = branch_service.create_branch(session, scene.id, "B")
    b.ab_group = "g1"
    session.commit()
    branch_service.create_branch(session, scene.id, "普通分支")

    names = [row["name"] for row in branch_service.list_branches(session, scene.id)]

    assert names == ["普通分支"]
    # 过滤只发生在列表上：A/B 两行仍在库里，A/B 会话还要用它们生成与采纳。
    assert session.get(SceneBranch, a.id) is not None
    assert session.get(SceneBranch, b.id) is not None


def test_v12_is_frozen_history():
    """v12 的语句写死成字面量、只加可空列，`requires` 指向它真正要改的表。

    刻意不与任何常量 / 计划里的字符串拼接对拍 —— 迁移一旦在作者的库上跑过
    就是既成事实，日后加列只能新开一条迁移，不能改这一条。
    """
    step = next(m for m in migrations.MIGRATIONS if m.version == 12)

    assert step.requires == ("scene_branch",)
    assert step.statements == ("ALTER TABLE scene_branch ADD COLUMN ab_group TEXT",)


def test_migration_12_adds_ab_group_to_an_existing_database(tmp_path):
    """存量库（已盖到 v11）跑到 v12 后，`scene_branch` 有 `ab_group` 且旧数据还在。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as conn:
        # v12 之前的 scene_branch：没有 ab_group。
        conn.exec_driver_sql(
            "CREATE TABLE scene_branch ("
            " id VARCHAR(36) PRIMARY KEY,"
            " scene_id VARCHAR(36) NOT NULL,"
            " name VARCHAR(120) NOT NULL,"
            " content TEXT, draft_content TEXT, draft_run_id VARCHAR(36),"
            " note TEXT,"
            " created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL)"
        )
        conn.exec_driver_sql(
            "INSERT INTO scene_branch"
            " (id, scene_id, name, content, draft_content, draft_run_id, note,"
            "  created_at, updated_at)"
            " VALUES ('b1', 's1', '旧分支', '旧正文。', '', NULL, '',"
            "  '2026-10-23', '2026-10-23')"
        )
        db_session._ensure_migration_table(conn)
        conn.exec_driver_sql(
            "INSERT INTO schema_migration (version, note, applied_at)"
            " VALUES (11, 'test', '2026-10-24')"
        )

    try:
        db_session.run_migrations(engine)

        with engine.connect() as conn:
            columns = {
                row[1] for row in conn.exec_driver_sql("PRAGMA table_info(scene_branch)")
            }
            versions = [
                row[0]
                for row in conn.exec_driver_sql(
                    "SELECT version FROM schema_migration ORDER BY version"
                )
            ]
            legacy = conn.exec_driver_sql(
                "SELECT name, content, ab_group FROM scene_branch WHERE id = 'b1'"
            ).fetchone()
    finally:
        engine.dispose()

    assert "ab_group" in columns
    assert 12 in versions
    # 新列对存量行是 NULL（不是空串、不是默认分组），旧数据一个字没动。
    assert legacy == ("旧分支", "旧正文。", None)
