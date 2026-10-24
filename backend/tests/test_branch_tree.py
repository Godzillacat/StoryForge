"""分支树：派生、深度、丢弃提升为根，以及迁移 v13。

三条地基：

1. `depth` 由服务层沿父链算（根 = 1），列表与详情两条路径都要填；
2. 派生复制父分支正文，最多三层，父必须同场景且不是 A/B 临时分支；
3. 丢弃父分支时子分支**提升为根**（`parent_branch_id` 置空），不级联删。

迁移用例用**自己的一次性库**（`tmp_path`）：共享库是整进程共用的，迁移
留下的 `schema_migration` 会被别的用例的 `init_db` 判成存量库、把改表步骤
重放一遍 —— 测试污染会伪装成产品缺陷（沿用 `test_ab_service` 的做法）。
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, update

from app.db import migrations
from app.db import session as db_session
from app.db.models import Chapter, Project, Scene, SceneBranch, Volume
from app.services import branch_service


def _seed_scene(session, *, body: str | None = "主版正文。"):
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


@pytest.fixture()
def scene_with_branches(session):
    """一棵三层树：根一 → 二层 → 三层，另有独立的根二。"""
    scene = _seed_scene(session)
    root1 = branch_service.create_branch(session, scene.id, "根一")
    root2 = branch_service.create_branch(session, scene.id, "根二")
    level2 = branch_service.create_branch(session, scene.id, "二层", parent_id=root1.id)
    level3 = branch_service.create_branch(
        session, scene.id, "三层", parent_id=level2.id
    )
    return SimpleNamespace(
        scene=scene,
        root1=root1,
        root2=root2,
        level2=level2,
        level3=level3,
    )


# ---- 深度 ----


def test_depth_is_one_for_roots(session, scene_with_branches):
    tree = scene_with_branches

    rows = branch_service.list_branches(session, tree.scene.id)

    assert [row["depth"] for row in rows if row["parent_id"] is None] == [1, 1]


def test_depth_counts_every_level(session, scene_with_branches):
    tree = scene_with_branches

    rows = {row["id"]: row for row in branch_service.list_branches(session, tree.scene.id)}

    assert rows[tree.root1.id]["depth"] == 1
    assert rows[tree.root2.id]["depth"] == 1
    assert rows[tree.level2.id]["depth"] == 2
    assert rows[tree.level3.id]["depth"] == 3
    assert rows[tree.root1.id]["parent_id"] is None
    assert rows[tree.level2.id]["parent_id"] == tree.root1.id
    assert rows[tree.level3.id]["parent_id"] == tree.level2.id
    # 单条详情也要填 —— 写作台选中一条分支时读的是这条路径。
    detail = branch_service.get_branch(session, tree.level3.id)
    assert detail["parent_id"] == tree.level2.id
    assert detail["depth"] == 3


def test_a_fourth_level_is_rejected(session, scene_with_branches):
    tree = scene_with_branches

    with pytest.raises(ValueError, match="最多三层"):
        branch_service.create_branch(
            session, tree.scene.id, "四层", parent_id=tree.level3.id
        )


def test_a_third_level_is_allowed_under_a_level_two_parent(session, scene_with_branches):
    """深 2 的父允许派生（新分支深 3）。「最多三层」拦的是第四层。"""
    tree = scene_with_branches

    created = branch_service.create_branch(
        session, tree.scene.id, "三层之二", parent_id=tree.level2.id
    )

    detail = branch_service.get_branch(session, created.id)
    assert detail["depth"] == 3
    assert detail["parent_id"] == tree.level2.id


def test_cycles_in_dirty_data_do_not_hang(session):
    """正常接口建不出环；手工改库能。脏数据不该让列表接口转不出来。"""
    scene = _seed_scene(session)
    a = branch_service.create_branch(session, scene.id, "甲")
    b = branch_service.create_branch(session, scene.id, "乙", parent_id=a.id)
    # 根接回自己的孙子：a → b → a。
    session.execute(
        update(SceneBranch)
        .where(SceneBranch.id == a.id)
        .values(parent_branch_id=b.id)
    )
    session.commit()

    depths = {
        row["id"]: row["depth"] for row in branch_service.list_branches(session, scene.id)
    }

    # 环上没有合法的根，按 1 处理：不死循环、不给出越界的深度。
    assert depths == {a.id: 1, b.id: 1}


# ---- 派生 ----


def test_a_derived_branch_copies_the_parent_body(session):
    scene = _seed_scene(session)
    parent = branch_service.create_branch(session, scene.id, "父")
    branch_service.save_branch_body(session, parent.id, "父分支的正文。")

    created = branch_service.create_branch(
        session, scene.id, "子", parent_id=parent.id
    )

    detail = branch_service.get_branch(session, created.id)
    assert detail["content"] == "父分支的正文。"
    assert detail["parent_id"] == parent.id
    assert detail["depth"] == 2
    # 没有显式 note 时默认记下它从哪来 —— 树里迟早要显示这句。
    assert detail["note"] == "派生自 父"


def test_a_derived_branch_of_an_empty_parent_starts_empty(session):
    scene = _seed_scene(session, body=None)
    parent = branch_service.create_branch(session, scene.id, "父")

    created = branch_service.create_branch(
        session, scene.id, "子", parent_id=parent.id
    )

    assert branch_service.get_branch(session, created.id)["content"] == ""


def test_an_explicit_note_wins_over_the_default(session):
    scene = _seed_scene(session)
    parent = branch_service.create_branch(session, scene.id, "父")

    created = branch_service.create_branch(
        session, scene.id, "子", note="换个写法", parent_id=parent.id
    )

    assert branch_service.get_branch(session, created.id)["note"] == "换个写法"


def test_a_parent_from_another_scene_is_not_found(session):
    scene = _seed_scene(session)
    other = Scene(chapter_id=scene.chapter_id, seq=1, goal="第二场")
    session.add(other)
    session.commit()
    foreign = branch_service.create_branch(session, other.id, "别场的分支")

    with pytest.raises(ValueError, match="分支不存在"):
        branch_service.create_branch(
            session, scene.id, "派生", parent_id=foreign.id
        )


def test_an_unknown_parent_is_not_found(session):
    scene = _seed_scene(session)

    with pytest.raises(ValueError, match="分支不存在"):
        branch_service.create_branch(session, scene.id, "派生", parent_id="nope")


def test_an_ab_branch_cannot_be_a_parent(session):
    scene = _seed_scene(session)
    created = branch_service.ab_create(session, scene.id)

    with pytest.raises(ValueError, match="A/B 分支不能作为派生起点"):
        branch_service.create_branch(
            session, scene.id, "派生", parent_id=created["branches"][0]["id"]
        )


# ---- 丢弃 ----


def test_child_promoted_when_parent_discarded(session, scene_with_branches):
    tree = scene_with_branches
    branch_service.save_branch_body(session, tree.level3.id, "三层自己的正文。")
    branch_service.save_branch_draft(session, tree.level3.id, "三层自己的草稿。")

    branch_service.discard_branch(session, tree.level2.id)

    child = branch_service.get_branch(session, tree.level3.id)
    assert child["parent_id"] is None
    assert child["depth"] == 1
    # 提升只动关系，不动子分支的正文与草稿 —— 那是作者写过的内容。
    assert child["content"] == "三层自己的正文。"
    assert child["draft"]["content"] == "三层自己的草稿。"


def test_discarding_a_leaf_keeps_the_rest_of_the_tree(session, scene_with_branches):
    tree = scene_with_branches

    branch_service.discard_branch(session, tree.level3.id)

    rows = {row["id"]: row for row in branch_service.list_branches(session, tree.scene.id)}
    assert set(rows) == {tree.root1.id, tree.root2.id, tree.level2.id}
    assert rows[tree.level2.id]["depth"] == 2


def test_discarding_an_ab_branch_does_not_touch_the_tree(session):
    """A/B 丢弃直接删行，不走提升逻辑；它不该顺手改到普通分支的父指针。"""
    scene = _seed_scene(session)
    parent = branch_service.create_branch(session, scene.id, "父")
    child = branch_service.create_branch(session, scene.id, "子", parent_id=parent.id)
    created = branch_service.ab_create(session, scene.id)

    branch_service.ab_discard(session, scene.id, created["branches"][0]["id"])

    detail = branch_service.get_branch(session, child.id)
    assert detail["parent_id"] == parent.id
    assert detail["depth"] == 2


# ---- 迁移 v13 ----


def test_v13_is_frozen_history():
    """v13 的语句写死成字面量、只加可空列，`requires` 指向它真正要改的表。

    刻意不与任何常量对拍 —— 迁移一旦在作者的库上跑过就是既成事实，
    日后加列只能新开一条迁移。
    """
    step = next(m for m in migrations.MIGRATIONS if m.version == 13)

    assert step.requires == ("scene_branch",)
    assert step.statements == (
        "ALTER TABLE scene_branch ADD COLUMN parent_branch_id TEXT",
    )


def test_migration_13_adds_parent_branch_id_to_an_existing_database(tmp_path):
    """存量库（已盖到 v12）跑到 v13 后补出这一列，旧分支一律是根。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as conn:
        # v13 之前的 scene_branch：没有 parent_branch_id。
        conn.exec_driver_sql(
            "CREATE TABLE scene_branch ("
            " id VARCHAR(36) PRIMARY KEY,"
            " scene_id VARCHAR(36) NOT NULL,"
            " name VARCHAR(120) NOT NULL,"
            " content TEXT, draft_content TEXT, draft_run_id VARCHAR(36),"
            " note TEXT, ab_group TEXT,"
            " created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL)"
        )
        conn.exec_driver_sql(
            "INSERT INTO scene_branch"
            " (id, scene_id, name, content, draft_content, draft_run_id, note,"
            "  ab_group, created_at, updated_at)"
            " VALUES ('b1', 's1', '旧分支', '旧正文。', '', NULL, '', NULL,"
            "  '2026-10-23', '2026-10-23')"
        )
        db_session._ensure_migration_table(conn)
        conn.exec_driver_sql(
            "INSERT INTO schema_migration (version, note, applied_at)"
            " VALUES (12, 'test', '2026-10-24')"
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
                "SELECT name, content, parent_branch_id FROM scene_branch WHERE id = 'b1'"
            ).fetchone()

        assert "parent_branch_id" in columns
        assert versions.count(13) == 1
        # 旧分支没有父 —— 它们全是根，这正是可空列的默认语义，不回填。
        assert legacy == ("旧分支", "旧正文。", None)

        # 再跑一次不重复执行：版本表里 v13 仍只有一行。
        db_session.run_migrations(engine)
        with engine.connect() as conn:
            versions = [
                row[0]
                for row in conn.exec_driver_sql(
                    "SELECT version FROM schema_migration ORDER BY version"
                )
            ]
    finally:
        engine.dispose()

    assert versions.count(13) == 1


