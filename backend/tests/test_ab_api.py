"""A/B 并排生成的接口：建一对、查最近一组、采纳一版、丢弃一版。

这里只钉接口面 —— 状态码、响应形状与「错误文案 → HTTP 状态码」的翻译。
服务层的事务性、命名与锁语义在 `test_ab_service.py` 里；两边分开，接口
测试才能证明 `_value_error` 真的把新文案映射对了，而服务测试不必被 HTTP
细节干扰。
"""

from app.text_stats import count_words


def _seed(client, body: str = "主版正文。"):
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
    client.put(f"/api/scenes/{scene['id']}/body", json={"content": body})
    return project, scene


def _create_ab(client, scene_id: str) -> dict:
    response = client.post(f"/api/scenes/{scene_id}/ab")
    assert response.status_code == 201, response.text
    return response.json()


def _current(client, scene_id: str) -> dict:
    response = client.get(f"/api/scenes/{scene_id}/ab")
    assert response.status_code == 200, response.text
    return response.json()


def test_create_returns_two_sides_and_current_reads_them_back(client):
    _project, scene = _seed(client)

    created = _create_ab(client, scene["id"])
    current = _current(client, scene["id"])

    assert created["group"]
    assert [row["label"] for row in created["branches"]] == ["A", "B"]
    assert current["group"] == created["group"]
    branches = current["branches"]
    # `label` 是库里的名字（作者看到的就是它）；`side` 才是并排面板的两栏。
    assert [row["label"] for row in branches] == ["A/B · A", "A/B · B"]
    assert [row["side"] for row in branches] == ["A", "B"]
    assert [row["id"] for row in branches] == [row["id"] for row in created["branches"]]
    # 还没生成：两条都只有从主版继承来的正文，没有草稿。
    assert [row["has_draft"] for row in branches] == [False, False]
    assert [row["chars"] for row in branches] == [5, 5]


def test_current_is_empty_before_the_first_ab(client):
    _project, scene = _seed(client)

    assert _current(client, scene["id"]) == {"group": None, "branches": []}


def test_second_ab_is_allowed_and_current_returns_the_latest_group(client):
    _project, scene = _seed(client)
    first = _create_ab(client, scene["id"])

    second = _create_ab(client, scene["id"])

    assert second["group"] != first["group"]
    current = _current(client, scene["id"])
    assert current["group"] == second["group"]
    # 第二组自动加序号；序号后缀不改变侧别。
    assert [row["label"] for row in current["branches"]] == ["A/B · A 2", "A/B · B 2"]
    assert [row["side"] for row in current["branches"]] == ["A", "B"]


def test_current_reports_the_draft_length(client):
    _project, scene = _seed(client)
    created = _create_ab(client, scene["id"])
    a, b = created["branches"]
    client.put(f"/api/branches/{b['id']}/draft", json={"content": "B 的草稿，比较长一些。"})

    branches = _current(client, scene["id"])["branches"]

    assert [row["has_draft"] for row in branches] == [False, True]
    # 面板显示的是这一版正文的字数：有草稿看草稿，没有才回落到分支正文。
    assert branches[0]["chars"] == 5
    assert branches[1]["chars"] == count_words("B 的草稿，比较长一些。")


def test_create_on_a_locked_scene_is_409(client):
    _project, scene = _seed(client)
    client.patch(f"/api/locks/scene/{scene['id']}", json={"locked": True})

    response = client.post(f"/api/scenes/{scene['id']}/ab")

    assert response.status_code == 409
    assert "已锁定" in response.json()["detail"]
    assert _current(client, scene["id"]) == {"group": None, "branches": []}


def test_adopt_is_200_and_clears_the_group(client):
    _project, scene = _seed(client)
    created = _create_ab(client, scene["id"])
    a, b = created["branches"]
    client.put(f"/api/branches/{a['id']}/draft", json={"content": "A 的草稿。"})

    response = client.post(f"/api/scenes/{scene['id']}/ab/{a['id']}/adopt")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["body"] == "A 的草稿。"
    assert body["chars"] == 5
    assert body["revision_created"] is True
    # 两条都在 discarded 里：A 已合入正文，B 是落选方案。
    assert body["discarded"] == ["A/B · A", "A/B · B"]
    # 组已清空 —— 刷新页面不会再找回一个已经采纳完的 A/B。
    assert _current(client, scene["id"]) == {"group": None, "branches": []}
    assert client.get(f"/api/branches/{a['id']}").status_code == 404
    assert client.get(f"/api/branches/{b['id']}").status_code == 404
    text = client.get(f"/api/scenes/{scene['id']}/text").json()
    assert text["body"] == "A 的草稿。"
    assert text["revisions"][0]["source"] == "branch"


def test_discard_is_200_and_keeps_the_other_side(client):
    _project, scene = _seed(client)
    created = _create_ab(client, scene["id"])
    a, b = created["branches"]

    response = client.post(f"/api/scenes/{scene['id']}/ab/{a['id']}/discard")

    assert response.status_code == 200, response.text
    assert response.json()["removed"] == ["A/B · A"]
    current = _current(client, scene["id"])
    # 组还在，只剩 B —— 还能继续采纳或再丢弃。
    assert current["group"] == created["group"]
    assert [row["id"] for row in current["branches"]] == [b["id"]]
    assert [row["side"] for row in current["branches"]] == ["B"]
    assert client.get(f"/api/branches/{b['id']}").status_code == 200
    # 丢弃不动正文。
    assert client.get(f"/api/scenes/{scene['id']}/text").json()["body"] == "主版正文。"


def test_a_branch_from_another_scene_is_404(client):
    _project, scene = _seed(client)
    other = client.post(
        f"/api/chapters/{scene['chapter_id']}/scenes", json={"goal": "第二场"}
    ).json()
    other_ab = _create_ab(client, other["id"])
    branch_id = other_ab["branches"][0]["id"]

    adopted = client.post(f"/api/scenes/{scene['id']}/ab/{branch_id}/adopt")
    discarded = client.post(f"/api/scenes/{scene['id']}/ab/{branch_id}/discard")

    assert adopted.status_code == 404
    assert "不属于这个场景" in adopted.json()["detail"]
    assert discarded.status_code == 404
    # 拒绝之后那条分支原样还在，没被别的场景顺手删掉。
    assert client.get(f"/api/branches/{branch_id}").status_code == 200


def test_a_regular_branch_is_400(client):
    _project, scene = _seed(client)
    branch = client.post(
        f"/api/scenes/{scene['id']}/branches", json={"name": "手建分支"}
    ).json()
    client.put(f"/api/branches/{branch['id']}/draft", json={"content": "手写草稿。"})

    adopted = client.post(f"/api/scenes/{scene['id']}/ab/{branch['id']}/adopt")
    discarded = client.post(f"/api/scenes/{scene['id']}/ab/{branch['id']}/discard")

    assert adopted.status_code == 400
    assert "这不是 A/B 分支" in adopted.json()["detail"]
    assert discarded.status_code == 400
    assert client.get(f"/api/branches/{branch['id']}").status_code == 200
