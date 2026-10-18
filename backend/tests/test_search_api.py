def _project_with_entry(client, name="南滨旧城"):
    project = client.post("/api/projects", json={"name": "检索"}).json()
    entry = client.post(
        f"/api/projects/{project['id']}/entries",
        json={"name": name, "type": "place", "summary": "记忆清算网络的据点"},
    ).json()
    return project, entry


def test_search_returns_results(client):
    project, entry = _project_with_entry(client)

    response = client.get(
        f"/api/projects/{project['id']}/search", params={"q": "南滨旧城"}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "南滨旧城"
    assert any(item["entity_id"] == entry["id"] for item in payload["results"])
    hit = next(item for item in payload["results"] if item["entity_id"] == entry["id"])
    assert hit["entity_type"] == "entry"
    assert hit["subtype"] == "place"
    assert hit["title"] == "南滨旧城"
    assert "南滨旧城" in hit["snippet"]


def test_search_project_not_found(client):
    response = client.get("/api/projects/not-a-project/search", params={"q": "旧城"})
    assert response.status_code == 404


def test_search_rejects_blank_query(client):
    project, _ = _project_with_entry(client)
    assert client.get(
        f"/api/projects/{project['id']}/search", params={"q": "   "}
    ).status_code == 400


def test_search_rejects_unknown_types(client):
    project, _ = _project_with_entry(client)
    response = client.get(
        f"/api/projects/{project['id']}/search",
        params={"q": "旧城", "types": "entry,nope"},
    )
    assert response.status_code == 400


def test_search_rejects_bad_limit(client):
    project, _ = _project_with_entry(client)
    for limit in (0, 51):
        response = client.get(
            f"/api/projects/{project['id']}/search",
            params={"q": "旧城", "limit": limit},
        )
        assert response.status_code == 400


def test_search_types_filter(client):
    project, _ = _project_with_entry(client)

    entries = client.get(
        f"/api/projects/{project['id']}/search",
        params={"q": "旧城", "types": "entry"},
    ).json()
    chapters = client.get(
        f"/api/projects/{project['id']}/search",
        params={"q": "旧城", "types": "chapter"},
    ).json()

    assert entries["results"]
    assert chapters["results"] == []


def test_adopted_scene_body_is_searchable(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "第一卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "第一章"}
    ).json()
    scene = client.post(
        f"/api/chapters/{chapter['id']}/scenes", json={"goal": "找到录音带"}
    ).json()
    client.put(
        f"/api/scenes/{scene['id']}/body",
        json={"content": "灯塔下的密信被雨水泡开。"},
    )

    results = client.get(
        f"/api/projects/{project['id']}/search", params={"q": "灯塔下的密信"}
    ).json()["results"]
    assert any(row["entity_type"] == "scene" for row in results)
