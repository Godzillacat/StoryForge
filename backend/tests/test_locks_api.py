"""锁定接口与段落锁。"""

from app.db.models import Chapter, Project, Scene, SceneDraft, SettingEntry, Volume
from app.db.session import SessionLocal


def _add_draft(scene_id: str, content: str) -> None:
    """草稿由生成路径创建；这里直接插一条，只为走到采纳那一步。"""
    with SessionLocal() as session:
        session.add(SceneDraft(scene_id=scene_id, content=content))
        session.commit()


def _tree(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "第一卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "第一章"}
    ).json()
    scene = client.post(
        f"/api/chapters/{chapter['id']}/scenes", json={"goal": "开场"}
    ).json()
    entry = client.post(
        f"/api/projects/{project['id']}/entries",
        json={"type": "character", "name": "沈砚"},
    ).json()
    return project, volume, chapter, scene, entry


def test_lock_targets_are_published(client):
    body = client.get("/api/lock-targets").json()

    assert [item["key"] for item in body["targets"]] == [
        "architecture",
        "entry",
        "volume",
        "chapter",
        "scene",
    ]


def test_lock_round_trips_for_each_target_type(client):
    _project, volume, chapter, scene, entry = _tree(client)

    for kind, target_id in (
        ("volume", volume["id"]),
        ("chapter", chapter["id"]),
        ("scene", scene["id"]),
        ("entry", entry["id"]),
    ):
        locked = client.patch(f"/api/locks/{kind}/{target_id}", json={"locked": True})
        assert locked.status_code == 200
        assert locked.json()["own_locked"] is True

        unlocked = client.patch(f"/api/locks/{kind}/{target_id}", json={"locked": False})
        assert unlocked.json()["own_locked"] is False


def test_a_locked_volume_shows_up_as_locked_on_its_scene(client):
    _project, volume, _chapter, scene, _entry = _tree(client)
    client.patch(f"/api/locks/volume/{volume['id']}", json={"locked": True})

    state = client.get(f"/api/locks/scene/{scene['id']}").json()

    assert state["locked"] is True
    assert state["own_locked"] is False
    assert state["source"] == "volume"


def test_an_unknown_target_type_is_400(client):
    response = client.patch("/api/locks/chapterr/nope", json={"locked": True})

    assert response.status_code == 400
    assert "未知的锁定目标类型" in response.json()["detail"]


def test_a_missing_target_is_404(client):
    response = client.patch("/api/locks/scene/nope", json={"locked": True})

    assert response.status_code == 404


def test_paragraph_locks_round_trip(client):
    _project, _volume, _chapter, scene, _entry = _tree(client)

    assert client.get(f"/api/scenes/{scene['id']}/paragraph-locks").json()["paragraphs"] == []

    saved = client.put(
        f"/api/scenes/{scene['id']}/paragraph-locks",
        json={"paragraphs": [" 第一段。 ", "第一段。", ""]},
    )

    assert saved.status_code == 200
    assert saved.json()["paragraphs"] == ["第一段。"]
    assert client.get(f"/api/scenes/{scene['id']}/paragraph-locks").json()["paragraphs"] == [
        "第一段。"
    ]


def test_paragraph_locks_on_a_missing_scene_is_404(client):
    response = client.put(
        "/api/scenes/nope/paragraph-locks", json={"paragraphs": ["一段"]}
    )

    assert response.status_code == 404


def test_generation_on_a_locked_scene_is_409(client):
    _project, _volume, _chapter, scene, _entry = _tree(client)
    client.patch(f"/api/locks/scene/{scene['id']}", json={"locked": True})

    response = client.post(f"/api/scenes/{scene['id']}/generate")

    assert response.status_code == 409
    assert "已锁定" in response.json()["detail"]


def test_adopting_a_draft_on_a_locked_scene_is_409(client):
    _project, _volume, _chapter, scene, _entry = _tree(client)
    _add_draft(scene["id"], "草稿正文。")
    client.patch(f"/api/locks/scene/{scene['id']}", json={"locked": True})

    response = client.post(f"/api/scenes/{scene['id']}/adopt")

    assert response.status_code == 409
    assert "已锁定" in response.json()["detail"]
    # 草稿与正文都没被动过 —— 拒绝发生在写入之前。
    state = client.get(f"/api/scenes/{scene['id']}/text").json()
    assert state["body"] is None
    assert state["draft"]["content"] == "草稿正文。"


def test_replace_scene_write_on_a_locked_scene_is_409(client):
    _project, _volume, chapter, scene, _entry = _tree(client)
    client.patch(f"/api/locks/scene/{scene['id']}", json={"locked": True})

    response = client.put(
        f"/api/chapters/{chapter['id']}/scenes",
        json={"mode": "replace", "scenes": [{"goal": "新开场"}]},
    )

    assert response.status_code == 409
    assert "已锁定" in response.json()["detail"]


def test_replace_chapter_plan_on_a_locked_volume_is_409(client):
    project, volume, _chapter, _scene, _entry = _tree(client)
    client.patch(f"/api/locks/volume/{volume['id']}", json={"locked": True})

    response = client.put(
        f"/api/projects/{project['id']}/chapters",
        json={"mode": "replace", "volumes": [{"name": "新卷"}]},
    )

    assert response.status_code == 409
    assert "已锁定" in response.json()["detail"]


def test_lock_state_survives_a_reload(client):
    _project, _volume, _chapter, scene, _entry = _tree(client)
    client.patch(f"/api/locks/scene/{scene['id']}", json={"locked": True})

    tree = client.get(f"/api/projects/{_project['id']}/chapters/tree").json()

    # 章节树把锁定透出来，前端才能标出「AI 不会碰这里」。
    assert tree["volumes"][0]["chapters"][0]["scenes"][0]["locked"] is True
