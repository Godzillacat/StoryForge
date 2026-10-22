"""快照与改动历史的接口。"""


def _seed(client):
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
    client.put(f"/api/scenes/{scene['id']}/body", json={"content": "第一段。"})
    return project, volume, chapter, scene


def test_snapshot_round_trip(client):
    project, _volume, _chapter, _scene = _seed(client)

    created = client.post(
        f"/api/projects/{project['id']}/snapshots",
        json={"name": "初稿", "note": "开写之前"},
    )

    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "初稿"
    assert body["volumes"] == 1 and body["scenes"] == 1
    assert body["auto"] is False

    listed = client.get(f"/api/projects/{project['id']}/snapshots").json()
    assert len(listed) == 1

    detail = client.get(f"/api/snapshots/{body['id']}").json()
    assert detail["preview"]["volume_names"] == ["第一卷"]


def test_duplicate_snapshot_name_is_400(client):
    project, *_ = _seed(client)
    client.post(f"/api/projects/{project['id']}/snapshots", json={"name": "初稿"})

    response = client.post(
        f"/api/projects/{project['id']}/snapshots", json={"name": "初稿"}
    )

    assert response.status_code == 400
    assert "已经有叫" in response.json()["detail"]


def test_empty_snapshot_name_is_400(client):
    project, *_ = _seed(client)

    response = client.post(
        f"/api/projects/{project['id']}/snapshots", json={"name": "   "}
    )

    assert response.status_code == 400


def test_snapshots_of_an_unknown_project_is_404(client):
    assert client.get("/api/projects/nope/snapshots").status_code == 404


def test_unknown_snapshot_is_404(client):
    assert client.get("/api/snapshots/nope").status_code == 404
    assert client.post("/api/snapshots/nope/restore").status_code == 404
    assert client.delete("/api/snapshots/nope").status_code == 404


def test_restoring_brings_the_body_back_and_makes_a_backup(client):
    project, _volume, _chapter, scene = _seed(client)
    snapshot = client.post(
        f"/api/projects/{project['id']}/snapshots", json={"name": "初稿"}
    ).json()
    client.put(f"/api/scenes/{scene['id']}/body", json={"content": "改过了。"})

    result = client.post(f"/api/snapshots/{snapshot['id']}/restore").json()

    assert result["backup"]["auto"] is True
    body = client.get(f"/api/scenes/{scene['id']}/text").json()["body"]
    assert body == "第一段。"

    undo = client.post(f"/api/snapshots/{result['backup']['id']}/restore").json()
    assert undo["snapshot"]["id"] == result["backup"]["id"]
    restored = client.get(f"/api/scenes/{scene['id']}/text").json()["body"]
    assert restored == "改过了。"


def test_deleting_a_snapshot_is_204(client):
    project, *_ = _seed(client)
    snapshot = client.post(
        f"/api/projects/{project['id']}/snapshots", json={"name": "初稿"}
    ).json()

    assert client.delete(f"/api/snapshots/{snapshot['id']}").status_code == 204
    assert client.get(f"/api/projects/{project['id']}/snapshots").json() == []


def test_changes_are_listed_after_a_write(client):
    project, _volume, _chapter, scene = _seed(client)
    client.put(f"/api/scenes/{scene['id']}/body", json={"content": "又改了。"})

    body = client.get(f"/api/projects/{project['id']}/changes").json()

    assert body["changes"][0]["target_type"] == "scene"
    assert body["changes"][0]["action_label"] == "编辑"
    assert {item["key"] for item in body["target_types"]} >= {"scene", "entry"}


def test_changes_can_be_filtered_by_target(client):
    project, volume, _chapter, scene = _seed(client)
    client.patch(f"/api/volumes/{volume['id']}", json={"name": "改名"})
    client.put(f"/api/scenes/{scene['id']}/body", json={"content": "又改了。"})

    body = client.get(
        f"/api/projects/{project['id']}/changes",
        params={"target_type": "scene", "target_id": scene["id"]},
    ).json()

    # `_seed` 已经写过一次正文，所以这里是两条 —— 但**都**是这一场的。
    assert {row["target_type"] for row in body["changes"]} == {"scene"}
    assert {row["target_id"] for row in body["changes"]} == {scene["id"]}


def test_changes_of_an_unknown_project_is_404(client):
    assert client.get("/api/projects/nope/changes").status_code == 404


def test_changes_with_an_unknown_type_is_400(client):
    project, *_ = _seed(client)

    response = client.get(
        f"/api/projects/{project['id']}/changes", params={"target_type": "chapterr"}
    )

    assert response.status_code == 400
