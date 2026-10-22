"""场景分支接口。"""


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
    client.put(f"/api/scenes/{scene['id']}/body", json={"content": "主版正文。"})
    return project, scene


def test_branch_round_trip(client):
    _project, scene = _seed(client)

    created = client.post(
        f"/api/scenes/{scene['id']}/branches", json={"name": "A 案"}
    )

    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "A 案"
    assert body["content"] == "主版正文。"

    listed = client.get(f"/api/scenes/{scene['id']}/branches").json()
    assert [row["name"] for row in listed] == ["A 案"]

    detail = client.get(f"/api/branches/{body['id']}").json()
    assert detail["chars"] == len("主版正文。")


def test_duplicate_branch_name_is_400(client):
    _project, scene = _seed(client)
    client.post(f"/api/scenes/{scene['id']}/branches", json={"name": "A 案"})

    response = client.post(f"/api/scenes/{scene['id']}/branches", json={"name": "A 案"})

    assert response.status_code == 400
    assert "已经有叫" in response.json()["detail"]


def test_empty_branch_name_is_400(client):
    _project, scene = _seed(client)

    response = client.post(f"/api/scenes/{scene['id']}/branches", json={"name": "  "})

    assert response.status_code == 400


def test_unknown_scene_or_branch_is_404(client):
    assert client.get("/api/scenes/nope/branches").status_code == 404
    assert client.get("/api/branches/nope").status_code == 404
    assert client.post("/api/branches/nope/merge").status_code == 404
    assert client.delete("/api/branches/nope").status_code == 404


def test_renaming_a_branch(client):
    _project, scene = _seed(client)
    branch = client.post(
        f"/api/scenes/{scene['id']}/branches", json={"name": "A 案"}
    ).json()

    renamed = client.patch(
        f"/api/branches/{branch['id']}", json={"name": "B 案", "note": "换个说法"}
    )

    assert renamed.status_code == 200
    assert renamed.json()["name"] == "B 案"
    assert renamed.json()["note"] == "换个说法"


def test_saving_a_branch_body_and_adopting_its_draft(client):
    _project, scene = _seed(client)
    branch = client.post(
        f"/api/scenes/{scene['id']}/branches", json={"name": "A 案"}
    ).json()

    saved = client.put(
        f"/api/branches/{branch['id']}/body", json={"content": "作者手写的另一版。"}
    )
    assert saved.json()["content"] == "作者手写的另一版。"

    client.put(f"/api/branches/{branch['id']}/draft", json={"content": "分支草稿。"})
    adopted = client.post(f"/api/branches/{branch['id']}/adopt")

    assert adopted.status_code == 200
    assert adopted.json()["content"] == "分支草稿。"
    assert adopted.json()["draft"] is None


def test_adopting_without_a_draft_is_409(client):
    _project, scene = _seed(client)
    branch = client.post(
        f"/api/scenes/{scene['id']}/branches", json={"name": "A 案"}
    ).json()

    assert client.post(f"/api/branches/{branch['id']}/adopt").status_code == 409


def test_merging_a_branch(client):
    _project, scene = _seed(client)
    branch = client.post(
        f"/api/scenes/{scene['id']}/branches", json={"name": "A 案"}
    ).json()
    client.put(f"/api/branches/{branch['id']}/body", json={"content": "另一版正文。"})

    result = client.post(f"/api/branches/{branch['id']}/merge").json()

    assert result["body"] == "另一版正文。"
    text = client.get(f"/api/scenes/{scene['id']}/text").json()
    assert text["body"] == "另一版正文。"
    assert text["revisions"][0]["source"] == "branch"
    # 分支仍在 —— 合并是「选它作主版」，不是作废其余。
    assert client.get(f"/api/branches/{branch['id']}").status_code == 200


def test_merging_an_empty_branch_is_400(client):
    project = client.post("/api/projects", json={"name": "空项目"}).json()
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "第一卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "第一章"}
    ).json()
    scene = client.post(
        f"/api/chapters/{chapter['id']}/scenes", json={"goal": "开场"}
    ).json()
    branch = client.post(
        f"/api/scenes/{scene['id']}/branches", json={"name": "A 案"}
    ).json()

    response = client.post(f"/api/branches/{branch['id']}/merge")

    assert response.status_code == 400
    assert "分支正文为空" in response.json()["detail"]


def test_merging_on_a_locked_scene_is_409(client):
    _project, scene = _seed(client)
    branch = client.post(
        f"/api/scenes/{scene['id']}/branches", json={"name": "A 案"}
    ).json()
    client.put(f"/api/branches/{branch['id']}/body", json={"content": "另一版。"})
    client.patch(f"/api/locks/scene/{scene['id']}", json={"locked": True})

    response = client.post(f"/api/branches/{branch['id']}/merge")

    assert response.status_code == 409
    assert "已锁定" in response.json()["detail"]


def test_discarding_a_branch_is_204(client):
    _project, scene = _seed(client)
    branch = client.post(
        f"/api/scenes/{scene['id']}/branches", json={"name": "A 案"}
    ).json()

    assert client.delete(f"/api/branches/{branch['id']}").status_code == 204
    assert client.get(f"/api/scenes/{scene['id']}/branches").json() == []
    assert client.get(f"/api/scenes/{scene['id']}/text").json()["body"] == "主版正文。"


def test_branch_writes_show_up_in_the_change_log(client):
    project, scene = _seed(client)
    branch = client.post(
        f"/api/scenes/{scene['id']}/branches", json={"name": "A 案"}
    ).json()
    client.put(f"/api/branches/{branch['id']}/body", json={"content": "另一版。"})
    client.post(f"/api/branches/{branch['id']}/merge")
    client.delete(f"/api/branches/{branch['id']}")

    rows = client.get(
        f"/api/projects/{project['id']}/changes",
        params={"target_type": "scene", "target_id": scene["id"]},
    ).json()["changes"]
    summaries = " ".join(row["summary"] for row in rows)

    assert "开分支「A 案」" in summaries
    assert "合并分支「A 案」" in summaries
    assert "丢弃分支「A 案」" in summaries
