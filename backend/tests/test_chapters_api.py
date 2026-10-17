def test_tree_and_volume_chapter_crud_over_http(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()

    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "第一卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "第一章"}
    ).json()

    tree = client.get(f"/api/projects/{project['id']}/chapters/tree").json()["volumes"]
    assert tree[0]["name"] == "第一卷"
    assert tree[0]["chapters"][0]["title"] == "第一章"
    assert tree[0]["chapters"][0]["scenes"] == []

    updated = client.patch(
        f"/api/chapters/{chapter['id']}",
        json={"hook": "门后有人", "conflict_level": 4, "dialogue_ratio": 0.3},
    ).json()
    assert updated["hook"] == "门后有人"
    assert updated["conflict_level"] == 4

    moved = client.post(
        f"/api/volumes/{volume['id']}/move", json={"direction": "down"}
    )
    assert moved.status_code == 200

    assert client.delete(f"/api/chapters/{chapter['id']}").status_code == 204
    assert client.delete(f"/api/volumes/{volume['id']}").status_code == 204


def test_chapter_types_lists_the_status_vocabulary(client):
    payload = client.get("/api/chapter-types").json()
    assert payload["statuses"] == [
        {"key": "planned", "label": "规划中"},
        {"key": "confirmed", "label": "已确认"},
    ]


def test_volume_validation_is_a_readable_400(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    response = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "   "}
    )
    assert response.status_code == 400
    assert "卷名" in response.json()["detail"]


def test_chapter_bad_rhythm_is_a_readable_400(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "卷"}
    ).json()

    response = client.post(
        f"/api/volumes/{volume['id']}/chapters",
        json={"title": "章", "conflict_level": 9},
    )
    assert response.status_code == 400
    assert "冲突强度" in response.json()["detail"]


def test_missing_volume_is_404(client):
    assert client.patch("/api/volumes/nope", json={"name": "X"}).status_code == 404
    assert client.post("/api/volumes/nope/move", json={"direction": "up"}).status_code == 404
