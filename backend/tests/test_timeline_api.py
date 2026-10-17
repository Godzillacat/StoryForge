def _project(client, name: str = "雾港") -> dict:
    return client.post("/api/projects", json={"name": name}).json()


def _entry(client, project_id: str, type_: str, name: str) -> dict:
    return client.post(
        f"/api/projects/{project_id}/entries", json={"type": type_, "name": name}
    ).json()


def test_timeline_crud_and_order_over_http(client):
    project = _project(client)
    character = _entry(client, project["id"], "人物", "陈默")
    place = _entry(client, project["id"], "地理", "南滨")

    first = client.post(
        f"/api/projects/{project['id']}/timeline",
        json={"title": "初遇", "story_time": "第三年·春"},
    ).json()
    second = client.post(
        f"/api/projects/{project['id']}/timeline",
        json={
            "title": "离别",
            "story_time": "第三年·冬",
            "participants": [character["id"]],
            "location_id": place["id"],
        },
    ).json()

    listed = client.get(f"/api/projects/{project['id']}/timeline").json()
    assert [e["title"] for e in listed] == ["初遇", "离别"]
    assert listed[1]["participants"] == [character["id"]]
    assert listed[1]["location_id"] == place["id"]

    moved = client.post(
        f"/api/timeline/{second['id']}/move", json={"direction": "up"}
    ).json()
    assert moved["title"] == "离别"
    assert [e["title"] for e in client.get(f"/api/projects/{project['id']}/timeline").json()] == [
        "离别",
        "初遇",
    ]

    updated = client.patch(
        f"/api/timeline/{first['id']}",
        json={"title": "初遇（改）", "location_id": None},
    ).json()
    assert updated["title"] == "初遇（改）"
    assert updated["location_id"] is None

    assert client.delete(f"/api/timeline/{first['id']}").status_code == 204
    assert len(client.get(f"/api/projects/{project['id']}/timeline").json()) == 1


def test_timeline_rejects_a_non_character_participant(client):
    project = _project(client)
    place = _entry(client, project["id"], "地理", "南滨")

    response = client.post(
        f"/api/projects/{project['id']}/timeline",
        json={"title": "事件", "participants": [place["id"]]},
    )

    assert response.status_code == 400
    assert "不是人物" in response.json()["detail"]


def test_timeline_unknown_event_is_404(client):
    assert client.patch("/api/timeline/nope", json={"title": "X"}).status_code == 404
    assert client.post("/api/timeline/nope/move", json={"direction": "up"}).status_code == 404
    assert client.delete("/api/timeline/nope").status_code == 404


def test_timeline_move_rejects_an_unknown_direction(client):
    project = _project(client)
    event = client.post(
        f"/api/projects/{project['id']}/timeline", json={"title": "事件"}
    ).json()

    response = client.post(f"/api/timeline/{event['id']}/move", json={"direction": "left"})

    assert response.status_code == 422
