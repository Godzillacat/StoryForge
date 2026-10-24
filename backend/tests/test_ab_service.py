"""A/B 并排生成：`ab_group` 列、列表过滤，以及服务层的创建 / 采纳 / 丢弃。

前两个用例钉地基：

1. 带 `ab_group` 的分支**不出现在普通分支列表里**（它是一次 A/B 会话的
   临时产物，用完即删，作者不该在分支列表里看到它们）；
2. 存量库跑到 v12 后 `scene_branch` 真的多出 `ab_group` 列 —— 迁移是历史
   记录，冻结的字面量必须在**已有的表**上真能执行。

后面的用例钉生命周期：一次 A/B = 两条带同一个 `ab_group` 的分支；
采纳是 adopt + merge + 删同组，**一个事务**；丢弃一条时另一条保留。

迁移用例用**自己的一次性库**（`tmp_path`），不碰 conftest 的共享 engine：
共享库是整进程共用的，迁移测试留下的 `schema_migration` 会被别的用例的
`init_db` 判成存量库、把改表步骤重放一遍 —— 测试污染会伪装成产品缺陷。
"""

import pytest
from sqlalchemy import create_engine, select

from app.db import migrations
from app.db import session as db_session
from app.db.models import (
    BranchRevision,
    ChangeLog,
    Chapter,
    Project,
    Scene,
    SceneBranch,
    SceneRevision,
    Volume,
)
from app.services import branch_service
from app.text_stats import count_words


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


# ---- 以下：服务层的 A/B 生命周期（Task 2）----


def _branches_of(session, group: str) -> list[SceneBranch]:
    return list(
        session.scalars(select(SceneBranch).where(SceneBranch.ab_group == group))
    )


def test_ab_create_makes_two_branches_in_one_group(session):
    scene = _scene(session)

    created = branch_service.ab_create(session, scene.id)

    a, b = created["branches"]
    # `side` 是并排面板的两栏；`label` 与 GET 一致，是库里的名字。
    assert [item["side"] for item in created["branches"]] == ["A", "B"]
    assert [item["label"] for item in created["branches"]] == ["A/B · A", "A/B · B"]
    rows = [session.get(SceneBranch, item["id"]) for item in created["branches"]]
    # 两条共用一个组号，名字带保留前缀 —— 与作者手建的分支一眼分得开。
    assert {row.ab_group for row in rows} == {created["group"]}
    assert [row.name for row in rows] == ["A/B · A", "A/B · B"]
    # 都从主版正文起步：生成覆盖的是草稿，正文在采纳之前一律不动。
    assert [row.content for row in rows] == ["主版正文。", "主版正文。"]
    # A/B 不进普通分支列表（Task 1 的过滤在这里再走一遍端到端）。
    assert branch_service.list_branches(session, scene.id) == []


def test_ab_create_rejects_a_locked_scene_and_leaves_nothing_behind(session):
    scene = _scene(session)
    scene.locked = True
    session.commit()

    with pytest.raises(ValueError, match="这一场已锁定，不能并排生成"):
        branch_service.ab_create(session, scene.id)

    session.expire_all()
    assert session.scalars(select(SceneBranch)).all() == []


def test_ab_names_step_around_existing_branches(session):
    """命名冲突时追加序号，而不是报错 —— 前缀只避开语义冲突，躲不开重名。"""
    scene = _scene(session)
    branch_service.create_branch(session, scene.id, "A/B · A")

    created = branch_service.ab_create(session, scene.id)

    names = [session.get(SceneBranch, item["id"]).name for item in created["branches"]]
    assert names == ["A/B · A 2", "A/B · B"]
    # 作者手建的那条原样还在，没有被改名或覆盖。
    kept = branch_service.list_branches(session, scene.id)
    assert [row["name"] for row in kept] == ["A/B · A"]


