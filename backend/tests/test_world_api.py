from app.world_types import ENTRY_TYPES, HARDNESS_LEVELS


def test_entry_types_endpoint_is_the_frontends_only_source(client):
    payload = client.get("/api/entry-types").json()

    assert {t["key"]: t["label"] for t in payload["types"]} == ENTRY_TYPES
    assert {h["key"]: h["label"] for h in payload["hardness"]} == HARDNESS_LEVELS
    # 顺序稳定，前端不必再排一次
    assert [t["key"] for t in payload["types"]] == list(ENTRY_TYPES)


def test_entry_crud_over_http(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()

    created = client.post(
        f"/api/projects/{project['id']}/entries",
        json={"type": "势力", "name": "记忆交易局", "aliases": ["交易局"], "tags": ["机构"]},
    ).json()
    assert created["type"] == "faction"  # 中文名被归一化
    assert created["aliases"] == ["交易局"]
    assert created["hardness"] is None

    listed = client.get(f"/api/projects/{project['id']}/entries", params={"type": "faction"}).json()
    assert [e["id"] for e in listed] == [created["id"]]

    updated = client.patch(f"/api/entries/{created['id']}", json={"summary": "管记忆买卖"}).json()
    assert updated["summary"] == "管记忆买卖"
    assert updated["name"] == "记忆交易局"  # 没传的字段不动

    assert client.delete(f"/api/entries/{created['id']}").status_code == 204
    assert client.get(f"/api/projects/{project['id']}/entries").json() == []


def test_duplicate_name_over_http_is_a_readable_400(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    body = {"type": "place", "name": "雾港旧城"}
    client.post(f"/api/projects/{project['id']}/entries", json=body)

    response = client.post(f"/api/projects/{project['id']}/entries", json=body)

    assert response.status_code == 400
    assert "雾港旧城" in response.json()["detail"]


def test_relation_crud_over_http(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    a = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "faction", "name": "甲"}
    ).json()
    b = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "place", "name": "乙"}
    ).json()

    relation = client.post(
        f"/api/projects/{project['id']}/relations",
        json={"from_id": a["id"], "to_id": b["id"], "kind": "位于"},
    ).json()
    assert relation["kind"] == "位于"

    assert client.get(f"/api/projects/{project['id']}/relations").json()[0]["id"] == relation["id"]
    assert client.delete(f"/api/relations/{relation['id']}").status_code == 204
    assert client.get(f"/api/projects/{project['id']}/relations").json() == []


def test_deleting_an_entry_removes_it_from_relations_list(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    a = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "faction", "name": "甲"}
    ).json()
    b = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "place", "name": "乙"}
    ).json()
    client.post(
        f"/api/projects/{project['id']}/relations",
        json={"from_id": a["id"], "to_id": b["id"], "kind": "位于"},
    )

    client.delete(f"/api/entries/{a['id']}")

    assert client.get(f"/api/projects/{project['id']}/relations").json() == []