# ---- 接口：body 的 parent_id 与错误映射 ----


def _api_scene(client, goal: str = "开场"):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "第一卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "第一章"}
    ).json()
    scene = client.post(
        f"/api/chapters/{chapter['id']}/scenes", json={"goal": goal}
    ).json()
    client.put(f"/api/scenes/{scene['id']}/body", json={"content": "主版正文。"})
    return scene


def test_api_deriving_from_a_parent(client):
    scene = _api_scene(client)
    root = client.post(
        f"/api/scenes/{scene['id']}/branches", json={"name": "根"}
    ).json()

    created = client.post(
        f"/api/scenes/{scene['id']}/branches",
        json={"name": "子", "parent_id": root["id"]},
    )

    assert created.status_code == 201
    body = created.json()
    assert body["parent_id"] == root["id"]
    assert body["depth"] == 2
    assert body["content"] == "主版正文。"
    listed = client.get(f"/api/scenes/{scene['id']}/branches").json()
    assert {row["id"]: row["depth"] for row in listed}[body["id"]] == 2


def test_api_parent_from_another_scene_is_404(client):
    scene = _api_scene(client)
    other = _api_scene(client, goal="第二场")
    foreign = client.post(
        f"/api/scenes/{other['id']}/branches", json={"name": "别场"}
    ).json()

    response = client.post(
        f"/api/scenes/{scene['id']}/branches",
        json={"name": "派生", "parent_id": foreign["id"]},
    )

    assert response.status_code == 404
    assert response.json()["detail"].startswith("分支不存在")


def test_api_ab_parent_is_400(client):
    scene = _api_scene(client)
    ab = client.post(f"/api/scenes/{scene['id']}/ab").json()

    response = client.post(
        f"/api/scenes/{scene['id']}/branches",
        json={"name": "派生", "parent_id": ab["branches"][0]["id"]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "A/B 分支不能作为派生起点"


def test_api_fourth_level_is_400(client):
    scene = _api_scene(client)
    level1 = client.post(
        f"/api/scenes/{scene['id']}/branches", json={"name": "一"}
    ).json()
    level2 = client.post(
        f"/api/scenes/{scene['id']}/branches",
        json={"name": "二", "parent_id": level1["id"]},
    ).json()
    level3 = client.post(
        f"/api/scenes/{scene['id']}/branches",
        json={"name": "三", "parent_id": level2["id"]},
    ).json()

    response = client.post(
        f"/api/scenes/{scene['id']}/branches",
        json={"name": "四", "parent_id": level3["id"]},
    )

    assert response.status_code == 400
    assert "最多三层" in response.json()["detail"]