def test_ab_adopt_merges_the_draft_and_discards_the_whole_group(session):
    scene = _scene(session)
    created = branch_service.ab_create(session, scene.id)
    a, b = created["branches"]
    branch_service.save_branch_draft(session, a["id"], "A 的草稿。")
    branch_service.save_branch_draft(session, b["id"], "B 的草稿。")

    out = branch_service.ab_adopt(session, scene.id, a["id"])

    session.expire_all()
    assert out["revision_created"] is True
    assert out["body"] == "A 的草稿。"
    assert out["chars"] == count_words("A 的草稿。")
    assert out["discarded"] == ["A/B · A", "A/B · B"]
    assert session.get(Scene, scene.id).body == "A 的草稿。"
    # 同组两条都不在了：A 已合进正文、B 是落选方案。
    assert session.get(SceneBranch, a["id"]) is None
    assert session.get(SceneBranch, b["id"]) is None
    assert _branches_of(session, created["group"]) == []
    # 分支修订随分支行一起被库级外键级联删掉，不留孤儿。
    assert (
        session.scalars(
            select(BranchRevision).where(BranchRevision.branch_id == a["id"])
        ).all()
        == []
    )
    # 旧主版进修订，来源沿用 `branch`（不新造一种来源）。
    revisions = session.scalars(
        select(SceneRevision).where(SceneRevision.scene_id == scene.id)
    ).all()
    assert [row.source for row in revisions] == ["branch"]
    assert revisions[0].content == "主版正文。"
    # 正文整份替换的那一笔改动历史恰好一条。
    adopts = session.scalars(
        select(ChangeLog).where(
            ChangeLog.target_id == scene.id, ChangeLog.action == "adopt"
        )
    ).all()
    assert len(adopts) == 1
    assert "A/B · A" in adopts[0].summary


def test_ab_adopt_of_an_empty_main_body_creates_no_revision(session):
    scene = _scene(session, body=None)
    created = branch_service.ab_create(session, scene.id)
    a = created["branches"][0]
    branch_service.save_branch_draft(session, a["id"], "第一版草稿。")

    out = branch_service.ab_adopt(session, scene.id, a["id"])

    assert out["revision_created"] is False
    assert session.query(SceneRevision).filter_by(scene_id=scene.id).count() == 0
    assert out["body"] == "第一版草稿。"


def test_ab_adopt_is_rejected_when_the_scene_is_locked(session):
    """采纳时再查一次锁：建 A/B 时没锁、采纳时锁了 —— 拒绝且草稿不动。"""
    scene = _scene(session)
    created = branch_service.ab_create(session, scene.id)
    a = created["branches"][0]
    branch_service.save_branch_draft(session, a["id"], "A 的草稿。")
    scene.locked = True
    session.commit()

    with pytest.raises(ValueError, match="已锁定"):
        branch_service.ab_adopt(session, scene.id, a["id"])

    session.expire_all()
    assert session.get(SceneBranch, a["id"]).draft_content == "A 的草稿。"
    assert session.get(SceneBranch, a["id"]).name == "A/B · A"
    assert session.get(Scene, scene.id).body == "主版正文。"


def test_ab_adopt_rolls_back_when_a_later_step_fails(session, monkeypatch):
    """adopt 已经改过分支，merge 才失败 —— 三步一个事务，前一步必须一起回滚。"""
    scene = _scene(session)
    created = branch_service.ab_create(session, scene.id)
    a = created["branches"][0]
    branch_service.save_branch_draft(session, a["id"], "A 的草稿。")

    def boom(*_args, **_kwargs):
        raise RuntimeError("合并失败")

    monkeypatch.setattr(branch_service, "merge_branch", boom)

    with pytest.raises(RuntimeError, match="合并失败"):
        branch_service.ab_adopt(session, scene.id, a["id"])

    session.expire_all()
    row = session.get(SceneBranch, a["id"])
    # adopt 写下的三样东西（分支正文、清空的草稿、AI 修订）都不该留下。
    assert row.content == "主版正文。"
    assert row.draft_content == "A 的草稿。"
    assert branch_service.list_branch_revisions(session, a["id"]) == []
    assert session.get(Scene, scene.id).body == "主版正文。"


def test_ab_create_rejects_a_second_group_until_the_first_is_resolved(session):
    """一场戏同时只允许一组 A/B：旧组未处理时**明确拒绝**，而不是静默删掉。

    否则旧组会变成刷新后找不回的残留行：普通分支列表过滤 A/B，而
    `GET /scenes/{id}/ab` 只返回最近一组。
    """
    scene = _scene(session)
    first = branch_service.ab_create(session, scene.id)
    a, b = first["branches"]

    with pytest.raises(ValueError, match="还有未处理的 A/B"):
        branch_service.ab_create(session, scene.id)

    # 丢弃一条后另一条还在，组没结束，仍然拒绝。
    branch_service.ab_discard(session, scene.id, a["id"])
    with pytest.raises(ValueError, match="还有未处理的 A/B"):
        branch_service.ab_create(session, scene.id)

    # 两条都丢弃后组结束，可以再建；名字回到不带序号的形式。
    branch_service.ab_discard(session, scene.id, b["id"])
    second = branch_service.ab_create(session, scene.id)
    assert second["group"] != first["group"]
    assert [item["label"] for item in second["branches"]] == ["A/B · A", "A/B · B"]


