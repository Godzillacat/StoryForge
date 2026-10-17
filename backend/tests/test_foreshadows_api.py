def test_foreshadow_crud_over_http(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()

    created = client.post(
        f"/api/projects/{project['id']}/foreshadows",
        json={"name": "失忆的录音带", "note": "主角的过去"},
    ).json()
    assert created["name"] == "失忆的录音带"

    listed = client.get(f"/api/projects/{project['id']}/foreshadows").json()
    assert [row["id"] for row in listed] == [created["id"]]

    updated = client.patch(
        f"/api/foreshadows/{created['id']}",
        json={"name": "录音带", "status": "confirmed"},
    ).json()
    assert updated["name"] == "录音带"
    assert updated["status"] == "confirmed"

    assert client.delete(f"/api/foreshadows/{created['id']}").status_code == 204
    assert client.get(f"/api/projects/{project['id']}/foreshadows").json() == []