def test_ab_adopt_rejects_an_empty_side_with_its_own_message(session):
    """A/B 的「还没生成」是作者可重试的状态，不是「没有可采纳的草稿」那种 409。"""
    scene = _scene(session)
    created = branch_service.ab_create(session, scene.id)
    a = created["branches"][0]

    with pytest.raises(ValueError, match="这一版还没有生成内容"):
        branch_service.ab_adopt(session, scene.id, a["id"])

    session.expire_all()
    assert session.get(SceneBranch, a["id"]) is not None
    assert session.get(Scene, scene.id).body == "主版正文。"


def test_ab_adopt_rejects_a_draft_missing_a_locked_paragraph(session):
    """段落锁：A 的草稿缺了锁住的段落 → 拒绝，正文与两条分支都不动。"""
    scene = _scene(session)
    scene.locked_paragraphs_json = ["必须原样保留的段落。"]
    session.commit()
    created = branch_service.ab_create(session, scene.id)
    a, b = created["branches"]
    branch_service.save_branch_draft(session, a["id"], "A 的草稿，但没有锁住的那段。")

    with pytest.raises(ValueError, match="草稿缺少已锁定的段落"):
        branch_service.ab_adopt(session, scene.id, a["id"])

    session.expire_all()
    assert session.get(Scene, scene.id).body == "主版正文。"
    row = session.get(SceneBranch, a["id"])
    assert row is not None
    assert row.draft_content == "A 的草稿，但没有锁住的那段。"
    assert row.content == "主版正文。"
    # 另一条也不受牵连，组还在。
    assert session.get(SceneBranch, b["id"]) is not None
    assert (
        session.scalars(
            select(SceneRevision).where(SceneRevision.scene_id == scene.id)
        ).all()
        == []
    )


def test_ab_discard_removes_one_side_and_keeps_the_other(session):
    scene = _scene(session)
    created = branch_service.ab_create(session, scene.id)
    a, b = created["branches"]

    removed_a = branch_service.ab_discard(session, scene.id, a["id"])

    session.expire_all()
    assert removed_a == {"removed": ["A/B · A"]}
    assert session.get(SceneBranch, a["id"]) is None
    assert session.get(SceneBranch, b["id"]) is not None
    # 剩下的那条还能继续采纳（界面「两版都不要」是连点两次丢弃）。
    assert session.get(SceneBranch, b["id"]).ab_group == created["group"]

    removed_b = branch_service.ab_discard(session, scene.id, b["id"])

    session.expire_all()
    assert removed_b == {"removed": ["A/B · B"]}
    assert _branches_of(session, created["group"]) == []
    assert session.get(Scene, scene.id).body == "主版正文。"


def test_ab_adopt_and_discard_reject_a_regular_branch(session):
    scene = _scene(session)
    row = branch_service.create_branch(session, scene.id, "手建分支")

    with pytest.raises(ValueError, match="这不是 A/B 分支"):
        branch_service.ab_adopt(session, scene.id, row.id)
    with pytest.raises(ValueError, match="这不是 A/B 分支"):
        branch_service.ab_discard(session, scene.id, row.id)

    session.expire_all()
    assert session.get(SceneBranch, row.id) is not None


def test_ab_adopt_and_discard_reject_a_branch_from_another_scene(session):
    scene = _scene(session)
    other = Scene(chapter_id=scene.chapter_id, seq=1, goal="第二场")
    session.add(other)
    session.commit()
    created = branch_service.ab_create(session, other.id)
    branch_id = created["branches"][0]["id"]

    with pytest.raises(ValueError, match="分支不属于这个场景"):
        branch_service.ab_adopt(session, scene.id, branch_id)
    with pytest.raises(ValueError, match="分支不属于这个场景"):
        branch_service.ab_discard(session, scene.id, branch_id)

    session.expire_all()
    assert session.get(SceneBranch, branch_id) is not None


def test_commit_false_defers_the_commit_to_the_caller(session):
    """三个既有函数加上 `commit` 后，`commit=False` 只是把提交时机交出去。"""
    scene = _scene(session)

    row = branch_service.create_branch(session, scene.id, "待提交", commit=False)
    assert session.get(SceneBranch, row.id) is not None  # 已 flush，同一事务里可见
    session.rollback()
    assert session.get(SceneBranch, row.id) is None


def test_adopt_with_commit_false_can_still_be_rolled_back(session):
    scene = _scene(session)
    row = branch_service.create_branch(session, scene.id, "A 案")
    branch_service.save_branch_draft(session, row.id, "草稿。")

    branch_service.adopt_branch_draft(session, row.id, commit=False)
    session.rollback()

    session.expire_all()
    assert session.get(SceneBranch, row.id).draft_content == "草稿。"
    assert session.get(SceneBranch, row.id).content == "主版正文。"
